import secrets
import string
import logging
from datetime import datetime
from bson import ObjectId
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.core.websocket import ws_manager
from app.schemas.operator_activation import ActivationStatus
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class OperatorActivationService:
    """
    Manages operator desktop client activation lifecycle, approval flow,
    session verification, and real-time operator operational context.
    """

    @staticmethod
    def _format_activation(doc: dict, mask_code: bool = False) -> dict:
        if not doc:
            return None
        res = dict(doc)
        res["id"] = str(res["_id"])
        res["_id"] = str(res["_id"])
        if "operatorId" in res and isinstance(res["operatorId"], ObjectId):
            res["operatorId"] = str(res["operatorId"])
        if mask_code and res.get("status") != ActivationStatus.NOT_ACTIVATED.value:
            res["activationCode"] = None
        return res

    @staticmethod
    def _generate_code(employee_id: str) -> str:
        clean_emp = employee_id.replace("-", "").upper()[:6]
        chars = string.ascii_uppercase + string.digits
        random_suffix = ''.join(secrets.choice(chars) for _ in range(6))
        return f"ACT-{clean_emp}-{random_suffix}"

    @staticmethod
    async def generate_activation_code(operator_id: str, admin_id: str = "ADMIN") -> dict:
        """
        Admin action: Generate a fresh one-time activation code for an operator.
        """
        db = get_db()
        if not ObjectId.is_valid(operator_id):
            # Check by employeeId
            user = await db.users.find_one({"employeeId": operator_id})
        else:
            user = await db.users.find_one({"_id": ObjectId(operator_id)})

        if not user:
            raise ValueError(f"Operator user '{operator_id}' not found")
        if user.get("role") != "OPERATOR":
            raise ValueError(f"User '{user.get('name')}' is not an OPERATOR (role={user.get('role')})")

        op_user_id = str(user["_id"])
        emp_id = user.get("employeeId", "OP-001")
        code = OperatorActivationService._generate_code(emp_id)

        # Invalidate any prior unapproved activations
        await db.operator_activations.update_many(
            {"operatorId": op_user_id, "status": {"$in": [ActivationStatus.NOT_ACTIVATED.value, ActivationStatus.PENDING.value]}},
            {"$set": {"status": ActivationStatus.REVOKED.value, "revokedAt": datetime.utcnow()}}
        )

        activation_doc = {
            "activationCode": code,
            "operatorId": op_user_id,
            "operatorEmployeeId": emp_id,
            "operatorName": user.get("name"),
            "status": ActivationStatus.NOT_ACTIVATED.value,
            "sessionToken": None,
            "createdAt": datetime.utcnow(),
            "requestedAt": None,
            "approvedAt": None,
            "approvedBy": None,
            "revokedAt": None,
            "metadata": {"createdBy": admin_id}
        }

        result = await db.operator_activations.insert_one(activation_doc)
        activation_doc["_id"] = result.inserted_id

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="USER",
            action="OPERATOR_ACTIVATION_CODE_GENERATED",
            entity_type="operator_activation",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={"operatorEmployeeId": emp_id, "operatorName": user.get("name")}
        )

        return OperatorActivationService._format_activation(activation_doc, mask_code=False)

    @staticmethod
    async def submit_activation(activation_code: str, client_info: Optional[Dict[str, Any]] = None) -> dict:
        """
        Operator Client action: Submit an activation code on desktop startup.
        Creates a session token and transitions activation to PENDING approval.
        """
        db = get_db()
        code_clean = activation_code.strip().upper()

        activation = await db.operator_activations.find_one({
            "activationCode": code_clean,
            "status": {"$in": [ActivationStatus.NOT_ACTIVATED.value, ActivationStatus.PENDING.value]}
        })

        if not activation:
            raise ValueError("Invalid or expired activation code. Please contact your shop-floor administrator.")

        session_token = f"sess_{secrets.token_urlsafe(32)}"
        now = datetime.utcnow()

        updated_doc = await db.operator_activations.find_one_and_update(
            {"_id": activation["_id"]},
            {"$set": {
                "status": ActivationStatus.PENDING.value,
                "sessionToken": session_token,
                "requestedAt": now,
                "clientInfo": client_info or {},
                "updatedAt": now
            }},
            return_document=True
        )

        formatted = OperatorActivationService._format_activation(updated_doc, mask_code=True)

        # Notify Admin UI via WebSocket
        await ws_manager.broadcast({
            "type": "ACTIVATION_REQUESTED",
            "data": {
                "id": formatted["id"],
                "operatorEmployeeId": formatted["operatorEmployeeId"],
                "operatorName": formatted["operatorName"],
                "status": ActivationStatus.PENDING.value
            }
        })

        await AuditService.log_event(
            actor_id=formatted["operatorEmployeeId"],
            actor_type="SYSTEM",
            action="OPERATOR_ACTIVATION_REQUESTED",
            entity_type="operator_activation",
            entity_id=formatted["id"],
            source="OPERATOR_CLIENT",
            metadata={"operatorName": formatted["operatorName"]}
        )

        return formatted

    @staticmethod
    async def get_activation_status(session_token: str) -> dict:
        """
        Check current approval status of an operator client session.
        """
        db = get_db()
        activation = await db.operator_activations.find_one({"sessionToken": session_token})
        if not activation:
            raise ValueError("Invalid or unrecognized operator session token")

        return OperatorActivationService._format_activation(activation, mask_code=True)

    @staticmethod
    async def approve_activation(activation_id: str, admin_id: str = "ADMIN") -> dict:
        """
        Admin action: Approve a pending operator client activation.
        """
        db = get_db()
        if not ObjectId.is_valid(activation_id):
            raise ValueError(f"Invalid activation ID format: '{activation_id}'")

        activation = await db.operator_activations.find_one({"_id": ObjectId(activation_id)})
        if not activation:
            raise ValueError("Activation record not found")

        now = datetime.utcnow()
        updated_doc = await db.operator_activations.find_one_and_update(
            {"_id": ObjectId(activation_id)},
            {"$set": {
                "status": ActivationStatus.APPROVED.value,
                "approvedAt": now,
                "approvedBy": admin_id,
                "updatedAt": now
            }},
            return_document=True
        )

        formatted = OperatorActivationService._format_activation(updated_doc, mask_code=True)

        # Broadcast approval so Operator Client unlocks instantly
        await ws_manager.broadcast({
            "type": "ACTIVATION_APPROVED",
            "data": {
                "id": formatted["id"],
                "sessionToken": formatted.get("sessionToken"),
                "operatorId": formatted["operatorId"],
                "operatorEmployeeId": formatted["operatorEmployeeId"],
                "status": ActivationStatus.APPROVED.value
            }
        })

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="USER",
            action="OPERATOR_ACTIVATION_APPROVED",
            entity_type="operator_activation",
            entity_id=str(activation_id),
            source="ADMIN",
            metadata={"operatorEmployeeId": formatted["operatorEmployeeId"], "operatorName": formatted["operatorName"]}
        )

        return formatted

    @staticmethod
    async def reject_activation(activation_id: str, reason: str = "Rejected by administrator", admin_id: str = "ADMIN") -> dict:
        """
        Admin action: Reject a pending operator client activation.
        """
        db = get_db()
        if not ObjectId.is_valid(activation_id):
            raise ValueError(f"Invalid activation ID format: '{activation_id}'")

        now = datetime.utcnow()
        updated_doc = await db.operator_activations.find_one_and_update(
            {"_id": ObjectId(activation_id)},
            {"$set": {
                "status": ActivationStatus.REJECTED.value,
                "rejectionReason": reason,
                "updatedAt": now
            }},
            return_document=True
        )

        if not updated_doc:
            raise ValueError("Activation record not found")

        formatted = OperatorActivationService._format_activation(updated_doc, mask_code=True)

        await ws_manager.broadcast({
            "type": "ACTIVATION_REJECTED",
            "data": {
                "id": formatted["id"],
                "sessionToken": formatted.get("sessionToken"),
                "status": ActivationStatus.REJECTED.value,
                "reason": reason
            }
        })

        return formatted

    @staticmethod
    async def revoke_activation(activation_id: str, admin_id: str = "ADMIN") -> dict:
        """
        Admin action: Revoke access for an approved operator client.
        """
        db = get_db()
        if not ObjectId.is_valid(activation_id):
            raise ValueError(f"Invalid activation ID format: '{activation_id}'")

        now = datetime.utcnow()
        updated_doc = await db.operator_activations.find_one_and_update(
            {"_id": ObjectId(activation_id)},
            {"$set": {
                "status": ActivationStatus.REVOKED.value,
                "revokedAt": now,
                "updatedAt": now
            }},
            return_document=True
        )

        if not updated_doc:
            raise ValueError("Activation record not found")

        formatted = OperatorActivationService._format_activation(updated_doc, mask_code=True)

        await ws_manager.broadcast({
            "type": "ACTIVATION_REVOKED",
            "data": {
                "id": formatted["id"],
                "sessionToken": formatted.get("sessionToken"),
                "status": ActivationStatus.REVOKED.value
            }
        })

        return formatted

    @staticmethod
    async def list_activations() -> List[dict]:
        """
        List all operator activation records for admin management.
        """
        db = get_db()
        activations = []
        async for doc in db.operator_activations.find().sort("createdAt", -1):
            activations.append(OperatorActivationService._format_activation(doc, mask_code=False))
        return activations

    @staticmethod
    async def get_operator_context(session_token: str) -> dict:
        """
        Derives operator identity and live workstation / operation assignment
        based on the validated active session token.
        """
        db = get_db()
        if not session_token:
            raise ValueError("Session token is required")

        activation = await db.operator_activations.find_one({"sessionToken": session_token})
        if not activation:
            raise ValueError("Invalid session token")

        if activation.get("status") != ActivationStatus.APPROVED.value:
            raise PermissionError(f"Operator client is in status '{activation.get('status')}'. Admin approval required.")

        op_id = activation.get("operatorId")
        user = await db.users.find_one({"_id": ObjectId(op_id)}) if ObjectId.is_valid(op_id) else None
        if not user:
            raise ValueError(f"Operator user account '{op_id}' was not found")

        now = datetime.utcnow()

        # Operator identifiers: both ObjectId string and employeeId
        op_identifiers = [str(user["_id"])]
        if user.get("employeeId"):
            op_identifiers.append(user["employeeId"])

        # Find active assignment across running work orders
        assignment = None
        
        # 1. Check in running work orders for any operation assigned to this operator
        # Support states: IN_PROGRESS, WAITING_FOR_RESOURCE, READY, INTERRUPTED, PAUSED
        active_statuses = ["IN_PROGRESS", "WAITING_FOR_RESOURCE", "READY", "INTERRUPTED", "PAUSED"]
        wo = await db.work_orders.find_one({
            "status": "IN_PROGRESS",
            "operations": {
                "$elemMatch": {
                    "assignedOperatorId": {"$in": op_identifiers},
                    "status": {"$in": active_statuses}
                }
            }
        })

        if wo:
            matched_ops = [
                o for o in wo.get("operations", [])
                if o.get("assignedOperatorId") in op_identifiers and o.get("status") in active_statuses
            ]
            # Prioritize IN_PROGRESS first, then WAITING_FOR_RESOURCE, READY, INTERRUPTED, etc.
            active_op = (
                next((o for o in matched_ops if o.get("status") == "IN_PROGRESS"), None) or
                next((o for o in matched_ops if o.get("status") == "WAITING_FOR_RESOURCE"), None) or
                next((o for o in matched_ops if o.get("status") == "READY"), None) or
                (matched_ops[0] if matched_ops else None)
            )

            if active_op:
                mach_id = active_op.get("assignedMachineId")
                mach = await db.machines.find_one({"_id": ObjectId(mach_id)}) if mach_id and ObjectId.is_valid(mach_id) else None
                
                rem_seconds = 0
                if active_op.get("estimatedCompletionAt"):
                    rem_seconds = max(0, int((active_op["estimatedCompletionAt"] - now).total_seconds()))

                assignment = {
                    "machineId": str(mach["_id"]) if mach else str(mach_id or "UNASSIGNED"),
                    "machineCode": mach.get("machineCode", active_op.get("assignedMachineCode", "M-PENDING")) if mach else active_op.get("assignedMachineCode", "M-PENDING"),
                    "machineName": mach.get("name", "Workstation") if mach else "Workstation",
                    "machineType": mach.get("type", active_op.get("requiredMachineType", "GENERAL")) if mach else active_op.get("requiredMachineType", "GENERAL"),
                    "operationId": active_op.get("operationId", "OP-00"),
                    "operationName": active_op.get("name", "Production Step"),
                    "workOrderId": str(wo["_id"]),
                    "workOrderCode": wo.get("workOrderCode", "WO-0000"),
                    "status": active_op.get("status", "IN_PROGRESS"),
                    "remainingSeconds": rem_seconds,
                    "waitingReason": active_op.get("waitingReason")
                }

        # 2. Check if user document directly has active work order pointers
        if not assignment and user.get("currentWorkOrderId"):
            wo = await db.work_orders.find_one({"_id": ObjectId(user["currentWorkOrderId"])}) if ObjectId.is_valid(user["currentWorkOrderId"]) else None
            if wo and wo.get("status") == "IN_PROGRESS":
                op_id = user.get("currentOperationId")
                active_op = next((o for o in wo.get("operations", []) if o.get("operationId") == op_id), None)
                if active_op:
                    mach_id = active_op.get("assignedMachineId")
                    mach = await db.machines.find_one({"_id": ObjectId(mach_id)}) if mach_id and ObjectId.is_valid(mach_id) else None
                    rem_seconds = 0
                    if active_op.get("estimatedCompletionAt"):
                        rem_seconds = max(0, int((active_op["estimatedCompletionAt"] - now).total_seconds()))
                    assignment = {
                        "machineId": str(mach["_id"]) if mach else str(mach_id or "UNASSIGNED"),
                        "machineCode": mach.get("machineCode", "M-UNKNOWN") if mach else "M-UNKNOWN",
                        "machineName": mach.get("name", "Workstation") if mach else "Workstation",
                        "machineType": mach.get("type", "GENERAL") if mach else "GENERAL",
                        "operationId": active_op.get("operationId", "OP-00"),
                        "operationName": active_op.get("name", "Production Step"),
                        "workOrderId": str(wo["_id"]),
                        "workOrderCode": wo.get("workOrderCode", "WO-0000"),
                        "status": active_op.get("status", "IN_PROGRESS"),
                        "remainingSeconds": rem_seconds,
                        "waitingReason": active_op.get("waitingReason")
                    }
            else:
                # Clear orphaned pointer on user
                await db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"currentWorkOrderId": None, "currentOperationId": None}}
                )

        # 3. Fallback: check if machine directly holds this operator
        if not assignment:
            mach = await db.machines.find_one({
                "currentOperatorId": {"$in": op_identifiers},
                "status": {"$in": ["OCCUPIED", "DOWN", "MAINTENANCE"]}
            })
            if mach:
                wo_id = mach.get("currentWorkOrderId")
                wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)}) if wo_id and ObjectId.is_valid(wo_id) else None
                # If work order document exists in DB and is already COMPLETED / CANCELLED, clean orphaned machine lock
                if wo and wo.get("status") in ["COMPLETED", "CANCELLED"]:
                    if mach.get("status") == "OCCUPIED":
                        await db.machines.update_one(
                            {"_id": mach["_id"]},
                            {"$set": {
                                "status": "IDLE",
                                "currentWorkOrderId": None,
                                "currentWorkOrderCode": None,
                                "currentOperationId": None,
                                "currentOperatorId": None
                            }}
                        )
                else:
                    assignment = {
                        "machineId": str(mach["_id"]),
                        "machineCode": mach.get("machineCode", "M-UNKNOWN"),
                        "machineName": mach.get("name", "Workstation"),
                        "machineType": mach.get("type", "GENERAL"),
                        "operationId": mach.get("currentOperationId", "OP-ACTIVE"),
                        "operationName": "Active Operation",
                        "workOrderId": str(wo["_id"]) if wo else str(mach.get("currentWorkOrderId") or "WO-ACTIVE"),
                        "workOrderCode": wo.get("workOrderCode") if wo else str(mach.get("currentWorkOrderCode") or "WO-ACTIVE"),
                        "status": "OCCUPIED" if mach.get("status") == "OCCUPIED" else mach.get("status"),
                        "remainingSeconds": 0,
                        "waitingReason": None
                    }

        return {
            "operator": {
                "id": str(user["_id"]),
                "operatorId": user.get("employeeId", "OP-001"),
                "name": user.get("name"),
                "role": user.get("role", "OPERATOR"),
                "department": user.get("department", "Shop Floor"),
                "availabilityStatus": user.get("availabilityStatus", "AVAILABLE")
            },
            "activationStatus": activation.get("status"),
            "assignment": assignment,
            "serverTime": now
        }
