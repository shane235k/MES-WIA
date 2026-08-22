from datetime import datetime
from bson import ObjectId
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.schemas.material_transaction import MaterialTransactionType, ScrapReasonCode
from app.services.audit_service import AuditService

class MaterialTransactionService:
    @staticmethod
    async def log_transaction(
        transaction_type: MaterialTransactionType,
        material_id: str,
        lot_id: str,
        lot_number: str,
        quantity: float,
        previous_balance: float,
        resulting_balance: float,
        specification_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        work_order_code: Optional[str] = None,
        operation_id: Optional[str] = None,
        actor_id: str = "SYSTEM",
        actor_type: str = "SYSTEM",
        notes: Optional[str] = None,
        scrap_reason: Optional[ScrapReasonCode] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        Append an immutable transaction record to the material_transactions collection.
        Historical transactions can NEVER be mutated or overwritten.
        """
        db = get_db()
        tx_id = str(ObjectId())
        tx_data = {
            "transactionId": tx_id,
            "transactionType": transaction_type.value if hasattr(transaction_type, "value") else str(transaction_type),
            "material_id": material_id,
            "materialId": material_id,
            "specificationId": specification_id,
            "lotId": lot_id,
            "lotNumber": lot_number,
            "workOrderId": work_order_id,
            "workOrderCode": work_order_code,
            "operationId": operation_id,
            "quantity": quantity,
            "previousBalance": round(previous_balance, 4),
            "resultingBalance": round(resulting_balance, 4),
            "actorId": actor_id,
            "actorType": actor_type,
            "timestamp": datetime.utcnow(),
            "notes": notes,
            "scrapReason": scrap_reason.value if hasattr(scrap_reason, "value") else (str(scrap_reason) if scrap_reason else None),
            "metadata": metadata or {}
        }

        result = await db.material_transactions.insert_one(tx_data)
        tx_data["_id"] = result.inserted_id

        # Also mirror to MES audit log
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type=actor_type,
            action=f"MATERIAL_TX_{tx_data['transactionType']}",
            entity_type="inventory_lot",
            entity_id=lot_id,
            source="MATERIAL_LEDGER",
            metadata={
                "transactionId": tx_id,
                "materialId": material_id,
                "lotNumber": lot_number,
                "quantity": quantity,
                "previousBalance": previous_balance,
                "resultingBalance": resulting_balance,
                "workOrderCode": work_order_code,
                "operationId": operation_id
            }
        )
        return tx_data

    @staticmethod
    async def list_transactions(
        material_id: Optional[str] = None,
        lot_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        db = get_db()
        query = {}
        if material_id:
            query["materialId"] = material_id
        if lot_id:
            query["lotId"] = lot_id
        if work_order_id:
            query["workOrderId"] = work_order_id
        if transaction_type:
            query["transactionType"] = transaction_type

        txs = []
        async for doc in db.material_transactions.find(query).sort("timestamp", -1).limit(limit):
            txs.append(doc)
        return txs
