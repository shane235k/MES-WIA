import logging
from datetime import datetime
from bson import ObjectId
from typing import Dict, Any, List, Optional

from app.core.database import get_db
from app.core.websocket import ws_manager
from app.services.audit_service import AuditService
from app.services.machine_service import MachineService
from app.ai.schemas import (
    AILifecycleStatus, AIInvestigationFinding, AIActionPlan,
    AIOllamaVerification, AIToolAction
)
from app.ai.context_builder import AIContextBuilder
from app.ai.gemini_client import gemini_client
from app.ai.ollama_verifier import ollama_verifier
from app.ai.tool_registry import validate_tool_call
from app.ai.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

class AIOrchestrator:
    @staticmethod
    def _format_op(doc: Optional[dict]) -> Optional[dict]:
        if not doc:
            return None
        d = dict(doc)
        if "_id" in d:
            d["id"] = str(d["_id"])
            d["_id"] = str(d["_id"])
        for key in ["incidentId", "machineId", "workOrderId"]:
            if key in d and isinstance(d[key], ObjectId):
                d[key] = str(d[key])
        return d

    @staticmethod
    async def start_investigation(incident_id: str, requested_by: str = "ADMIN") -> dict:
        """
        Stage 1 & 2: Build MES context snapshot, invoke Gemini investigation, and transition state.
        No mutations occur during this stage.
        """
        db = get_db()
        if not ObjectId.is_valid(incident_id):
            raise ValueError(f"Invalid incident ID format: '{incident_id}'")

        incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        # Check if an AI operation already exists for this incident
        existing_op = await db.ai_operations.find_one({"incidentId": incident_id})
        
        now = datetime.utcnow()
        if not existing_op:
            # Calculate next monotonic unique AI-OP-XXXX code
            all_ops = await db.ai_operations.find({}, {"operationId": 1}).to_list(5000)
            max_num = 0
            for item in all_ops:
                code = item.get("operationId", "")
                if code.startswith("AI-OP-"):
                    try:
                        num = int(code.split("-")[-1])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            next_num = max(max_num + 1, len(all_ops) + 1)
            op_code = f"AI-OP-{str(next_num).zfill(4)}"

            op_doc = {
                "operationId": op_code,
                "incidentId": incident_id,
                "incidentCode": incident.get("incidentCode"),
                "workOrderId": str(incident.get("workOrderId")) if incident.get("workOrderId") else None,
                "workOrderCode": incident.get("workOrderCode"),
                "machineId": str(incident.get("machineId")) if incident.get("machineId") else None,
                "machineCode": incident.get("machineCode"),
                "status": AILifecycleStatus.AI_INVESTIGATING.value,
                "investigation": None,
                "actionPlan": None,
                "toolCalls": None,
                "ollamaVerification": None,
                "executionResults": None,
                "failureReason": None,
                "requestedBy": requested_by,
                "approvedBy": None,
                "createdAt": now,
                "updatedAt": now,
                "completedAt": None
            }
            ins_res = await db.ai_operations.insert_one(op_doc)
            op_doc["_id"] = ins_res.inserted_id
            op_doc["id"] = str(ins_res.inserted_id)
            active_op = op_doc
        else:
            active_op = existing_op
            await db.ai_operations.update_one(
                {"_id": active_op["_id"]},
                {"$set": {"status": AILifecycleStatus.AI_INVESTIGATING.value, "updatedAt": now}}
            )

        ai_op_id = str(active_op["_id"])

        # 1. Build rich context snapshot
        context = await AIContextBuilder.build_incident_context(incident_id)

        # 2. Invoke Gemini for deep incident reasoning
        investigation: AIInvestigationFinding = await gemini_client.investigate_incident(context)

        # 3. Transition to AI_INVESTIGATION_READY
        now = datetime.utcnow()
        updated_op = await db.ai_operations.find_one_and_update(
            {"_id": ObjectId(ai_op_id)},
            {"$set": {
                "status": AILifecycleStatus.AI_INVESTIGATION_READY.value,
                "investigation": investigation.model_dump(),
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=requested_by,
            actor_type="ADMIN",
            action="AI_INVESTIGATION_COMPLETED",
            entity_type="ai_operation",
            entity_id=ai_op_id,
            source="AI_ORCHESTRATOR",
            metadata={
                "operationId": active_op.get("operationId"),
                "incidentCode": incident.get("incidentCode"),
                "confidence": investigation.confidence,
                "summary": investigation.summary
            }
        )

        await ws_manager.broadcast({
            "type": "AI_INVESTIGATION_READY",
            "data": AIOrchestrator._format_op(updated_op)
        })

        return AIOrchestrator._format_op(updated_op)

    @staticmethod
    async def generate_action_plan(ai_operation_id: str, requested_by: str = "ADMIN") -> dict:
        """
        Stage 3 & 4: Generate concrete proposed actions mapping strictly to the safe registered tools catalog.
        """
        db = get_db()
        if not ObjectId.is_valid(ai_operation_id):
            raise ValueError(f"Invalid AI Operation ID format: '{ai_operation_id}'")

        op_doc = await db.ai_operations.find_one({"_id": ObjectId(ai_operation_id)})
        if not op_doc:
            raise ValueError(f"AI Operation '{ai_operation_id}' not found")

        investigation_data = op_doc.get("investigation")
        if not investigation_data:
            raise ValueError("Cannot generate action plan without prior investigation findings.")

        investigation = AIInvestigationFinding(**investigation_data)
        context = await AIContextBuilder.build_incident_context(op_doc["incidentId"])

        now = datetime.utcnow()
        await db.ai_operations.update_one(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {"status": AILifecycleStatus.AI_ACTION_PLAN_REQUESTED.value, "updatedAt": now}}
        )

        # 1. Invoke Gemini Action Planning
        action_plan: AIActionPlan = await gemini_client.generate_action_plan(context, investigation)

        # 2. Validate every proposed tool against Safe Registry
        validated_actions = []
        for action in action_plan.actions:
            is_valid, err_msg = validate_tool_call(action.tool, action.parameters)
            if not is_valid:
                logger.error(f"Gemini proposed invalid tool or parameters: {err_msg}")
                raise ValueError(f"Action plan validation rejected: {err_msg}")
            validated_actions.append(action)

        # 3. Transition to AI_ACTION_PLAN_READY
        now = datetime.utcnow()
        updated_op = await db.ai_operations.find_one_and_update(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {
                "status": AILifecycleStatus.AI_ACTION_PLAN_READY.value,
                "actionPlan": action_plan.model_dump(),
                "toolCalls": [a.model_dump() for a in validated_actions],
                "ollamaVerification": None,  # Reset prior verification if plan regenerated
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=requested_by,
            actor_type="ADMIN",
            action="AI_ACTION_PLAN_GENERATED",
            entity_type="ai_operation",
            entity_id=ai_operation_id,
            source="AI_ORCHESTRATOR",
            metadata={
                "operationId": op_doc.get("operationId"),
                "actionsCount": len(validated_actions),
                "summary": action_plan.summary
            }
        )

        await ws_manager.broadcast({
            "type": "AI_ACTION_PLAN_READY",
            "data": AIOrchestrator._format_op(updated_op)
        })

        return AIOrchestrator._format_op(updated_op)

    @staticmethod
    async def verify_with_ollama(ai_operation_id: str, requested_by: str = "ADMIN") -> dict:
        """
        Stage 5: Optional Ollama verification comparing recommendation with exact tool sequence.
        """
        db = get_db()
        if not ObjectId.is_valid(ai_operation_id):
            raise ValueError(f"Invalid AI Operation ID format: '{ai_operation_id}'")

        op_doc = await db.ai_operations.find_one({"_id": ObjectId(ai_operation_id)})
        if not op_doc or not op_doc.get("actionPlan") or not op_doc.get("investigation"):
            raise ValueError("Action plan must be generated prior to Ollama verification.")

        investigation = AIInvestigationFinding(**op_doc["investigation"])
        action_plan = AIActionPlan(**op_doc["actionPlan"])
        context = await AIContextBuilder.build_incident_context(op_doc["incidentId"])

        now = datetime.utcnow()
        await db.ai_operations.update_one(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {"status": AILifecycleStatus.AI_VERIFICATION_REQUESTED.value, "updatedAt": now}}
        )

        verification = await ollama_verifier.verify_plan(
            incident_context=context,
            recommendation=investigation.recommendation or investigation.summary,
            action_plan=action_plan
        )

        now = datetime.utcnow()
        updated_op = await db.ai_operations.find_one_and_update(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {
                "status": AILifecycleStatus.AI_VERIFICATION_COMPLETE.value,
                "ollamaVerification": verification.model_dump(),
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=requested_by,
            actor_type="ADMIN",
            action="AI_OLLAMA_VERIFICATION_COMPLETED",
            entity_type="ai_operation",
            entity_id=ai_operation_id,
            source="AI_ORCHESTRATOR",
            metadata={
                "operationId": op_doc.get("operationId"),
                "status": verification.status,
                "explanation": verification.explanation
            }
        )

        await ws_manager.broadcast({
            "type": "AI_VERIFICATION_COMPLETE",
            "data": AIOrchestrator._format_op(updated_op)
        })

        return AIOrchestrator._format_op(updated_op)

    @staticmethod
    async def approve_and_execute(ai_operation_id: str, admin_id: str = "ADMIN") -> dict:
        """
        Stage 6: Mandatory Admin approval and sequential execution of the validated safe tool calls.
        """
        db = get_db()
        if not ObjectId.is_valid(ai_operation_id):
            raise ValueError(f"Invalid AI Operation ID format: '{ai_operation_id}'")

        op_doc = await db.ai_operations.find_one({"_id": ObjectId(ai_operation_id)})
        if not op_doc:
            raise ValueError(f"AI Operation '{ai_operation_id}' not found")

        # Must have an action plan ready or verified
        if op_doc.get("status") not in [
            AILifecycleStatus.AI_ACTION_PLAN_READY.value,
            AILifecycleStatus.AI_VERIFICATION_COMPLETE.value,
            AILifecycleStatus.AI_EXECUTION_APPROVED.value
        ]:
            raise ValueError(f"AI Operation in status '{op_doc.get('status')}' cannot be executed. Admin approval required.")

        tool_calls = op_doc.get("toolCalls") or []
        if not tool_calls:
            raise ValueError("No tool calls registered in this action plan.")

        now = datetime.utcnow()
        await db.ai_operations.update_one(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {
                "status": AILifecycleStatus.AI_EXECUTING.value,
                "approvedBy": admin_id,
                "updatedAt": now
            }}
        )

        execution_results = []
        try:
            for idx, action_data in enumerate(tool_calls):
                tool_name = action_data["tool"]
                params = action_data.get("parameters", {})

                logger.info(f"Executing step {idx+1}/{len(tool_calls)}: {tool_name}")
                res = await ToolExecutor.execute_tool(tool_name=tool_name, parameters=params, actor_id=admin_id)
                execution_results.append({
                    "step": idx + 1,
                    "tool": tool_name,
                    "parameters": params,
                    "status": "SUCCESS",
                    "result": res,
                    "timestamp": datetime.utcnow().isoformat()
                })

            # All actions executed successfully!
            now = datetime.utcnow()
            updated_op = await db.ai_operations.find_one_and_update(
                {"_id": ObjectId(ai_operation_id)},
                {"$set": {
                    "status": AILifecycleStatus.AI_EXECUTION_COMPLETE.value,
                    "executionResults": execution_results,
                    "completedAt": now,
                    "updatedAt": now
                }},
                return_document=True
            )

            await AuditService.log_event(
                actor_id=admin_id,
                actor_type="ADMIN",
                action="AI_PLAN_EXECUTION_COMPLETED",
                entity_type="ai_operation",
                entity_id=ai_operation_id,
                source="AI_ORCHESTRATOR",
                metadata={
                    "operationId": op_doc.get("operationId"),
                    "actionsExecuted": len(execution_results),
                    "approvedBy": admin_id
                }
            )

            await ws_manager.broadcast({
                "type": "AI_EXECUTION_COMPLETE",
                "data": AIOrchestrator._format_op(updated_op)
            })

            return AIOrchestrator._format_op(updated_op)

        except Exception as e:
            logger.error(f"Execution failed during AI action sequence: {e}", exc_info=True)
            now = datetime.utcnow()
            updated_op = await db.ai_operations.find_one_and_update(
                {"_id": ObjectId(ai_operation_id)},
                {"$set": {
                    "status": AILifecycleStatus.AI_EXECUTION_FAILED.value,
                    "executionResults": execution_results,
                    "failureReason": str(e),
                    "updatedAt": now
                }},
                return_document=True
            )

            # Trigger standard deterministic automated fallback recovery so shop floor is not stuck
            try:
                inc_id = op_doc.get("incidentId")
                if inc_id and ObjectId.is_valid(inc_id):
                    inc = await db.incidents.find_one({"_id": ObjectId(inc_id)})
                    if inc and inc.get("machineId"):
                        m_id = str(inc["machineId"])
                        mach = await db.machines.find_one({"_id": ObjectId(m_id)})
                        if mach and mach.get("status") not in ["DOWN", "MAINTENANCE"]:
                            logger.warning("⚙️ [AI_AUTOMATED_FALLBACK] Triggering standard MachineService.fail_machine automated fallback recovery.")
                            await MachineService.fail_machine(
                                machine_id=m_id,
                                reason=f"Automated fallback recovery following AI execution failure ({str(e)[:60]})",
                                actor_id=admin_id,
                                incident_id=str(inc["_id"]),
                                incident_code=inc.get("incidentCode")
                            )
            except Exception as fb_err:
                logger.error(f"Failed to execute automated fallback recovery after AI execution failure: {fb_err}")

            await AuditService.log_event(
                actor_id=admin_id,
                actor_type="ADMIN",
                action="AI_PLAN_EXECUTION_FAILED",
                entity_type="ai_operation",
                entity_id=ai_operation_id,
                source="AI_ORCHESTRATOR",
                metadata={
                    "operationId": op_doc.get("operationId"),
                    "error": str(e)
                }
            )

            await ws_manager.broadcast({
                "type": "AI_EXECUTION_FAILED",
                "data": AIOrchestrator._format_op(updated_op)
            })

            raise

    @staticmethod
    async def reject_investigation(ai_operation_id: str, admin_id: str = "ADMIN", reason: str = "Rejected by Admin") -> dict:
        db = get_db()
        if not ObjectId.is_valid(ai_operation_id):
            raise ValueError(f"Invalid AI Operation ID format: '{ai_operation_id}'")

        now = datetime.utcnow()
        updated_op = await db.ai_operations.find_one_and_update(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {
                "status": AILifecycleStatus.REJECTED.value,
                "failureReason": reason,
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="ADMIN",
            action="AI_INVESTIGATION_REJECTED",
            entity_type="ai_operation",
            entity_id=ai_operation_id,
            source="AI_ORCHESTRATOR",
            metadata={"reason": reason}
        )

        return AIOrchestrator._format_op(updated_op)

    @staticmethod
    async def get_operation(ai_operation_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(ai_operation_id):
            return None
        doc = await db.ai_operations.find_one({"_id": ObjectId(ai_operation_id)})
        return AIOrchestrator._format_op(doc)

    @staticmethod
    async def get_active_by_incident(incident_id: str) -> Optional[dict]:
        db = get_db()
        doc = await db.ai_operations.find_one({"incidentId": incident_id}, sort=[("createdAt", -1)])
        return AIOrchestrator._format_op(doc)

    @staticmethod
    async def reinvestigate_with_feedback(ai_operation_id: str, requested_by: str = "ADMIN") -> dict:
        """
        Send Ollama verification feedback & critique back to Gemini to re-evaluate the Stage 1 diagnosis.
        Clears previous action plan and tool calls so a fresh, corrected action plan can be generated.
        """
        db = get_db()
        if not ObjectId.is_valid(ai_operation_id):
            raise ValueError(f"Invalid AI Operation ID format: '{ai_operation_id}'")

        op_doc = await db.ai_operations.find_one({"_id": ObjectId(ai_operation_id)})
        if not op_doc:
            raise ValueError(f"AI Operation '{ai_operation_id}' not found")

        feedback = op_doc.get("ollamaVerification")
        if not feedback:
            raise ValueError("No Ollama verification feedback found on this AI Operation.")

        now = datetime.utcnow()
        await db.ai_operations.update_one(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {"status": AILifecycleStatus.AI_INVESTIGATING.value, "updatedAt": now}}
        )

        context = await AIContextBuilder.build_incident_context(op_doc["incidentId"])
        refined_investigation = await gemini_client.investigate_incident(context, feedback=feedback)

        now = datetime.utcnow()
        updated_op = await db.ai_operations.find_one_and_update(
            {"_id": ObjectId(ai_operation_id)},
            {"$set": {
                "status": AILifecycleStatus.AI_INVESTIGATION_READY.value,
                "investigation": refined_investigation.model_dump(),
                "actionPlan": None,
                "toolCalls": None,
                "updatedAt": now
            }},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=requested_by,
            actor_type="ADMIN",
            action="AI_REINVESTIGATION_WITH_FEEDBACK",
            entity_type="ai_operation",
            entity_id=ai_operation_id,
            source="AI_ORCHESTRATOR",
            metadata={
                "operationId": op_doc.get("operationId"),
                "ollamaStatus": feedback.get("status"),
                "summary": refined_investigation.summary
            }
        )

        await ws_manager.broadcast({
            "type": "AI_INVESTIGATION_READY",
            "data": AIOrchestrator._format_op(updated_op)
        })

        return AIOrchestrator._format_op(updated_op)

    @staticmethod
    async def list_operations() -> List[dict]:
        db = get_db()
        res = []
        async for doc in db.ai_operations.find().sort("createdAt", -1).limit(50):
            res.append(AIOrchestrator._format_op(doc))
        return res
