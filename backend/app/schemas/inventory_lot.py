from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.schemas.base import PyObjectId, BaseSchemaModel

class LotStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    QUARANTINED = "QUARANTINED"
    EXPIRED = "EXPIRED"
    DEPLETED = "DEPLETED"

class InventoryLotBase(BaseModel):
    lotNumber: str = Field(..., pattern="^[A-Z0-9_-]+$", description="Unique physical lot / tracking number")
    materialId: str = Field(..., description="ObjectId of the associated Material")
    specificationId: Optional[str] = Field(default=None, description="Optional ObjectId of the MaterialSpecification")
    quantityOnHand: float = Field(..., ge=0.0, description="Total physical inventory in this lot")
    quantityReserved: float = Field(default=0.0, ge=0.0, description="Quantity locked for planned/in-progress work orders")
    unit: str = Field(default="sheets", description="Stock unit of measure")
    supplier: Optional[str] = Field(default=None, description="Supplier / Vendor name")
    batchNumber: Optional[str] = Field(default=None, description="Supplier batch number")
    heatNumber: Optional[str] = Field(default=None, description="Metallurgical heat number")
    location: str = Field(default="Main Warehouse", description="Storage bay, aisle, bin or rack")
    receivedDate: datetime = Field(default_factory=datetime.utcnow)
    expiryDate: Optional[datetime] = Field(default=None, description="Expiry date for perishable items")
    unitCost: Optional[float] = Field(default=None, ge=0.0, description="Acquisition / standard unit cost")
    status: LotStatus = Field(default=LotStatus.AVAILABLE)

    @property
    def quantityAvailable(self) -> float:
        """
        Dynamically derived available stock quantity. Never stored independently.
        """
        if self.status != LotStatus.AVAILABLE:
            return 0.0
        return max(0.0, round(self.quantityOnHand - self.quantityReserved, 4))

class InventoryLotCreate(BaseModel):
    lotNumber: str = Field(..., pattern="^[A-Z0-9_-]+$")
    materialId: str
    specificationId: Optional[str] = None
    quantityOnHand: float = Field(..., ge=0.0)
    unit: str = Field(default="sheets")
    supplier: Optional[str] = None
    batchNumber: Optional[str] = None
    heatNumber: Optional[str] = None
    location: str = Field(default="Main Warehouse")
    receivedDate: Optional[datetime] = None
    expiryDate: Optional[datetime] = None
    unitCost: Optional[float] = Field(default=None, ge=0.0)
    status: LotStatus = Field(default=LotStatus.AVAILABLE)

class InventoryLotReceive(BaseModel):
    quantity: float = Field(..., gt=0.0, description="Additional quantity received into this lot")
    unitCost: Optional[float] = Field(default=None, ge=0.0, description="Updated or receipt unit cost")
    supplier: Optional[str] = None
    notes: Optional[str] = None
    actorId: str = Field(default="SYSTEM")

class InventoryLotAdjust(BaseModel):
    newQuantityOnHand: float = Field(..., ge=0.0, description="Corrected physical on-hand quantity")
    reason: str = Field(..., min_length=3, description="Audit justification for stock adjustment")
    actorId: str = Field(default="SYSTEM")

class InventoryLotInDB(InventoryLotBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    quantityAvailable: float = Field(default=0.0)
    createdAt: datetime
    updatedAt: datetime

    @model_validator(mode="before")
    @classmethod
    def calculate_available(cls, data: Any) -> Any:
        if isinstance(data, dict):
            q_on_hand = float(data.get("quantityOnHand", 0.0))
            q_reserved = float(data.get("quantityReserved", 0.0))
            status_val = data.get("status", "AVAILABLE")
            if status_val != "AVAILABLE":
                data["quantityAvailable"] = 0.0
            else:
                data["quantityAvailable"] = max(0.0, round(q_on_hand - q_reserved, 4))
        return data
