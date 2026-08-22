from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class MaterialTransactionType(str, Enum):
    RECEIPT = "RECEIPT"
    RESERVATION_CREATED = "RESERVATION_CREATED"
    RESERVATION_RELEASED = "RESERVATION_RELEASED"
    CONSUMPTION = "CONSUMPTION"
    SCRAP = "SCRAP"
    RETURN = "RETURN"
    INVENTORY_ADJUSTMENT = "INVENTORY_ADJUSTMENT"

class ScrapReasonCode(str, Enum):
    DIMENSIONAL_DEFECT = "DIMENSIONAL_DEFECT"
    MACHINE_JAM = "MACHINE_JAM"
    SURFACE_CONTAMINATION = "SURFACE_CONTAMINATION"
    OPERATOR_ERROR = "OPERATOR_ERROR"
    SETUP_SCRAP = "SETUP_SCRAP"
    OTHER = "OTHER"

class MaterialTransactionBase(BaseModel):
    transactionId: str = Field(..., description="Unique transaction ID")
    transactionType: MaterialTransactionType
    materialId: str
    specificationId: Optional[str] = None
    lotId: str
    lotNumber: str
    workOrderId: Optional[str] = None
    workOrderCode: Optional[str] = None
    operationId: Optional[str] = None
    quantity: float = Field(..., description="Quantity delta for this transaction")
    previousBalance: float = Field(..., ge=0.0, description="On-hand balance before transaction")
    resultingBalance: float = Field(..., ge=0.0, description="On-hand balance after transaction")
    actorId: str = Field(default="SYSTEM")
    actorType: str = Field(default="SYSTEM", description="USER, OPERATOR, or SYSTEM")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    scrapReason: Optional[ScrapReasonCode] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MaterialTransactionInDB(MaterialTransactionBase, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
