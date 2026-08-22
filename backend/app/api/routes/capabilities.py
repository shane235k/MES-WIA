from typing import List
from fastapi import APIRouter, HTTPException, status
from app.schemas.capability import CapabilityCreate, CapabilityUpdate, CapabilityInDB
from app.services.capability_service import CapabilityService

router = APIRouter()

@router.post("", response_model=CapabilityInDB, status_code=status.HTTP_201_CREATED)
async def create_capability(capability_in: CapabilityCreate):
    try:
        return await CapabilityService.create_capability(capability_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("", response_model=List[CapabilityInDB])
async def list_capabilities():
    return await CapabilityService.list_capabilities()

@router.get("/{id}", response_model=CapabilityInDB)
async def get_capability(id: str):
    capability = await CapabilityService.get_capability_by_id(id)
    if not capability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability not found")
    return capability

@router.put("/{id}", response_model=CapabilityInDB)
async def update_capability(id: str, capability_update: CapabilityUpdate):
    capability = await CapabilityService.update_capability(id, capability_update)
    if not capability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability not found")
    return capability

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capability(id: str):
    deleted = await CapabilityService.delete_capability(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability not found")
