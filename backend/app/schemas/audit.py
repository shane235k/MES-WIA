from datetime import datetime
from enum import Enum
from typing import Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class ActorType(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"
    OPERATOR = "OPERATOR"

class EventSource(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    OPERATOR_CLIENT = "OPERATOR_CLIENT"
    AI = "AI"
    AI_ORCHESTRATOR = "AI_ORCHESTRATOR"
    SYSTEM = "SYSTEM"
    EXECUTION_ENGINE = "EXECUTION_ENGINE"
    MATERIAL_LEDGER = "MATERIAL_LEDGER"
    MATERIAL_SERVICE = "MATERIAL_SERVICE"

class AuditEventBase(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actorId: str = Field(default="SYSTEM", description="ID or identifier of the actor")
    actorType: Union[ActorType, str] = Field(default=ActorType.SYSTEM)
    action: str = Field(..., description="e.g. USER_CREATED, MACHINE_UPDATED")
    entityType: str = Field(..., description="e.g. user, machine, workflow")
    entityId: str = Field(default="SYSTEM", description="Id of the changed entity")
    source: Union[EventSource, str] = Field(default=EventSource.SYSTEM)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AuditEventCreate(AuditEventBase):
    pass

class AuditEventInDB(AuditEventBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
