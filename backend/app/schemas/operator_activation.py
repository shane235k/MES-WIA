from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ActivationStatus(str, Enum):
    NOT_ACTIVATED = "NOT_ACTIVATED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"

class OperatorActivationCreate(BaseModel):
    operatorId: str = Field(..., description="ID or ObjectId string of the operator user")

class OperatorActivationRequest(BaseModel):
    activationCode: str = Field(..., description="Activation code entered by operator on desktop client")
    clientInfo: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Client device / app metadata")

class OperatorActivationResponse(BaseModel):
    id: str = Field(..., description="Unique activation record ID")
    activationCode: Optional[str] = Field(None, description="Activation code (visible only to admin or on creation)")
    operatorId: str = Field(..., description="Operator User ID")
    operatorEmployeeId: str = Field(..., description="Operator Employee ID (e.g. OP-001)")
    operatorName: str = Field(..., description="Operator Full Name")
    status: ActivationStatus = Field(..., description="Current client activation status")
    sessionToken: Optional[str] = Field(None, description="Client session token for authorized requests")
    createdAt: datetime = Field(..., description="Creation timestamp")
    requestedAt: Optional[datetime] = Field(None, description="Timestamp when operator entered code")
    approvedAt: Optional[datetime] = Field(None, description="Approval timestamp")
    approvedBy: Optional[str] = Field(None, description="Admin who approved the activation")
    revokedAt: Optional[datetime] = Field(None, description="Revocation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class OperatorIdentity(BaseModel):
    id: str
    operatorId: str = Field(..., description="Employee Code (e.g. OP-001)")
    name: str
    role: str
    department: Optional[str] = None
    availabilityStatus: Optional[str] = None

class ActiveOperatorAssignment(BaseModel):
    machineId: str
    machineCode: str
    machineName: str
    machineType: str
    operationId: str
    operationName: str
    workOrderId: str
    workOrderCode: str
    status: str
    remainingSeconds: Optional[int] = 0
    waitingReason: Optional[str] = None

class OperatorContextResponse(BaseModel):
    operator: OperatorIdentity
    activationStatus: ActivationStatus
    assignment: Optional[ActiveOperatorAssignment] = None
    serverTime: datetime = Field(default_factory=datetime.utcnow)
