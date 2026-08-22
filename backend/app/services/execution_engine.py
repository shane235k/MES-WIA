import asyncio
import logging
from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.websocket import ws_manager
from app.schemas.execution import ExecutionStatus, ExecutionEventType
from app.schemas.work_order import WorkOrderStatus, WorkOrderOperationStatus
from app.schemas.machine import MachineStatus
from app.schemas.user import OperatorAvailability, UserRole
from app.services.redis_service import RedisService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Real-time MES Execution Engine.
    Coordinates Work Order execution, machine/operator resource occupancy,
    dependency-driven concurrency, and append-only execution events.
    """

    @staticmethod
    async def log_execution_event(
        execution_id: str,
        work_order_id: str,
        work_order_code: str,
        event_type: ExecutionEventType,
        message: str,
        operation_id: Optional[str] = None,
        machine_id: Optional[str] = None,
        machine_code: Optional[str] = None,
        operator_id: Optional[str] = None,
        operator_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        Append an event to the execution_events collection and broadcast via WebSocket.
        """
        db = get_db()
        event_data = {
            "executionId": execution_id,
            "workOrderId": work_order_id,
            "workOrderCode": work_order_code,
            "operationId": operation_id,
            "machineId": machine_id,
            "machineCode": machine_code,
            "operatorId": operator_id,
            "operatorName": operator_name,
            "eventType": event_type.value,
            "message": message,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }
        result = await db.execution_events.insert_one(event_data)
        event_data["_id"] = str(result.inserted_id)

        # Mirror event to central Audit Trail
        await AuditService.log_event(
            actor_id=operator_id or "SYSTEM",
            actor_type="USER" if operator_id else "SYSTEM",
            action=event_type.value,
            entity_type="work_order",
            entity_id=work_order_id,
            source="EXECUTION_ENGINE",
            metadata={
                "workOrderCode": work_order_code,
                "operationId": operation_id,
                "machineCode": machine_code,
                "operatorName": operator_name,
                "message": message,
                **(metadata or {})
            }
        )

        # Broadcast event in real-time
        await ws_manager.broadcast({
            "type": "EXECUTION_EVENT",
            "data": event_data
        })
        return event_data

    @staticmethod
    async def start_work_order(work_order_id: str, actor_id: str = "SYSTEM") -> dict:
        """
        Validate and start execution for a Work Order.
        Does not block if future resources are busy; starts all ready operations immediately.
        """
        db = get_db()
        if not ObjectId.is_valid(work_order_id):
            raise ValueError(f"Invalid work order ID format: '{work_order_id}'")

        wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found")

        if wo.get("status") == WorkOrderStatus.COMPLETED.value:
            raise ValueError("Work order is already completed")

        # 1. Validation: Operators existence check
        operator_count = await db.users.count_documents({
            "role": UserRole.OPERATOR.value,
            "status": "ACTIVE"
        })
        if operator_count == 0:
            raise ValueError("No available operators in the system. Production execution cannot start.")

        # 2. Validation: Supervisor check
        supervisor_id = wo.get("supervisorId")
        if not supervisor_id or not ObjectId.is_valid(supervisor_id):
            raise ValueError("Work order has no supervisor assigned.")
        supervisor = await db.users.find_one({"_id": ObjectId(supervisor_id)})
        if not supervisor:
            raise ValueError("Assigned supervisor does not exist.")

        # 3. Material Reservation Check (Phase 6)
        from app.services.material_reservation_service import MaterialReservationService
        res_check = await MaterialReservationService.reserve_for_work_order(work_order_id, actor_id=actor_id)
        if not res_check.get("success", True):
            # Shortage detected! WO is placed into WAITING_FOR_MATERIAL without assigning/locking machines or operators
            await ws_manager.broadcast({
                "type": "WORK_ORDER_MATERIAL_SHORTAGE",
                "data": {
                    "workOrderId": work_order_id,
                    "workOrderCode": wo.get("workOrderCode"),
                    "status": WorkOrderStatus.WAITING_FOR_MATERIAL.value,
                    "shortages": res_check.get("shortages", []),
                    "message": res_check.get("message")
                }
            })
            return await ExecutionEngine.get_execution_state(work_order_id)

        # 4. Create or fetch Execution record
        execution = await db.executions.find_one({"workOrderId": work_order_id})
        now = datetime.utcnow()
        if not execution:
            exec_data = {
                "workOrderId": work_order_id,
                "workOrderCode": wo.get("workOrderCode"),
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
            exec_data["_id"] = exec_res.inserted_id
            execution = exec_data
        else:
            await db.executions.update_one(
                {"_id": execution["_id"]},
                {"$set": {"status": ExecutionStatus.IN_PROGRESS.value, "updatedAt": now}}
            )

        exec_id_str = str(execution["_id"])

        # Update Work Order status to IN_PROGRESS
        await db.work_orders.update_one(
            {"_id": ObjectId(work_order_id)},
            {"$set": {"status": WorkOrderStatus.IN_PROGRESS.value, "startedAt": now, "updatedAt": now}}
        )

        # Log WORK_ORDER_STARTED
        await ExecutionEngine.log_execution_event(
            execution_id=exec_id_str,
            work_order_id=work_order_id,
            work_order_code=wo.get("workOrderCode"),
            event_type=ExecutionEventType.WORK_ORDER_STARTED,
            message=f"Work Order {wo.get('workOrderCode')} execution started.",
            metadata={"quantity": wo.get("quantity"), "priority": wo.get("priority")}
        )

        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="WORK_ORDER_STARTED",
            entity_type="work_order",
            entity_id=work_order_id,
            source="EXECUTION_ENGINE",
            metadata={"workOrderCode": wo.get("workOrderCode")}
        )

        # Evaluate execution transitions
        await ExecutionEngine.evaluate_execution(work_order_id)
        return await ExecutionEngine.get_execution_state(work_order_id)

    @staticmethod
    async def evaluate_execution(work_order_id: str) -> None:
        """
        Evaluate and advance execution state for a work order.
        Protected by Redis per-work-order lock.
        """
        db = get_db()
        lock_key = f"execution-lock:{work_order_id}"
        
        # Acquire distributed lock (5 sec TTL)
        lock_acquired = await RedisService.acquire_lock(lock_key, ttl_seconds=5)
        if not lock_acquired:
            logger.info(f"Could not acquire lock for {work_order_id}, evaluation skipped for this tick.")
            return

        try:
            wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
            execution = await db.executions.find_one({"workOrderId": work_order_id})
            if not wo or not execution or wo.get("status") != WorkOrderStatus.IN_PROGRESS.value:
                return

            exec_id_str = str(execution["_id"])
            work_order_code = wo.get("workOrderCode")
            now = datetime.utcnow()
            operations = wo.get("operations", [])
            modified_ops = False

            # ----------------------------------------------------
            # STEP 0: Check for machines completing scheduled maintenance
            # ----------------------------------------------------
            async for m_maint in db.machines.find({
                "status": MachineStatus.MAINTENANCE.value,
                "maintenanceEstimatedEnd": {"$lte": now}
            }):
                await MachineService.recover_machine(str(m_maint["_id"]), actor_id="SYSTEM")
                if m_maint.get("currentIncidentId") and ObjectId.is_valid(m_maint["currentIncidentId"]):
                    await db.incidents.update_one(
                        {"_id": ObjectId(m_maint["currentIncidentId"])},
                        {"$set": {
                            "status": "RESOLVED",
                            "resolvedAt": now,
                            "resolution": "Auto-recovered after scheduled maintenance window completed."
                        }}
                    )

            # ----------------------------------------------------
            # STEP A: Check running operations for completion
            # ----------------------------------------------------
            for op in operations:
                if op.get("status") == WorkOrderOperationStatus.IN_PROGRESS.value:
                    est_end = op.get("estimatedCompletionAt")
                    if est_end and now >= est_end:
                        in_qty = float(op.get("inputQuantity") or wo.get("quantity", 10.0))
                        scrap_qty = float(op.get("scrapQuantity", 0.0))
                        out_qty = max(0.0, in_qty - scrap_qty)
                        
                        op["status"] = WorkOrderOperationStatus.COMPLETED.value
                        op["actualEnd"] = now
                        op["processedQuantity"] = in_qty
                        op["outputQuantity"] = out_qty
                        op["quantityCompleted"] = out_qty
                        modified_ops = True

                        # Release Machine
                        mach_id = op.get("assignedMachineId")
                        mach_code = "Unknown"
                        if mach_id and ObjectId.is_valid(mach_id):
                            mach = await db.machines.find_one({"_id": ObjectId(mach_id)})
                            if mach:
                                mach_code = mach.get("machineCode", "Unknown")
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
                            await ExecutionEngine.log_execution_event(
                                execution_id=exec_id_str,
                                work_order_id=work_order_id,
                                work_order_code=work_order_code,
                                event_type=ExecutionEventType.MACHINE_RELEASED,
                                message=f"Machine {mach_code} returned to IDLE state.",
                                operation_id=op.get("operationId"),
                                machine_id=mach_id,
                                machine_code=mach_code
                            )

                        # Release Operator
                        op_user_id = op.get("assignedOperatorId")
                        op_user_name = "Unknown"
                        if op_user_id and ObjectId.is_valid(op_user_id):
                            oper = await db.users.find_one({"_id": ObjectId(op_user_id)})
                            if oper:
                                op_user_name = oper.get("name", "Unknown")
                            await db.users.update_one(
                                {"_id": ObjectId(op_user_id)},
                                {"$set": {
                                    "availabilityStatus": OperatorAvailability.AVAILABLE.value,
                                    "currentOperationId": None,
                                    "currentWorkOrderId": None,
                                    "updatedAt": now
                                }}
                            )
                            await ExecutionEngine.log_execution_event(
                                execution_id=exec_id_str,
                                work_order_id=work_order_id,
                                work_order_code=work_order_code,
                                event_type=ExecutionEventType.OPERATOR_RELEASED,
                                message=f"Operator {op_user_name} returned to AVAILABLE state.",
                                operation_id=op.get("operationId"),
                                operator_id=op_user_id,
                                operator_name=op_user_name
                            )

                        # Log OPERATION_COMPLETED
                        await ExecutionEngine.log_execution_event(
                            execution_id=exec_id_str,
                            work_order_id=work_order_id,
                            work_order_code=work_order_code,
                            event_type=ExecutionEventType.OPERATION_COMPLETED,
                            message=f"Operation {op.get('operationId')} ({op.get('name')}) completed.",
                            operation_id=op.get("operationId"),
                            machine_id=mach_id,
                            machine_code=mach_code,
                            operator_id=op_user_id,
                            operator_name=op_user_name
                        )

                        # Phase 6: Convert reserved materials to actual consumption upon operation completion
                        try:
                            from app.services.material_reservation_service import MaterialReservationService
                            await MaterialReservationService.consume_for_operation(
                                work_order_id=work_order_id,
                                operation_id=op.get("operationId"),
                                actor_id="SYSTEM"
                            )
                        except Exception as mat_err:
                            logger.error(f"Material consumption hook error for operation {op.get('operationId')}: {mat_err}")

            # ----------------------------------------------------
            # STEP B: Promote PENDING operations to READY if dependencies are met
            # ----------------------------------------------------
            completed_op_ids = {
                o.get("operationId") for o in operations 
                if o.get("status") == WorkOrderOperationStatus.COMPLETED.value
            }

            for op in operations:
                if op.get("status") == WorkOrderOperationStatus.PENDING.value:
                    deps = op.get("dependencies", [])
                    if all(dep in completed_op_ids for dep in deps):
                        # Compute inputQuantity from completed predecessor operations
                        pred_ops = [o for o in operations if o.get("operationId") in deps]
                        if pred_ops:
                            input_qty = min(float(p.get("outputQuantity", wo.get("quantity", 10.0))) for p in pred_ops)
                        else:
                            input_qty = float(wo.get("quantity", 10.0))
                        
                        op["inputQuantity"] = input_qty
                        op["status"] = WorkOrderOperationStatus.READY.value
                        modified_ops = True
                        await ExecutionEngine.log_execution_event(
                            execution_id=exec_id_str,
                            work_order_id=work_order_id,
                            work_order_code=work_order_code,
                            event_type=ExecutionEventType.OPERATION_READY,
                            message=f"Operation {op.get('operationId')} ({op.get('name')}) is now READY with input quantity {input_qty}.",
                            operation_id=op.get("operationId"),
                            metadata={"inputQuantity": input_qty}
                        )

            # ----------------------------------------------------
            # STEP B.2: Auto-resume PAUSED operations if compatible machine has recovered and is online
            # ----------------------------------------------------
            for op in operations:
                if op.get("status") == WorkOrderOperationStatus.PAUSED.value:
                    mach_id = op.get("assignedMachineId")
                    req_type = (op.get("requiredMachineType") or "").upper()
                    
                    mach_available = False
                    if mach_id and ObjectId.is_valid(mach_id):
                        m = await db.machines.find_one({"_id": ObjectId(mach_id)})
                        if m and m.get("status") == MachineStatus.IDLE.value and m.get("availability", True):
                            mach_available = True
                    
                    if not mach_available and req_type:
                        async for m in db.machines.find({"status": MachineStatus.IDLE.value, "availability": True}):
                            m_type = m.get("type", "").upper()
                            m_supp = [t.upper() for t in m.get("supportedTypes", [])]
                            if m_type == req_type or (m_type == "MULTI_PURPOSE" and req_type in m_supp):
                                mach_available = True
                                break
                    
                    if mach_available:
                        op["status"] = WorkOrderOperationStatus.READY.value
                        op["waitingReason"] = None
                        modified_ops = True
                        await ExecutionEngine.log_execution_event(
                            execution_id=exec_id_str,
                            work_order_id=work_order_id,
                            work_order_code=work_order_code,
                            event_type=ExecutionEventType.OPERATION_READY,
                            message=f"Operation {op.get('operationId')} auto-resumed to READY as machine is now available.",
                            operation_id=op.get("operationId"),
                            metadata={"autoResume": True}
                        )

            # ----------------------------------------------------
            # STEP C: Start READY / WAITING_FOR_RESOURCE / INTERRUPTED operations if resources are available
            # ----------------------------------------------------
            for op in operations:
                if op.get("status") in [
                    WorkOrderOperationStatus.READY.value, 
                    WorkOrderOperationStatus.WAITING_FOR_RESOURCE.value,
                    WorkOrderOperationStatus.INTERRUPTED.value
                ]:
                    mach_id = op.get("assignedMachineId")
                    op_user_id = op.get("assignedOperatorId")
                    
                    machine = None
                    if mach_id and ObjectId.is_valid(mach_id):
                        machine = await db.machines.find_one({"_id": ObjectId(mach_id)})
                        
                    operator = None
                    if op_user_id and ObjectId.is_valid(op_user_id):
                        operator = await db.users.find_one({"_id": ObjectId(op_user_id)})

                    mach_code = machine.get("machineCode", "None") if machine else "None"
                    op_user_name = operator.get("name", "None") if operator else "None"

                    # 1. Resolve or find compatible machine
                    req_type = (op.get("requiredMachineType") or "").upper()
                    if not req_type and machine:
                        req_type = (machine.get("type") or "").upper()

                    # Dynamic Failover / Allocation:
                    # If no machine assigned OR assigned machine is DOWN / in MAINTENANCE, search for an idle alternative
                    if not machine or machine.get("status") in [MachineStatus.DOWN.value, MachineStatus.MAINTENANCE.value]:
                        alt_machine = None
                        query = {
                            "status": MachineStatus.IDLE.value,
                            "availability": True
                        }
                        if machine:
                            query["_id"] = {"$ne": machine["_id"]}

                        async for m in db.machines.find(query):
                            m_type = (m.get("type") or "").upper()
                            m_supp = [t.upper() for t in m.get("supportedTypes", [])]
                            if req_type:
                                if m_type == req_type or (m_type == "MULTI_PURPOSE" and req_type in m_supp):
                                    alt_machine = m
                                    break
                            else:
                                alt_machine = m
                                break

                        if alt_machine:
                            prev_code = mach_code
                            machine = alt_machine
                            mach_id = str(alt_machine["_id"])
                            mach_code = alt_machine.get("machineCode")
                            op["assignedMachineId"] = mach_id
                            op["assignedMachineCode"] = mach_code
                            modified_ops = True
                            if prev_code != "None":
                                await ExecutionEngine.log_execution_event(
                                    execution_id=exec_id_str,
                                    work_order_id=work_order_id,
                                    work_order_code=work_order_code,
                                    event_type=ExecutionEventType.OPERATION_REROUTED,
                                    message=f"Operation {op.get('operationId')} auto-rerouted from machine {prev_code} to available backup {mach_code}.",
                                    operation_id=op.get("operationId"),
                                    machine_id=mach_id,
                                    machine_code=mach_code,
                                    metadata={"failover": True, "previousMachine": prev_code}
                                )

                    # 2. Resolve operator: keep assigned operator if active and available or already assigned to this WO
                    if not operator or operator.get("status") != "ACTIVE":
                        avail_op = await db.users.find_one({
                            "role": UserRole.OPERATOR.value,
                            "status": "ACTIVE",
                            "availabilityStatus": OperatorAvailability.AVAILABLE.value
                        })
                        if avail_op:
                            operator = avail_op
                            op_user_id = str(avail_op["_id"])
                            op_user_name = avail_op.get("name", "Operator")
                            op["assignedOperatorId"] = op_user_id
                            modified_ops = True

                    # Check resource availability
                    machine_ready = (
                        machine is not None and 
                        machine.get("availability", True) is True and
                        (
                            machine.get("status") == MachineStatus.IDLE.value or
                            (
                                machine.get("status") == MachineStatus.OCCUPIED.value and
                                str(machine.get("currentWorkOrderId", "")) == str(work_order_id) and
                                machine.get("currentOperationId") == op.get("operationId")
                            )
                        )
                    )
                    
                    operator_ready = (
                        operator is not None and 
                        operator.get("status") == "ACTIVE" and
                        (
                            operator.get("availabilityStatus") == OperatorAvailability.AVAILABLE.value or
                            (
                                str(operator.get("currentWorkOrderId", "")) == str(work_order_id) and
                                operator.get("currentOperationId") == op.get("operationId")
                            )
                        )
                    )

                    if machine_ready and operator_ready:
                        # Resources available -> Start operation!
                        op["status"] = WorkOrderOperationStatus.IN_PROGRESS.value
                        op["waitingReason"] = None
                        
                        # Compute duration strictly from operation inputQuantity / machine.processingRate
                        proc_rate = float(machine.get("processingRate", 1.0)) if machine else 1.0
                        in_qty = float(op.get("inputQuantity") or wo.get("quantity", 10.0))
                        duration = max(3, int(in_qty / proc_rate)) if proc_rate > 0 else 10
                        
                        op["inputQuantity"] = in_qty
                        op["durationSeconds"] = duration
                        op["startedAt"] = now
                        op["actualStart"] = now
                        op["estimatedCompletionAt"] = now + timedelta(seconds=duration)
                        modified_ops = True

                        # Set machine to OCCUPIED
                        await db.machines.update_one(
                            {"_id": machine["_id"]},
                            {"$set": {
                                "status": MachineStatus.OCCUPIED.value,
                                "currentOperationId": op.get("operationId"),
                                "currentWorkOrderId": work_order_id,
                                "currentWorkOrderCode": work_order_code,
                                "currentOperatorId": op_user_id,
                                "updatedAt": now
                            }}
                        )

                        # Set operator to ASSIGNED
                        await db.users.update_one(
                            {"_id": operator["_id"]},
                            {"$set": {
                                "availabilityStatus": OperatorAvailability.ASSIGNED.value,
                                "currentOperationId": op.get("operationId"),
                                "currentWorkOrderId": work_order_id,
                                "updatedAt": now
                            }}
                        )

                        await ExecutionEngine.log_execution_event(
                            execution_id=exec_id_str,
                            work_order_id=work_order_id,
                            work_order_code=work_order_code,
                            event_type=ExecutionEventType.OPERATION_STARTED,
                            message=f"Operation {op.get('operationId')} started on Machine {mach_code} with Operator {op_user_name}.",
                            operation_id=op.get("operationId"),
                            machine_id=mach_id,
                            machine_code=mach_code,
                            operator_id=op_user_id,
                            operator_name=op_user_name,
                            metadata={"durationSeconds": duration}
                        )

                        await ExecutionEngine.log_execution_event(
                            execution_id=exec_id_str,
                            work_order_id=work_order_id,
                            work_order_code=work_order_code,
                            event_type=ExecutionEventType.MACHINE_OCCUPIED,
                            message=f"Machine {mach_code} is now OCCUPIED by {op.get('operationId')}.",
                            operation_id=op.get("operationId"),
                            machine_id=mach_id,
                            machine_code=mach_code
                        )

                        await ExecutionEngine.log_execution_event(
                            execution_id=exec_id_str,
                            work_order_id=work_order_id,
                            work_order_code=work_order_code,
                            event_type=ExecutionEventType.OPERATOR_ASSIGNED,
                            message=f"Operator {op_user_name} is ASSIGNED to {op.get('operationId')}.",
                            operation_id=op.get("operationId"),
                            operator_id=op_user_id,
                            operator_name=op_user_name
                        )
                    else:
                        # Resource unavailable -> Enter WAITING_FOR_RESOURCE
                        prev_status = op.get("status")
                        if prev_status != WorkOrderOperationStatus.WAITING_FOR_RESOURCE.value:
                            op["status"] = WorkOrderOperationStatus.WAITING_FOR_RESOURCE.value
                            modified_ops = True
                        
                        reasons = []
                        if not machine:
                            reasons.append("No compatible machine assigned")
                        elif not machine_ready:
                            m_status = machine.get('status')
                            inc_id = machine.get('currentIncidentId')
                            if m_status == MachineStatus.DOWN.value and inc_id and ObjectId.is_valid(inc_id):
                                inc = await db.incidents.find_one({"_id": ObjectId(inc_id)})
                                inc_code = inc.get("incidentCode", "INC-XXXX") if inc else "Incident"
                                reasons.append(f"Machine {mach_code} is DOWN due to incident {inc_code}")
                            else:
                                reasons.append(f"Machine {mach_code} is {m_status}")
                            
                        if not operator:
                            reasons.append("No operator assigned")
                        elif not operator_ready:
                            reasons.append(f"Operator {op_user_name} is {operator.get('availabilityStatus')}")
                            
                        new_reason = " & ".join(reasons)
                        if op.get("waitingReason") != new_reason or prev_status != WorkOrderOperationStatus.WAITING_FOR_RESOURCE.value:
                            op["waitingReason"] = new_reason
                            modified_ops = True
                            await ExecutionEngine.log_execution_event(
                                execution_id=exec_id_str,
                                work_order_id=work_order_id,
                                work_order_code=work_order_code,
                                event_type=ExecutionEventType.RESOURCE_WAITING,
                                message=f"Operation {op.get('operationId')} is waiting: {new_reason}.",
                                operation_id=op.get("operationId"),
                                machine_id=mach_id,
                                machine_code=mach_code,
                                operator_id=op_user_id,
                                operator_name=op_user_name,
                                metadata={"reason": new_reason}
                            )

            # ----------------------------------------------------
            # STEP D: Check overall Work Order completion
            # ----------------------------------------------------
            all_completed = all(
                o.get("status") == WorkOrderOperationStatus.COMPLETED.value 
                for o in operations
            )
            
            active_count = sum(
                1 for o in operations 
                if o.get("status") == WorkOrderOperationStatus.IN_PROGRESS.value
            )
            completed_count = sum(
                1 for o in operations 
                if o.get("status") == WorkOrderOperationStatus.COMPLETED.value
            )

            # Persist operations and execution counters
            if modified_ops or all_completed:
                update_fields = {
                    "operations": operations,
                    "updatedAt": now
                }
                exec_update = {
                    "activeOperationsCount": active_count,
                    "completedOperationsCount": completed_count,
                    "updatedAt": now
                }

                if all_completed:
                    update_fields["status"] = WorkOrderStatus.COMPLETED.value
                    update_fields["completedAt"] = now
                    exec_update["status"] = ExecutionStatus.COMPLETED.value
                    exec_update["completedAt"] = now

                    await ExecutionEngine.log_execution_event(
                        execution_id=exec_id_str,
                        work_order_id=work_order_id,
                        work_order_code=work_order_code,
                        event_type=ExecutionEventType.WORK_ORDER_COMPLETED,
                        message=f"Work Order {work_order_code} completed successfully! All operations finished.",
                        metadata={"totalOperations": len(operations)}
                    )

                await db.work_orders.update_one(
                    {"_id": ObjectId(work_order_id)},
                    {"$set": update_fields}
                )
                await db.executions.update_one(
                    {"_id": execution["_id"]},
                    {"$set": exec_update}
                )

                # Broadcast full state sync
                state_data = await ExecutionEngine.get_execution_state(work_order_id)
                await ws_manager.broadcast({
                    "type": "EXECUTION_STATE_UPDATE",
                    "data": state_data
                })

        except Exception as e:
            logger.error(f"Error during evaluate_execution for {work_order_id}: {e}", exc_info=True)
        finally:
            await RedisService.release_lock(lock_key)

    @staticmethod
    async def get_execution_state(work_order_id: str) -> dict:
        """
        Reconstruct dynamic execution state with calculated remainingSeconds for all active operations.
        """
        db = get_db()
        if not ObjectId.is_valid(work_order_id):
            return {}

        wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
        if not wo:
            return {}

        execution = await db.executions.find_one({"workOrderId": work_order_id})
        events_cursor = db.execution_events.find({"workOrderId": work_order_id}).sort("timestamp", -1).limit(50)
        events = []
        async for ev in events_cursor:
            ev["_id"] = str(ev["_id"])
            events.append(ev)

        now = datetime.utcnow()
        operations_output = []

        for op in wo.get("operations", []):
            op_dict = dict(op)
            
            # Dynamic remainingSeconds calculation from server timestamps
            if op.get("status") == WorkOrderOperationStatus.IN_PROGRESS.value and op.get("estimatedCompletionAt"):
                rem = (op["estimatedCompletionAt"] - now).total_seconds()
                op_dict["remainingSeconds"] = max(0, int(rem))
            elif op.get("status") == WorkOrderOperationStatus.COMPLETED.value:
                op_dict["remainingSeconds"] = 0
            else:
                op_dict["remainingSeconds"] = op.get("durationSeconds", 0)

            # Enrich with machine color & code
            mach_id = op.get("assignedMachineId")
            if mach_id and ObjectId.is_valid(mach_id):
                mach = await db.machines.find_one({"_id": ObjectId(mach_id)})
                if mach:
                    op_dict["machineCode"] = mach.get("machineCode")
                    op_dict["machineType"] = mach.get("type")
                    op_dict["machineColor"] = mach.get("color", "#3B82F6")
                    op_dict["processingRate"] = mach.get("processingRate", 1.0)
                    op_dict["rateUnit"] = mach.get("rateUnit", "units/sec")

            # Enrich with operator name
            op_user_id = op.get("assignedOperatorId")
            if op_user_id and ObjectId.is_valid(op_user_id):
                oper = await db.users.find_one({"_id": ObjectId(op_user_id)})
                if oper:
                    op_dict["operatorName"] = oper.get("name")
                    op_dict["operatorEmployeeId"] = oper.get("employeeId")

            operations_output.append(op_dict)

        return {
            "workOrderId": str(wo["_id"]),
            "workOrderCode": wo.get("workOrderCode"),
            "status": wo.get("status"),
            "startedAt": wo.get("startedAt"),
            "completedAt": wo.get("completedAt"),
            "quantity": wo.get("quantity"),
            "priority": wo.get("priority"),
            "operations": operations_output,
            "execution": {
                "id": str(execution["_id"]) if execution else None,
                "status": execution.get("status") if execution else "PLANNED",
                "activeOperationsCount": execution.get("activeOperationsCount", 0) if execution else 0,
                "completedOperationsCount": execution.get("completedOperationsCount", 0) if execution else 0,
                "totalOperationsCount": len(operations_output)
            } if execution else None,
            "events": events
        }

    @staticmethod
    async def run_execution_loop_tick() -> None:
        """
        Periodic background task called every second by FastAPI background scheduler.
        1. Checks and auto-recovers machines whose scheduled maintenance has completed.
        2. Resolves incidents associated with completed maintenance windows.
        3. Scans all IN_PROGRESS work orders and advances their state.
        """
        db = get_db()
        now = datetime.utcnow()
        try:
            # 1. Check and recover machines whose maintenance has expired
            async for m_maint in db.machines.find({
                "status": MachineStatus.MAINTENANCE.value,
                "maintenanceEstimatedEnd": {"$lte": now}
            }):
                m_id_str = str(m_maint["_id"])
                await MachineService.recover_machine(m_id_str, actor_id="SYSTEM")
                inc_id = m_maint.get("currentIncidentId")
                if inc_id and ObjectId.is_valid(inc_id):
                    await db.incidents.update_one(
                        {"_id": ObjectId(inc_id)},
                        {"$set": {
                            "status": "RESOLVED",
                            "resolvedAt": now,
                            "resolvedBy": "SYSTEM",
                            "resolution": "Maintenance completed. Machine automatically recovered to IDLE."
                        }}
                    )
                    await ws_manager.broadcast({
                        "type": "INCIDENT_RESOLVED",
                        "data": {
                            "id": str(inc_id),
                            "status": "RESOLVED",
                            "resolution": "Maintenance completed. Machine automatically recovered to IDLE."
                        }
                    })

            # 2. Check and resolve any incidents with expired maintenance timers
            async for inc in db.incidents.find({
                "status": "ACTION_REQUIRED",
                "maintenanceEstimatedEnd": {"$lte": now}
            }):
                inc_id_str = str(inc["_id"])
                m_id = inc.get("machineId")
                if m_id and ObjectId.is_valid(m_id):
                    await MachineService.recover_machine(str(m_id), actor_id="SYSTEM")
                await db.incidents.update_one(
                    {"_id": ObjectId(inc_id_str)},
                    {"$set": {
                        "status": "RESOLVED",
                        "resolvedAt": now,
                        "resolvedBy": "SYSTEM",
                        "resolution": "Maintenance window ended. Workstation restored to IDLE."
                    }}
                )
                await ws_manager.broadcast({
                    "type": "INCIDENT_RESOLVED",
                    "data": {
                        "id": inc_id_str,
                        "status": "RESOLVED",
                        "resolution": "Maintenance window ended. Workstation restored to IDLE."
                    }
                })

            # 3. Check and auto-resume WAITING_FOR_MATERIAL work orders if stock has arrived
            await ExecutionEngine.check_and_resume_waiting_material_work_orders()

            # 4. Advance all IN_PROGRESS work orders
            async for wo in db.work_orders.find({"status": WorkOrderStatus.IN_PROGRESS.value}):
                wo_id = str(wo["_id"])
                await ExecutionEngine.evaluate_execution(wo_id)
        except Exception as e:
            logger.error(f"Error during execution loop tick: {e}")

    @staticmethod
    async def check_and_resume_waiting_material_work_orders() -> None:
        """
        Scan all work orders in WAITING_FOR_MATERIAL status and attempt reservation.
        If materials have been restocked, automatically transition to IN_PROGRESS and start production.
        """
        db = get_db()
        from app.services.material_reservation_service import MaterialReservationService
        
        async for wo in db.work_orders.find({
            "$or": [
                {"status": WorkOrderStatus.WAITING_FOR_MATERIAL.value},
                {"operations.status": WorkOrderOperationStatus.WAITING_FOR_MATERIAL.value}
            ]
        }):
            wo_id = str(wo["_id"])
            wo_code = wo.get("workOrderCode", "WO")
            now = datetime.utcnow()

            # Attempt reservation
            res_result = await MaterialReservationService.reserve_for_work_order(wo_id, actor_id="SYSTEM")
            if res_result.get("success", False):
                logger.info(f"Materials restocked! Auto-resuming Work Order {wo_code} from WAITING_FOR_MATERIAL to IN_PROGRESS.")
                
                # Update any operations that were WAITING_FOR_MATERIAL to READY
                ops = wo.get("operations", [])
                for op in ops:
                    if op.get("status") == WorkOrderOperationStatus.WAITING_FOR_MATERIAL.value:
                        op["status"] = WorkOrderOperationStatus.READY.value
                        op["waitingReason"] = None

                # Ensure execution record exists
                execution = await db.executions.find_one({"workOrderId": wo_id})
                if not execution:
                    exec_data = {
                        "workOrderId": wo_id,
                        "workOrderCode": wo_code,
                        "workflowId": wo.get("workflowId"),
                        "productId": wo.get("productId"),
                        "status": ExecutionStatus.IN_PROGRESS.value,
                        "startedAt": now,
                        "completedAt": None,
                        "activeOperationsCount": 0,
                        "completedOperationsCount": 0,
                        "totalOperationsCount": len(ops),
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

                # Set Work Order status to IN_PROGRESS with updated operations
                await db.work_orders.update_one(
                    {"_id": ObjectId(wo_id)},
                    {"$set": {
                        "status": WorkOrderStatus.IN_PROGRESS.value,
                        "operations": ops,
                        "startedAt": wo.get("startedAt") or now,
                        "updatedAt": now
                    }}
                )

                # Log event
                await ExecutionEngine.log_execution_event(
                    execution_id=exec_id_str,
                    work_order_id=wo_id,
                    work_order_code=wo_code,
                    event_type=ExecutionEventType.WORK_ORDER_STARTED,
                    message=f"Work Order {wo_code} auto-resumed: Required materials are now in stock.",
                    metadata={"autoResumeMaterial": True}
                )

                # Advance execution
                await ExecutionEngine.evaluate_execution(wo_id)

                state_data = await ExecutionEngine.get_execution_state(wo_id)
                await ws_manager.broadcast({
                    "type": "EXECUTION_STATE_UPDATE",
                    "data": state_data
                })

