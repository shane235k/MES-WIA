from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
from app.schemas.incident import (
    IncidentResponse, IncidentContextResponse,
    IncidentResolveRequest, IncidentDismissRequest,
    IncidentMaintenanceRequest
)
from app.services.incident_service import IncidentService

router = APIRouter()

@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    machine_id: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None, alias="type")
):
    """
    Retrieve all recorded factory incidents with optional filtering.
    """
    return await IncidentService.list_incidents(
        status=status,
        severity=severity,
        machine_id=machine_id,
        incident_type=incident_type
    )

@router.get("/{incident_id}", response_model=IncidentContextResponse)
async def get_incident_context(incident_id: str):
    """
    Retrieve deep incident context including machine, work order, operations,
    operators, and historical telemetry for inspection and AI processing.
    """
    context = await IncidentService.get_incident_context(incident_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return context

@router.post("/{incident_id}/confirm-failure")
async def confirm_machine_failure(incident_id: str):
    """
    Admin Review: Confirm an operator report and transition the machine to DOWN state.
    """
    try:
        return await IncidentService.confirm_failure(incident_id=incident_id, admin_id="ADMIN")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(incident_id: str, request: IncidentDismissRequest):
    """
    Admin Review: Dismiss an operator report as a false alarm without altering production state.
    """
    try:
        return await IncidentService.dismiss_incident(
            incident_id=incident_id,
            reason=request.reason or "Dismissed by admin",
            admin_id=request.dismissedBy or "ADMIN"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(incident_id: str, request: IncidentResolveRequest):
    """
    Admin Action: Resolve a confirmed incident and recover the workstation to IDLE.
    """
    try:
        return await IncidentService.resolve_incident(
            incident_id=incident_id,
            resolution=request.resolution,
            admin_id=request.resolvedBy or "ADMIN"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{incident_id}/maintenance", response_model=IncidentResponse)
async def schedule_incident_maintenance(incident_id: str, request: IncidentMaintenanceRequest):
    """
    Admin Action: Put workstation in maintenance mode with an estimated recovery time.
    """
    try:
        return await IncidentService.schedule_incident_maintenance(
            incident_id=incident_id,
            duration_minutes=request.durationMinutes,
            resolution=request.resolution or "Put in maintenance for scheduled repair",
            admin_id=request.adminId or "ADMIN"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
