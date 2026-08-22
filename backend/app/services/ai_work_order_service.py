import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.core.database import get_db
from app.ai.work_order_context import WorkOrderContextBuilder
from app.ai.work_order_planner import AIWorkOrderPlanner
from app.schemas.ai_work_order import (
    AIWorkOrderSessionStatus, AIWorkOrderResponseEnvelope,
    AIWorkOrderDraft, AIWorkOrderSession
)
from app.schemas.work_order import WorkOrderCreate, WorkOrderPriority
from app.services.work_order_service import WorkOrderService

logger = logging.getLogger(__name__)

class AIWorkOrderService:
    @staticmethod
    async def create_session(user_id: str = "ADMIN") -> Dict[str, Any]:
        """Initializes a new conversational AI Work Order planning session."""
        db = get_db()
        session_id = f"ai-wosess-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()

        session_doc = {
            "sessionId": session_id,
            "userId": user_id,
            "status": AIWorkOrderSessionStatus.COLLECTING_REQUIREMENTS.value,
            "conversationHistory": [
                {
                    "sender": "AI",
                    "content": "Hello! I am your AI Manufacturing Planning Assistant. What product would you like to manufacture, and how many units?",
                    "timestamp": now
                }
            ],
            "collectedFields": {},
            "missingRequiredFields": ["productId", "workflowId", "quantity", "supervisorId"],
            "suggestedOptionalFields": {},
            "draft": None,
            "createdAt": now,
            "updatedAt": now
        }

        await db.ai_work_order_sessions.insert_one(session_doc)
        return {
            "sessionId": session_id,
            "status": session_doc["status"],
            "message": session_doc["conversationHistory"][0]["content"],
            "missingFields": session_doc["missingRequiredFields"],
            "conversationHistory": session_doc["conversationHistory"]
        }

    @staticmethod
    async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves active session state."""
        db = get_db()
        doc = await db.ai_work_order_sessions.find_one({"sessionId": session_id})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return doc

    @staticmethod
    async def process_user_message(session_id: str, message: str) -> AIWorkOrderResponseEnvelope:
        """Processes user natural language input, updates session history and returns AI response envelope."""
        db = get_db()
        session = await db.ai_work_order_sessions.find_one({"sessionId": session_id})
        if not session:
            raise ValueError(f"AI Work Order session '{session_id}' not found.")

        now = datetime.utcnow()
        history = session.get("conversationHistory", [])
        history.append({
            "sender": "USER",
            "content": message,
            "timestamp": now
        })

        # Build sanitized MES planning context
        context = await WorkOrderContextBuilder.build_planning_context()
        planner = AIWorkOrderPlanner()

        collected = session.get("collectedFields", {})
        suggested = session.get("suggestedOptionalFields", {})

        # Plan response
        envelope = await planner.plan_step(
            conversation_history=history,
            context=context,
            collected_fields=collected,
            suggested_fields=suggested,
            session_id=session_id
        )

        history.append({
            "sender": "AI",
            "content": envelope.message,
            "timestamp": datetime.utcnow(),
            "data": envelope.model_dump()
        })

        new_status = AIWorkOrderSessionStatus.READY.value if envelope.status == "READY" else AIWorkOrderSessionStatus.COLLECTING_REQUIREMENTS.value

        await db.ai_work_order_sessions.update_one(
            {"sessionId": session_id},
            {
                "$set": {
                    "conversationHistory": history,
                    "collectedFields": envelope.collectedFields,
                    "suggestedOptionalFields": envelope.suggestions,
                    "missingRequiredFields": envelope.missingFields,
                    "status": new_status,
                    "draft": envelope.draft.model_dump() if envelope.draft else None,
                    "updatedAt": datetime.utcnow()
                }
            }
        )

        return envelope

    @staticmethod
    async def validate_draft(draft_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authoritative validation adapter. Verifies that all entities in the AI/User draft
        actually exist and are active in MongoDB before allowing creation.
        """
        db = get_db()

        # 1. Product validation
        prod_id = draft_dict.get("productId")
        if not prod_id or not ObjectId.is_valid(prod_id):
            raise ValueError(f"Invalid or missing Product ID: '{prod_id}'")
        product = await db.products.find_one({"_id": ObjectId(prod_id)})
        if not product:
            raise ValueError(f"Product with ID '{prod_id}' does not exist in MES catalog.")
        if product.get("active") is False:
            raise ValueError(f"Product '{product.get('productCode')}' is currently inactive.")

        # 2. Workflow validation
        wf_id = draft_dict.get("workflowId")
        if not wf_id or not ObjectId.is_valid(wf_id):
            raise ValueError(f"Invalid or missing Workflow ID: '{wf_id}'")
        workflow = await db.workflows.find_one({"_id": ObjectId(wf_id)})
        if not workflow:
            raise ValueError(f"Workflow with ID '{wf_id}' does not exist.")
        if str(workflow.get("productId")) != prod_id:
            raise ValueError(f"Workflow '{workflow.get('workflowCode')}' belongs to product '{workflow.get('productId')}', not selected product '{prod_id}'.")

        # 3. Quantity validation
        qty = draft_dict.get("quantity")
        if qty is None or float(qty) <= 0:
            raise ValueError("Work order quantity must be greater than 0.")
        qty = float(qty)

        # 4. Supervisor validation
        sup_id = draft_dict.get("supervisorId")
        if sup_id:
            if not ObjectId.is_valid(sup_id):
                raise ValueError(f"Invalid Supervisor ID: '{sup_id}'")
            supervisor = await db.users.find_one({"_id": ObjectId(sup_id)})
            if not supervisor:
                raise ValueError(f"Supervisor with ID '{sup_id}' does not exist.")
            if "SUPERVISOR" not in supervisor.get("role", "").upper():
                raise ValueError(f"Assigned user '{supervisor.get('name')}' does not have the SUPERVISOR role.")

        # 5. Due Date validation
        due_date = draft_dict.get("dueDate")
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            except ValueError:
                due_date = datetime.utcnow() + timedelta(days=7)
        elif not isinstance(due_date, datetime):
            due_date = datetime.utcnow() + timedelta(days=7)

        # 6. Operations validation
        ops = draft_dict.get("operations") or []
        for op in ops:
            m_id = op.get("assignedMachineId")
            if m_id and ObjectId.is_valid(m_id):
                mach = await db.machines.find_one({"_id": ObjectId(m_id)})
                if not mach:
                    logger.warning(f"Assigned machine '{m_id}' not found in database.")

        return {
            "valid": True,
            "product": {
                "id": prod_id,
                "code": product.get("productCode"),
                "name": product.get("name")
            },
            "workflow": {
                "id": wf_id,
                "code": workflow.get("workflowCode"),
                "version": workflow.get("version", 1)
            },
            "quantity": qty,
            "dueDate": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date)
        }

    @staticmethod
    async def create_work_order_from_draft(draft_dict: Dict[str, Any], actor_id: str = "SYSTEM") -> Dict[str, Any]:
        """
        Converts a validated AIWorkOrderDraft into the EXISTING WorkOrderService.create_work_order.
        Authoritative creation guarantees 100% compliance with business rules, reservations, and DAG routing.
        """
        # Validate draft first
        await AIWorkOrderService.validate_draft(draft_dict)

        prod_id = draft_dict.get("productId")
        wf_id = draft_dict.get("workflowId")
        qty = float(draft_dict.get("quantity"))

        # Generate unique code if not given
        wo_code = draft_dict.get("workOrderCode")
        if not wo_code:
            prod_code = draft_dict.get("productCode", "WO")
            wo_code = f"WO-{prod_code}-{uuid.uuid4().hex[:6].upper()}"

        wo_name = draft_dict.get("name") or f"{wo_code} Batch"
        priority_val = WorkOrderPriority(draft_dict.get("priority", "NORMAL")) if draft_dict.get("priority") in ["LOW", "NORMAL", "HIGH", "URGENT"] else WorkOrderPriority.NORMAL

        due_date = draft_dict.get("dueDate")
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            except ValueError:
                due_date = datetime.utcnow() + timedelta(days=7)
        elif not isinstance(due_date, datetime):
            due_date = datetime.utcnow() + timedelta(days=7)

        payload = WorkOrderCreate(
            workOrderCode=wo_code,
            name=wo_name,
            productId=prod_id,
            workflowId=wf_id,
            workflowVersion=draft_dict.get("workflowVersion", 1),
            supervisorId=draft_dict.get("supervisorId"),
            quantity=qty,
            priority=priority_val,
            dueDate=due_date,
            operations=draft_dict.get("operations"),
            createdBy=actor_id
        )

        # Call authoritative existing creation logic
        created_wo = await WorkOrderService.create_work_order(payload, actor_id=actor_id)
        return created_wo
