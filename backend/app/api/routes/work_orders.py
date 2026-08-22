from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderInDB
from app.services.work_order_service import WorkOrderService
from app.services.execution_engine import ExecutionEngine

router = APIRouter()

@router.post("", response_model=WorkOrderInDB, status_code=status.HTTP_201_CREATED)
async def create_work_order(wo_in: WorkOrderCreate):
    try:
        return await WorkOrderService.create_work_order(wo_in)
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.get("", response_model=List[WorkOrderInDB])
async def list_work_orders():
    return await WorkOrderService.list_work_orders()

@router.get("/{id}", response_model=WorkOrderInDB)
async def get_work_order(id: str):
    wo = await WorkOrderService.get_work_order_by_id(id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return wo

@router.post("/{id}/start")
async def start_work_order(id: str):
    """
    Start execution of a work order. Starts eligible ready operations and sets up background concurrency.
    """
    try:
        return await ExecutionEngine.start_work_order(id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{id}/execution-state")
async def get_work_order_execution_state(id: str):
    """
    Get live reconstructed execution state with dynamic remainingSeconds, machine colors, and event logs.
    """
    state = await ExecutionEngine.get_execution_state(id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return state

@router.put("/{id}", response_model=WorkOrderInDB)
async def update_work_order(id: str, wo_update: WorkOrderUpdate):
    try:
        wo = await WorkOrderService.update_work_order(id, wo_update)
        if not wo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
        return wo
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

class PauseOperationRequest(BaseModel):
    reason: Optional[str] = "Admin paused operation node"

class ResumeOperationRequest(BaseModel):
    machineId: Optional[str] = None
    operatorId: Optional[str] = None

@router.post("/{id}/operations/{operation_id}/pause")
async def pause_operation_node(id: str, operation_id: str, body: Optional[PauseOperationRequest] = None):
    """
    Pause an active operation node in a work order. Releases current machine/operator.
    """
    reason = body.reason if body and body.reason else "Admin paused operation node"
    try:
        return await WorkOrderService.pause_operation_node(id, operation_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{id}/operations/{operation_id}/resume")
async def resume_operation_node(id: str, operation_id: str, body: Optional[ResumeOperationRequest] = None):
    """
    Resume a paused operation node. Optionally reassign machine or operator.
    """
    m_id = body.machineId if body else None
    op_id = body.operatorId if body else None
    try:
        return await WorkOrderService.resume_operation_node(id, operation_id, machine_id=m_id, operator_id=op_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(id: str):
    deleted = await WorkOrderService.delete_work_order(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
