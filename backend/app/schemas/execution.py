from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class ExecutionStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ExecutionEventType(str, Enum):
    WORK_ORDER_STARTED = "WORK_ORDER_STARTED"
    WORK_ORDER_COMPLETED = "WORK_ORDER_COMPLETED"
    WORK_ORDER_PAUSED = "WORK_ORDER_PAUSED"
    WORK_ORDER_FAILED = "WORK_ORDER_FAILED"
    OPERATION_READY = "OPERATION_READY"
    OPERATION_WAITING = "OPERATION_WAITING"
    OPERATION_STARTED = "OPERATION_STARTED"
    OPERATION_COMPLETED = "OPERATION_COMPLETED"
    OPERATION_FAILED = "OPERATION_FAILED"
    OPERATION_PAUSED = "OPERATION_PAUSED"
    OPERATION_RESUMED = "OPERATION_RESUMED"
    OPERATION_REROUTED = "OPERATION_REROUTED"
    MACHINE_OCCUPIED = "MACHINE_OCCUPIED"
    MACHINE_RELEASED = "MACHINE_RELEASED"
    OPERATOR_ASSIGNED = "OPERATOR_ASSIGNED"
    OPERATOR_RELEASED = "OPERATOR_RELEASED"
    RESOURCE_WAITING = "RESOURCE_WAITING"

class ExecutionBase(BaseModel):
    workOrderId: str = Field(..., description="ObjectId of the executed WorkOrder")
    workOrderCode: str = Field(..., description="Business code of the WorkOrder")
    workflowId: str = Field(..., description="ObjectId of the executed Workflow")
    productId: str = Field(..., description="ObjectId of the Product")
    status: ExecutionStatus = Field(default=ExecutionStatus.PLANNED)
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    activeOperationsCount: int = Field(default=0)
    completedOperationsCount: int = Field(default=0)
    totalOperationsCount: int = Field(default=0)

class ExecutionCreate(ExecutionBase):
    pass

class ExecutionInDB(ExecutionBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime

class ExecutionEventBase(BaseModel):
    executionId: str = Field(..., description="ObjectId of the parent Execution")
    workOrderId: str = Field(..., description="ObjectId of the WorkOrder")
    workOrderCode: str = Field(..., description="Code of the WorkOrder")
    operationId: Optional[str] = Field(default=None, description="Operation ID within workflow, e.g. OP-10")
    machineId: Optional[str] = Field(default=None, description="ObjectId of the Machine")
    machineCode: Optional[str] = Field(default=None, description="Machine code, e.g. M-01")
    operatorId: Optional[str] = Field(default=None, description="ObjectId of the Operator")
    operatorName: Optional[str] = Field(default=None, description="Name or code of the operator")
    eventType: ExecutionEventType
    message: str = Field(..., description="Human-readable event summary")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExecutionEventCreate(ExecutionEventBase):
    pass

class ExecutionEventInDB(ExecutionEventBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
