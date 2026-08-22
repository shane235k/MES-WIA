from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query, status
from app.schemas.operator_activation import OperatorContextResponse
from app.services.operator_activation_service import OperatorActivationService

router = APIRouter(prefix="/api/operators", tags=["operators"])

@router.get("/me/context", response_model=OperatorContextResponse)
async def get_my_operator_context(
    x_operator_session: Optional[str] = Header(None, alias="X-Operator-Session"),
    sessionToken: Optional[str] = Query(None)
):
    """
    Operator Client: Fetch current operator identity and real-time shop-floor assignment.
    """
    token = x_operator_session or sessionToken
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing operator session token. Please provide X-Operator-Session header or sessionToken query param."
        )

    try:
        return await OperatorActivationService.get_operator_context(token)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
