import asyncio
import logging
from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderOperationStatus, WorkOrderStatus
from app.schemas.machine import MachineStatus
from app.schemas.user import OperatorAvailability
from app.services.audit_service import AuditService
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)

class WorkOrderService:
    @staticmethod
    async def create_work_order(wo_in: WorkOrderCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate workOrderCode
        existing = await db.work_orders.find_one({"workOrderCode": wo_in.workOrderCode})
        if existing:
            raise ValueError(f"Work order with code '{wo_in.workOrderCode}' already exists")
            
        # Check product exists
        if not ObjectId.is_valid(wo_in.productId):
            raise ValueError(f"Invalid product ID format: '{wo_in.productId}'")
        product = await db.products.find_one({"_id": ObjectId(wo_in.productId)})
        if not product:
            raise ValueError(f"Product with ID '{wo_in.productId}' does not exist")
            
        # Check workflow exists
        if not ObjectId.is_valid(wo_in.workflowId):
            raise ValueError(f"Invalid workflow ID format: '{wo_in.workflowId}'")
        workflow = await db.workflows.find_one({"_id": ObjectId(wo_in.workflowId)})
        if not workflow:
            raise ValueError(f"Workflow with ID '{wo_in.workflowId}' does not exist")
            
        wf_version = workflow.get("version", 1)
        if wo_in.workflowVersion is not None and wo_in.workflowVersion != wf_version:
            # Allow fallback to actual workflow version to prevent accidental blocking
            wo_in.workflowVersion = wf_version
        else:
            wo_in.workflowVersion = wf_version

        # Check target quantity
        if wo_in.quantity <= 0:
            raise ValueError("Work order quantity must be positive")

        # Map and clone workflow operations to execution snapshot operations
        execution_ops = []
        workflow_ops = workflow.get("operations", [])
        custom_ops_by_id = {}
        if wo_in.operations:
            for cop in wo_in.operations:
                if isinstance(cop, dict) and "operationId" in cop:
                    custom_ops_by_id[cop["operationId"]] = cop
        
        for op in workflow_ops:
            op_id = op["operationId"]
            custom_op = custom_ops_by_id.get(op_id, {})
            deps = op.get("dependencies", [])
            initial_status = (
                WorkOrderOperationStatus.READY.value 
                if not deps 
                else WorkOrderOperationStatus.PENDING.value
            )
            
            # Prioritize work order's custom personnel & workstation selection
            mach_id = custom_op.get("assignedMachineId") or op.get("assignedMachineId")
            oper_id = custom_op.get("assignedOperatorId") or op.get("assignedOperatorId")
            
            # Build immutable required material snapshot for this operation
            req_mats_snapshot = []
            for rm in op.get("requiredMaterials", []):
                qty_per_unit = float(rm.get("quantity", 0.0))
                total_req = round(qty_per_unit * wo_in.quantity, 4)
                mat_id_val = rm.get("materialId")
                spec_id_val = rm.get("specificationId")
                
                mat_doc = await db.materials.find_one({"_id": ObjectId(mat_id_val)}) if (mat_id_val and ObjectId.is_valid(mat_id_val)) else None
                spec_doc = await db.material_specifications.find_one({"_id": ObjectId(spec_id_val)}) if (spec_id_val and ObjectId.is_valid(spec_id_val)) else None
                
                mat_name = mat_doc.get("name") if mat_doc else "Raw Material"
                spec_name = spec_doc.get("name") if spec_doc else None
                unit_val = rm.get("unit") or (mat_doc.get("unit") if mat_doc else "units")
                unit_cost = mat_doc.get("unitCost") if mat_doc else None
                est_cost = round(total_req * unit_cost, 2) if (unit_cost is not None and unit_cost >= 0) else None

                req_mats_snapshot.append({
                    "materialId": mat_id_val,
                    "specificationId": spec_id_val,
                    "materialName": mat_name,
                    "specificationName": spec_name,
                    "unit": unit_val,
                    "quantityPerUnit": qty_per_unit,
                    "totalRequiredQuantity": total_req,
                    "quantityReserved": 0.0,
                    "quantityConsumed": 0.0,
                    "unitCost": unit_cost,
                    "estimatedCost": est_cost,
                    "actualCost": 0.0
                })

            exec_op = {
                "operationId": op_id,
                "name": op.get("name", ""),
                "sequence": op["sequence"],
                "requiredMachineType": op.get("requiredMachineType"),
                "requiredCapabilityIds": op.get("requiredCapabilityIds", []),
                "assignedMachineId": mach_id,
                "assignedOperatorId": oper_id,
                "status": initial_status,
                "waitingReason": None,
                "dependencies": deps,
                "requiredMaterials": req_mats_snapshot,
                "startedAt": None,
                "estimatedCompletionAt": None,
                "actualStart": None,
                "actualEnd": None,
                "durationSeconds": None,
                "inputQuantity": float(wo_in.quantity) if not deps else 0.0,
                "processedQuantity": 0.0,
                "outputQuantity": 0.0,
                "scrapQuantity": 0.0,
                "quantityCompleted": 0.0,
                "quantityRejected": 0.0
            }
            execution_ops.append(exec_op)

        wo_data = wo_in.model_dump()
        wo_data["operations"] = execution_ops
            
        wo_data["createdAt"] = datetime.utcnow()
        wo_data["updatedAt"] = datetime.utcnow()
        
        result = await db.work_orders.insert_one(wo_data)
        wo_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="WORK_ORDER_CREATED",
            entity_type="work_order",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={
                "workOrderCode": wo_in.workOrderCode,
                "productId": wo_in.productId,
                "workflowId": wo_in.workflowId,
                "quantity": wo_in.quantity
            }
        )
        return wo_data

    @staticmethod
    async def get_work_order_by_id(wo_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(wo_id):
            return None
        return await db.work_orders.find_one({"_id": ObjectId(wo_id)})

    @staticmethod
    async def list_work_orders() -> List[dict]:
        db = get_db()
        work_orders = []
        async for doc in db.work_orders.find():
            work_orders.append(doc)
        return work_orders

    @staticmethod
    async def update_work_order(wo_id: str, wo_update: WorkOrderUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(wo_id):
            return None
            
        update_data = wo_update.model_dump(exclude_unset=True)
        if not update_data:
            return await WorkOrderService.get_work_order_by_id(wo_id)
            
        if "operations" in update_data and update_data["operations"] is not None:
            serialized_ops = []
            for op in update_data["operations"]:
                if hasattr(op, "model_dump"):
                    serialized_ops.append(op.model_dump())
                else:
                    serialized_ops.append(op)
            update_data["operations"] = serialized_ops
            
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.work_orders.find_one_and_update(
            {"_id": ObjectId(wo_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            if update_data.get("status") == WorkOrderStatus.CANCELLED.value:
                from app.services.material_reservation_service import MaterialReservationService
                await MaterialReservationService.release_for_work_order(str(wo_id), actor_id=actor_id)

            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="WORK_ORDER_UPDATED",
                entity_type="work_order",
                entity_id=str(wo_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys()), "status": update_data.get("status")}
            )
        return result

    @staticmethod
    async def delete_work_order(wo_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(wo_id):
            return False
            
        wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
        if not wo:
            return False

        wo_id_str = str(wo_id)
        wo_code = wo.get("workOrderCode", "Unknown")
        now = datetime.utcnow()

        # Release any active material reservations
        try:
            from app.services.material_reservation_service import MaterialReservationService
            await MaterialReservationService.release_for_work_order(wo_id_str, actor_id=actor_id)
        except Exception as e:
            logger.warning(f"Failed to release material reservations on WO deletion: {e}")

        # 1. Delete the work order document
        result = await db.work_orders.delete_one({"_id": ObjectId(wo_id)})
        deleted = result.deleted_count > 0

        if deleted:
            # 2. Release all OCCUPIED machines bound to this work order
            async for mach in db.machines.find({
                "$or": [
                    {"currentWorkOrderId": wo_id_str},
                    {"currentWorkOrderId": ObjectId(wo_id)}
                ]
            }):
                mach_id = str(mach["_id"])
                update_status = MachineStatus.IDLE.value if mach.get("status") == MachineStatus.OCCUPIED.value else mach.get("status")
                await db.machines.update_one(
                    {"_id": mach["_id"]},
                    {"$set": {
                        "status": update_status,
                        "currentOperationId": None,
                        "currentWorkOrderId": None,
                        "currentWorkOrderCode": None,
                        "currentOperatorId": None,
                        "updatedAt": now
                    }}
                )
                await ws_manager.broadcast({
                    "type": "MACHINE_RELEASED",
                    "data": {
                        "machineId": mach_id,
                        "machineCode": mach.get("machineCode"),
                        "status": update_status
                    }
                })

            # Also release any machine explicitly referenced in operations
            for op in wo.get("operations", []):
                m_id = op.get("assignedMachineId")
                if m_id and ObjectId.is_valid(m_id):
                    await db.machines.update_one(
                        {"_id": ObjectId(m_id), "currentWorkOrderId": wo_id_str},
                        {"$set": {
                            "status": MachineStatus.IDLE.value,
                            "currentOperationId": None,
                            "currentWorkOrderId": None,
                            "currentWorkOrderCode": None,
                            "currentOperatorId": None,
                            "updatedAt": now
                        }}
                    )

            # 3. Release all ASSIGNED operators bound to this work order
            async for user in db.users.find({
                "$or": [
                    {"currentWorkOrderId": wo_id_str},
                    {"currentWorkOrderId": ObjectId(wo_id)}
                ]
            }):
                update_avail = OperatorAvailability.AVAILABLE.value if user.get("availabilityStatus") == OperatorAvailability.ASSIGNED.value else user.get("availabilityStatus", "AVAILABLE")
                await db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "availabilityStatus": update_avail,
                        "currentOperationId": None,
                        "currentWorkOrderId": None,
                        "updatedAt": now
                    }}
                )

            # Also release operators referenced in operations
            for op in wo.get("operations", []):
                op_user_id = op.get("assignedOperatorId")
                if op_user_id:
                    query = {"$or": [{"employeeId": op_user_id}]}
                    if ObjectId.is_valid(op_user_id):
                        query["$or"].append({"_id": ObjectId(op_user_id)})
                    await db.users.update_many(
                        query,
                        {"$set": {
                            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
                            "currentOperationId": None,
                            "currentWorkOrderId": None,
                            "updatedAt": now
                        }}
                    )

            # 4. Release assigned supervisor pointers
            sup_id = wo.get("supervisorId")
            if sup_id:
                sup_query = {"$or": [{"employeeId": sup_id}]}
                if ObjectId.is_valid(sup_id):
                    sup_query["$or"].append({"_id": ObjectId(sup_id)})
                await db.users.update_many(
                    sup_query,
                    {"$set": {
                        "currentWorkOrderId": None,
                        "currentOperationId": None,
                        "updatedAt": now
                    }}
                )

            # 5. Clean up associated Executions & Execution Events
            await db.executions.delete_many({"workOrderId": wo_id_str})

            # 6. Log audit event & broadcast deletion
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="WORK_ORDER_DELETED",
                entity_type="work_order",
                entity_id=wo_id_str,
                source="ADMIN",
                metadata={"workOrderCode": wo_code, "releasedResources": True}
            )

            await ws_manager.broadcast({
                "type": "WORK_ORDER_DELETED",
                "data": {
                    "workOrderId": wo_id_str,
                    "workOrderCode": wo_code
                }
            })

            # 7. Advance other IN_PROGRESS work orders now that resources are liberated
            try:
                from app.services.execution_engine import ExecutionEngine
                async for other_wo in db.work_orders.find({"status": "IN_PROGRESS"}):
                    asyncio.create_task(ExecutionEngine.evaluate_execution(str(other_wo["_id"])))
            except Exception as e:
                logger.error(f"Error evaluating work orders after work order deletion: {e}")

        return deleted

    @staticmethod
    async def pause_operation_node(wo_id: str, op_id: str, reason: str = "Admin paused operation node", actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        if not ObjectId.is_valid(wo_id):
            raise ValueError("Invalid work order ID")

        wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
        if not wo:
            raise ValueError("Work order not found")

        wo_id_str = str(wo["_id"])
        wo_code = wo.get("workOrderCode", "Unknown")
        now = datetime.utcnow()

        target_op = next((o for o in wo.get("operations", []) if o.get("operationId") == op_id), None)
        if not target_op:
            raise ValueError(f"Operation '{op_id}' not found in work order")

        # 1. Release assigned machine if occupied
        mach_id = target_op.get("assignedMachineId")
        if mach_id and ObjectId.is_valid(mach_id):
            await db.machines.update_one(
                {"_id": ObjectId(mach_id), "currentWorkOrderId": wo_id_str},
                {"$set": {
                    "status": MachineStatus.IDLE.value,
                    "currentOperationId": None,
                    "currentWorkOrderId": None,
                    "currentWorkOrderCode": None,
                    "currentOperatorId": None,
                    "updatedAt": now
                }}
            )

        # 2. Release operator if assigned
        oper_id = target_op.get("assignedOperatorId")
        if oper_id:
            query = {"$or": [{"employeeId": oper_id}]}
            if ObjectId.is_valid(oper_id):
                query["$or"].append({"_id": ObjectId(oper_id)})
            await db.users.update_many(
                query,
                {"$set": {
                    "availabilityStatus": OperatorAvailability.AVAILABLE.value,
                    "currentOperationId": None,
                    "currentWorkOrderId": None,
                    "updatedAt": now
                }}
            )

        # 3. Mark operation as PAUSED
        await db.work_orders.update_one(
            {"_id": wo["_id"], "operations.operationId": op_id},
            {"$set": {
                "operations.$.status": WorkOrderOperationStatus.PAUSED.value,
                "operations.$.waitingReason": reason,
                "operations.$.actualEnd": now,
                "updatedAt": now
            }}
        )

        # 4. Log event
        from app.schemas.execution import ExecutionEventType
        from app.services.execution_engine import ExecutionEngine
        await ExecutionEngine.log_execution_event(
            execution_id=str(wo.get("executionId", wo_id_str)),
            work_order_id=wo_id_str,
            work_order_code=wo_code,
            event_type=ExecutionEventType.OPERATION_PAUSED,
            message=f"Operation {op_id} paused by administrator: {reason}",
            operation_id=op_id,
            metadata={"adminAction": True, "reason": reason}
        )

        state_data = await ExecutionEngine.get_execution_state(wo_id_str)
        await ws_manager.broadcast({
            "type": "EXECUTION_STATE_UPDATE",
            "data": state_data
        })

        return await WorkOrderService.get_work_order_by_id(wo_id)

    @staticmethod
    async def resume_operation_node(
        wo_id: str, 
        op_id: str, 
        machine_id: Optional[str] = None, 
        operator_id: Optional[str] = None, 
        actor_id: str = "SYSTEM"
    ) -> dict:
        db = get_db()
        if not ObjectId.is_valid(wo_id):
            raise ValueError("Invalid work order ID")

        wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
        if not wo:
            raise ValueError("Work order not found")

        wo_id_str = str(wo["_id"])
        wo_code = wo.get("workOrderCode", "Unknown")
        now = datetime.utcnow()

        target_op = next((o for o in wo.get("operations", []) if o.get("operationId") == op_id), None)
        if not target_op:
            raise ValueError(f"Operation '{op_id}' not found in work order")

        update_fields = {
            "operations.$.status": WorkOrderOperationStatus.READY.value,
            "operations.$.waitingReason": None,
            "updatedAt": now
        }

        # If reassigning machine
        if machine_id:
            if ObjectId.is_valid(machine_id):
                m = await db.machines.find_one({"_id": ObjectId(machine_id)})
                if m:
                    update_fields["operations.$.assignedMachineId"] = str(m["_id"])
                    update_fields["operations.$.assignedMachineCode"] = m.get("machineCode")
            elif machine_id == "AUTO":
                update_fields["operations.$.assignedMachineId"] = None
                update_fields["operations.$.assignedMachineCode"] = None

        # If reassigning operator
        if operator_id:
            if ObjectId.is_valid(operator_id):
                u = await db.users.find_one({"_id": ObjectId(operator_id)})
                if u:
                    update_fields["operations.$.assignedOperatorId"] = str(u["_id"])
            elif operator_id == "AUTO":
                update_fields["operations.$.assignedOperatorId"] = None

        from app.schemas.execution import ExecutionEventType, ExecutionStatus
        from app.services.execution_engine import ExecutionEngine
        from app.services.material_reservation_service import MaterialReservationService

        # If work order is not IN_PROGRESS (e.g. WAITING_FOR_MATERIAL, PLANNED, PAUSED), attempt to activate it
        if wo.get("status") != WorkOrderStatus.IN_PROGRESS.value:
            res_result = await MaterialReservationService.reserve_for_work_order(wo_id_str, actor_id=actor_id)
            if res_result.get("success", False):
                await db.work_orders.update_one(
                    {"_id": wo["_id"]},
                    {"$set": {"status": WorkOrderStatus.IN_PROGRESS.value, "startedAt": wo.get("startedAt") or now, "updatedAt": now}}
                )

        # Ensure execution record exists
        execution = await db.executions.find_one({"workOrderId": wo_id_str})
        if not execution:
            exec_data = {
                "workOrderId": wo_id_str,
                "workOrderCode": wo_code,
                "workflowId": wo.get("workflowId"),
                "productId": wo.get("productId"),
                "status": ExecutionStatus.IN_PROGRESS.value,
                "startedAt": now,
                "completedAt": None,
                "activeOperationsCount": 0,
                "completedOperationsCount": 0,
                "totalOperationsCount": len(wo.get("operations", [])),
                "createdAt": now,
                "updatedAt": now
            }
            exec_res = await db.executions.insert_one(exec_data)
            exec_id_str = str(exec_res.inserted_id)
        else:
            exec_id_str = str(execution["_id"])
            await db.executions.update_one(
                {"_id": execution["_id"]},
                {"$set": {"status": ExecutionStatus.IN_PROGRESS.value, "updatedAt": now}}
            )

        # Update target operation
        await db.work_orders.update_one(
            {"_id": wo["_id"], "operations.operationId": op_id},
            {"$set": update_fields}
        )

        await ExecutionEngine.log_execution_event(
            execution_id=exec_id_str,
            work_order_id=wo_id_str,
            work_order_code=wo_code,
            event_type=ExecutionEventType.OPERATION_READY,
            message=f"Operation {op_id} resumed by administrator and set to READY.",
            operation_id=op_id,
            metadata={"adminAction": True, "reassignedMachine": machine_id, "reassignedOperator": operator_id}
        )

        # Trigger immediate execution evaluation
        await ExecutionEngine.evaluate_execution(wo_id_str)

        state_data = await ExecutionEngine.get_execution_state(wo_id_str)
        await ws_manager.broadcast({
            "type": "EXECUTION_STATE_UPDATE",
            "data": state_data
        })

        return await WorkOrderService.get_work_order_by_id(wo_id)
