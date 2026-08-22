from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.work_order import WorkOrderPriority, WorkOrderStatus

class AIWorkOrderSessionStatus(str, Enum):
    COLLECTING_REQUIREMENTS = "COLLECTING_REQUIREMENTS"
    AWAITING_USER_CONFIRMATION = "AWAITING_USER_CONFIRMATION"
    READY = "READY"
    CONVERTING = "CONVERTING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

class AIWorkOrderOperationDraft(BaseModel):
    operationId: str = Field(..., description="Operation identifier (e.g., OP-10)")
    name: str = Field(default="", description="Operation name")
    sequence: int = Field(default=1, description="Sequence index")
    requiredMachineType: str = Field(..., description="Required machine category")
    assignedMachineId: Optional[str] = Field(default=None, description="ObjectId of assigned Machine")
    assignedOperatorId: Optional[str] = Field(default=None, description="ObjectId of assigned Operator")
    dependencies: List[str] = Field(default_factory=list)
    requiredMaterials: List[Dict[str, Any]] = Field(default_factory=list)

class AIMaterialRequirementSummary(BaseModel):
    materialId: str
    materialName: str
    specificationName: Optional[str] = None
    unit: str
    quantityPerUnit: float
    totalRequiredQuantity: float
    unitCost: Optional[float] = None
    subtotalCost: Optional[float] = None

class AIWorkOrderDraft(BaseModel):
    productId: str = Field(..., description="ObjectId of the selected Product")
    productCode: Optional[str] = Field(default=None, description="Product code (e.g. BRACKET-A)")
    productName: Optional[str] = Field(default=None, description="Product name")
    recipeId: Optional[str] = Field(default=None, description="Recipe identifier or version tag")
    recipeVersion: Optional[int] = Field(default=1, description="Recipe version integer")
    workflowId: str = Field(..., description="ObjectId of the routing Workflow")
    workflowCode: Optional[str] = Field(default=None, description="Workflow Code")
    workflowVersion: Optional[int] = Field(default=1, ge=1, description="Workflow version")
    quantity: float = Field(..., gt=0.0, description="Number of finished product units to manufacture")
    priority: WorkOrderPriority = Field(default=WorkOrderPriority.NORMAL)
    dueDate: Optional[datetime] = Field(default=None, description="Target completion due date")
    workOrderCode: Optional[str] = Field(default=None, description="Generated or user-defined Work Order Code")
    name: Optional[str] = Field(default=None, description="Descriptive batch name")
    supervisorId: Optional[str] = Field(default=None, description="ObjectId of the assigned Shift Supervisor")
    supervisorName: Optional[str] = Field(default=None, description="Name of the supervisor")
    notes: Optional[str] = Field(default=None, description="Planner notes")
    operations: List[AIWorkOrderOperationDraft] = Field(default_factory=list)
    materialRequirements: List[AIMaterialRequirementSummary] = Field(default_factory=list)
    totalEstimatedCost: Optional[float] = Field(default=None, ge=0.0)

class AIWorkOrderResponseEnvelope(BaseModel):
    status: str = Field(..., description="NEEDS_INFORMATION | OPTIONAL_CONFIRMATION | READY | ERROR")
    message: str = Field(..., description="Natural conversational explanation for the user")
    sessionId: Optional[str] = Field(default=None, description="Active planning session ID")
    missingFields: List[str] = Field(default_factory=list, description="Mandatory fields still required")
    collectedFields: Dict[str, Any] = Field(default_factory=dict, description="Currently recognized values")
    suggestions: Dict[str, Any] = Field(default_factory=dict, description="Optional values suggested by AI")
    options: List[Dict[str, Any]] = Field(default_factory=list, description="Available selectable entity options (recipes, workflows, supervisors)")
    draft: Optional[AIWorkOrderDraft] = Field(default=None, description="Populated structured draft when READY or in review")

class AIWorkOrderSessionMessage(BaseModel):
    sender: str = Field(..., description="USER | AI")
    content: str = Field(..., description="Message text")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None

class AIWorkOrderSession(BaseModel):
    sessionId: str
    userId: str = "ADMIN"
    status: AIWorkOrderSessionStatus = AIWorkOrderSessionStatus.COLLECTING_REQUIREMENTS
    conversationHistory: List[AIWorkOrderSessionMessage] = Field(default_factory=list)
    collectedFields: Dict[str, Any] = Field(default_factory=dict)
    missingRequiredFields: List[str] = Field(default_factory=list)
    suggestedOptionalFields: Dict[str, Any] = Field(default_factory=dict)
    draft: Optional[AIWorkOrderDraft] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
