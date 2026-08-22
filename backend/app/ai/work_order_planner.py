import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.ai.prompts import WORK_ORDER_PLANNING_SYSTEM_PROMPT
from app.schemas.ai_work_order import (
    AIWorkOrderResponseEnvelope, AIWorkOrderDraft,
    AIWorkOrderOperationDraft, AIMaterialRequirementSummary,
    WorkOrderPriority
)

logger = logging.getLogger(__name__)

class AIWorkOrderPlanner:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key
        self._model = model

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key or settings.GEMINI_API_KEY

    @property
    def model(self) -> Optional[str]:
        return self._model or settings.GEMINI_MODEL

    def _extract_json(self, text: str) -> Dict[str, Any]:
        clean = text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        return json.loads(clean.strip())

    async def plan_step(
        self,
        conversation_history: List[Dict[str, str]],
        context: Dict[str, Any],
        collected_fields: Optional[Dict[str, Any]] = None,
        suggested_fields: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> AIWorkOrderResponseEnvelope:
        """
        Takes conversation history and sanitized MES context, queries Gemini,
        and returns an AIWorkOrderResponseEnvelope.
        Falls back to local deterministic rule engine on simulation mode or error.
        """
        api_key = self.api_key
        model = self.model

        # Check for live LLM mode
        if api_key and model and not getattr(settings, "AI_SIMULATION_MODE", False):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                user_content = (
                    f"MES PLANNING CONTEXT:\n{json.dumps(context, indent=2, default=str)}\n\n"
                    f"PREVIOUSLY COLLECTED FIELDS:\n{json.dumps(collected_fields or {}, indent=2, default=str)}\n\n"
                    f"CONVERSATION HISTORY:\n{json.dumps(conversation_history, indent=2, default=str)}\n\n"
                    f"Respond according to the system prompt and return strict JSON."
                )

                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": f"{WORK_ORDER_PLANNING_SYSTEM_PROMPT}\n\n{user_content}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.1,
                        "responseMimeType": "application/json"
                    }
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = self._extract_json(text_out)
                        parsed["sessionId"] = session_id
                        return AIWorkOrderResponseEnvelope(**parsed)
                    else:
                        logger.warning(f"Gemini API returned {resp.status_code}: {resp.text}. Using deterministic planner.")
            except Exception as e:
                logger.error(f"Gemini API error during Work Order planning ({e}). Using deterministic planner.", exc_info=True)

        # Local deterministic planning engine fallback
        return self._deterministic_plan_step(
            conversation_history=conversation_history,
            context=context,
            collected_fields=dict(collected_fields or {}),
            suggested_fields=dict(suggested_fields or {}),
            session_id=session_id
        )

    def _deterministic_plan_step(
        self,
        conversation_history: List[Dict[str, str]],
        context: Dict[str, Any],
        collected_fields: Dict[str, Any],
        suggested_fields: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> AIWorkOrderResponseEnvelope:
        """
        Robust rule-based parser that guarantees compliant conversational requirement collection.
        """
        products = context.get("products", [])
        workflows = context.get("workflows", [])
        supervisors = context.get("supervisors", [])
        machines = context.get("machines", [])
        materials = context.get("materials", [])

        # Process conversation messages sequentially to collect fields
        last_user_msg = ""
        for msg in conversation_history:
            if msg.get("sender") == "USER" or msg.get("role") == "user":
                text = msg.get("content", "").strip()
                last_user_msg = text
                self._extract_fields_from_text(text, collected_fields, suggested_fields, context)

        # 1. Check Product
        prod_id = collected_fields.get("productId")
        selected_prod = next((p for p in products if p["productId"] == prod_id), None) if prod_id else None

        if not selected_prod:
            # Need product
            options = [
                {"label": f"{p['productCode']} — {p['name']}", "value": p["productId"], "code": p["productCode"]}
                for p in products
            ]
            return AIWorkOrderResponseEnvelope(
                status="NEEDS_INFORMATION",
                sessionId=session_id,
                message="What product would you like to manufacture? Please specify a product from the factory catalog.",
                missingFields=["productId"],
                collectedFields=collected_fields,
                suggestions={},
                options=options
            )

        # 2. Check Workflow
        matching_wfs = [w for w in workflows if w.get("productId") == selected_prod["productId"]]
        wf_id = collected_fields.get("workflowId")
        selected_wf = next((w for w in matching_wfs if w["workflowId"] == wf_id), None) if wf_id else None

        if not selected_wf:
            if len(matching_wfs) == 1:
                # Suggest the single canonical workflow
                wf_cand = matching_wfs[0]
                if last_user_msg.lower() in ["yes", "y", "sure", "ok", "use it", "confirm"]:
                    collected_fields["workflowId"] = wf_cand["workflowId"]
                    collected_fields["workflowCode"] = wf_cand["workflowCode"]
                    selected_wf = wf_cand
                else:
                    options = [{"label": f"{wf_cand['workflowCode']} ({wf_cand['name']})", "value": wf_cand["workflowId"]}]
                    return AIWorkOrderResponseEnvelope(
                        status="NEEDS_INFORMATION",
                        sessionId=session_id,
                        message=f"I found {selected_prod['productCode']}. Available workflow: {wf_cand['workflowCode']}. Would you like to use it?",
                        missingFields=["workflowId"],
                        collectedFields=collected_fields,
                        suggestions={"workflowId": wf_cand["workflowId"]},
                        options=options
                    )
            elif len(matching_wfs) > 1:
                options = [
                    {"label": f"{w['workflowCode']} (v{w.get('version', 1)})", "value": w["workflowId"]}
                    for w in matching_wfs
                ]
                return AIWorkOrderResponseEnvelope(
                    status="NEEDS_INFORMATION",
                    sessionId=session_id,
                    message=f"I found multiple available workflows for {selected_prod['productCode']}. Which routing workflow would you like to use?",
                    missingFields=["workflowId"],
                    collectedFields=collected_fields,
                    suggestions={},
                    options=options
                )
            else:
                return AIWorkOrderResponseEnvelope(
                    status="ERROR",
                    sessionId=session_id,
                    message=f"No active workflows found for product {selected_prod['productCode']}. Please configure a workflow first.",
                    missingFields=["workflowId"],
                    collectedFields=collected_fields
                )

        # 3. Check Quantity
        qty = collected_fields.get("quantity")
        if not qty or float(qty) <= 0:
            return AIWorkOrderResponseEnvelope(
                status="NEEDS_INFORMATION",
                sessionId=session_id,
                message=f"How many units of {selected_prod['productCode']} would you like to manufacture?",
                missingFields=["quantity"],
                collectedFields=collected_fields,
                suggestions={"quantity": 50},
                options=[]
            )

        # 4. Check Supervisor
        sup_id = collected_fields.get("supervisorId")
        selected_sup = next((s for s in supervisors if s["supervisorId"] == sup_id), None) if sup_id else None

        if not selected_sup:
            if len(supervisors) == 1:
                sup_cand = supervisors[0]
                if last_user_msg.lower() in ["yes", "y", "sure", "ok", "confirm"]:
                    collected_fields["supervisorId"] = sup_cand["supervisorId"]
                    collected_fields["supervisorName"] = sup_cand["name"]
                    selected_sup = sup_cand
                else:
                    options = [{"label": f"{sup_cand['name']} ({sup_cand.get('employeeId', 'SUP')})", "value": sup_cand["supervisorId"]}]
                    return AIWorkOrderResponseEnvelope(
                        status="NEEDS_INFORMATION",
                        sessionId=session_id,
                        message=f"Which shift supervisor should be assigned? Available: {sup_cand['name']} ({sup_cand.get('employeeId', '')}).",
                        missingFields=["supervisorId"],
                        collectedFields=collected_fields,
                        suggestions={"supervisorId": sup_cand["supervisorId"]},
                        options=options
                    )
            else:
                options = [
                    {"label": f"{s['name']} ({s.get('employeeId', '')})", "value": s["supervisorId"]}
                    for s in supervisors
                ]
                return AIWorkOrderResponseEnvelope(
                    status="NEEDS_INFORMATION",
                    sessionId=session_id,
                    message="Which supervisor should be assigned to oversee this production batch?",
                    missingFields=["supervisorId"],
                    collectedFields=collected_fields,
                    suggestions={},
                    options=options
                )

        # 5. Check Optional Name / Batch Code
        custom_name = collected_fields.get("name")
        suggested_name = suggested_fields.get("name")
        date_str = datetime.utcnow().strftime("%Y%m%d")
        default_batch_name = f"{selected_prod['productCode']}-BATCH-{date_str}-001"
        default_wo_code = f"WO-{selected_prod['productCode']}-{uuid.uuid4().hex[:4].upper()}"

        if not custom_name and not suggested_name:
            suggested_fields["name"] = default_batch_name
            suggested_fields["workOrderCode"] = default_wo_code
            return AIWorkOrderResponseEnvelope(
                status="OPTIONAL_CONFIRMATION",
                sessionId=session_id,
                message=f"I have all required parameters. I generated this optional batch name: {default_batch_name}. Would you like to use it or enter your own?",
                missingFields=[],
                collectedFields=collected_fields,
                suggestions={"name": default_batch_name, "workOrderCode": default_wo_code},
                options=[{"label": "Use suggested name", "value": "USE_SUGGESTED"}]
            )

        if not custom_name and suggested_name:
            if "yes" in last_user_msg.lower() or "use suggested" in last_user_msg.lower() or "ok" in last_user_msg.lower() or "sure" in last_user_msg.lower():
                collected_fields["name"] = suggested_name
                collected_fields["workOrderCode"] = suggested_fields.get("workOrderCode", default_wo_code)
            elif "no" in last_user_msg.lower():
                # User rejected suggestion, ask for custom name
                return AIWorkOrderResponseEnvelope(
                    status="NEEDS_INFORMATION",
                    sessionId=session_id,
                    message="Please provide your custom Work Order name.",
                    missingFields=["name"],
                    collectedFields=collected_fields,
                    suggestions={}
                )
            else:
                collected_fields["name"] = suggested_name
                collected_fields["workOrderCode"] = suggested_fields.get("workOrderCode", default_wo_code)

        final_wo_name = collected_fields.get("name") or default_batch_name
        final_wo_code = collected_fields.get("workOrderCode") or default_wo_code

        # 6. Build Draft Operations & Material Requirements
        draft_ops = []
        material_summaries_map = {}
        total_estimated_cost = 0.0

        for op in selected_wf.get("operations", []):
            req_machine_type = op.get("requiredMachineType", "GENERIC")
            comp_mach = next((m for m in machines if m.get("type") == req_machine_type or req_machine_type in m.get("supportedTypes", [])), None)

            # Materials for this operation
            op_mats = []
            for rm in op.get("requiredMaterials", []):
                m_id = rm.get("materialId")
                q_per_u = float(rm.get("quantity", 1.0))
                tot_q = round(q_per_u * float(qty), 4)
                mat_obj = next((m for m in materials if m["materialId"] == m_id), None)
                m_name = mat_obj["name"] if mat_obj else "Raw Material"
                u_cost = float(mat_obj.get("unitCost", 0.0)) if mat_obj else 0.0
                subtotal = round(tot_q * u_cost, 2)

                op_mats.append({
                    "materialId": m_id,
                    "quantity": q_per_u,
                    "unit": rm.get("unit") or (mat_obj.get("unit") if mat_obj else "units")
                })

                if m_id not in material_summaries_map:
                    material_summaries_map[m_id] = {
                        "materialId": m_id,
                        "materialName": m_name,
                        "unit": rm.get("unit") or (mat_obj.get("unit") if mat_obj else "units"),
                        "quantityPerUnit": 0.0,
                        "totalRequiredQuantity": 0.0,
                        "unitCost": u_cost,
                        "subtotalCost": 0.0
                    }
                material_summaries_map[m_id]["quantityPerUnit"] = round(material_summaries_map[m_id]["quantityPerUnit"] + q_per_u, 4)
                material_summaries_map[m_id]["totalRequiredQuantity"] = round(material_summaries_map[m_id]["totalRequiredQuantity"] + tot_q, 4)
                material_summaries_map[m_id]["subtotalCost"] = round(material_summaries_map[m_id]["subtotalCost"] + subtotal, 2)
                total_estimated_cost += subtotal

            draft_ops.append(AIWorkOrderOperationDraft(
                operationId=op["operationId"],
                name=op.get("name", ""),
                sequence=op.get("sequence", 1),
                requiredMachineType=req_machine_type,
                assignedMachineId=comp_mach["machineId"] if comp_mach else None,
                dependencies=op.get("dependencies", []),
                requiredMaterials=op_mats
            ))

        material_requirements = [
            AIMaterialRequirementSummary(**item)
            for item in material_summaries_map.values()
        ]

        priority_val = WorkOrderPriority(collected_fields.get("priority", "NORMAL").upper()) if collected_fields.get("priority") in ["LOW", "NORMAL", "HIGH", "URGENT"] else WorkOrderPriority.NORMAL
        due_date = collected_fields.get("dueDate") or (datetime.utcnow() + timedelta(days=7))

        draft = AIWorkOrderDraft(
            productId=selected_prod["productId"],
            productCode=selected_prod["productCode"],
            productName=selected_prod["name"],
            workflowId=selected_wf["workflowId"],
            workflowCode=selected_wf["workflowCode"],
            workflowVersion=selected_wf.get("version", 1),
            quantity=float(qty),
            priority=priority_val,
            dueDate=due_date,
            workOrderCode=final_wo_code,
            name=final_wo_name,
            supervisorId=selected_sup["supervisorId"],
            supervisorName=selected_sup["name"],
            notes=collected_fields.get("notes", "Generated by AI Planning Assistant"),
            operations=draft_ops,
            materialRequirements=material_requirements,
            totalEstimatedCost=round(total_estimated_cost, 2)
        )

        mat_summary_str = "\n".join([
            f"• {m.materialName}: {m.totalRequiredQuantity} {m.unit} (Subtotal: ₹{m.subtotalCost})"
            for m in material_requirements
        ]) if material_requirements else "None (Material-free process)"

        ready_msg = (
            f"Here is the finalized Work Order Draft:\n\n"
            f"• Product: {selected_prod['productCode']} ({selected_prod['name']})\n"
            f"• Routing Workflow: {selected_wf['workflowCode']}\n"
            f"• Production Target: {qty} finished units\n"
            f"• Shift Supervisor: {selected_sup['name']}\n"
            f"• Priority: {priority_val.value}\n"
            f"• Batch Name: {final_wo_name}\n\n"
            f"Expected Raw Material Requirements:\n{mat_summary_str}\n\n"
            f"Total Estimated Material Cost: ₹{round(total_estimated_cost, 2):,.2f}\n\n"
            f"Would you like to review and create this Work Order?"
        )

        return AIWorkOrderResponseEnvelope(
            status="READY",
            sessionId=session_id,
            message=ready_msg,
            missingFields=[],
            collectedFields=collected_fields,
            suggestions=suggested_fields,
            options=[],
            draft=draft
        )

    def _extract_fields_from_text(
        self,
        text: str,
        collected_fields: Dict[str, Any],
        suggested_fields: Dict[str, Any],
        context: Dict[str, Any]
    ) -> None:
        """Helper to extract products, numbers, workflows, supervisors, priorities, and custom names from text."""
        lower = text.lower()
        upper = text.upper()

        # 1. Match Product
        for p in context.get("products", []):
            p_code = p.get("productCode", "").upper()
            p_name = p.get("name", "").upper()
            if p_code in upper or p_name in upper:
                collected_fields["productId"] = p["productId"]
                collected_fields["productCode"] = p["productCode"]
                collected_fields["productName"] = p["name"]
                break

        # 2. Match Workflow
        for w in context.get("workflows", []):
            w_code = w.get("workflowCode", "").upper()
            if w_code in upper or w["workflowId"] in text:
                collected_fields["workflowId"] = w["workflowId"]
                collected_fields["workflowCode"] = w["workflowCode"]
                break

        # 3. Match Supervisor
        for s in context.get("supervisors", []):
            s_name = s.get("name", "").upper()
            s_emp = s.get("employeeId", "").upper()
            if (s_emp and s_emp in upper) or (s_name and s_name in upper) or s["supervisorId"] in text:
                collected_fields["supervisorId"] = s["supervisorId"]
                collected_fields["supervisorName"] = s["name"]
                break

        # 4. Match Priority
        for pr in ["URGENT", "HIGH", "NORMAL", "LOW"]:
            if re.search(rf'\b{pr}\b', upper):
                collected_fields["priority"] = pr
                break

        # 5. Match Custom Name (e.g. "call it Friday Production", "name: Batch Alpha")
        name_match = re.search(r'(?:call it|name it|name:|batch name is|batch:)\s*["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if name_match:
            custom_name = name_match.group(1).strip()
            if custom_name and custom_name.lower() not in ["yes", "no", "sure"]:
                collected_fields["name"] = custom_name

        # 6. Match Quantity safely:
        # Avoid picking up numbers inside entity codes like WF-BRACKET-988409 or SUP-AI-1234
        # Mask out known workflow codes, product codes, employee IDs in a scratch text
        clean_text_for_qty = text
        for w in context.get("workflows", []):
            if w.get("workflowCode"):
                clean_text_for_qty = clean_text_for_qty.replace(w["workflowCode"], " ")
        for p in context.get("products", []):
            if p.get("productCode"):
                clean_text_for_qty = clean_text_for_qty.replace(p["productCode"], " ")
        for s in context.get("supervisors", []):
            if s.get("employeeId"):
                clean_text_for_qty = clean_text_for_qty.replace(s["employeeId"], " ")

        # Look for explicit quantity patterns: "50 units", "produce 50", "quantity 50", or standalone "50"
        qty_patterns = [
            r'\b(?:produce|make|manufacture|quantity|qty|target)\s+(\d+(?:\.\d+)?)\b',
            r'\b(\d+(?:\.\d+)?)\s+(?:units|items|pieces|pcs|brackets|finished)\b',
            r'^\s*(\d+(?:\.\d+)?)\s*$'
        ]
        for pat in qty_patterns:
            m = re.search(pat, clean_text_for_qty, re.IGNORECASE)
            if m:
                try:
                    num = float(m.group(1))
                    if num > 0:
                        collected_fields["quantity"] = num
                        break
                except ValueError:
                    pass

        # 7. Check if user typed custom name directly after rejection
        if suggested_fields.get("name") and not collected_fields.get("name"):
            if not any(k in lower for k in ["yes", "sure", "ok", "confirm", "use suggested"]) and len(text.split()) < 6 and not any(k in lower for k in ["bracket", "unit", "workflow", "supervisor"]):
                if not text.isdigit() and len(text) > 3:
                    collected_fields["name"] = text.strip()
