from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class IncidentType(str, Enum):
    MACHINE_FAILURE = "MACHINE_FAILURE"
    MACHINE_DOWN = "MACHINE_DOWN"
    OPERATION_FAILURE = "OPERATION_FAILURE"
    PRODUCTION_DELAY = "PRODUCTION_DELAY"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    OTHER = "OTHER"

class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IncidentStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

class IncidentBase(BaseModel):
    incidentCode: str = Field(..., description="Unique sequential identifier, e.g. INC-0001")
    type: IncidentType = Field(default=IncidentType.MACHINE_FAILURE)
    severity: IncidentSeverity = Field(default=IncidentSeverity.HIGH)
    status: IncidentStatus = Field(default=IncidentStatus.PENDING_REVIEW)
    title: str = Field(..., min_length=2)
    description: str = Field(default="")
    machineId: Optional[str] = Field(default=None, description="ObjectId of affected machine")
    machineCode: Optional[str] = Field(default=None, description="Code of affected machine, e.g. M-03")
    machineType: Optional[str] = Field(default=None, description="Type of machine, e.g. CUTTING, WELDING")
    operatorId: Optional[str] = Field(default=None, description="ObjectId of assigned/reporting operator")
    operatorName: Optional[str] = Field(default=None, description="Name of operator")
    workOrderId: Optional[str] = Field(default=None, description="ObjectId of active work order")
    workOrderCode: Optional[str] = Field(default=None, description="Code of active work order, e.g. WO-1001")
    queuedWorkOrders: List[str] = Field(default_factory=list, description="Codes of other queued work orders impacted")
    executionId: Optional[str] = Field(default=None, description="Active execution trace ID")
    operationId: Optional[str] = Field(default=None, description="Active operation ID, e.g. OP-30")
    reportedAt: datetime = Field(default_factory=datetime.utcnow)
    detectedAt: Optional[datetime] = None
    resolvedAt: Optional[datetime] = None
    reportedBy: str = Field(default="SYSTEM", description="Operator ID or Actor ID")
    resolvedBy: Optional[str] = None
    resolution: Optional[str] = None
    dismissalReason: Optional[str] = None
    maintenanceEstimatedEnd: Optional[datetime] = None
    maintenanceDurationMinutes: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class IncidentCreate(BaseModel):
    type: IncidentType = Field(default=IncidentType.MACHINE_FAILURE)
    severity: IncidentSeverity = Field(default=IncidentSeverity.HIGH)
    status: IncidentStatus = Field(default=IncidentStatus.PENDING_REVIEW)
    title: str = Field(..., min_length=2)
    description: str = Field(default="")
    machineId: Optional[str] = None
    machineCode: Optional[str] = None
    machineType: Optional[str] = None
    operatorId: Optional[str] = None
    operatorName: Optional[str] = None
    workOrderId: Optional[str] = None
    workOrderCode: Optional[str] = None
    executionId: Optional[str] = None
    operationId: Optional[str] = None
    reportedBy: str = "SYSTEM"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class IncidentUpdate(BaseModel):
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    resolution: Optional[str] = None
    resolvedBy: Optional[str] = None
    dismissalReason: Optional[str] = None
    maintenanceEstimatedEnd: Optional[datetime] = None
    maintenanceDurationMinutes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class IncidentResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=3, description="Detailed explanation of the resolution/fix")
    resolvedBy: Optional[str] = Field(default="ADMIN", description="Actor or admin ID")

class IncidentMaintenanceRequest(BaseModel):
    durationMinutes: int = Field(..., gt=0, description="Estimated repair duration in minutes")
    resolution: Optional[str] = Field(default="Put in maintenance for scheduled repair", description="Repair notes")
    adminId: Optional[str] = Field(default="ADMIN", description="Admin user ID")

class IncidentDismissRequest(BaseModel):
    reason: Optional[str] = Field(default="Report evaluated as false alarm / dismissed by admin", description="Reason for dismissal")
    dismissedBy: Optional[str] = Field(default="ADMIN", description="Admin user ID")

class OperatorAlertRequest(BaseModel):
    operatorId: str = Field(..., description="Employee ID or User ID of operator reporting the issue")
    message: str = Field(..., min_length=2, description="Observation or breakdown description")
    machineId: Optional[str] = Field(default=None, description="Optional machine ID or machine code")

class MachineFailRequest(BaseModel):
    reason: str = Field(default="Machine stopped unexpectedly", description="Reason for failure simulation")
    reportedBy: str = Field(default="ADMIN", description="Admin or supervisor ID triggering the failure")

class IncidentInDB(IncidentBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime

class IncidentResponse(IncidentBase):
    id: str

class IncidentContextResponse(BaseModel):
    incident: IncidentResponse
    machine: Optional[Dict[str, Any]] = None
    workOrder: Optional[Dict[str, Any]] = None
    operation: Optional[Dict[str, Any]] = None
    reportingOperator: Optional[Dict[str, Any]] = None
    assignedOperator: Optional[Dict[str, Any]] = None
    supervisor: Optional[Dict[str, Any]] = None
    downstreamOperations: List[Dict[str, Any]] = Field(default_factory=list)
    recentExecutionEvents: List[Dict[str, Any]] = Field(default_factory=list)
    recentAuditEvents: List[Dict[str, Any]] = Field(default_factory=list)
