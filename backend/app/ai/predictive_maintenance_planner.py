import json
import logging
import re
from typing import Dict, Any, Optional

from app.schemas.machine_health import (
    MachineHealthAssessment, AIPredictiveMaintenanceAssessment,
    AIPredictiveMaintenanceFinding, AIPredictiveMaintenanceAction,
    RiskLevel, DataQuality
)
from app.ai.prompts import PREDICTIVE_MAINTENANCE_SYSTEM_PROMPT
from app.ai.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class AIPredictiveMaintenancePlanner:
    @staticmethod
    def build_sanitized_context(assessment: MachineHealthAssessment) -> Dict[str, Any]:
        """
        Builds a safe, sanitized context snapshot containing only operational metrics,
        without credentials, tokens, or system paths.
        """
        m = assessment.metrics
        return {
            "machine": {
                "machineCode": assessment.machineCode,
                "machineName": assessment.machineName,
                "machineType": assessment.machineType,
                "location": assessment.location,
                "status": assessment.status,
                "configuredProcessingRate": f"{m.configuredProcessingRate} units/sec"
            },
            "deterministicHealthAssessment": {
                "healthScore": f"{assessment.healthScore}/100",
                "riskLevel": assessment.riskLevel.value,
                "dataQuality": assessment.dataQuality.value,
                "dataPointsAnalyzed": assessment.dataPoints,
                "confidenceCeiling": assessment.confidenceCeiling
            },
            "operationalTelemetry": {
                "completedOperations": m.completedOperations,
                "totalOperatingSeconds": m.totalOperatingSeconds,
                "averageCycleTimeSeconds": m.averageCycleTime,
                "baselineCycleTimeSeconds": m.baselineCycleTime,
                "cycleTimeDeviationPercent": f"{'+' if m.cycleTimeDeviationPercent > 0 else ''}{m.cycleTimeDeviationPercent}%",
                "actualProcessingRate": f"{m.actualProcessingRate} units/sec",
                "processingRateEfficiencyPercent": f"{m.processingRateEfficiencyPercent}%",
                "cycleTimeTrend": assessment.trends.cycleTime.value,
                "rateEfficiencyTrend": assessment.trends.processingRate.value
            },
            "reliabilityHistory": {
                "failureCount24h": m.failureCount24h,
                "failureCount7d": m.failureCount7d,
                "failureCount30d": m.failureCount30d,
                "totalFailures": m.totalFailureCount,
                "totalDowntimeSeconds": m.totalDowntimeSeconds,
                "downtimePercentage": f"{m.downtimePercentage}%",
                "mtbfSeconds": m.mtbfSeconds if m.mtbfSeconds is not None else "N/A",
                "mttrSeconds": m.mttrSeconds if m.mttrSeconds is not None else "N/A"
            },
            "warningSignals": {
                "operatorWarnings24h": m.operatorWarnings24h,
                "operatorWarnings7d": m.operatorWarnings7d,
                "unresolvedOperatorWarnings": m.unresolvedOperatorWarnings,
                "recentIncidentCount": m.recentIncidentCount
            },
            "maintenanceContext": {
                "daysSinceLastMaintenance": m.daysSinceLastMaintenance if m.daysSinceLastMaintenance is not None else "N/A",
                "recentMaintenanceEvents": m.recentMaintenanceCount,
                "maintenanceOverdue": m.maintenanceOverdue
            },
            "materialTraceabilityCorrelations": [
                {
                    "materialName": pm.materialName,
                    "grade": pm.grade,
                    "lotNumber": pm.lotNumber,
                    "supplier": pm.supplier,
                    "incidentsDuringProcessing": pm.incidentCount,
                    "scrapsDuringProcessing": pm.scrapCount,
                    "observation": pm.observation
                }
                for pm in m.problematicMaterials
            ]
        }

    @staticmethod
    def _generate_fallback_assessment(assessment: MachineHealthAssessment) -> AIPredictiveMaintenanceAssessment:
        """
        Deterministic qualitative analysis fallback if Gemini API is offline or unconfigured.
        """
        m = assessment.metrics
        code = assessment.machineCode
        name = assessment.machineName
        score = assessment.healthScore
        risk = assessment.riskLevel

        findings = []
        actions = []

        if assessment.dataQuality == DataQuality.INSUFFICIENT_DATA:
            summary = f"Machine {code} ({name}) has limited historical production records ({assessment.dataPoints} completed ops). Health baseline is steady."
            failure_mode = "OPERATIONAL_STABLE"
            window = "ROUTINE"
            findings.append(AIPredictiveMaintenanceFinding(
                signal="DATA_QUALITY",
                observation=f"Only {assessment.dataPoints} completed operations available. Operating with standard baseline.",
                importance="LOW"
            ))
            actions.append(AIPredictiveMaintenanceAction(
                priority="LOW",
                action="Continue standard production logging to establish statistical operating baseline.",
                reason="Ensures sufficient sample size for high-confidence predictive analytics.",
                toolName="schedule_maintenance",
                parameters={"durationMinutes": 30, "reason": "Standard baseline verification"}
            ))

        elif risk == RiskLevel.CRITICAL:
            summary = f"CRITICAL: Machine {code} ({name}) shows severe operational stress or active failure indicators (Health Score {score}/100)."
            failure_mode = "MECHANICAL_OR_CALIBRATION_BREAKDOWN"
            window = "IMMEDIATE"
            if m.cycleTimeDeviationPercent > 20:
                findings.append(AIPredictiveMaintenanceFinding(
                    signal="CYCLE_TIME_DEGRADATION",
                    observation=f"Cycle time elongated by {m.cycleTimeDeviationPercent}% over baseline.",
                    importance="CRITICAL"
                ))
            if m.failureCount7d > 0:
                findings.append(AIPredictiveMaintenanceFinding(
                    signal="RECENT_FAILURES",
                    observation=f"{m.failureCount7d} breakdown incidents logged in the past 7 days.",
                    importance="CRITICAL"
                ))
            actions.append(AIPredictiveMaintenanceAction(
                priority="IMMEDIATE",
                action=f"Perform immediate comprehensive mechanical inspection and recalibration of {code}.",
                reason="Severe degradation signals predict imminent catastrophic breakdown.",
                toolName="schedule_maintenance",
                parameters={"durationMinutes": 60, "reason": f"Urgent predictive maintenance: Critical degradation on {code}"}
            ))

        elif risk == RiskLevel.HIGH:
            summary = f"HIGH RISK: Machine {code} ({name}) displays progressive performance degradation (Health Score {score}/100)."
            failure_mode = "TOOL_WEAR_DEGRADATION"
            window = "WITHIN_24_HOURS"
            if m.cycleTimeDeviationPercent > 10:
                findings.append(AIPredictiveMaintenanceFinding(
                    signal="CYCLE_TIME_DEGRADATION",
                    observation=f"Cycle time has increased by {m.cycleTimeDeviationPercent}% relative to historical baseline.",
                    importance="HIGH"
                ))
            if m.unresolvedOperatorWarnings > 0:
                findings.append(AIPredictiveMaintenanceFinding(
                    signal="OPERATOR_WARNINGS",
                    observation=f"{m.unresolvedOperatorWarnings} unresolved operator alert(s) reported on this machine.",
                    importance="HIGH"
                ))
            actions.append(AIPredictiveMaintenanceAction(
                priority="HIGH",
                action=f"Schedule 45-minute preventive maintenance on {code} to inspect tooling and recalibrate drive system.",
                reason="Mitigates cycle time slippage and prevents unplanned shift downtime.",
                toolName="schedule_maintenance",
                parameters={"durationMinutes": 45, "reason": f"Preventive maintenance: Tool wear and cycle degradation on {code}"}
            ))

        elif risk == RiskLevel.MEDIUM:
            summary = f"MODERATE: Machine {code} ({name}) exhibits mild variance (Health Score {score}/100). Monitor closely."
            failure_mode = "EARLY_DRIFT"
            window = "NEXT_SCHEDULED_SHIFT"
            findings.append(AIPredictiveMaintenanceFinding(
                signal="EARLY_VARIANCE",
                observation=f"Slight cycle deviation of {m.cycleTimeDeviationPercent}% detected; processing efficiency at {m.processingRateEfficiencyPercent}%.",
                importance="MEDIUM"
            ))
            actions.append(AIPredictiveMaintenanceAction(
                priority="MEDIUM",
                action=f"Inspect alignment and clean tooling surfaces during next planned shift break.",
                reason="Prevents gradual drift from worsening into high-severity degradation.",
                toolName="schedule_maintenance",
                parameters={"durationMinutes": 30, "reason": f"Routine shift inspection for {code}"}
            ))

        else:
            summary = f"HEALTHY: Machine {code} ({name}) operating efficiently at nominal processing parameters (Health Score {score}/100)."
            failure_mode = "OPERATIONAL_STABLE"
            window = "ROUTINE"
            findings.append(AIPredictiveMaintenanceFinding(
                signal="STABLE_OPERATION",
                observation=f"Operations running consistently with {m.processingRateEfficiencyPercent}% rate efficiency.",
                importance="LOW"
            ))
            actions.append(AIPredictiveMaintenanceAction(
                priority="LOW",
                action="Maintain standard preventive maintenance schedule.",
                reason="Equipment operating within normal statistical control limits.",
                toolName="schedule_maintenance",
                parameters={"durationMinutes": 30, "reason": f"Scheduled routine check for {code}"}
            ))

        mat_note = None
        if m.problematicMaterials:
            mat_note = m.problematicMaterials[0].observation

        return AIPredictiveMaintenanceAssessment(
            summary=summary,
            failureMode=failure_mode,
            diagnosisConfidence=round(min(0.92, assessment.confidenceCeiling), 2),
            findings=findings,
            recommendedActions=actions,
            recommendedMaintenanceWindow=window,
            materialCorrelationNote=mat_note,
            proposedToolCalls=[
                {
                    "tool": a.toolName or "schedule_maintenance",
                    "parameters": {
                        "machineCode": code,
                        **(a.parameters or {})
                    }
                }
                for a in actions if a.toolName
            ]
        )

    @staticmethod
    async def assess_machine_health(
        assessment: MachineHealthAssessment,
        actor_id: str = "ADMIN"
    ) -> AIPredictiveMaintenanceAssessment:
        """
        Executes Gemini AI predictive maintenance analysis with strict Pydantic validation
        and graceful deterministic fallback.
        """
        sanitized_context = AIPredictiveMaintenancePlanner.build_sanitized_context(assessment)
        prompt_content = f"{PREDICTIVE_MAINTENANCE_SYSTEM_PROMPT}\n\nMACHINE HEALTH CONTEXT SNAPSHOT:\n{json.dumps(sanitized_context, indent=2)}"

        try:
            raw_response = await gemini_client.generate_response(prompt_content)
            
            # Clean markdown JSON fences if present
            cleaned_text = raw_response.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

            parsed = json.loads(cleaned_text)

            # Validate against Pydantic schema
            findings = [
                AIPredictiveMaintenanceFinding(
                    signal=f.get("signal", "OBSERVATION"),
                    observation=f.get("observation", ""),
                    importance=f.get("importance", "MEDIUM")
                )
                for f in parsed.get("findings", [])
            ]

            actions = [
                AIPredictiveMaintenanceAction(
                    priority=a.get("priority", "HIGH"),
                    action=a.get("action", ""),
                    reason=a.get("reason", ""),
                    toolName=a.get("toolName", "schedule_maintenance"),
                    parameters=a.get("parameters", {"durationMinutes": 45, "reason": "AI Predictive Maintenance"})
                )
                for a in parsed.get("recommendedActions", [])
            ]

            # Generate structured tool proposals
            proposed_tools = []
            for act in actions:
                if act.toolName:
                    params = act.parameters or {}
                    params["machineCode"] = assessment.machineCode
                    proposed_tools.append({
                        "tool": act.toolName,
                        "parameters": params
                    })

            conf = float(parsed.get("diagnosisConfidence", 0.85))
            conf = min(conf, assessment.confidenceCeiling)

            return AIPredictiveMaintenanceAssessment(
                summary=parsed.get("summary", f"Health diagnosis for machine {assessment.machineCode}."),
                failureMode=parsed.get("failureMode", "TOOL_WEAR_DEGRADATION"),
                diagnosisConfidence=round(conf, 2),
                findings=findings,
                recommendedActions=actions,
                recommendedMaintenanceWindow=parsed.get("recommendedMaintenanceWindow", "WITHIN_24_HOURS"),
                materialCorrelationNote=parsed.get("materialCorrelationNote"),
                proposedToolCalls=proposed_tools
            )

        except Exception as e:
            logger.warning(f"Gemini Predictive Maintenance generation fallback triggered: {e}")
            return AIPredictiveMaintenancePlanner._generate_fallback_assessment(assessment)
