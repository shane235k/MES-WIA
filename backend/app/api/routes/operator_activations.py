from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Header, status
from app.schemas.operator_activation import (
    OperatorActivationCreate,
    OperatorActivationRequest,
    OperatorActivationResponse,
    OperatorContextResponse
)
from app.services.operator_activation_service import OperatorActivationService

router = APIRouter(prefix="/api/operator-activations", tags=["operator-activations"])

@router.post("/generate", response_model=OperatorActivationResponse)
async def generate_activation_code(payload: OperatorActivationCreate):
    """
    Admin: Generate a one-time activation code for an operator.
    """
    try:
        return await OperatorActivationService.generate_activation_code(payload.operatorId)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/activate", response_model=OperatorActivationResponse)
async def submit_activation(payload: OperatorActivationRequest):
    """
    Operator Client: Enter activation code to register client session and request approval.
    """
    try:
        return await OperatorActivationService.submit_activation(
            activation_code=payload.activationCode,
            client_info=payload.clientInfo
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/status/{session_token}", response_model=OperatorActivationResponse)
async def get_activation_status(session_token: str):
    """
    Operator Client: Poll or verify approval status of session.
    """
    try:
        return await OperatorActivationService.get_activation_status(session_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{activation_id}/approve", response_model=OperatorActivationResponse)
async def approve_activation(activation_id: str):
    """
    Admin: Approve operator client activation.
    """
    try:
        return await OperatorActivationService.approve_activation(activation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{activation_id}/reject", response_model=OperatorActivationResponse)
async def reject_activation(activation_id: str, reason: Optional[str] = Query("Rejected by administrator")):
    """
    Admin: Reject operator client activation.
    """
    try:
        return await OperatorActivationService.reject_activation(activation_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{activation_id}/revoke", response_model=OperatorActivationResponse)
async def revoke_activation(activation_id: str):
    """
    Admin: Revoke an approved operator client.
    """
    try:
        return await OperatorActivationService.revoke_activation(activation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("", response_model=List[OperatorActivationResponse])
async def list_activations():
    """
    Admin: List all operator activation records.
    """
    try:
        return await OperatorActivationService.list_activations()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
