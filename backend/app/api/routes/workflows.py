from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowInDB
from app.services.workflow_service import WorkflowService

router = APIRouter()

class GenerateCodeRequest(BaseModel):
    productCode: str

class AutoAssignRequest(BaseModel):
    operations: List[Dict[str, Any]]

@router.post("/generate-code")
async def generate_code(req: GenerateCodeRequest):
    code = WorkflowService.generate_default_workflow_code(req.productCode)
    return {"workflowCode": code}

@router.post("/auto-assign")
async def auto_assign_resources(req: AutoAssignRequest):
    assigned = await WorkflowService.auto_assign_resources(req.operations)
    return {"operations": assigned}

@router.post("", response_model=WorkflowInDB, status_code=status.HTTP_201_CREATED)
async def create_workflow(workflow_in: WorkflowCreate):
    try:
        return await WorkflowService.create_workflow(workflow_in)
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.get("", response_model=List[WorkflowInDB])
async def list_workflows(product_id: Optional[str] = Query(None)):
    return await WorkflowService.list_workflows(product_id)

@router.get("/{id}", response_model=WorkflowInDB)
async def get_workflow(id: str):
    wf = await WorkflowService.get_workflow_by_id(id)
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return wf

@router.put("/{id}", response_model=WorkflowInDB)
async def update_workflow(id: str, wf_update: WorkflowUpdate):
    try:
        wf = await WorkflowService.update_workflow(id, wf_update)
        if not wf:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return wf
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{id}/validate")
async def validate_workflow(id: str):
    wf = await WorkflowService.get_workflow_by_id(id)
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    is_valid, errors = await WorkflowService.validate_workflow_operations(
        wf["productId"], wf["operations"], wf.get("supervisorId")
    )
    return {"valid": is_valid, "errors": errors}

@router.post("/{id}/activate", response_model=WorkflowInDB)
async def activate_workflow(id: str):
    try:
        return await WorkflowService.activate_workflow(id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(id: str):
    deleted = await WorkflowService.delete_workflow(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
