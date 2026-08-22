from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Header, Query, status
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.schemas.machine_health import (
    MachineHealthSummary, MachineHealthAssessment
)
from app.services.machine_health_service import MachineHealthService
from app.ai.predictive_maintenance_planner import AIPredictiveMaintenancePlanner
from app.ai.tool_executor import ToolExecutor
from app.services.audit_service import AuditService

router = APIRouter()

class ActionApprovalRequest(BaseModel):
    tool: str = Field(default="schedule_maintenance", description="Safe tool name from registered catalog")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Validated tool parameters")
    adminId: Optional[str] = Field(default="ADMIN", description="Authorizing admin user ID")

@router.get("/machines", response_model=List[MachineHealthSummary])
async def list_all_machines_health():
    """
    Retrieve deterministic health summaries for all factory workstations.
    Does NOT invoke Gemini, ensuring fast response times without API rate limits.
    """
    try:
        summaries = await MachineHealthService.get_all_machines_health_summary()
        return summaries
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/alerts", response_model=List[MachineHealthSummary])
async def list_predictive_maintenance_alerts():
    """
    Retrieve workstations that require maintenance attention or have elevated risk levels.
    """
    try:
        summaries = await MachineHealthService.get_all_machines_health_summary()
        alerts = [
            s for s in summaries 
            if s.maintenanceAttention or s.riskLevel in ["CRITICAL", "HIGH", "MEDIUM"]
        ]
        return alerts
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/machines/{machine_id}", response_model=MachineHealthAssessment)
async def get_machine_health_detail(
    machine_id: str,
    timeWindowDays: int = Query(30, ge=1, le=180)
):
    """
    Retrieve deep deterministic health metrics, cycle time trends, MTBF/MTTR,
    health score breakdown, and material traceability correlations for a specific machine.
    """
    try:
        assessment = await MachineHealthService.get_machine_health_metrics(
            machine_id=machine_id,
            time_window_days=timeWindowDays
        )
        return assessment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/machines/{machine_id}/assess", response_model=MachineHealthAssessment)
async def assess_machine_with_ai(
    machine_id: str,
    actorId: Optional[str] = Query("ADMIN"),
    timeWindowDays: int = Query(30, ge=1, le=180)
):
    """
    Executes Google Gemini predictive maintenance analysis using sanitized context snapshot.
    Validates output, persists assessment in append-only db.machine_health_records,
    and returns complete diagnostic result.
    """
    try:
        # 1. Gather authoritative deterministic metrics
        assessment = await MachineHealthService.get_machine_health_metrics(
            machine_id=machine_id,
            time_window_days=timeWindowDays
        )

        # 2. Invoke Gemini reasoning engine
        ai_result = await AIPredictiveMaintenancePlanner.assess_machine_health(
            assessment=assessment,
            actor_id=actorId or "ADMIN"
        )
        assessment.aiAssessment = ai_result

        # 3. Persist assessment to append-only history collection
        await MachineHealthService.save_health_assessment(assessment)

        # 4. Log audit event
        await AuditService.log_event(
            actor_id=actorId or "ADMIN",
            actor_type="USER",
            action="AI_PREDICTIVE_MAINTENANCE_ASSESSED",
            entity_type="machine",
            entity_id=assessment.machineId,
            source="ADMIN",
            metadata={
                "machineCode": assessment.machineCode,
                "healthScore": assessment.healthScore,
                "riskLevel": assessment.riskLevel.value,
                "dataQuality": assessment.dataQuality.value,
                "failureMode": ai_result.failureMode
            }
        )

        return assessment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/machines/{machine_id}/history")
async def get_machine_health_history(
    machine_id: str,
    limit: int = Query(20, ge=1, le=100)
):
    """
    Retrieve historical AI predictive maintenance assessments for trend visualization.
    """
    try:
        history = await MachineHealthService.get_health_history(machine_id=machine_id, limit=limit)
        return history
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/alerts")
async def get_maintenance_alerts():
    """
    Return all factory workstations requiring supervisor review, maintenance attention,
    or exhibiting High/Critical risk levels.
    """
    try:
        alerts = await MachineHealthService.get_maintenance_alerts()
        return alerts
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/machines/{machine_id}/approve-action")
async def approve_and_execute_maintenance_action(
    machine_id: str,
    request: ActionApprovalRequest
):
    """
    Strict Admin Approval Gateway:
    Authoritatively validates and executes an approved maintenance action via the existing
    Safe Tool Registry and MachineService. Gemini cannot mutate state directly.
    """
    admin_id = request.adminId or "ADMIN"
    tool_name = request.tool

    # 1. Fetch Machine
    assessment = await MachineHealthService.get_machine_health_metrics(machine_id)
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Machine '{machine_id}' not found")

    # 2. Validate Action against Safe Tool Registry
    if tool_name != "schedule_maintenance":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{tool_name}' is not authorized for predictive maintenance execution. Supported tool: 'schedule_maintenance'."
        )

    # 3. Parameter Validation
    params = dict(request.parameters)
    params["machineId"] = assessment.machineId
    params["machineCode"] = assessment.machineCode

    duration = params.get("durationMinutes")
    if not duration or not isinstance(duration, (int, float)) or duration <= 0:
        params["durationMinutes"] = 45  # Sensible default duration

    if not params.get("reason"):
        params["reason"] = f"Approved AI Predictive Maintenance on {assessment.machineCode}"

    try:
        # 4. Authoritative Execution via existing ToolExecutor
        execution_result = await ToolExecutor.execute_tool(
            tool_name=tool_name,
            parameters=params,
            actor_id=admin_id
        )

        # 5. Log Authoritative Audit Record
        await AuditService.log_event(
            actor_id=admin_id,
            actor_type="USER",
            action="PREDICTIVE_MAINTENANCE_APPROVED",
            entity_type="machine",
            entity_id=assessment.machineId,
            source="ADMIN",
            metadata={
                "machineCode": assessment.machineCode,
                "tool": tool_name,
                "parameters": params,
                "healthScore": assessment.healthScore,
                "riskLevel": assessment.riskLevel.value
            }
        )

        return {
            "success": True,
            "message": f"Maintenance action approved and scheduled for machine {assessment.machineCode}.",
            "execution": execution_result
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
