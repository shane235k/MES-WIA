from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class AILifecycleStatus(str, Enum):
    AI_INVESTIGATION_REQUESTED = "AI_INVESTIGATION_REQUESTED"
    AI_INVESTIGATING = "AI_INVESTIGATING"
    AI_INVESTIGATION_READY = "AI_INVESTIGATION_READY"
    AI_ACTION_PLAN_REQUESTED = "AI_ACTION_PLAN_REQUESTED"
    AI_ACTION_PLAN_READY = "AI_ACTION_PLAN_READY"
    AI_VERIFICATION_REQUESTED = "AI_VERIFICATION_REQUESTED"
    AI_VERIFICATION_COMPLETE = "AI_VERIFICATION_COMPLETE"
    AI_EXECUTION_APPROVED = "AI_EXECUTION_APPROVED"
    AI_EXECUTING = "AI_EXECUTING"
    AI_EXECUTION_COMPLETE = "AI_EXECUTION_COMPLETE"
    AI_EXECUTION_FAILED = "AI_EXECUTION_FAILED"
    REJECTED = "REJECTED"

class AIInvestigationFinding(BaseModel):
    summary: str = Field(..., description="High-level incident analysis summary")
    observations: List[str] = Field(default_factory=list, description="Key empirical observations from MES telemetry")
    affectedResources: List[str] = Field(default_factory=list, description="Machines, workstations, or operators affected")
    affectedOperations: List[str] = Field(default_factory=list, description="Work order operations impacted or halted")
    possibleImpact: str = Field(default="", description="Production schedule, throughput, and bottleneck impact analysis")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence score from AI model")
    recommendation: Optional[str] = Field(default=None, description="Proposed high-level recovery course of action")

class AIToolAction(BaseModel):
    tool: str = Field(..., description="Name of the safe registered tool to execute")
    version: str = Field(default="1.0", description="Tool interface version")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Exact parameters to pass to the tool")
    reason: str = Field(..., description="Justification for this specific operational action")
    expectedEffect: str = Field(..., description="Expected shop-floor state transition upon execution")

class AIActionPlan(BaseModel):
    summary: str = Field(..., description="Summary of the proposed recovery sequence")
    actions: List[AIToolAction] = Field(default_factory=list, description="Ordered sequence of safe registered tool calls")

class AIOllamaVerification(BaseModel):
    status: str = Field(..., description="VALID, INVALID, or UNAVAILABLE")
    explanation: str = Field(..., description="Advisory explanation comparing tool sequence to recommendation")
    invalidSteps: List[Union[str, Dict[str, Any]]] = Field(default_factory=list, description="List of step descriptions or tool objects that diverge from recommendation")

class AIOperationBase(BaseModel):
    operationId: str = Field(..., description="Unique business identifier, e.g. AI-OP-0001")
    incidentId: str = Field(..., description="Associated Incident ObjectId")
    incidentCode: Optional[str] = Field(default=None, description="Incident business code, e.g. INC-0003")
    workOrderId: Optional[str] = Field(default=None, description="Impacted WorkOrder ObjectId")
    workOrderCode: Optional[str] = Field(default=None, description="Impacted WorkOrder business code")
    machineId: Optional[str] = Field(default=None, description="Impacted Machine ObjectId")
    machineCode: Optional[str] = Field(default=None, description="Impacted Machine business code")
    status: AILifecycleStatus = Field(default=AILifecycleStatus.AI_INVESTIGATION_REQUESTED)
    investigation: Optional[AIInvestigationFinding] = None
    actionPlan: Optional[AIActionPlan] = None
    toolCalls: Optional[List[AIToolAction]] = None
    ollamaVerification: Optional[AIOllamaVerification] = None
    executionResults: Optional[List[Dict[str, Any]]] = None
    failureReason: Optional[str] = None
    requestedBy: str = Field(default="ADMIN")
    approvedBy: Optional[str] = None

class AIOperationCreate(BaseModel):
    incidentId: str

class AIOperationInDB(AIOperationBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
    completedAt: Optional[datetime] = None

class AIOperationResponse(BaseModel):
    id: str
    operationId: str
    incidentId: str
    incidentCode: Optional[str] = None
    workOrderId: Optional[str] = None
    workOrderCode: Optional[str] = None
    machineId: Optional[str] = None
    machineCode: Optional[str] = None
    status: AILifecycleStatus
    investigation: Optional[AIInvestigationFinding] = None
    actionPlan: Optional[AIActionPlan] = None
    toolCalls: Optional[List[AIToolAction]] = None
    ollamaVerification: Optional[AIOllamaVerification] = None
    executionResults: Optional[List[Dict[str, Any]]] = None
    failureReason: Optional[str] = None
    requestedBy: str
    approvedBy: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    completedAt: Optional[datetime] = None
