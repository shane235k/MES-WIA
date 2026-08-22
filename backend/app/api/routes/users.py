from typing import List
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas.user import UserCreate, UserUpdate, UserInDB
from app.services.user_service import UserService

router = APIRouter()

@router.post("", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate):
    try:
        return await UserService.create_user(user_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("", response_model=List[UserInDB])
async def list_users():
    return await UserService.list_users()

@router.get("/operators", response_model=List[UserInDB])
async def list_operators(only_available: bool = Query(False)):
    return await UserService.list_operators(only_available=only_available)

@router.get("/supervisors", response_model=List[UserInDB])
async def list_supervisors():
    return await UserService.list_supervisors()

@router.get("/{id}", response_model=UserInDB)
async def get_user(id: str):
    user = await UserService.get_user_by_id(id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.put("/{id}", response_model=UserInDB)
async def update_user(id: str, user_update: UserUpdate):
    try:
        user = await UserService.update_user(id, user_update)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: str):
    deleted = await UserService.delete_user(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
