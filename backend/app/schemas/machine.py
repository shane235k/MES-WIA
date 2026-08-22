from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class MachineStatus(str, Enum):
    IDLE = "IDLE"
    OCCUPIED = "OCCUPIED"
    PAUSED = "PAUSED"
    DOWN = "DOWN"
    MAINTENANCE = "MAINTENANCE"

MACHINE_TYPE_COLORS = {
    "CUTTING": "#3B82F6",       # Blue
    "BENDING": "#10B981",       # Emerald
    "WELDING": "#F59E0B",       # Amber
    "PAINTING": "#EC4899",      # Pink
    "INSPECTION": "#06B6D4",    # Cyan
    "DRILLING": "#8B5CF6",      # Purple
    "MILLING": "#F97316",       # Orange
    "STAMPING": "#EF4444",      # Rose
    "ASSEMBLY": "#6366F1",      # Indigo
    "PACKAGING": "#14B8A6",     # Teal
    "MULTI_PURPOSE": "#84CC16", # Lime
}

class MachineBase(BaseModel):
    machineCode: str = Field(..., pattern="^[A-Z0-9_-]+$", description="Unique uppercase machine code")
    name: str = Field(..., min_length=2)
    type: str = Field(..., description="Machine type, e.g. CUTTING, BENDING, WELDING, DRILLING, MULTI_PURPOSE")
    supportedTypes: List[str] = Field(default_factory=list, description="For MULTI_PURPOSE machines, list of functional types performed")
    status: MachineStatus = Field(default=MachineStatus.IDLE)
    capabilityIds: List[str] = Field(default_factory=list, description="List of capability ObjectIds")
    location: str
    availability: bool = Field(default=True)
    processingRate: float = Field(default=1.0, gt=0, description="Processing speed in units per second")
    rateUnit: str = Field(default="units/sec", description="Display rate unit: units/sec, units/min, units/hour")
    color: Optional[str] = Field(default=None, description="Visual theme color derived from machine type")
    currentOperationId: Optional[str] = Field(default=None, description="Currently executing operationId")
    currentWorkOrderId: Optional[str] = Field(default=None, description="Currently executing workOrderId")
    currentWorkOrderCode: Optional[str] = Field(default=None, description="Currently executing workOrderCode")
    currentOperatorId: Optional[str] = Field(default=None, description="Currently assigned operator user ObjectId")
    currentIncidentId: Optional[str] = Field(default=None, description="Active incident ObjectId if DOWN/MAINTENANCE")
    maintenanceEstimatedEnd: Optional[datetime] = Field(default=None, description="Timestamp when maintenance repair is scheduled to complete")
    maintenanceDurationMinutes: Optional[int] = Field(default=None, description="Scheduled duration of maintenance in minutes")
    maintenanceReason: Optional[str] = Field(default=None, description="Reason / repair notes for maintenance")
    lastMaintenanceAt: Optional[datetime] = Field(default=None, description="Timestamp of most recent completed maintenance overhaul")
    lastMaintenanceDurationMinutes: Optional[int] = Field(default=None, description="Duration in minutes of most recent completed maintenance")
    supportedForms: List[str] = Field(default_factory=list, description="Supported material forms, e.g. SHEET, ROD, BAR")
    supportedGrades: List[str] = Field(default_factory=list, description="Supported material grades, e.g. SS304, AL6061")
    minThicknessMm: Optional[float] = Field(default=None, ge=0.0)
    maxThicknessMm: Optional[float] = Field(default=None, ge=0.0)
    maxWidthMm: Optional[float] = Field(default=None, ge=0.0)
    maxLengthMm: Optional[float] = Field(default=None, ge=0.0)

class MachineCreate(MachineBase):
    pass

class MachineUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    type: Optional[str] = None
    supportedTypes: Optional[List[str]] = None
    status: Optional[MachineStatus] = None
    capabilityIds: Optional[List[str]] = None
    location: Optional[str] = None
    availability: Optional[bool] = None
    processingRate: Optional[float] = Field(None, gt=0)
    rateUnit: Optional[str] = None
    color: Optional[str] = None
    currentOperationId: Optional[str] = None
    currentWorkOrderId: Optional[str] = None
    currentWorkOrderCode: Optional[str] = None
    currentOperatorId: Optional[str] = None
    currentIncidentId: Optional[str] = None
    maintenanceEstimatedEnd: Optional[datetime] = None
    maintenanceDurationMinutes: Optional[int] = None
    maintenanceReason: Optional[str] = None
    supportedForms: Optional[List[str]] = None
    supportedGrades: Optional[List[str]] = None
    minThicknessMm: Optional[float] = None
    maxThicknessMm: Optional[float] = None
    maxWidthMm: Optional[float] = None
    maxLengthMm: Optional[float] = None

class MachineMaintenanceRequest(BaseModel):
    durationMinutes: int = Field(..., gt=0, description="Estimated repair duration in minutes")
    reason: Optional[str] = Field(default="Scheduled repair & maintenance", description="Repair explanation")
    actorId: Optional[str] = Field(default="ADMIN", description="Admin user ID")

class MachineInDB(MachineBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    createdAt: datetime
    updatedAt: datetime
