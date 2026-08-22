from datetime import datetime
from bson import ObjectId
from typing import Dict, Any, Optional, List
from app.core.database import get_db
from app.services.incident_service import IncidentService
from app.services.machine_service import MachineService
from app.services.work_order_service import WorkOrderService
from app.services.execution_engine import ExecutionEngine

class AIContextBuilder:
    @staticmethod
    async def build_incident_context(incident_id: str) -> Dict[str, Any]:
        """
        Assemble a comprehensive, read-only structured snapshot of the incident and all related MES state.
        This provides Gemini with complete operational visibility without unrestricted database access.
        """
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            raise ValueError(f"Invalid incident ID format: '{incident_id}'")

        incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        incident_id_str = str(incident["_id"])
        machine_id = incident.get("machineId")
        work_order_id = incident.get("workOrderId")
        operator_id = incident.get("operatorId")
        operation_id = incident.get("operationId")

        # 1. Machine Details
        machine_data = None
        mach_type = "UNKNOWN"
        if machine_id:
            mach = None
            if ObjectId.is_valid(machine_id):
                mach = await db.machines.find_one({"_id": ObjectId(machine_id)})
            if not mach:
                mach = await db.machines.find_one({"machineCode": str(machine_id)})
            if mach:
                mach_type = mach.get("type", "UNKNOWN")
                machine_data = {
                    "id": str(mach["_id"]),
                    "machineCode": mach.get("machineCode"),
                    "name": mach.get("name"),
                    "type": mach.get("type"),
                    "supportedTypes": mach.get("supportedTypes", []),
                    "status": mach.get("status"),
                    "processingRate": mach.get("processingRate"),
                    "rateUnit": mach.get("rateUnit"),
                    "location": mach.get("location"),
                    "currentWorkOrderId": mach.get("currentWorkOrderId"),
                    "currentOperationId": mach.get("currentOperationId"),
                    "currentIncidentId": mach.get("currentIncidentId")
                }

        # 2. Operator Details
        operator_data = None
        if operator_id:
            oper = None
            if ObjectId.is_valid(operator_id):
                oper = await db.users.find_one({"_id": ObjectId(operator_id)})
            if not oper:
                oper = await db.users.find_one({"employeeId": str(operator_id)})
            if oper:
                operator_data = {
                    "id": str(oper["_id"]),
                    "employeeId": oper.get("employeeId"),
                    "name": oper.get("name"),
                    "role": oper.get("role"),
                    "department": oper.get("department"),
                    "availabilityStatus": oper.get("availabilityStatus"),
                    "currentWorkOrderId": oper.get("currentWorkOrderId"),
                    "currentOperationId": oper.get("currentOperationId")
                }

        # 3. Work Order & Execution Details
        work_order_data = None
        current_operation_data = None
        workflow_data = None
        wo = None
        if work_order_id:
            if ObjectId.is_valid(work_order_id):
                wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
            if not wo:
                wo = await db.work_orders.find_one({"workOrderCode": str(work_order_id)})
        
        if not wo and machine_id:
            # Fallback search for active or planned work orders targeting this machine
            wo = await db.work_orders.find_one({
                "status": {"$in": ["IN_PROGRESS", "SCHEDULED", "PLANNED"]},
                "operations.assignedMachineId": str(machine_id)
            })

        if wo:
            work_order_data = {
                "id": str(wo["_id"]),
                "workOrderCode": wo.get("workOrderCode"),
                "productId": wo.get("productId"),
                "workflowId": wo.get("workflowId"),
                "quantity": wo.get("quantity"),
                "priority": wo.get("priority"),
                "status": wo.get("status"),
                "dueDate": wo.get("dueDate").isoformat() if isinstance(wo.get("dueDate"), datetime) else str(wo.get("dueDate")),
                "startedAt": wo.get("startedAt").isoformat() if isinstance(wo.get("startedAt"), datetime) else None,
                "operations": []
            }

            for op in wo.get("operations", []):
                op_info = {
                    "operationId": op.get("operationId"),
                    "name": op.get("name"),
                    "sequence": op.get("sequence"),
                    "status": op.get("status"),
                    "assignedMachineId": op.get("assignedMachineId"),
                    "assignedOperatorId": op.get("assignedOperatorId"),
                    "dependencies": op.get("dependencies", []),
                    "startedAt": op.get("startedAt").isoformat() if isinstance(op.get("startedAt"), datetime) else None,
                    "durationSeconds": op.get("durationSeconds")
                }
                work_order_data["operations"].append(op_info)
                if op.get("operationId") == operation_id or (not current_operation_data and op.get("status") == "IN_PROGRESS"):
                    current_operation_data = op_info

            # Workflow DAG details
            if wo.get("workflowId") and ObjectId.is_valid(wo.get("workflowId")):
                wf = await db.workflows.find_one({"_id": ObjectId(wo["workflowId"])})
                if wf:
                    workflow_data = {
                        "id": str(wf["_id"]),
                        "workflowCode": wf.get("workflowCode"),
                        "name": wf.get("name"),
                        "version": wf.get("version"),
                        "status": wf.get("status")
                    }

        # 4. Recent Execution Events (Last 10)
        recent_events = []
        event_query = {}
        if work_order_id and ObjectId.is_valid(work_order_id):
            event_query["$or"] = [{"workOrderId": str(work_order_id)}, {"machineId": str(machine_id)}]
        elif machine_id:
            event_query["machineId"] = str(machine_id)

        if event_query:
            async for ev in db.execution_events.find(event_query).sort("timestamp", -1).limit(10):
                recent_events.append({
                    "eventType": ev.get("eventType"),
                    "message": ev.get("message"),
                    "operationId": ev.get("operationId"),
                    "machineCode": ev.get("machineCode"),
                    "timestamp": ev.get("timestamp").isoformat() if isinstance(ev.get("timestamp"), datetime) else str(ev.get("timestamp"))
                })

        # 5. Compatible Alternative Machines Available on Shop Floor
        compatible_alternatives = []
        async for m in db.machines.find({
            "status": "IDLE",
            "availability": True,
            "_id": {"$ne": ObjectId(machine_id)} if machine_id and ObjectId.is_valid(machine_id) else {"$exists": True}
        }):
            m_type = m.get("type", "").upper()
            m_supp = [t.upper() for t in m.get("supportedTypes", [])]
            if m_type == mach_type or (m_type == "MULTI_PURPOSE" and mach_type in m_supp) or mach_type == "UNKNOWN":
                compatible_alternatives.append({
                    "id": str(m["_id"]),
                    "machineCode": m.get("machineCode"),
                    "name": m.get("name"),
                    "type": m.get("type"),
                    "supportedTypes": m.get("supportedTypes", []),
                    "processingRate": m.get("processingRate", 1.0),
                    "location": m.get("location")
                })

        # 6. Available Certified Operators
        available_operators = []
        async for u in db.users.find({
            "role": "OPERATOR",
            "status": "ACTIVE",
            "availabilityStatus": "AVAILABLE"
        }):
            available_operators.append({
                "id": str(u["_id"]),
                "employeeId": u.get("employeeId"),
                "name": u.get("name"),
                "department": u.get("department")
            })

        # Final Context Assembly
        return {
            "incident": {
                "id": incident_id_str,
                "incidentCode": incident.get("incidentCode"),
                "type": incident.get("type"),
                "severity": incident.get("severity"),
                "status": incident.get("status"),
                "title": incident.get("title"),
                "description": incident.get("description"),
                "reportedAt": incident.get("reportedAt").isoformat() if isinstance(incident.get("reportedAt"), datetime) else str(incident.get("reportedAt")),
                "reportedBy": incident.get("reportedBy"),
                "machineCode": incident.get("machineCode"),
                "workOrderCode": incident.get("workOrderCode"),
                "operationId": incident.get("operationId")
            },
            "machine": machine_data,
            "currentOperation": current_operation_data,
            "workOrder": work_order_data,
            "workflow": workflow_data,
            "operator": operator_data,
            "recentExecutionEvents": recent_events,
            "availableAlternativeMachines": compatible_alternatives,
            "availableOperators": available_operators,
            "timestamp": datetime.utcnow().isoformat()
        }
