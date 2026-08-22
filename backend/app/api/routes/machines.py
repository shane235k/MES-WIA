from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas.machine import MachineCreate, MachineUpdate, MachineInDB
from app.services.machine_service import MachineService

router = APIRouter()

@router.post("", response_model=MachineInDB, status_code=status.HTTP_201_CREATED)
async def create_machine(machine_in: MachineCreate):
    try:
        return await MachineService.create_machine(machine_in)
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.get("", response_model=List[MachineInDB])
async def list_machines():
    return await MachineService.list_machines()

@router.get("/used-colors", response_model=List[str])
async def get_used_colors():
    return await MachineService.get_used_colors()

@router.get("/compatible", response_model=List[MachineInDB])
async def get_compatible_machines(
    capabilities: Optional[List[str]] = Query(None),
    machine_type: Optional[str] = Query(None),
    only_available: bool = Query(False)
):
    return await MachineService.find_compatible_machines(
        required_capability_ids=capabilities,
        required_machine_type=machine_type,
        only_available=only_available
    )

@router.get("/{id}", response_model=MachineInDB)
async def get_machine(id: str):
    machine = await MachineService.get_machine_by_id(id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
    return machine

@router.put("/{id}", response_model=MachineInDB)
async def update_machine(id: str, machine_update: MachineUpdate):
    try:
        machine = await MachineService.update_machine(id, machine_update)
        if not machine:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
        return machine
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine(id: str):
    deleted = await MachineService.delete_machine(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")

@router.post("/{id}/fail")
async def simulate_machine_failure(id: str, reason: Optional[str] = "Machine failure simulated"):
    """
    Deterministic Admin/Dev Failure Simulation endpoint:
    Calls the authoritative MachineService.fail_machine to transition machine to DOWN.
    """
    try:
        return await MachineService.fail_machine(
            machine_id=id,
            reason=reason or "Machine breakdown simulated by admin",
            actor_id="ADMIN"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{id}/maintenance")
async def schedule_machine_maintenance(id: str, durationMinutes: int = Query(..., gt=0), reason: Optional[str] = "Scheduled maintenance"):
    """
    Put a machine into MAINTENANCE state for a scheduled duration.
    """
    try:
        return await MachineService.schedule_maintenance(
            machine_id=id,
            duration_minutes=durationMinutes,
            reason=reason or "Scheduled maintenance",
            actor_id="ADMIN"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{id}/recover")
async def recover_machine(id: str):
    """
    Recover a machine from DOWN or MAINTENANCE to IDLE state.
    """
    try:
        return await MachineService.recover_machine(machine_id=id, actor_id="ADMIN")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
