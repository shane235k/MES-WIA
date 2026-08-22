from typing import List
from fastapi import APIRouter, HTTPException, status
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialInDB
from app.services.material_service import MaterialService

router = APIRouter()

@router.post("", response_model=MaterialInDB, status_code=status.HTTP_201_CREATED)
async def create_material(material_in: MaterialCreate):
    try:
        return await MaterialService.create_material(material_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("", response_model=List[MaterialInDB])
async def list_materials():
    return await MaterialService.list_materials()

@router.get("/{id}", response_model=MaterialInDB)
async def get_material(id: str):
    material = await MaterialService.get_material_by_id(id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return material

@router.put("/{id}", response_model=MaterialInDB)
async def update_material(id: str, material_update: MaterialUpdate):
    try:
        material = await MaterialService.update_material(id, material_update)
        if not material:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
        return material
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(id: str):
    deleted = await MaterialService.delete_material(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
