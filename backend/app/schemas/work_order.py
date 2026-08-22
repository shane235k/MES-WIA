from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class WorkOrderStatus(str, Enum):
    PLANNED = "PLANNED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_MATERIAL = "WAITING_FOR_MATERIAL"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class WorkOrderPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"

class WorkOrderOperationStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    WAITING_FOR_RESOURCE = "WAITING_FOR_RESOURCE"
    WAITING_FOR_MATERIAL = "WAITING_FOR_MATERIAL"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    INTERRUPTED = "INTERRUPTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class WorkOrderRequiredMaterialSnapshot(BaseModel):
    materialId: str = Field(..., description="ObjectId of the required Material")
    specificationId: Optional[str] = Field(default=None, description="Optional ObjectId of the MaterialSpecification")
    materialName: Optional[str] = Field(default=None, description="Cached name of the required material")
    specificationName: Optional[str] = Field(default=None, description="Cached name of the specification")
    unit: Optional[str] = Field(default=None, description="Stock unit of measure")
    quantityPerUnit: float = Field(..., gt=0.0, description="Quantity required per finished product unit")
    totalRequiredQuantity: float = Field(..., gt=0.0, description="Total quantity required for this work order batch")
    quantityReserved: float = Field(default=0.0, ge=0.0, description="Total quantity currently reserved across lots")
    quantityConsumed: float = Field(default=0.0, ge=0.0, description="Total quantity consumed upon completion")
    unitCost: Optional[float] = Field(default=None, ge=0.0, description="Estimated unit cost")
    estimatedCost: Optional[float] = Field(default=None, ge=0.0, description="Total estimated cost (totalRequiredQuantity * unitCost)")
    actualCost: Optional[float] = Field(default=None, ge=0.0, description="Total actual cost consumed")

class WorkOrderOperation(BaseModel):
    operationId: str = Field(..., description="Corresponds to WorkflowOperation operationId")
    name: str = Field(default="", description="Operation step name")
    sequence: int = Field(..., description="Step sequence number")
    assignedMachineId: Optional[str] = Field(default=None, description="ObjectId of the assigned machine")
    assignedOperatorId: Optional[str] = Field(default=None, description="ObjectId of the assigned operator")
    status: WorkOrderOperationStatus = Field(default=WorkOrderOperationStatus.PENDING)
    waitingReason: Optional[str] = Field(default=None, description="Explanation when waiting for resource")
    dependencies: List[str] = Field(default_factory=list, description="Operation IDs this step depends on")
    requiredMaterials: List[WorkOrderRequiredMaterialSnapshot] = Field(default_factory=list, description="Immutable material requirement snapshot")
    startedAt: Optional[datetime] = None
    estimatedCompletionAt: Optional[datetime] = None
    actualStart: Optional[datetime] = None
    actualEnd: Optional[datetime] = None
    durationSeconds: Optional[float] = None
    inputQuantity: float = Field(default=0.0, ge=0.0, description="Input production quantity received from predecessors")
    processedQuantity: float = Field(default=0.0, ge=0.0, description="Production units processed by this operation")
    outputQuantity: float = Field(default=0.0, ge=0.0, description="Good production units passed downstream")
    scrapQuantity: float = Field(default=0.0, ge=0.0, description="Defective/scrapped units during this operation")
    quantityCompleted: float = Field(default=0.0, ge=0.0)
    quantityRejected: float = Field(default=0.0, ge=0.0)

class WorkOrderBase(BaseModel):
    workOrderCode: str = Field(..., pattern="^[A-Z0-9_-]+$")
    name: Optional[str] = Field(default="", description="Descriptive Name or Batch Title")
    productId: str = Field(..., description="ObjectId of the associated Product")
    workflowId: str = Field(..., description="ObjectId of the selected template Workflow")
    workflowVersion: Optional[int] = Field(default=1, ge=1, description="Version of the selected template Workflow")
    supervisorId: Optional[str] = Field(default=None, description="ObjectId of the assigned Supervisor")
    quantity: float = Field(..., gt=0.0, description="Target quantity to produce, must be positive")
    priority: WorkOrderPriority = Field(default=WorkOrderPriority.NORMAL)
    dueDate: Optional[datetime] = Field(default=None)
    status: WorkOrderStatus = Field(default=WorkOrderStatus.PLANNED)
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    createdBy: str = Field(default="SYSTEM")

class WorkOrderCreate(WorkOrderBase):
    dueDate: datetime = Field(..., description="Target completion timestamp")
    operations: Optional[List[dict]] = None

class WorkOrderUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[WorkOrderStatus] = None
    priority: Optional[WorkOrderPriority] = None
    dueDate: Optional[datetime] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    operations: Optional[List[WorkOrderOperation]] = None

class WorkOrderInDB(WorkOrderBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    operations: List[WorkOrderOperation] = Field(default_factory=list)
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

