from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class ActorType(str, Enum):
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"
    OPERATOR = "OPERATOR"

class EventSource(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR_CLIENT = "OPERATOR_CLIENT"
    AI = "AI"
    SYSTEM = "SYSTEM"

class AuditEventBase(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actorId: str = Field(..., description="ID or identifier of the actor")
    actorType: ActorType
    action: str = Field(..., description="e.g. USER_CREATED, MACHINE_UPDATED")
    entityType: str = Field(..., description="e.g. user, machine, workflow")
    entityId: str = Field(..., description="Id of the changed entity")
    source: EventSource
    metadata: dict = Field(default_factory=dict)

class AuditEventCreate(AuditEventBase):
    pass

class AuditEventInDB(AuditEventBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
