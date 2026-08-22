from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class MaterialBase(BaseModel):
    materialCode: str = Field(..., pattern="^[A-Z0-9_-]+$", description="Unique material identifier code")
    name: str = Field(..., min_length=2)
    unit: str = Field(..., description="Stock unit of measure, e.g. kg, sheets, liters")
    quantityAvailable: float = Field(default=0.0, ge=0.0, description="Available stock quantity, cannot be negative")
    quantityOnHand: float = Field(default=0.0, ge=0.0, description="Aggregated physical on-hand quantity from lots")
    quantityReserved: float = Field(default=0.0, ge=0.0, description="Aggregated reserved quantity from lots")
    reorderLevel: float = Field(default=0.0, ge=0.0, description="Minimum stock level before reorder, cannot be negative")
    active: bool = Field(default=True)
    specificationId: Optional[str] = Field(default=None, description="Optional linked MaterialSpecification ObjectId")
    category: Optional[str] = Field(default=None, description="Material category/form, e.g. SHEET, ROD, TUBE")
    grade: Optional[str] = Field(default=None, description="Material grade, e.g. SS304, AL6061")
    dimensions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Physical dimensions")
    density: Optional[float] = Field(default=None, ge=0.0, description="Density in g/cm3")
    unitCost: Optional[float] = Field(default=None, ge=0.0, description="Standard / default material unit cost")

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    unit: Optional[str] = None
    quantityAvailable: Optional[float] = Field(None, ge=0.0)
    quantityOnHand: Optional[float] = Field(None, ge=0.0)
    quantityReserved: Optional[float] = Field(None, ge=0.0)
    reorderLevel: Optional[float] = Field(None, ge=0.0)
    active: Optional[bool] = None
    specificationId: Optional[str] = None
    category: Optional[str] = None
    grade: Optional[str] = None
    dimensions: Optional[Dict[str, Any]] = None
    density: Optional[float] = None
    unitCost: Optional[float] = None

class MaterialInDB(MaterialBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
