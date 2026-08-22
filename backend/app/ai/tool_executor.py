import logging
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Dict, Any, List, Optional

from app.core.database import get_db
from app.core.websocket import ws_manager
from app.services.audit_service import AuditService
from app.services.machine_service import MachineService
from app.services.incident_service import IncidentService
from app.services.execution_engine import ExecutionEngine
from app.schemas.execution import ExecutionEventType
from app.schemas.work_order import WorkOrderOperationStatus, WorkOrderStatus
from app.schemas.machine import MachineStatus
from app.schemas.user import OperatorAvailability
from app.ai.tool_registry import validate_tool_call, SAFE_TOOL_REGISTRY

logger = logging.getLogger(__name__)

class ToolExecutor:
    @staticmethod
    async def execute_tool(tool_name: str, parameters: Dict[str, Any], actor_id: str = "ADMIN") -> Dict[str, Any]:
        """
        Safely execute a single tool call from the registered tool registry.
        Re-validates parameters and current MES state before making mutations.
        """
        db = get_db()
        
        # 1. Schema & parameter validation
        is_valid, err = validate_tool_call(tool_name, parameters)
        if not is_valid:
            raise ValueError(f"Tool validation error for '{tool_name}': {err}")

        logger.info(f"Executing AI Tool: {tool_name} with params: {parameters} by {actor_id}")

        # -------------------------------------------------------------
        # Read-Only Tools
        # -------------------------------------------------------------
        if tool_name == "get_machine_status":
            m_id = parameters.get("machineId")
            m_code = parameters.get("machineCode")
            query = {}
            if m_id and ObjectId.is_valid(m_id):
                query["_id"] = ObjectId(m_id)
            elif m_code:
                query["machineCode"] = m_code
            mach = await db.machines.find_one(query) if query else None
            return {"result": MachineService._format_machine(mach)}

        elif tool_name == "get_work_order_execution":
            wo_id = parameters.get("workOrderId")
            wo_code = parameters.get("workOrderCode")
            target_id = wo_id
            if not target_id and wo_code:
                wo_doc = await db.work_orders.find_one({"workOrderCode": wo_code})
                if wo_doc:
                    target_id = str(wo_doc["_id"])
            if not target_id:
                raise ValueError("Work order not found")
            state = await ExecutionEngine.get_execution_state(target_id)
            return {"result": state}

        elif tool_name == "get_incident_context":
            inc_id = parameters["incidentId"]
            ctx = await IncidentService.get_incident_context(inc_id)
            return {"result": ctx}

        elif tool_name == "get_available_resources":
            req_type = parameters.get("requiredMachineType")
            compat = await MachineService.find_compatible_machines(req_type, only_available=True)
            return {"result": compat}

        # -------------------------------------------------------------
        # Mutation Tools
        # -------------------------------------------------------------
        elif tool_name == "pause_operation":
            wo_ref = str(parameters["workOrderId"])
            op_id = str(parameters["operationId"])
            reason = parameters.get("reason", "AI action plan executed pause")
            now = datetime.utcnow()

            # Locate work order
            wo_query = {"_id": ObjectId(wo_ref)} if ObjectId.is_valid(wo_ref) else {"workOrderCode": wo_ref}
            wo = await db.work_orders.find_one(wo_query)
            if not wo:
                raise ValueError(f"Work order '{wo_ref}' not found")

            wo_id_str = str(wo["_id"])
            wo_code = wo.get("workOrderCode")

            # Update target operation
            target_op = next((o for o in wo.get("operations", []) if o.get("operationId") == op_id), None)
            if not target_op:
                raise ValueError(f"Operation '{op_id}' not found in Work Order {wo_code}")

            # Release machine if currently occupied
            mach_id = target_op.get("assignedMachineId")
            if mach_id and ObjectId.is_valid(mach_id):
                await db.machines.update_one(
                    {"_id": ObjectId(mach_id)},
                    {"$set": {
                        "status": MachineStatus.IDLE.value,
                        "currentOperationId": None,
                        "currentWorkOrderId": None,
                        "currentOperatorId": None,
                        "updatedAt": now
                    }}
                )

            # Release operator if assigned
            oper_id = target_op.get("assignedOperatorId")
            if oper_id and ObjectId.is_valid(oper_id):
                await db.users.update_one(
                    {"_id": ObjectId(oper_id)},
                    {"$set": {
                        "availabilityStatus": OperatorAvailability.AVAILABLE.value,
                        "currentOperationId": None,
                        "currentWorkOrderId": None,
                        "updatedAt": now
                    }}
                )

            # Set operation status to PAUSED
            await db.work_orders.update_one(
                {"_id": wo["_id"], "operations.operationId": op_id},
                {"$set": {
                    "operations.$.status": WorkOrderOperationStatus.PAUSED.value,
                    "operations.$.waitingReason": f"Paused by AI Action: {reason}",
                    "updatedAt": now
                }}
            )

            # Log execution event
            await ExecutionEngine.log_execution_event(
                execution_id=str(wo.get("executionId", wo_id_str)),
                work_order_id=wo_id_str,
                work_order_code=wo_code,
                event_type=ExecutionEventType.OPERATION_PAUSED,
                message=f"Operation {op_id} paused by AI action plan: {reason}",
                operation_id=op_id,
                metadata={"aiAction": True, "reason": reason}
            )

            # Broadcast updated state
            state_data = await ExecutionEngine.get_execution_state(wo_id_str)
            await ws_manager.broadcast({
                "type": "EXECUTION_STATE_UPDATE",
                "data": state_data
            })

            return {"success": True, "message": f"Operation {op_id} successfully paused in {wo_code}."}

        elif tool_name == "resume_operation":
            wo_ref = str(parameters["workOrderId"])
            op_id = str(parameters["operationId"])
            reason = parameters.get("reason", "Resumed via AI Action")
            now = datetime.utcnow()

            wo_query = {"_id": ObjectId(wo_ref)} if ObjectId.is_valid(wo_ref) else {"workOrderCode": wo_ref}
            wo = await db.work_orders.find_one(wo_query)
            if not wo:
                raise ValueError(f"Work order '{wo_ref}' not found")

            wo_id_str = str(wo["_id"])
            wo_code = wo.get("workOrderCode")

            # Set operation status to READY
            await db.work_orders.update_one(
                {"_id": wo["_id"], "operations.operationId": op_id},
                {"$set": {
                    "operations.$.status": WorkOrderOperationStatus.READY.value,
                    "operations.$.waitingReason": None,
                    "updatedAt": now
                }}
            )

            await ExecutionEngine.log_execution_event(
                execution_id=str(wo.get("executionId", wo_id_str)),
                work_order_id=wo_id_str,
                work_order_code=wo_code,
                event_type=ExecutionEventType.OPERATION_READY,
                message=f"Operation {op_id} resumed and set to READY: {reason}",
                operation_id=op_id,
                metadata={"aiAction": True, "reason": reason}
            )

            # Trigger immediate execution evaluation
            await ExecutionEngine.evaluate_execution(wo_id_str)

            state_data = await ExecutionEngine.get_execution_state(wo_id_str)
            await ws_manager.broadcast({
                "type": "EXECUTION_STATE_UPDATE",
                "data": state_data
            })

            return {"success": True, "message": f"Operation {op_id} resumed in {wo_code}."}

        elif tool_name == "stop_work_order":
            wo_ref = str(parameters["workOrderId"])
            reason = parameters.get("reason", "Halted via AI Action")
            now = datetime.utcnow()

            wo_query = {"_id": ObjectId(wo_ref)} if ObjectId.is_valid(wo_ref) else {"workOrderCode": wo_ref}
            wo = await db.work_orders.find_one(wo_query)
            if not wo:
                raise ValueError(f"Work order '{wo_ref}' not found")

            wo_id_str = str(wo["_id"])
            wo_code = wo.get("workOrderCode")

            await db.work_orders.update_one(
                {"_id": wo["_id"]},
                {"$set": {
                    "status": WorkOrderStatus.PAUSED.value,
                    "updatedAt": now
                }}
            )

            await ExecutionEngine.log_execution_event(
                execution_id=str(wo.get("executionId", wo_id_str)),
                work_order_id=wo_id_str,
                work_order_code=wo_code,
                event_type=ExecutionEventType.WORK_ORDER_PAUSED,
                message=f"Work Order {wo_code} paused by AI action: {reason}",
                metadata={"aiAction": True, "reason": reason}
            )

            state_data = await ExecutionEngine.get_execution_state(wo_id_str)
            await ws_manager.broadcast({
                "type": "EXECUTION_STATE_UPDATE",
                "data": state_data
            })

            return {"success": True, "message": f"Work Order {wo_code} stopped."}

        elif tool_name == "mark_machine_down":
            m_id = parameters.get("machineId")
            m_code = parameters.get("machineCode")
            inc_id = parameters.get("incidentId")
            reason = parameters.get("reason", "AI action confirmed machine failure")

            mach_doc = None
            if m_id and ObjectId.is_valid(m_id):
                mach_doc = await db.machines.find_one({"_id": ObjectId(m_id)})
            elif m_code:
                mach_doc = await db.machines.find_one({"machineCode": m_code})

            if not mach_doc:
                raise ValueError(f"Target machine not found (ID: {m_id}, Code: {m_code})")

            target_mach_id = str(mach_doc["_id"])

            # Call authoritative MachineService.fail_machine
            fail_result = await MachineService.fail_machine(
                machine_id=target_mach_id,
                reason=reason,
                actor_id=actor_id,
                incident_id=inc_id
            )

            return {"success": True, "result": fail_result, "message": f"Machine {mach_doc.get('machineCode')} marked DOWN."}

        elif tool_name == "reroute_operation":
            wo_ref = str(parameters["workOrderId"])
            op_id = str(parameters["operationId"])
            target_mach_id = parameters.get("targetMachineId")
            target_mach_code = parameters.get("targetMachineCode")
            target_oper_id = parameters.get("targetOperatorId")
            now = datetime.utcnow()

            # Locate target machine
            target_mach = None
            if target_mach_id and ObjectId.is_valid(target_mach_id):
                target_mach = await db.machines.find_one({"_id": ObjectId(target_mach_id)})
            elif target_mach_code:
                target_mach = await db.machines.find_one({"machineCode": target_mach_code})

            if not target_mach:
                raise ValueError("Target backup machine not found")

            dest_mach_id = str(target_mach["_id"])
            dest_mach_code = target_mach.get("machineCode")

            wo_query = {"_id": ObjectId(wo_ref)} if ObjectId.is_valid(wo_ref) else {"workOrderCode": wo_ref}
            wo = await db.work_orders.find_one(wo_query)
            if not wo:
                raise ValueError(f"Work order '{wo_ref}' not found")

            wo_id_str = str(wo["_id"])
            wo_code = wo.get("workOrderCode")

            # Update work order operation
            update_data = {
                "operations.$.assignedMachineId": dest_mach_id,
                "operations.$.assignedMachineCode": dest_mach_code,
                "operations.$.status": WorkOrderOperationStatus.READY.value,
                "operations.$.waitingReason": f"Rerouted to backup machine {dest_mach_code}",
                "updatedAt": now
            }
            if target_oper_id and ObjectId.is_valid(target_oper_id):
                update_data["operations.$.assignedOperatorId"] = target_oper_id

            await db.work_orders.update_one(
                {"_id": wo["_id"], "operations.operationId": op_id},
                {"$set": update_data}
            )

            await ExecutionEngine.log_execution_event(
                execution_id=str(wo.get("executionId", wo_id_str)),
                work_order_id=wo_id_str,
                work_order_code=wo_code,
                event_type=ExecutionEventType.OPERATION_REROUTED,
                message=f"Operation {op_id} rerouted to backup machine {dest_mach_code}",
                operation_id=op_id,
                machine_id=dest_mach_id,
                machine_code=dest_mach_code,
                metadata={"aiAction": True, "backupMachineCode": dest_mach_code}
            )

            # Trigger execution tick
            await ExecutionEngine.evaluate_execution(wo_id_str)

            state_data = await ExecutionEngine.get_execution_state(wo_id_str)
            await ws_manager.broadcast({
                "type": "EXECUTION_STATE_UPDATE",
                "data": state_data
            })

            return {"success": True, "message": f"Operation {op_id} rerouted to {dest_mach_code}."}

        elif tool_name == "schedule_maintenance":
            m_id = parameters.get("machineId")
            m_code = parameters.get("machineCode")
            inc_id = parameters.get("incidentId")
            duration_minutes = int(parameters["durationMinutes"])
            reason = parameters.get("reason", "Scheduled AI maintenance repair")

            mach_doc = None
            if m_id and ObjectId.is_valid(m_id):
                mach_doc = await db.machines.find_one({"_id": ObjectId(m_id)})
            elif m_code:
                mach_doc = await db.machines.find_one({"machineCode": m_code})

            if not mach_doc:
                raise ValueError(f"Machine not found (ID: {m_id}, Code: {m_code})")

            mach_id_str = str(mach_doc["_id"])
            m_code_str = mach_doc.get("machineCode")

            if inc_id and ObjectId.is_valid(inc_id):
                res = await IncidentService.schedule_incident_maintenance(
                    incident_id=inc_id,
                    duration_minutes=duration_minutes,
                    resolution=reason,
                    admin_id=actor_id
                )
                return {"success": True, "result": res, "message": f"Maintenance scheduled for {m_code_str} ({duration_minutes} mins)."}
            else:
                res = await MachineService.schedule_maintenance(
                    machine_id=mach_id_str,
                    duration_minutes=duration_minutes,
                    reason=reason,
                    actor_id=actor_id
                )
                return {"success": True, "result": res, "message": f"Maintenance scheduled for {m_code_str} ({duration_minutes} mins)."}

        elif tool_name == "resolve_incident":
            inc_id = parameters["incidentId"]
            resolution = parameters.get("resolution", "Resolved by AI recovery plan")
            res = await IncidentService.resolve_incident(
                incident_id=inc_id,
                resolution=resolution,
                admin_id=actor_id
            )
            return {"success": True, "result": res, "message": f"Incident {inc_id} resolved."}

        elif tool_name == "create_execution_action_log":
            wo_ref = str(parameters["workOrderId"])
            message = parameters["message"]
            details = parameters.get("details", {})

            wo_query = {"_id": ObjectId(wo_ref)} if ObjectId.is_valid(wo_ref) else {"workOrderCode": wo_ref}
            wo = await db.work_orders.find_one(wo_query)
            if not wo:
                raise ValueError(f"Work order '{wo_ref}' not found")

            wo_id_str = str(wo["_id"])
            wo_code = wo.get("workOrderCode")

            await ExecutionEngine.log_execution_event(
                execution_id=str(wo.get("executionId", wo_id_str)),
                work_order_id=wo_id_str,
                work_order_code=wo_code,
                event_type=ExecutionEventType.OPERATION_READY,
                message=f"AI Advisory Log: {message}",
                metadata={"aiAction": True, **details}
            )
            return {"success": True, "message": f"Log appended to {wo_code}."}

        else:
            raise ValueError(f"Unknown tool execution handler: '{tool_name}'")
