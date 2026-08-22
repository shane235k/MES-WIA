from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
from app.ai.schemas import AIOperationResponse, AILifecycleStatus
from app.ai.orchestrator import AIOrchestrator

router = APIRouter(prefix="/api/ai", tags=["AI Operations"])

@router.post("/investigate/{incident_id}", response_model=AIOperationResponse)
async def investigate_incident(incident_id: str, requested_by: str = Query("ADMIN")):
    """
    Stage 1 & 2: Trigger AI diagnostic investigation on a production incident.
    Returns structured findings (summary, observations, impact, confidence, recommendation).
    Does NOT modify shop-floor state.
    """
    try:
        return await AIOrchestrator.start_investigation(incident_id=incident_id, requested_by=requested_by)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/operations", response_model=List[AIOperationResponse])
async def list_ai_operations():
    """
    Retrieve historical AI investigation and action planning sessions.
    """
    return await AIOrchestrator.list_operations()

@router.get("/operations/{id}", response_model=AIOperationResponse)
async def get_ai_operation(id: str):
    """
    Retrieve details of a specific AI Operation session.
    """
    op = await AIOrchestrator.get_operation(id)
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Operation not found")
    return op

@router.get("/operations/incident/{incident_id}", response_model=Optional[AIOperationResponse])
async def get_incident_ai_operation(incident_id: str):
    """
    Retrieve the latest AI operation associated with a given incident.
    """
    return await AIOrchestrator.get_active_by_incident(incident_id)

@router.post("/operations/{id}/generate-action-plan", response_model=AIOperationResponse)
@router.post("/operations/{id}/action-plan", response_model=AIOperationResponse)
async def generate_action_plan(id: str, requested_by: str = Query("ADMIN")):
    """
    Stage 3 & 4: Generate concrete proposed actions mapping to safe registered tools.
    """
    try:
        return await AIOrchestrator.generate_action_plan(ai_operation_id=id, requested_by=requested_by)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/operations/{id}/verify-ollama", response_model=AIOperationResponse)
async def verify_with_ollama(id: str, requested_by: str = Query("ADMIN")):
    """
    Stage 5: Optional advisory verification of the action plan using local Ollama.
    """
    try:
        return await AIOrchestrator.verify_with_ollama(ai_operation_id=id, requested_by=requested_by)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/operations/{id}/reinvestigate-with-feedback", response_model=AIOperationResponse)
async def reinvestigate_with_feedback(id: str, requested_by: str = Query("ADMIN")):
    """
    Send Ollama verification feedback back to Gemini to re-evaluate the diagnosis in Stage 1.
    """
    try:
        return await AIOrchestrator.reinvestigate_with_feedback(ai_operation_id=id, requested_by=requested_by)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/operations/{id}/approve-execute", response_model=AIOperationResponse)
@router.post("/operations/{id}/execute", response_model=AIOperationResponse)
async def approve_and_execute(id: str, admin_id: str = Query("ADMIN")):
    """
    Stage 6: Mandatory Admin approval. Sequentially executes the approved safe tool calls on the MES.
    """
    try:
        return await AIOrchestrator.approve_and_execute(ai_operation_id=id, admin_id=admin_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/operations/{id}/reject", response_model=AIOperationResponse)
async def reject_investigation(id: str, admin_id: str = Query("ADMIN"), reason: str = Query("Rejected by Admin")):
    """
    Admin action to reject AI investigation findings.
    """
    try:
        return await AIOrchestrator.reject_investigation(ai_operation_id=id, admin_id=admin_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/status")
async def get_ai_status():
    """
    Get current AI engine status, active model, and simulation mode flag.
    """
    from app.ai.gemini_client import gemini_client
    return gemini_client.get_status()

@router.post("/simulation-mode")
async def toggle_simulation_mode(enabled: Optional[bool] = Query(None)):
    """
    Toggle or explicitly set AI outage / fallback simulation mode.
    """
    from app.ai.gemini_client import gemini_client
    new_state = (not gemini_client.is_simulation_mode) if enabled is None else enabled
    gemini_client.set_simulation_mode(new_state)
    return gemini_client.get_status()
