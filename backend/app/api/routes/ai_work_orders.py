from fastapi import APIRouter, HTTPException, Query, status, Body
from typing import Dict, Any, Optional
from app.schemas.ai_work_order import AIWorkOrderResponseEnvelope, AIWorkOrderDraft
from app.services.ai_work_order_service import AIWorkOrderService

router = APIRouter(prefix="/api/ai/work-orders", tags=["AI Work Orders"])

@router.post("/session")
async def create_session(user_id: str = Query("ADMIN")):
    """Initialize a new AI Work Order requirement collection session."""
    try:
        return await AIWorkOrderService.create_session(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve the current session and draft state."""
    session = await AIWorkOrderService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")
    return session

@router.post("/session/{session_id}/message", response_model=AIWorkOrderResponseEnvelope)
async def send_message(session_id: str, payload: Dict[str, str] = Body(...)):
    """Send natural language instruction/response to AI Work Order planning session."""
    message = payload.get("message")
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty.")
    try:
        return await AIWorkOrderService.process_user_message(session_id, message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/validate-draft")
async def validate_draft(draft: Dict[str, Any] = Body(...)):
    """Validates an AI-generated or user-edited draft against authoritative database entities."""
    try:
        return await AIWorkOrderService.validate_draft(draft)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/create")
async def create_work_order(draft: Dict[str, Any] = Body(...), actor_id: str = Query("ADMIN")):
    """Converts a validated AI Draft into an authoritative Work Order in the MES."""
    try:
        return await AIWorkOrderService.create_work_order_from_draft(draft, actor_id=actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
