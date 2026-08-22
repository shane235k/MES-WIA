from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class MaterialForm(str, Enum):
    SHEET = "SHEET"
    ROD = "ROD"
    BAR = "BAR"
    TUBE = "TUBE"
    WIRE = "WIRE"
    POWDER = "POWDER"
    LIQUID = "LIQUID"
    FASTENER = "FASTENER"
    ELECTRONIC = "ELECTRONIC"
    CUSTOM = "CUSTOM"

class MaterialDimensions(BaseModel):
    thicknessMm: Optional[float] = None
    widthMm: Optional[float] = None
    lengthMm: Optional[float] = None
    diameterMm: Optional[float] = None
    outerDiameterMm: Optional[float] = None
    wallThicknessMm: Optional[float] = None
    customAttributes: Dict[str, Any] = Field(default_factory=dict)

class MaterialSpecificationBase(BaseModel):
    specificationCode: str = Field(..., pattern="^[A-Z0-9_-]+$", description="Unique specification identifier code")
    name: str = Field(..., min_length=2)
    category: MaterialForm = Field(default=MaterialForm.SHEET)
    grade: Optional[str] = Field(default=None, description="Alloy or material grade, e.g. SS304, AL6061-T6")
    dimensions: MaterialDimensions = Field(default_factory=MaterialDimensions)
    densityGcm3: Optional[float] = Field(default=None, ge=0.0, description="Material density in g/cm3")
    unitOfMeasure: str = Field(default="sheets", description="Unit of measure, e.g. sheets, meters, kg, pcs")
    active: bool = Field(default=True)

class MaterialSpecificationCreate(MaterialSpecificationBase):
    pass

class MaterialSpecificationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    category: Optional[MaterialForm] = None
    grade: Optional[str] = None
    dimensions: Optional[MaterialDimensions] = None
    densityGcm3: Optional[float] = None
    unitOfMeasure: Optional[str] = None
    active: Optional[bool] = None

class MaterialSpecificationInDB(MaterialSpecificationBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
