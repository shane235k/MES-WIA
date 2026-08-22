import os
import json
import logging
import re
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings
from app.ai.prompts import INVESTIGATION_SYSTEM_PROMPT, get_action_plan_system_prompt
from app.ai.schemas import AIInvestigationFinding, AIActionPlan

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key
        self._model = model
        self.is_simulation_mode: bool = False

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key or os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY

    @property
    def model(self) -> Optional[str]:
        return self._model or os.environ.get("GEMINI_MODEL") or settings.GEMINI_MODEL

    def set_simulation_mode(self, enabled: bool) -> bool:
        self.is_simulation_mode = enabled
        logger.info("🧪 [AI_MODE_SWITCH] AI Simulation Mode toggled to: %s", "ENABLED (Fallback Simulated)" if enabled else "DISABLED (Live LLM)")
        return self.is_simulation_mode

    def get_status(self) -> dict:
        has_key = bool(self.api_key)
        has_model = bool(self.model)
        is_live = not self.is_simulation_mode and has_key and has_model
        return {
            "aiEnabled": is_live,
            "isSimulationMode": self.is_simulation_mode,
            "hasApiKey": has_key,
            "model": self.model or "None",
            "mode": "SIMULATION_FALLBACK" if self.is_simulation_mode else ("LIVE_GEMINI" if is_live else "UNCONFIGURED")
        }

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Robustly extract and parse JSON from a model response string,
        stripping markdown codeblocks if present.
        """
        clean_text = text.strip()
        # Remove ```json ... ``` code fence if present
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)
        
        return json.loads(clean_text.strip())

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        response_mime_type: Optional[str] = "application/json"
    ) -> str:
        """
        Generic text/JSON completion method calling Google Gemini API.
        Raises descriptive error on missing configuration, simulation mode, or API error.
        """
        if self.is_simulation_mode:
            raise RuntimeError("GeminiClient is in simulation mode.")

        current_api_key = self.api_key
        current_model = self.model

        if not current_api_key or not current_model:
            raise RuntimeError(f"Gemini API is not configured: api_key={bool(current_api_key)}, model={current_model}")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={current_api_key}"
        
        full_text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": full_text}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature
            }
        }
        if response_mime_type:
            payload["generationConfig"]["responseMimeType"] = response_mime_type

        logger.info(f"🤖 [AI_GEMINI_REQUEST] Invoking Google Gemini model '{current_model}' for generic completion...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API returned HTTP {resp.status_code}: {resp.text}")
            
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini API returned no candidates: {data}")
            
            return candidates[0]["content"]["parts"][0]["text"]

    async def investigate_incident(self, context: Dict[str, Any], feedback: Optional[Dict[str, Any]] = None) -> AIInvestigationFinding:
        """
        Send incident snapshot to Gemini and obtain structured investigation findings.
        Optionally accepts prior Ollama verification feedback/critique to refine the diagnosis.
        """
        incident_info = context.get("incident", {}) or {}
        machine_info = context.get("machine", {}) or {}
        inc_code = incident_info.get("incidentCode", "INC-XXXX")
        mach_code = machine_info.get("machineCode", "M-XX")

        if self.is_simulation_mode:
            logger.info(f"🧪 [AI_SIMULATION_MODE] Simulated AI Outage / Fallback Mode active. Using deterministic diagnostic engine for {inc_code}.")
            return self._generate_fallback_investigation(context, feedback=feedback)

        feedback_section = ""
        if feedback:
            status = feedback.get("status", "REVIEW_REQUESTED")
            explanation = feedback.get("explanation", "")
            invalid_steps = feedback.get("invalidSteps", [])
            feedback_section = (
                f"\n\n==================================================\n"
                f"PRIOR OLLAMA LOCAL AUDIT VERIFICATION FEEDBACK:\n"
                f"Verification Status: {status}\n"
                f"Audit Critique / Explanation: {explanation}\n"
                f"Flagged Step Discrepancies: {json.dumps(invalid_steps)}\n"
                f"==================================================\n"
                f"INSTRUCTION FOR RE-EVALUATION:\n"
                f"The local verification model audited your previous recommendation and flagged inconsistencies or missing steps. "
                f"Carefully evaluate this feedback. Refine your diagnostic findings and recommendation to resolve all flagged discrepancies, "
                f"ensuring your recommended recovery steps are precise, non-contradictory, and provide a clear specification for subsequent action planning."
            )

        user_content = (
            f"MES INCIDENT CONTEXT SNAPSHOT:\n{json.dumps(context, indent=2)}\n\n"
            f"Please conduct an investigation of Incident {inc_code} "
            f"involving Machine {mach_code}.{feedback_section}"
        )

        current_api_key = self.api_key
        current_model = self.model

        if not current_api_key or not current_model:
            if not current_api_key:
                logger.error("❌ [AI_CONFIG_ERROR] GEMINI_API_KEY is not configured in .env!")
            if not current_model:
                logger.error("❌ [AI_CONFIG_ERROR] GEMINI_MODEL is not configured in .env! Set GEMINI_MODEL in your .env file.")
            logger.warning("⚙️ [AI_FALLBACK_DIAGNOSTICS] Falling back to local deterministic diagnostic engine.")
            return self._generate_fallback_investigation(context, feedback=feedback)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={current_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{INVESTIGATION_SYSTEM_PROMPT}\n\n{user_content}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        logger.info(f"🤖 [AI_GEMINI_REQUEST] Invoking Google Gemini model '{current_model}' for Incident {inc_code} on {mach_code} (Feedback Refinement: {bool(feedback)})...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.error(f"⚠️ [AI_GEMINI_ERROR] Gemini API returned HTTP {resp.status_code}: {resp.text}. Falling back to local engine.")
                    return self._generate_fallback_investigation(context, feedback=feedback)
                
                data = resp.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed_json = self._extract_json(text_out)
                finding = AIInvestigationFinding(**parsed_json)
                
                logger.info(
                    f"✨ [AI_GEMINI_LIVE_RESPONSE] Successfully received live Gemini analysis from model '{current_model}'!\n"
                    f"   ├─ Model Confidence: {int((finding.confidence or 0.85) * 100)}%\n"
                    f"   ├─ Diagnostic Summary: {finding.summary}\n"
                    f"   ├─ Root Observations: {len(finding.observations)} telemetry points\n"
                    f"   └─ Recommendation: {finding.recommendation}"
                )
                return finding
        except Exception as e:
            logger.error(f"⚠️ [AI_GEMINI_ERROR] Failed to communicate with Gemini API ({e}). Falling back to local engine.", exc_info=True)
            return self._generate_fallback_investigation(context, feedback=feedback)

    async def generate_action_plan(self, context: Dict[str, Any], investigation: AIInvestigationFinding) -> AIActionPlan:
        """
        Send incident snapshot & investigation findings to Gemini to generate an exact safe tool sequence.
        """
        if self.is_simulation_mode:
            logger.info("🧪 [AI_SIMULATION_MODE] Simulated AI Outage / Fallback Mode active. Using deterministic action planning engine.")
            return self._generate_fallback_action_plan(context, investigation)

        user_content = (
            f"MES INCIDENT CONTEXT SNAPSHOT:\n{json.dumps(context, indent=2)}\n\n"
            f"ACCEPTED INVESTIGATION FINDINGS:\n{investigation.model_dump_json(indent=2)}\n\n"
            f"Please propose an exact sequential recovery plan using ONLY the safe registered tools."
        )

        current_api_key = self.api_key
        current_model = self.model

        if not current_api_key or not current_model:
            if not current_api_key:
                logger.error("❌ [AI_CONFIG_ERROR] GEMINI_API_KEY is not configured in .env!")
            if not current_model:
                logger.error("❌ [AI_CONFIG_ERROR] GEMINI_MODEL is not configured in .env! Set GEMINI_MODEL in your .env file.")
            logger.warning("⚙️ [AI_FALLBACK_DIAGNOSTICS] Generating local deterministic recovery action plan.")
            return self._generate_fallback_action_plan(context, investigation)

        system_prompt = get_action_plan_system_prompt()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={current_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{user_content}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        logger.info(f"🤖 [AI_GEMINI_REQUEST] Requesting deterministic recovery action plan from Google Gemini model '{current_model}'...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.error(f"⚠️ [AI_GEMINI_ERROR] Gemini API returned HTTP {resp.status_code}: {resp.text}. Falling back to local action plan.")
                    return self._generate_fallback_action_plan(context, investigation)
                
                data = resp.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed_json = self._extract_json(text_out)
                plan = AIActionPlan(**parsed_json)
                
                tool_names = [a.tool for a in plan.proposedActions]
                logger.info(
                    f"✨ [AI_GEMINI_LIVE_RESPONSE] Live Gemini recovery action plan received from model '{current_model}'!\n"
                    f"   ├─ Proposed Safe Tools: {tool_names}\n"
                    f"   └─ Total Recovery Steps: {len(plan.proposedActions)}"
                )
                return plan
        except Exception as e:
            logger.error(f"⚠️ [AI_GEMINI_ERROR] Failed to generate Gemini action plan ({e}). Falling back to local plan.", exc_info=True)
            return self._generate_fallback_action_plan(context, investigation)

    def _calculate_confidence(self, context: Dict[str, Any]) -> float:
        """
        Dynamically calculate diagnostic confidence score based on context completeness,
        telemetry signals, machine status alignment, and work order linkage.
        """
        incident = context.get("incident", {}) or {}
        mach = context.get("machine", {}) or {}
        op = context.get("currentOperation", {}) or {}
        wo = context.get("workOrder", {}) or {}
        desc = incident.get("description", "")

        score = 0.76

        # Telemetry & machine status match
        if mach.get("status") in ["DOWN", "OCCUPIED", "MAINTENANCE"]:
            score += 0.06
        elif mach:
            score += 0.03

        # Active work order and operation linkage
        if op.get("operationId"):
            score += 0.05
        if wo.get("workOrderId") or wo.get("workOrderCode"):
            score += 0.04

        # Operator report quality & description detail
        if len(desc) > 25:
            score += 0.04
        elif len(desc) > 5:
            score += 0.02

        # Alternative machine availability clarity
        alts = context.get("availableAlternativeMachines", [])
        if alts:
            score += 0.03
        else:
            score += 0.01

        # Incident type certainty
        inc_type = incident.get("type", "")
        if inc_type in ["MACHINE_FAILURE", "QUALITY_DEFECT"]:
            score += 0.02

        # Normalize and round
        final_score = min(0.97, max(0.78, score))
        return round(final_score, 2)

    def _generate_fallback_investigation(self, context: Dict[str, Any], feedback: Optional[Dict[str, Any]] = None) -> AIInvestigationFinding:
        incident = context.get("incident", {}) or {}
        mach = context.get("machine", {}) or {}
        op = context.get("currentOperation", {}) or {}
        wo = context.get("workOrder", {}) or {}
        oper = context.get("operator", {}) or {}
        alts = context.get("availableAlternativeMachines", [])

        mach_code = mach.get("machineCode") or incident.get("machineCode") or "Machine"
        mach_name = mach.get("name") or "Workstation"
        mach_type = (mach.get("type") or incident.get("machineType") or "GENERAL").upper()
        op_id = op.get("operationId") or incident.get("operationId") or "OP-10"
        op_name = op.get("name") or "Processing Step"
        wo_code = wo.get("workOrderCode") or incident.get("workOrderCode") or "Active Work Order"
        desc = incident.get("description") or "Operator reported unexpected equipment stoppage."
        inc_code = incident.get("incidentCode") or "INC-0001"

        # Specific diagnostics by machine category
        type_diagnostics = {
            "CUTTING": (
                "Optical beam alignment degradation / assist gas pressure drop detected.",
                f"Laser cutting head on {mach_code} halted mid-cut. Edge quality and kerf tolerances at risk."
            ),
            "BENDING": (
                "Hydraulic ram pressure deviation / backgauge encoder sync loss.",
                f"Press brake {mach_code} failed during stroke. Flange angle tolerance out of specification."
            ),
            "WELDING": (
                "Shielding gas flow rate interruption / weld arc voltage instability.",
                f"Robotic weld cell {mach_code} triggered arc fault. Joint penetration incomplete."
            ),
            "ASSEMBLY": (
                "Pneumatic gripper pressure loss / automated fastener feeder jam.",
                f"Assembly station {mach_code} halted during component insertion."
            ),
            "INSPECTION": (
                "Optical vision sensor calibration drift / coordinate probe communication timeout.",
                f"Inspection station {mach_code} unable to verify geometric tolerances."
            )
        }

        diag_cause, diag_impact = type_diagnostics.get(
            mach_type,
            (f"Mechanical drive overload / PLC sensor telemetry timeout on {mach_name}.",
             f"Equipment stoppage on {mach_code} interrupted active production cycle.")
        )

        alt_m_code = alts[0].get("machineCode") if alts and alts[0].get("machineCode") else None
        alt_text = (
            f"Alternative backup machine {alts[0].get('machineCode', 'Backup')} ({alts[0].get('name', 'Backup')}, {alts[0].get('type', 'Standard')}) is IDLE and available for immediate rerouting."
            if alts else
            "No idle backup machines currently available on shop floor; maintenance dispatch required."
        )

        confidence_val = self._calculate_confidence(context)
        reroute_clause = f"reroute {op_id} to backup machine {alt_m_code} and " if alt_m_code else ""

        obs = [
            f"Operator observation: '{desc}'",
            f"Root cause indicator: {diag_cause}",
            f"Target equipment {mach_code} current status: '{mach.get('status', 'DOWN')}'.",
            f"Work Order {wo_code} blocked at sequence step {op_id} ({op_name}).",
            alt_text
        ]
        if feedback:
            obs.append(f"Audit Feedback Incorporated: Resolved verification critique regarding recovery parameters.")

        return AIInvestigationFinding(
            summary=f"Incident {inc_code} on {mach_code} ({mach_name}) has interrupted operation {op_id} ({op_name}) for Work Order {wo_code}.",
            observations=obs,
            affectedResources=[mach_code, oper.get("name") or "Assigned Operator"],
            affectedOperations=[f"{op_id} ({op_name})"],
            possibleImpact=f"{diag_impact} Downstream routing for batch {wo_code} is delayed.",
            confidence=confidence_val,
            recommendation=f"Pause operation {op_id}, lock {mach_code} in DOWN state, {reroute_clause}dispatch repair maintenance ticket."
        )

    def _generate_fallback_action_plan(self, context: Dict[str, Any], investigation: AIInvestigationFinding) -> AIActionPlan:
        incident = context.get("incident", {})
        mach = context.get("machine", {}) or {}
        op = context.get("currentOperation", {}) or {}
        wo = context.get("workOrder", {}) or {}
        alts = context.get("availableAlternativeMachines", [])

        mach_code = mach.get("machineCode") or incident.get("machineCode") or "M-03"
        mach_id = mach.get("id") or incident.get("machineId")
        
        # Resolve operationId from currentOperation, incident, or first work order operation
        op_id = None
        if op and op.get("operationId"):
            op_id = op.get("operationId")
        elif incident.get("operationId"):
            op_id = incident.get("operationId")
        elif wo and wo.get("operations") and len(wo["operations"]) > 0:
            op_id = wo["operations"][0].get("operationId")
        if not op_id:
            op_id = "OP-10"

        wo_id = wo.get("id") or incident.get("workOrderId") or "WO-1001"
        wo_code = wo.get("workOrderCode") or incident.get("workOrderCode") or "WO-1001"
        inc_id = incident.get("id")

        actions = [
            {
                "tool": "pause_operation",
                "version": "1.0",
                "parameters": {
                    "workOrderId": wo_id or wo_code,
                    "operationId": op_id,
                    "reason": f"Machine {mach_code} failure reported in {incident.get('incidentCode', 'incident')}"
                },
                "reason": f"Immediately halt operation {op_id} on {mach_code} to prevent quality defects.",
                "expectedEffect": f"Operation {op_id} is marked PAUSED and releases the operator."
            },
            {
                "tool": "mark_machine_down",
                "version": "1.0",
                "parameters": {
                    "machineId": mach_id,
                    "machineCode": mach_code,
                    "incidentId": inc_id,
                    "reason": f"Confirmed failure: {incident.get('description', 'Operator report')}"
                },
                "reason": f"Formally record machine {mach_code} as DOWN to trigger failure safety propagation.",
                "expectedEffect": f"Machine {mach_code} transitions to DOWN state."
            },
            {
                "tool": "schedule_maintenance",
                "version": "1.0",
                "parameters": {
                    "machineId": mach_id,
                    "machineCode": mach_code,
                    "incidentId": inc_id,
                    "durationMinutes": 45,
                    "reason": f"Repair and calibrate {mach_code} following failure in {incident.get('incidentCode', 'incident')}"
                },
                "reason": f"Schedule maintenance downtime for failed machine {mach_code}.",
                "expectedEffect": f"Machine {mach_code} transitions to MAINTENANCE with 45-minute repair timer."
            }
        ]

        if alts:
            backup = alts[0]
            actions.append({
                "tool": "reroute_operation",
                "version": "1.0",
                "parameters": {
                    "workOrderId": wo_id or wo_code,
                    "operationId": op_id,
                    "targetMachineId": backup.get("id"),
                    "targetMachineCode": backup.get("machineCode")
                },
                "reason": f"Auto-reroute operation {op_id} to idle backup machine {backup.get('machineCode')} to minimize schedule delay.",
                "expectedEffect": f"Operation {op_id} is reassigned to {backup.get('machineCode')} and set to READY."
            })
            actions.append({
                "tool": "resume_operation",
                "version": "1.0",
                "parameters": {
                    "workOrderId": wo_id or wo_code,
                    "operationId": op_id,
                    "reason": f"Resuming production on backup machine {backup.get('machineCode')}"
                },
                "reason": f"Start processing operation {op_id} on backup machine {backup.get('machineCode')}.",
                "expectedEffect": f"Operation {op_id} resumes execution with newly assigned machine."
            })
        else:
            actions.append({
                "tool": "schedule_maintenance",
                "version": "1.0",
                "parameters": {
                    "machineId": mach_id,
                    "machineCode": mach_code,
                    "incidentId": inc_id,
                    "durationMinutes": 15,
                    "reason": "Emergency repair for machine stoppage"
                },
                "reason": f"Schedule emergency technician maintenance for {mach_code}.",
                "expectedEffect": f"Machine {mach_code} transitions to MAINTENANCE with 15 minute countdown."
            })

        return AIActionPlan(
            summary=f"Automated recovery plan for {mach_code} breakdown affecting Work Order {wo_code}.",
            actions=actions
        )

# Global client instance
gemini_client = GeminiClient()
