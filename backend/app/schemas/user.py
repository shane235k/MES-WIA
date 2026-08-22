from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    PLANNER = "PLANNER"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"

class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    SUSPENDED = "SUSPENDED"

class OperatorAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    OFFLINE = "OFFLINE"
    SUSPENDED = "SUSPENDED"

class UserBase(BaseModel):
    employeeId: str = Field(..., description="Unique employee identifier")
    name: str = Field(..., min_length=2)
    email: EmailStr
    role: UserRole
    department: str
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    availabilityStatus: OperatorAvailability = Field(default=OperatorAvailability.AVAILABLE)
    currentWorkOrderId: Optional[str] = Field(default=None, description="Active work order if assigned")
    currentWorkOrderCode: Optional[str] = Field(default=None, description="Active work order code if assigned")
    currentWorkOrderName: Optional[str] = Field(default=None, description="Active work order name if assigned")
    currentOperationId: Optional[str] = Field(default=None, description="Active operation if assigned")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    status: Optional[UserStatus] = None
    availabilityStatus: Optional[OperatorAvailability] = None
    currentWorkOrderId: Optional[str] = None
    currentWorkOrderCode: Optional[str] = None
    currentWorkOrderName: Optional[str] = None
    currentOperationId: Optional[str] = None

class UserInDB(UserBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
