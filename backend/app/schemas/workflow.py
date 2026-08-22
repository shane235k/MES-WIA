from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class RequiredMaterial(BaseModel):
    materialId: str = Field(..., description="ObjectId of the required Material")
    specificationId: Optional[str] = Field(default=None, description="Optional ObjectId of the MaterialSpecification")
    quantity: float = Field(..., gt=0.0, description="Quantity required, must be positive")
    unit: Optional[str] = Field(default=None, description="Optional unit of measure")

class WorkflowOperation(BaseModel):
    operationId: str = Field(..., description="Unique operation ID within the workflow, e.g. OP-10")
    name: str = Field(..., min_length=2)
    sequence: int = Field(..., gt=0, description="Step sequence number, must be positive")
    description: Optional[str] = Field(default="", description="Detailed step instructions")
    requiredCapabilityIds: List[str] = Field(default_factory=list, description="Required Capability ObjectIds")
    requiredMachineType: Optional[str] = Field(default=None, description="Required generic machine type")
    assignedMachineId: Optional[str] = Field(default=None, description="ObjectId of assigned Machine")
    assignedOperatorId: Optional[str] = Field(default=None, description="ObjectId of assigned Operator User")
    estimatedDurationSeconds: int = Field(default=60, gt=0, description="Estimated duration in seconds, must be positive")
    dependencies: List[str] = Field(default_factory=list, description="Operation IDs this step depends on")
    requiredMaterials: List[RequiredMaterial] = Field(default_factory=list)
    quantityRules: Dict[str, Any] = Field(default_factory=dict)

class WorkflowBase(BaseModel):
    workflowCode: str = Field(..., pattern="^[A-Z0-9_-]+$")
    name: str = Field(..., min_length=2)
    productId: str = Field(..., description="ObjectId of the associated Product")
    recipeId: Optional[str] = Field(default=None, description="RecipeId from which this workflow was derived")
    supervisorId: Optional[str] = Field(default=None, description="ObjectId of the assigned Supervisor User")
    version: int = Field(default=1, ge=1)
    status: WorkflowStatus = Field(default=WorkflowStatus.DRAFT)
    operations: List[WorkflowOperation] = Field(default_factory=list)
    createdBy: str = Field(default="SYSTEM")

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    productId: Optional[str] = None
    recipeId: Optional[str] = None
    supervisorId: Optional[str] = None
    version: Optional[int] = Field(None, ge=1)
    status: Optional[WorkflowStatus] = None
    operations: Optional[List[WorkflowOperation]] = None

class WorkflowInDB(WorkflowBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
