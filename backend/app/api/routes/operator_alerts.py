from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Query, status
from app.core.database import get_db
from app.schemas.incident import OperatorAlertRequest, IncidentResponse
from app.services.incident_service import IncidentService

router = APIRouter()

@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_operator_alert(
    request: OperatorAlertRequest,
    x_operator_session: Optional[str] = Header(None, alias="X-Operator-Session")
):
    """
    Operator Intake API:
    Allows operators to report machine issues. Creates a PENDING_REVIEW incident without
    mutating machine state directly until reviewed and confirmed by an Admin.
    """
    op_id = request.operatorId

    # If operatorId not in request body, derive from approved session
    if (not op_id or op_id == "OPERATOR") and x_operator_session:
        db = get_db()
        activation = await db.operator_activations.find_one({
            "sessionToken": x_operator_session,
            "status": "APPROVED"
        })
        if activation:
            op_id = activation.get("operatorId") or activation.get("operatorEmployeeId")

    if not op_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator identity required. Provide operatorId in payload or X-Operator-Session header."
        )

    try:
        incident = await IncidentService.create_operator_alert(
            operator_id=op_id,
            message=request.message,
            machine_id=request.machineId
        )
        return incident
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/my-alerts", response_model=List[IncidentResponse])
async def get_my_operator_alerts(
    x_operator_session: Optional[str] = Header(None, alias="X-Operator-Session"),
    operatorId: Optional[str] = Query(None)
):
    """
    Fetch all incidents submitted by the authenticated operator.
    """
    op_id = operatorId
    if not op_id and x_operator_session:
        db = get_db()
        activation = await db.operator_activations.find_one({
            "sessionToken": x_operator_session,
            "status": "APPROVED"
        })
        if activation:
            op_id = activation.get("operatorId") or activation.get("operatorEmployeeId")

    if not op_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token or operatorId required to view submitted reports."
        )

    try:
        return await IncidentService.get_operator_reports(op_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
