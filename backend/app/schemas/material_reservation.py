from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class ReservationStatus(str, Enum):
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"

class MaterialReservationBase(BaseModel):
    workOrderId: str = Field(..., description="ObjectId of the associated WorkOrder")
    workOrderCode: str = Field(..., description="Business code of the WorkOrder")
    operationId: str = Field(..., description="Operation step ID within the work order, e.g. OP-10")
    materialId: str = Field(..., description="ObjectId of the reserved Material")
    specificationId: Optional[str] = Field(default=None, description="Optional ObjectId of the MaterialSpecification")
    lotId: str = Field(..., description="ObjectId of the allocated InventoryLot")
    lotNumber: str = Field(..., description="Lot number allocated")
    quantityReserved: float = Field(..., gt=0.0, description="Quantity locked for this operation")
    quantityConsumed: float = Field(default=0.0, ge=0.0, description="Quantity actually consumed upon completion")
    unitCost: Optional[float] = Field(default=None, ge=0.0, description="Lot unit acquisition cost")
    status: ReservationStatus = Field(default=ReservationStatus.RESERVED)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    releasedAt: Optional[datetime] = None
    consumedAt: Optional[datetime] = None

class MaterialReservationInDB(MaterialReservationBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
