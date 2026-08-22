import asyncio
import logging
from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.schemas.machine import MachineCreate, MachineUpdate, MachineStatus, MACHINE_TYPE_COLORS
from app.services.audit_service import AuditService
from app.services.redis_service import RedisService
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)

class MachineService:
    @staticmethod
    def _format_machine(doc: Optional[dict]) -> Optional[dict]:
        if not doc:
            return None
        d = dict(doc)
        if "_id" in d:
            d["id"] = str(d["_id"])
            d["_id"] = str(d["_id"])
        for key in ["currentOperatorId", "currentWorkOrderId", "currentOperationId", "currentIncidentId"]:
            if key in d and isinstance(d[key], ObjectId):
                d[key] = str(d[key])
        if "capabilityIds" in d:
            d["capabilityIds"] = [str(c) if isinstance(c, ObjectId) else c for c in d["capabilityIds"]]
        return d

    @staticmethod
    async def validate_capabilities(capability_ids: List[str]) -> None:
        """
        Verify that all provided capabilityIds correspond to existing Capability records.
        """
        db = get_db()
        for cap_id in capability_ids:
            if not ObjectId.is_valid(cap_id):
                raise ValueError(f"Invalid capability format: '{cap_id}'")
            exists = await db.capabilities.find_one({"_id": ObjectId(cap_id)})
            if not exists:
                raise ValueError(f"Capability with ID '{cap_id}' does not exist")

    @staticmethod
    async def create_machine(machine_in: MachineCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate machineCode
        existing = await db.machines.find_one({"machineCode": machine_in.machineCode})
        if existing:
            raise ValueError(f"Machine with code '{machine_in.machineCode}' already exists")
            
        # Validate capabilities
        await MachineService.validate_capabilities(machine_in.capabilityIds)
        
        machine_data = machine_in.model_dump()
        # Machine colors are determined by machine type
        machine_data["color"] = MACHINE_TYPE_COLORS.get(machine_in.type.upper(), "#3B82F6")
        machine_data["createdAt"] = datetime.utcnow()
        machine_data["updatedAt"] = datetime.utcnow()
        machine_data["status"] = MachineStatus.IDLE.value
        machine_data["currentOperationId"] = None
        machine_data["currentWorkOrderId"] = None
        machine_data["currentOperatorId"] = None
        machine_data["currentIncidentId"] = None
        machine_data["maintenanceEstimatedEnd"] = None
        machine_data["maintenanceDurationMinutes"] = None
        machine_data["maintenanceReason"] = None
        
        result = await db.machines.insert_one(machine_data)
        machine_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="MACHINE_CREATED",
            entity_type="machine",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={
                "machineCode": machine_in.machineCode,
                "name": machine_in.name,
                "type": machine_in.type,
                "supportedTypes": machine_in.supportedTypes,
                "color": machine_data["color"]
            }
        )
        return MachineService._format_machine(machine_data)

    @staticmethod
    async def get_machine_by_id(machine_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(machine_id):
            return None
        doc = await db.machines.find_one({"_id": ObjectId(machine_id)})
        return MachineService._format_machine(doc)

    @staticmethod
    async def list_machines() -> List[dict]:
        db = get_db()
        # Auto-recover any machines whose maintenance duration has expired
        now = datetime.utcnow()
        async for m in db.machines.find({
            "status": MachineStatus.MAINTENANCE.value,
            "maintenanceEstimatedEnd": {"$lte": now}
        }):
            await MachineService.recover_machine(str(m["_id"]), actor_id="SYSTEM")

        machines = []
        async for doc in db.machines.find():
            formatted = MachineService._format_machine(doc)
            if formatted.get("currentWorkOrderId") and not formatted.get("currentWorkOrderCode"):
                wo_id = formatted["currentWorkOrderId"]
                if ObjectId.is_valid(wo_id):
                    wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
                    if wo:
                        formatted["currentWorkOrderCode"] = wo.get("workOrderCode")
            machines.append(formatted)
        return machines

    @staticmethod
    async def find_compatible_machines(
        required_capability_ids: Optional[List[str]] = None, 
        required_machine_type: Optional[str] = None,
        only_available: bool = False
    ) -> List[dict]:
        """
        Find machines capable of performing an operation based on capability IDs or machine type.
        Supports dedicated machines matching type and MULTI_PURPOSE machines supporting that type.
        Strictly requires all specified constraints (machine type AND/OR capabilities) to match.
        """
        db = get_db()
        query = {}
        if only_available:
            query["status"] = MachineStatus.IDLE.value
            query["availability"] = True

        machines = []
        async for doc in db.machines.find(query):
            doc_caps = doc.get("capabilityIds", [])
            doc_type = doc.get("type", "").upper()
            doc_supported = [t.upper() for t in doc.get("supportedTypes", [])]
            
            type_match = True
            if required_machine_type:
                req_u = required_machine_type.upper()
                type_match = (doc_type == req_u) or (doc_type == "MULTI_PURPOSE" and req_u in doc_supported)
                
            cap_match = True
            if required_capability_ids:
                cap_match = all(cid in doc_caps for cid in required_capability_ids)
                
            # Both type_match and cap_match must be satisfied
            if type_match and cap_match:
                machines.append(MachineService._format_machine(doc))
                
        return machines

    @staticmethod
    async def update_machine(machine_id: str, machine_update: MachineUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(machine_id):
            return None
            
        update_data = machine_update.model_dump(exclude_unset=True)
        if not update_data:
            return await MachineService.get_machine_by_id(machine_id)
            
        if "capabilityIds" in update_data and update_data["capabilityIds"] is not None:
            await MachineService.validate_capabilities(update_data["capabilityIds"])
            
        if "type" in update_data and update_data["type"]:
            update_data["color"] = MACHINE_TYPE_COLORS.get(update_data["type"].upper(), "#3B82F6")
            
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.machines.find_one_and_update(
            {"_id": ObjectId(machine_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MACHINE_UPDATED",
                entity_type="machine",
                entity_id=str(machine_id),
                source="ADMIN",
                metadata={"updatedFields": list(update_data.keys())}
            )
        return MachineService._format_machine(result)

    @staticmethod
    async def delete_machine(machine_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(machine_id):
            return False
            
        machine = await db.machines.find_one({"_id": ObjectId(machine_id)})
        if not machine:
            return False
            
        # Ensure machine is not currently running an active operation
        if machine.get("status") == MachineStatus.OCCUPIED.value:
            raise ValueError("Cannot delete machine while it is executing an active operation")
            
        result = await db.machines.delete_one({"_id": ObjectId(machine_id)})
        if result.deleted_count > 0:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MACHINE_DELETED",
                entity_type="machine",
                entity_id=str(machine_id),
                source="ADMIN",
                metadata={"machineCode": machine.get("machineCode"), "name": machine.get("name")}
            )
            return True
        return False

    @staticmethod
    async def get_used_colors() -> List[str]:
        db = get_db()
        pipeline = [
            {"$group": {"_id": "$color"}},
            {"$project": {"color": "$_id", "_id": 0}}
        ]
        results = await db.machines.aggregate(pipeline).to_list(length=100)
        return [r["color"] for r in results if "color" in r and r["color"]]

    @staticmethod
    async def schedule_maintenance(
        machine_id: str,
        duration_minutes: int,
        reason: str = "Scheduled repair & maintenance",
        actor_id: str = "ADMIN",
        incident_id: Optional[str] = None
    ) -> dict:
        """
        Transitions a machine into MAINTENANCE state with a scheduled recovery timestamp.
        """
        db = get_db()
        if not ObjectId.is_valid(machine_id):
            raise ValueError(f"Invalid machine ID format: '{machine_id}'")

        machine = await db.machines.find_one({"_id": ObjectId(machine_id)})
        if not machine:
            raise ValueError(f"Machine with ID '{machine_id}' not found")

        est_end = datetime.utcnow() + timedelta(minutes=duration_minutes)

        updated_machine = await db.machines.find_one_and_update(
            {"_id": ObjectId(machine_id)},
            {"$set": {
                "status": MachineStatus.MAINTENANCE.value,
                "currentIncidentId": incident_id or machine.get("currentIncidentId"),
                "maintenanceEstimatedEnd": est_end,
                "maintenanceDurationMinutes": duration_minutes,
                "maintenanceReason": reason,
                "updatedAt": datetime.utcnow()
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="MACHINE_MAINTENANCE_SCHEDULED",
            entity_type="machine",
            entity_id=str(machine_id),
            source="ADMIN",
            metadata={
                "machineCode": machine.get("machineCode"),
                "durationMinutes": duration_minutes,
                "estimatedEnd": est_end.isoformat(),
                "reason": reason,
                "incidentId": incident_id
            }
        )

        await ws_manager.broadcast({
            "type": "MACHINE_MAINTENANCE_SCHEDULED",
            "data": {
                "machineId": str(machine_id),
                "machineCode": machine.get("machineCode"),
                "status": "MAINTENANCE",
                "durationMinutes": duration_minutes,
                "estimatedEnd": est_end.isoformat(),
                "reason": reason,
                "incidentId": incident_id
            }
        })

        return MachineService._format_machine(updated_machine)

    @staticmethod
    async def fail_machine(
        machine_id: str,
        reason: str = "Machine failure confirmed",
        actor_id: str = "ADMIN",
        incident_id: Optional[str] = None,
        incident_code: Optional[str] = None
    ) -> dict:
        """
        Authoritative single entrypoint for transitioning a machine to DOWN.
        Propagates failure to active operation (INTERRUPTED or auto-failover), releases operator,
        links incident, records execution/audit events, and broadcasts via WebSocket.
        """
        db = get_db()
        if not ObjectId.is_valid(machine_id):
            raise ValueError(f"Invalid machine ID format: '{machine_id}'")

        machine = await db.machines.find_one({"_id": ObjectId(machine_id)})
        if not machine:
            raise ValueError(f"Machine with ID '{machine_id}' not found")

        if machine.get("status") == MachineStatus.DOWN.value:
            raise ValueError(f"Machine '{machine.get('machineCode')}' is already in DOWN state")

        machine_code = machine.get("machineCode")
        machine_type = machine.get("type", "").upper()
        current_wo_id = machine.get("currentWorkOrderId")
        current_op_id = machine.get("currentOperationId")
        current_operator_id = machine.get("currentOperatorId")

        # 1. Acquire Redis execution lock
        await RedisService.acquire_lock("execution_engine_lock", ttl_seconds=10)

        try:
            # 2. If no incident_id was provided (e.g. direct admin simulation), create one
            if not incident_id:
                incident_count = await db.incidents.count_documents({})
                inc_code = f"INC-{str(incident_count + 1).zfill(4)}"
                incident_doc = {
                    "incidentCode": inc_code,
                    "type": "MACHINE_FAILURE",
                    "severity": "HIGH",
                    "status": "ACTION_REQUIRED",
                    "title": f"Machine {machine_code} Confirmed Failure",
                    "description": reason,
                    "machineId": str(machine["_id"]),
                    "machineCode": machine_code,
                    "machineType": machine_type,
                    "operatorId": current_operator_id,
                    "workOrderId": current_wo_id,
                    "operationId": current_op_id,
                    "reportedAt": datetime.utcnow(),
                    "detectedAt": datetime.utcnow(),
                    "reportedBy": actor_id,
                    "metadata": {"simulation": True if actor_id == "ADMIN" else False},
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow()
                }
                res = await db.incidents.insert_one(incident_doc)
                incident_id = str(res.inserted_id)
                incident_code = inc_code
            else:
                # Update existing incident to ACTION_REQUIRED
                await db.incidents.update_one(
                    {"_id": ObjectId(incident_id)},
                    {"$set": {
                        "status": "ACTION_REQUIRED",
                        "detectedAt": datetime.utcnow(),
                        "updatedAt": datetime.utcnow()
                    }}
                )

            # 3. Transition Machine to DOWN, retaining runtime references
            updated_machine = await db.machines.find_one_and_update(
                {"_id": ObjectId(machine_id)},
                {"$set": {
                    "status": MachineStatus.DOWN.value,
                    "currentIncidentId": incident_id,
                    "updatedAt": datetime.utcnow()
                }},
                return_document=True
            )

            # 4. Release assigned operator back to AVAILABLE
            if current_operator_id and ObjectId.is_valid(current_operator_id):
                await db.users.update_one(
                    {"_id": ObjectId(current_operator_id)},
                    {"$set": {"availabilityStatus": "AVAILABLE", "updatedAt": datetime.utcnow()}}
                )

            # 5. Check if an active operation was running on this machine
            failover_occurred = False
            backup_machine_id = None
            affected_wo_code = None

            if current_wo_id and ObjectId.is_valid(current_wo_id) and current_op_id:
                wo = await db.work_orders.find_one({"_id": ObjectId(current_wo_id)})
                if wo:
                    affected_wo_code = wo.get("workOrderCode")
                    
                    # Look up operation object in work order
                    op_obj = next((o for o in wo.get("operations", []) if o.get("operationId") == current_op_id), None)
                    target_machine_type = (op_obj.get("requiredMachineType") if op_obj else None) or machine_type
                    target_caps = (op_obj.get("requiredCapabilityIds") if op_obj else None)

                    # Search for compatible IDLE machine strictly matching required type / capabilities
                    compat_machines = await MachineService.find_compatible_machines(
                        required_machine_type=target_machine_type,
                        required_capability_ids=target_caps,
                        only_available=True
                    )
                    # Filter out the failed machine itself
                    avail_backups = [m for m in compat_machines if (m.get("id") or str(m.get("_id"))) != str(machine_id)]

                    if avail_backups:
                        # Auto-failover to available backup machine!
                        backup_m = avail_backups[0]
                        backup_machine_id = backup_m.get("id") or str(backup_m.get("_id"))
                        backup_m_code = backup_m.get("machineCode")

                        # Reassign operator to AVAILABLE so they can be seamlessly bound to the backup machine
                        if current_operator_id and ObjectId.is_valid(current_operator_id):
                            await db.users.update_one(
                                {"_id": ObjectId(current_operator_id)},
                                {"$set": {"availabilityStatus": "AVAILABLE", "updatedAt": datetime.utcnow()}}
                            )

                        # Update work order operation to use the backup machine seamlessly and status to READY
                        await db.work_orders.update_one(
                            {"_id": ObjectId(current_wo_id), "operations.operationId": current_op_id},
                            {"$set": {
                                "operations.$.assignedMachineId": backup_machine_id,
                                "operations.$.assignedMachineCode": backup_m_code,
                                "operations.$.status": "READY",
                                "operations.$.waitingReason": f"Auto-rerouted to backup machine {backup_m_code}",
                                "updatedAt": datetime.utcnow()
                            }}
                        )
                        failover_occurred = True

                        # Log failover execution event
                        await db.execution_events.insert_one({
                            "workOrderId": str(current_wo_id),
                            "workOrderCode": affected_wo_code,
                            "eventType": "FAILOVER_REROUTE",
                            "machineCode": backup_m_code,
                            "message": f"Operation {current_op_id} automatically rerouted from failed machine {machine_code} to backup {backup_m_code}",
                            "timestamp": datetime.utcnow(),
                            "details": {
                                "failedMachineId": str(machine_id),
                                "failedMachineCode": machine_code,
                                "backupMachineId": backup_machine_id,
                                "backupMachineCode": backup_m_code,
                                "operationId": current_op_id
                            }
                        })
                    else:
                        # No backup available -> Transition operation to INTERRUPTED
                        await db.work_orders.update_one(
                            {"_id": ObjectId(current_wo_id), "operations.operationId": current_op_id},
                            {"$set": {
                                "operations.$.status": "INTERRUPTED",
                                "operations.$.waitingReason": f"Machine {machine_code} breakdown ({reason})",
                                "updatedAt": datetime.utcnow()
                            }}
                        )

                        await db.execution_events.insert_one({
                            "workOrderId": str(current_wo_id),
                            "workOrderCode": affected_wo_code,
                            "eventType": "OPERATION_INTERRUPTED",
                            "machineCode": machine_code,
                            "message": f"Operation {current_op_id} interrupted due to failure on machine {machine_code}",
                            "timestamp": datetime.utcnow(),
                            "details": {
                                "machineId": str(machine_id),
                                "machineCode": machine_code,
                                "operationId": current_op_id,
                                "reason": reason
                            }
                        })

            # 6. Log authoritative audit event
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MACHINE_FAILED",
                entity_type="machine",
                entity_id=str(machine_id),
                source="ADMIN",
                metadata={
                    "machineCode": machine_code,
                    "reason": reason,
                    "incidentId": incident_id,
                    "incidentCode": incident_code,
                    "failoverOccurred": failover_occurred,
                    "backupMachineId": backup_machine_id,
                    "interruptedWorkOrder": affected_wo_code
                }
            )

            # 7. WebSocket broadcast
            await ws_manager.broadcast({
                "type": "MACHINE_FAILED",
                "data": {
                    "machineId": str(machine_id),
                    "machineCode": machine_code,
                    "status": "DOWN",
                    "reason": reason,
                    "incidentId": incident_id,
                    "incidentCode": incident_code,
                    "failoverOccurred": failover_occurred,
                    "backupMachineId": backup_machine_id
                }
            })

            # Immediately trigger ExecutionEngine to evaluate and dispatch failover operation
            try:
                from app.services.execution_engine import ExecutionEngine
                if current_wo_id:
                    asyncio.create_task(ExecutionEngine.evaluate_execution(str(current_wo_id)))
            except Exception as e:
                logger.error(f"Error evaluating execution after machine failure: {e}")

            return {
                "machine": MachineService._format_machine(updated_machine),
                "incidentId": incident_id,
                "incidentCode": incident_code,
                "failoverOccurred": failover_occurred,
                "backupMachineId": backup_machine_id
            }

        finally:
            await RedisService.release_lock("execution_engine_lock")

    @staticmethod
    async def recover_machine(machine_id: str, actor_id: str = "ADMIN") -> dict:
        """
        Recover a machine from DOWN / MAINTENANCE -> IDLE state.
        Safely updates lastMaintenanceAt, clears currentIncidentId, clears maintenance pointers,
        and auto-resolves all open incidents on this machine.
        """
        db = get_db()
        if not ObjectId.is_valid(machine_id):
            raise ValueError(f"Invalid machine ID format: '{machine_id}'")

        machine = await db.machines.find_one({"_id": ObjectId(machine_id)})
        if not machine:
            raise ValueError(f"Machine with ID '{machine_id}' not found")

        now = datetime.utcnow()
        was_maintenance = (machine.get("status") == MachineStatus.MAINTENANCE.value or bool(machine.get("maintenanceEstimatedEnd")))

        update_set: Dict[str, Any] = {
            "status": MachineStatus.IDLE.value,
            "currentIncidentId": None,
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentOperatorId": None,
            "maintenanceEstimatedEnd": None,
            "maintenanceDurationMinutes": None,
            "maintenanceReason": None,
            "updatedAt": now
        }

        if was_maintenance:
            update_set["lastMaintenanceAt"] = now
            update_set["lastMaintenanceDurationMinutes"] = machine.get("maintenanceDurationMinutes") or 45

        updated_machine = await db.machines.find_one_and_update(
            {"_id": ObjectId(machine_id)},
            {"$set": update_set},
            return_document=True
        )

        # Auto-resolve all open incidents for this machine (including currentIncidentId)
        mach_code = machine.get("machineCode")
        inc_filter = {
            "$or": [
                {"machineId": str(machine_id)},
                {"machineCode": mach_code}
            ],
            "status": {"$in": ["OPEN", "ACTION_REQUIRED", "PENDING_REVIEW", "INVESTIGATING"]}
        }
        if machine.get("currentIncidentId"):
            inc_filter["$or"].append({"_id": ObjectId(machine["currentIncidentId"])})

        async for open_inc in db.incidents.find(inc_filter):
            inc_oid = open_inc["_id"]
            await db.incidents.update_one(
                {"_id": inc_oid},
                {"$set": {
                    "status": "RESOLVED",
                    "resolvedAt": now,
                    "resolvedBy": actor_id,
                    "resolution": f"Equipment overhauled and recovered to IDLE via maintenance signoff by {actor_id}."
                }}
            )
            await ws_manager.broadcast({
                "type": "INCIDENT_RESOLVED",
                "data": {
                    "id": str(inc_oid),
                    "status": "RESOLVED",
                    "resolution": "Equipment overhauled and recovered to IDLE."
                }
            })

        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="MACHINE_RECOVERED",
            entity_type="machine",
            entity_id=str(machine_id),
            source="ADMIN",
            metadata={"machineCode": machine.get("machineCode"), "previousStatus": machine.get("status")}
        )

        await ws_manager.broadcast({
            "type": "MACHINE_RECOVERED",
            "data": {
                "machineId": str(machine_id),
                "machineCode": machine.get("machineCode"),
                "status": "IDLE"
            }
        })

        # Immediately trigger ExecutionEngine to evaluate waiting/interrupted work orders
        try:
            from app.services.execution_engine import ExecutionEngine
            async for wo in db.work_orders.find({"status": "IN_PROGRESS"}):
                asyncio.create_task(ExecutionEngine.evaluate_execution(str(wo["_id"])))
        except Exception as e:
            logger.error(f"Error evaluating work orders after machine recovery: {e}")

        return MachineService._format_machine(updated_machine)
