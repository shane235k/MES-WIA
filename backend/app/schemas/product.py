from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class RecipeStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class RequiredMaterial(BaseModel):
    materialId: str = Field(..., description="ObjectId of the required Material")
    specificationId: Optional[str] = Field(default=None, description="Optional ObjectId of the MaterialSpecification")
    quantity: float = Field(..., gt=0.0, description="Quantity required per unit, must be positive")
    unit: Optional[str] = Field(default=None, description="Optional unit of measure")

class RecipeStep(BaseModel):
    stepId: str = Field(..., description="Unique step identifier, e.g. STEP-10")
    sequence: int = Field(..., gt=0, description="Sequence order of the step")
    name: str = Field(..., min_length=2)
    description: Optional[str] = Field(default="", description="Detailed step instructions")
    requiredCapabilityIds: List[str] = Field(default_factory=list, description="List of required Capability ObjectIds")
    requiredMachineType: str = Field(..., description="Generic machine type required, e.g. CUTTING, BENDING, WELDING")
    estimatedQuantityRate: Optional[float] = Field(default=None, gt=0, description="Expected processing rate (units/sec)")
    unit: str = Field(default="pcs", description="Unit of measure")
    dependencies: List[str] = Field(default_factory=list, description="List of stepIds this step depends on")
    requiredMaterials: List[RequiredMaterial] = Field(default_factory=list)
    quantityRules: Dict[str, Any] = Field(default_factory=dict)

class ProductRecipe(BaseModel):
    recipeId: str = Field(..., description="Unique recipe code, e.g. RECIPE-BRACKET-A-V1")
    recipeName: str = Field(..., min_length=2)
    version: int = Field(default=1, ge=1)
    status: RecipeStatus = Field(default=RecipeStatus.ACTIVE)
    steps: List[RecipeStep] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class ProductBase(BaseModel):
    productCode: str = Field(..., pattern="^[A-Z0-9_-]+$", description="Unique product identifier code")
    name: str = Field(..., min_length=2)
    description: str
    unit: str = Field(default="pcs", description="Stock unit of measure, e.g. pcs, kg, meters")
    active: bool = Field(default=True)
    recipes: List[ProductRecipe] = Field(default_factory=list, description="Canonical recipes for manufacturing this product")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    description: Optional[str] = None
    unit: Optional[str] = None
    active: Optional[bool] = None
    recipes: Optional[List[ProductRecipe]] = None

class ProductInDB(ProductBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
