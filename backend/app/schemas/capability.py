from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class CapabilityBase(BaseModel):
    code: str = Field(..., pattern="^[A-Z0-9_-]+$", description="Unique uppercase capability code")
    name: str = Field(..., min_length=2)
    description: str

class CapabilityCreate(CapabilityBase):
    pass

class CapabilityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    description: Optional[str] = None

class CapabilityInDB(CapabilityBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
