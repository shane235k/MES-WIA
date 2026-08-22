import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.ai.prompts import OLLAMA_VERIFICATION_PROMPT
from app.ai.schemas import AIOllamaVerification, AIActionPlan, AIInvestigationFinding

logger = logging.getLogger(__name__)

class OllamaVerifier:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self._base_url = base_url
        self._model = model

    @property
    def base_url(self) -> str:
        return self._base_url or os.environ.get("OLLAMA_BASE_URL") or settings.OLLAMA_BASE_URL or "http://localhost:11434"

    @property
    def model(self) -> str:
        return self._model or os.environ.get("OLLAMA_MODEL") or settings.OLLAMA_MODEL or "mistral:latest"

    def _extract_json(self, text: str) -> Dict[str, Any]:
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)
        return json.loads(clean_text.strip())

    async def _resolve_active_model(self, client: httpx.AsyncClient) -> str:
        """
        Dynamically verifies if the configured model exists in Ollama.
        If missing, discovers the first available locally installed model.
        """
        configured = self.model
        try:
            tags_resp = await client.get(f"{self.base_url.rstrip('/')}/api/tags", timeout=5.0)
            if tags_resp.status_code == 200:
                installed_models = [m.get("name") for m in tags_resp.json().get("models", [])]
                if configured in installed_models:
                    return configured
                # Match by prefix (e.g. 'mistral' matches 'mistral:latest')
                matched = next((m for m in installed_models if m.startswith(configured.split(":")[0])), None)
                if matched:
                    return matched
                if installed_models:
                    logger.info(f"🦙 [OLLAMA_AUTO_DETECT] Configured model '{configured}' not found. Auto-selected installed model: '{installed_models[0]}'")
                    return installed_models[0]
        except Exception:
            pass
        return configured

    async def verify_plan(
        self,
        incident_context: Dict[str, Any],
        recommendation: str,
        action_plan: AIActionPlan
    ) -> AIOllamaVerification:
        """
        Send the recommendation and exact tool sequence to Ollama to verify alignment.
        Advisory only — failure of Ollama never blocks execution or the MES.
        """
        incident = incident_context.get("incident", {}) or {}
        tools_text = json.dumps([a.model_dump() for a in action_plan.actions], indent=2)

        prompt = (
            f"{OLLAMA_VERIFICATION_PROMPT}\n\n"
            f"ORIGINAL ISSUE / INCIDENT:\n"
            f"Code: {incident.get('incidentCode')}\n"
            f"Description: {incident.get('description')}\n"
            f"Machine: {incident.get('machineCode')}\n\n"
            f"GEMINI RECOMMENDATION:\n"
            f"{recommendation}\n\n"
            f"PROPOSED EXACT TOOL SEQUENCE:\n"
            f"{tools_text}\n\n"
            f"Please verify whether the tool sequence faithfully implements the recommendation."
        )

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                target_model = await self._resolve_active_model(client)
                url = f"{self.base_url.rstrip('/')}/api/generate"
                payload = {
                    "model": target_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }

                logger.info(f"🦙 [OLLAMA_REQUEST] Dispatching advisory verification to Ollama model '{target_model}' at {url}...")
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "{}")
                    parsed = self._extract_json(response_text)
                    status_res = str(parsed.get("status", "VALID")).upper()
                    explanation_res = str(parsed.get("explanation", "Verification completed by Ollama."))
                    invalid_steps_raw = parsed.get("invalidSteps", [])
                    if isinstance(invalid_steps_raw, list):
                        invalid_steps = [
                            s if isinstance(s, (str, dict)) else str(s)
                            for s in invalid_steps_raw
                        ]
                    else:
                        invalid_steps = []

                    logger.info(
                        f"✨ [OLLAMA_RESPONSE] Successfully received Ollama verification from '{target_model}'!\n"
                        f"   ├─ Status: {status_res}\n"
                        f"   ├─ Explanation: {explanation_res}\n"
                        f"   └─ Invalid Steps Flagged: {invalid_steps}"
                    )

                    return AIOllamaVerification(
                        status=status_res,
                        explanation=explanation_res,
                        invalidSteps=invalid_steps
                    )
                else:
                    logger.warning(f"⚠️ [OLLAMA_WARNING] Ollama server at {self.base_url} returned HTTP {resp.status_code} ({resp.text}).")
                    return AIOllamaVerification(
                        status="UNAVAILABLE",
                        explanation=f"Ollama returned HTTP {resp.status_code}. Verification advisory unavailable.",
                        invalidSteps=[]
                    )
        except httpx.TimeoutException:
            logger.warning(f"⏱️ [OLLAMA_TIMEOUT] Ollama response timed out after 45.0s at {self.base_url}.")
            return AIOllamaVerification(
                status="UNAVAILABLE",
                explanation=f"Ollama verification timed out after 45s at {self.base_url}. Verification skipped.",
                invalidSteps=[]
            )
        except Exception as e:
            logger.info(f"ℹ️ [OLLAMA_OFFLINE] Ollama connection unavailable at {self.base_url} ({e}).")
            return AIOllamaVerification(
                status="UNAVAILABLE",
                explanation=f"Local Ollama server is offline or unreachable at {self.base_url} ({e}). Verification skipped.",
                invalidSteps=[]
            )

# Global verifier instance
ollama_verifier = OllamaVerifier()
