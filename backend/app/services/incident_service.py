from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.schemas.incident import (
    IncidentType, IncidentSeverity, IncidentStatus,
    IncidentResponse, IncidentContextResponse
)
from app.schemas.machine import MachineStatus
from app.services.audit_service import AuditService
from app.services.machine_service import MachineService
from app.core.websocket import ws_manager

class IncidentService:
    @staticmethod
    def _format_incident(doc: Optional[dict]) -> Optional[dict]:
        if not doc:
            return None
        d = dict(doc)
        if "_id" in d:
            d["id"] = str(d["_id"])
            d["_id"] = str(d["_id"])
        for key in ["machineId", "operatorId", "workOrderId", "executionId", "operationId"]:
            if key in d and isinstance(d[key], ObjectId):
                d[key] = str(d[key])
        return d

    @staticmethod
    async def create_operator_alert(
        operator_id: str,
        message: str,
        machine_id: Optional[str] = None
    ) -> dict:
        """
        Create a pending incident from an operator report.
        DOES NOT fail the machine or alter production state.
        Automatically derives runtime context (machine, work order, operation) if not explicitly provided.
        """
        db = get_db()
        
        # 1. Validate operator
        oper_query = {}
        if ObjectId.is_valid(operator_id):
            oper_query = {"$or": [{"_id": ObjectId(operator_id)}, {"employeeId": operator_id}]}
        else:
            oper_query = {"employeeId": operator_id}
            
        operator = await db.users.find_one(oper_query)
        if not operator:
            raise ValueError(f"Operator '{operator_id}' not found in registered users")

        oper_obj_id = str(operator["_id"])
        oper_name = operator.get("name", "Unknown Operator")
        oper_emp_id = operator.get("employeeId", operator_id)

        # 2. Derive runtime context if machine_id is not specified
        derived_machine_id = None
        derived_machine_code = None
        derived_wo_id = None
        derived_wo_code = None
        derived_op_id = None
        derived_exec_id = None

        if machine_id:
            mach_query = {}
            if ObjectId.is_valid(machine_id):
                mach_query = {"$or": [{"_id": ObjectId(machine_id)}, {"machineCode": machine_id}]}
            else:
                mach_query = {"machineCode": machine_id}
            mach = await db.machines.find_one(mach_query)
            if mach:
                derived_machine_id = str(mach["_id"])
                derived_machine_code = mach.get("machineCode")
                derived_wo_id = mach.get("currentWorkOrderId")
                derived_op_id = mach.get("currentOperationId")
        else:
            # Check if operator is currently locked to a machine
            active_mach = await db.machines.find_one({"currentOperatorId": oper_obj_id})
            if active_mach:
                derived_machine_id = str(active_mach["_id"])
                derived_machine_code = active_mach.get("machineCode")
                derived_wo_id = active_mach.get("currentWorkOrderId")
                derived_op_id = active_mach.get("currentOperationId")

        # If we have a work order, fetch its code
        if derived_wo_id and ObjectId.is_valid(derived_wo_id):
            wo = await db.work_orders.find_one({"_id": ObjectId(derived_wo_id)})
            if wo:
                derived_wo_code = wo.get("workOrderCode")

        # 3. Generate sequential incident code
        count = await db.incidents.count_documents({})
        inc_code = f"INC-{str(count + 1).padStart(4, '0')}" if hasattr(str, 'padStart') else f"INC-{str(count + 1).zfill(4)}"

        now = datetime.utcnow()
        title = f"Operator Report on {derived_machine_code or 'Equipment'}: {message[:40]}"

        # 4. Insert incident in PENDING_REVIEW state (Machine state NOT modified yet)
        incident_doc = {
            "incidentCode": inc_code,
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.HIGH.value,
            "status": IncidentStatus.PENDING_REVIEW.value,
            "title": title,
            "description": message,
            "machineId": derived_machine_id,
            "machineCode": derived_machine_code,
            "operatorId": oper_obj_id,
            "operatorName": oper_name,
            "workOrderId": derived_wo_id,
            "workOrderCode": derived_wo_code,
            "executionId": derived_exec_id,
            "operationId": derived_op_id,
            "reportedAt": now,
            "detectedAt": None,
            "resolvedAt": None,
            "reportedBy": oper_emp_id,
            "resolvedBy": None,
            "resolution": None,
            "dismissalReason": None,
            "metadata": {"reportedVia": "OPERATOR_ALERT_API"},
            "createdAt": now,
            "updatedAt": now
        }

        result = await db.incidents.insert_one(incident_doc)
        incident_doc["_id"] = result.inserted_id
        incident_doc["id"] = str(result.inserted_id)

        # 5. Log audit event
        await AuditService.log_event(
            actor_id=oper_emp_id,
            actor_type="USER",
            action="OPERATOR_ALERT_SUBMITTED",
            entity_type="incident",
            entity_id=str(result.inserted_id),
            source="OPERATOR",
            metadata={
                "incidentCode": inc_code,
                "machineCode": derived_machine_code,
                "workOrderCode": derived_wo_code,
                "operationId": derived_op_id,
                "message": message
            }
        )

        # 6. Broadcast WebSocket alert
        await ws_manager.broadcast({
            "type": "INCIDENT_CREATED",
            "data": {
                "id": str(result.inserted_id),
                "incidentCode": inc_code,
                "status": IncidentStatus.PENDING_REVIEW.value,
                "machineCode": derived_machine_code,
                "workOrderCode": derived_wo_code,
                "operatorName": oper_name,
                "message": message
            }
        })

        return IncidentService._format_incident(incident_doc)

    @staticmethod
    async def confirm_failure(incident_id: str, admin_id: str = "ADMIN") -> dict:
        """
        Admin review action: Confirms the operator report and triggers the authoritative
        MachineService.fail_machine transition.
        """
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            raise ValueError(f"Invalid incident ID format: '{incident_id}'")

        incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if incident.get("status") not in [IncidentStatus.PENDING_REVIEW.value, IncidentStatus.OPEN.value]:
            raise ValueError(f"Incident '{incident.get('incidentCode')}' is already in {incident.get('status')} state")

        machine_id = incident.get("machineId")
        if not machine_id:
            raise ValueError("Incident does not have an associated machine to fail")

        # Call authoritative machine failure service
        fail_res = await MachineService.fail_machine(
            machine_id=machine_id,
            reason=incident.get("description", "Admin confirmed failure"),
            actor_id=admin_id,
            incident_id=str(incident["_id"]),
            incident_code=incident.get("incidentCode")
        )

        now = datetime.utcnow()
        updated_incident = await db.incidents.find_one_and_update(
            {"_id": ObjectId(incident_id)},
            {"$set": {
                "status": IncidentStatus.ACTION_REQUIRED.value,
                "detectedAt": now,
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="ADMIN",
            action="INCIDENT_REVIEWED",
            entity_type="incident",
            entity_id=str(incident_id),
            source="ADMIN",
            metadata={
                "incidentCode": incident.get("incidentCode"),
                "decision": "CONFIRMED",
                "machineId": machine_id
            }
        )

        return {
            "incident": IncidentService._format_incident(updated_incident),
            "machine": fail_res.get("machine")
        }

    @staticmethod
    async def dismiss_incident(incident_id: str, reason: str = "Dismissed by admin", admin_id: str = "ADMIN") -> dict:
        """
        Admin review action: Dismisses a pending operator report as a false alarm.
        Leaves machine and production state completely unchanged.
        """
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            raise ValueError(f"Invalid incident ID format: '{incident_id}'")

        incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if incident.get("status") not in [IncidentStatus.PENDING_REVIEW.value, IncidentStatus.OPEN.value]:
            raise ValueError(f"Cannot dismiss incident in status '{incident.get('status')}'")

        now = datetime.utcnow()
        updated_incident = await db.incidents.find_one_and_update(
            {"_id": ObjectId(incident_id)},
            {"$set": {
                "status": IncidentStatus.DISMISSED.value,
                "dismissalReason": reason,
                "resolvedBy": admin_id,
                "resolvedAt": now,
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="ADMIN",
            action="INCIDENT_DISMISSED",
            entity_type="incident",
            entity_id=str(incident_id),
            source="ADMIN",
            metadata={"incidentCode": incident.get("incidentCode"), "reason": reason}
        )

        await ws_manager.broadcast({
            "type": "INCIDENT_DISMISSED",
            "data": {
                "id": str(incident_id),
                "incidentCode": incident.get("incidentCode"),
                "status": IncidentStatus.DISMISSED.value,
                "reason": reason
            }
        })

        return IncidentService._format_incident(updated_incident)

    @staticmethod
    async def resolve_incident(
        incident_id: str,
        resolution: str,
        admin_id: str = "ADMIN"
    ) -> dict:
        """
        Admin action: Resolves a confirmed incident and recovers the associated machine to IDLE.
        """
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            raise ValueError(f"Invalid incident ID format: '{incident_id}'")

        incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if incident.get("status") == IncidentStatus.RESOLVED.value:
            raise ValueError(f"Incident '{incident.get('incidentCode')}' is already resolved")

        # Recover machine if associated and DOWN
        machine_id = incident.get("machineId")
        if machine_id and ObjectId.is_valid(machine_id):
            mach = await db.machines.find_one({"_id": ObjectId(machine_id)})
            if mach and mach.get("status") == MachineStatus.DOWN.value:
                await MachineService.recover_machine(machine_id=machine_id, actor_id=admin_id)

        now = datetime.utcnow()
        updated_incident = await db.incidents.find_one_and_update(
            {"_id": ObjectId(incident_id)},
            {"$set": {
                "status": IncidentStatus.RESOLVED.value,
                "resolution": resolution,
                "resolvedBy": admin_id,
                "resolvedAt": now,
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="ADMIN",
            action="INCIDENT_RESOLVED",
            entity_type="incident",
            entity_id=str(incident_id),
            source="ADMIN",
            metadata={
                "incidentCode": incident.get("incidentCode"),
                "resolution": resolution,
                "machineId": machine_id
            }
        )

        await ws_manager.broadcast({
            "type": "INCIDENT_RESOLVED",
            "data": {
                "id": str(incident_id),
                "incidentCode": incident.get("incidentCode"),
                "status": IncidentStatus.RESOLVED.value,
                "resolution": resolution,
                "machineId": machine_id
            }
        })

        return IncidentService._format_incident(updated_incident)

    @staticmethod
    async def schedule_incident_maintenance(
        incident_id: str,
        duration_minutes: int,
        resolution: str = "Put in maintenance for scheduled repair",
        admin_id: str = "ADMIN"
    ) -> dict:
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            raise ValueError(f"Invalid incident ID format: '{incident_id}'")

        incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        now = datetime.utcnow()
        est_end = now + timedelta(minutes=duration_minutes)

        machine_id = incident.get("machineId")
        if machine_id and ObjectId.is_valid(machine_id):
            await MachineService.schedule_maintenance(
                machine_id=machine_id,
                duration_minutes=duration_minutes,
                reason=resolution,
                actor_id=admin_id,
                incident_id=incident_id
            )

        updated_incident = await db.incidents.find_one_and_update(
            {"_id": ObjectId(incident_id)},
            {"$set": {
                "status": IncidentStatus.ACTION_REQUIRED.value,
                "resolution": resolution,
                "resolvedBy": admin_id,
                "maintenanceEstimatedEnd": est_end,
                "maintenanceDurationMinutes": duration_minutes,
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="ADMIN",
            action="INCIDENT_MAINTENANCE_SCHEDULED",
            entity_type="incident",
            entity_id=str(incident_id),
            source="ADMIN",
            metadata={
                "incidentCode": incident.get("incidentCode"),
                "resolution": resolution,
                "durationMinutes": duration_minutes,
                "estimatedEnd": est_end.isoformat(),
                "machineId": machine_id
            }
        )

        await ws_manager.broadcast({
            "type": "INCIDENT_MAINTENANCE_SCHEDULED",
            "data": {
                "id": str(incident_id),
                "incidentCode": incident.get("incidentCode"),
                "status": IncidentStatus.ACTION_REQUIRED.value,
                "resolution": resolution,
                "durationMinutes": duration_minutes,
                "estimatedEnd": est_end.isoformat(),
                "machineId": machine_id
            }
        })

        return IncidentService._format_incident(updated_incident)

    @staticmethod
    async def list_incidents(
        status: Optional[str] = None,
        severity: Optional[str] = None,
        machine_id: Optional[str] = None,
        incident_type: Optional[str] = None
    ) -> List[dict]:
        db = get_db()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        if machine_id:
            query["machineId"] = machine_id
        if incident_type:
            query["type"] = incident_type

        incidents = []
        async for doc in db.incidents.find(query).sort("createdAt", -1):
            doc = IncidentService._format_incident(doc)
            m_id = doc.get("machineId")
            if m_id and ObjectId.is_valid(m_id):
                mach = await db.machines.find_one({"_id": ObjectId(m_id)})
                if mach:
                    doc["machineType"] = mach.get("type")
                
                # Discover any work orders running or queued for this machine
                wos = []
                async for wo_item in db.work_orders.find({
                    "operations.assignedMachineId": str(m_id),
                    "status": {"$in": ["IN_PROGRESS", "PLANNED"]}
                }):
                    status_lbl = "Running" if wo_item.get("status") == "IN_PROGRESS" else "Queued"
                    wos.append(f"{wo_item.get('workOrderCode')} ({status_lbl})")
                doc["queuedWorkOrders"] = wos
            incidents.append(doc)
        return incidents

    @staticmethod
    async def get_incident_by_id(incident_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            return None
        doc = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if doc:
            doc = IncidentService._format_incident(doc)
            m_id = doc.get("machineId")
            if m_id and ObjectId.is_valid(m_id):
                mach = await db.machines.find_one({"_id": ObjectId(m_id)})
                if mach:
                    doc["machineType"] = mach.get("type")
                wos = []
                async for wo_item in db.work_orders.find({
                    "operations.assignedMachineId": str(m_id),
                    "status": {"$in": ["IN_PROGRESS", "PLANNED"]}
                }):
                    status_lbl = "Running" if wo_item.get("status") == "IN_PROGRESS" else "Queued"
                    wos.append(f"{wo_item.get('workOrderCode')} ({status_lbl})")
                doc["queuedWorkOrders"] = wos
        return doc

    @staticmethod
    async def get_incident_context(incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Builds a deep structured context representation for investigation and future AI inspection.
        """
        db = get_db()
        incident = await IncidentService.get_incident_by_id(incident_id)
        if not incident:
            return None

        machine = None
        if incident.get("machineId") and ObjectId.is_valid(incident["machineId"]):
            machine = await db.machines.find_one({"_id": ObjectId(incident["machineId"])})
            if machine:
                machine["id"] = str(machine["_id"])
                del machine["_id"]
                incident["machineType"] = machine.get("type")

        work_order = None
        operation = None
        downstream_ops = []
        supervisor = None

        if incident.get("workOrderId") and ObjectId.is_valid(incident["workOrderId"]):
            work_order = await db.work_orders.find_one({"_id": ObjectId(incident["workOrderId"])})
            if work_order:
                work_order["id"] = str(work_order["_id"])
                del work_order["_id"]
                
                # Extract affected operation
                op_id = incident.get("operationId")
                for op in work_order.get("operations", []):
                    if op.get("operationId") == op_id:
                        operation = op
                    elif op_id in op.get("dependencies", []):
                        downstream_ops.append(op)

                # Extract supervisor
                sup_id = work_order.get("supervisorId")
                if sup_id and ObjectId.is_valid(sup_id):
                    supervisor = await db.users.find_one({"_id": ObjectId(sup_id)})
                    if supervisor:
                        supervisor["id"] = str(supervisor["_id"])
                        del supervisor["_id"]

        # Operators
        reporting_operator = None
        if incident.get("operatorId") and ObjectId.is_valid(incident["operatorId"]):
            reporting_operator = await db.users.find_one({"_id": ObjectId(incident["operatorId"])})
            if reporting_operator:
                reporting_operator["id"] = str(reporting_operator["_id"])
                del reporting_operator["_id"]

        assigned_operator = reporting_operator
        if operation and operation.get("assignedOperatorId") and ObjectId.is_valid(operation["assignedOperatorId"]):
            if str(operation["assignedOperatorId"]) != incident.get("operatorId"):
                assigned_operator = await db.users.find_one({"_id": ObjectId(operation["assignedOperatorId"])})
                if assigned_operator:
                    assigned_operator["id"] = str(assigned_operator["_id"])
                    del assigned_operator["_id"]

        # Recent execution events
        recent_exec_events = []
        if incident.get("workOrderId"):
            async for ev in db.execution_events.find({"workOrderId": incident["workOrderId"]}).sort("timestamp", -1).limit(10):
                ev["id"] = str(ev["_id"])
                del ev["_id"]
                recent_exec_events.append(ev)

        # Recent audit events
        recent_audit_events = []
        async for a_ev in db.audit_events.find({
            "$or": [
                {"entityId": incident_id},
                {"metadata.incidentId": incident_id},
                {"entityId": incident.get("machineId")}
            ]
        }).sort("timestamp", -1).limit(10):
            a_ev["id"] = str(a_ev["_id"])
            del a_ev["_id"]
            recent_audit_events.append(a_ev)

        return {
            "incident": incident,
            "machine": machine,
            "workOrder": work_order,
            "operation": operation,
            "reportingOperator": reporting_operator,
            "assignedOperator": assigned_operator,
            "supervisor": supervisor,
            "downstreamOperations": downstream_ops,
            "recentExecutionEvents": recent_exec_events,
            "recentAuditEvents": recent_audit_events
        }

    @staticmethod
    async def get_operator_reports(operator_id: str) -> List[dict]:
        """
        Fetch all incidents reported by a specific operator (by user id or employeeId).
        """
        db = get_db()
        oper_query = {}
        if ObjectId.is_valid(operator_id):
            oper_query = {"$or": [{"_id": ObjectId(operator_id)}, {"employeeId": operator_id}]}
        else:
            oper_query = {"employeeId": operator_id}
            
        operator = await db.users.find_one(oper_query)
        if not operator:
            return []

        op_id_str = str(operator["_id"])
        op_emp_id = operator.get("employeeId")

        incidents = []
        async for doc in db.incidents.find({
            "$or": [
                {"operatorId": op_id_str},
                {"operatorId": op_emp_id},
                {"operatorEmployeeId": op_emp_id}
            ]
        }).sort("createdAt", -1):
            incidents.append(IncidentService._format_incident(doc))
        return incidents
