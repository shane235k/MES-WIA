import logging
from datetime import datetime
from bson import ObjectId
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.schemas.inventory_lot import InventoryLotCreate, InventoryLotReceive, InventoryLotAdjust, LotStatus
from app.schemas.material_transaction import MaterialTransactionType
from app.services.material_transaction_service import MaterialTransactionService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class InventoryLotService:
    @staticmethod
    async def sync_material_stock(material_id: str) -> None:
        """
        Aggregate total quantityOnHand and quantityReserved across all lots for a Material,
        and synchronize quantityAvailable on the parent Material document.
        """
        db = get_db()
        if not ObjectId.is_valid(material_id):
            return

        pipeline = [
            {"$match": {"materialId": material_id}},
            {"$group": {
                "_id": "$materialId",
                "totalOnHand": {"$sum": "$quantityOnHand"},
                "totalReserved": {"$sum": "$quantityReserved"}
            }}
        ]
        agg = await db.inventory_lots.aggregate(pipeline).to_list(1)
        total_on_hand = 0.0
        total_reserved = 0.0
        if agg:
            total_on_hand = round(agg[0].get("totalOnHand", 0.0), 4)
            total_reserved = round(agg[0].get("totalReserved", 0.0), 4)

        avail = max(0.0, round(total_on_hand - total_reserved, 4))

        await db.materials.update_one(
            {"_id": ObjectId(material_id)},
            {"$set": {
                "quantityOnHand": total_on_hand,
                "quantityReserved": total_reserved,
                "quantityAvailable": avail,
                "updatedAt": datetime.utcnow()
            }}
        )

    @staticmethod
    async def create_lot(lot_in: InventoryLotCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()

        # Validate Material ID
        if not ObjectId.is_valid(lot_in.materialId):
            raise ValueError(f"Invalid Material ID: '{lot_in.materialId}'")
        material = await db.materials.find_one({"_id": ObjectId(lot_in.materialId)})
        if not material:
            raise ValueError(f"Material '{lot_in.materialId}' does not exist")

        # Check unique compound constraint: lotNumber + materialId
        existing = await db.inventory_lots.find_one({
            "lotNumber": lot_in.lotNumber,
            "materialId": lot_in.materialId
        })
        if existing:
            raise ValueError(f"Lot '{lot_in.lotNumber}' already exists for material '{material.get('materialCode')}'")

        now = datetime.utcnow()
        lot_data = lot_in.model_dump()
        lot_data["quantityReserved"] = 0.0
        lot_data["receivedDate"] = lot_in.receivedDate or now
        lot_data["createdAt"] = now
        lot_data["updatedAt"] = now

        result = await db.inventory_lots.insert_one(lot_data)
        lot_id = str(result.inserted_id)
        lot_data["_id"] = result.inserted_id

        # Record RECEIPT in transaction ledger
        if lot_in.quantityOnHand > 0:
            await MaterialTransactionService.log_transaction(
                transaction_type=MaterialTransactionType.RECEIPT,
                material_id=lot_in.materialId,
                lot_id=lot_id,
                lot_number=lot_in.lotNumber,
                quantity=lot_in.quantityOnHand,
                previous_balance=0.0,
                resulting_balance=lot_in.quantityOnHand,
                specification_id=lot_in.specificationId,
                actor_id=actor_id,
                notes=f"Initial lot creation receipt of {lot_in.quantityOnHand} {lot_in.unit}"
            )

        # Sync parent material stock
        await InventoryLotService.sync_material_stock(lot_in.materialId)
        return lot_data

    @staticmethod
    async def receive_stock(lot_id: str, receive_in: InventoryLotReceive) -> dict:
        """
        Receive additional incoming physical stock into an existing InventoryLot.
        """
        db = get_db()
        if not ObjectId.is_valid(lot_id):
            raise ValueError(f"Invalid Lot ID: '{lot_id}'")

        lot = await db.inventory_lots.find_one({"_id": ObjectId(lot_id)})
        if not lot:
            raise ValueError(f"Lot '{lot_id}' not found")

        prev_on_hand = float(lot.get("quantityOnHand", 0.0))
        new_on_hand = round(prev_on_hand + receive_in.quantity, 4)
        
        # If lot was depleted and now has stock, restore to AVAILABLE unless quarantined
        current_status = lot.get("status", LotStatus.AVAILABLE.value)
        new_status = LotStatus.AVAILABLE.value if current_status == LotStatus.DEPLETED.value else current_status

        now = datetime.utcnow()
        set_fields: dict = {
            "quantityOnHand": new_on_hand,
            "status": new_status,
            "updatedAt": now
        }
        if receive_in.unitCost is not None:
            set_fields["unitCost"] = receive_in.unitCost
        if receive_in.supplier is not None:
            set_fields["supplier"] = receive_in.supplier

        updated_lot = await db.inventory_lots.find_one_and_update(
            {"_id": ObjectId(lot_id)},
            {"$set": set_fields},
            return_document=True
        )

        # Record in ledger
        await MaterialTransactionService.log_transaction(
            transaction_type=MaterialTransactionType.RECEIPT,
            material_id=str(lot["materialId"]),
            lot_id=lot_id,
            lot_number=lot.get("lotNumber"),
            quantity=receive_in.quantity,
            previous_balance=prev_on_hand,
            resulting_balance=new_on_hand,
            specification_id=lot.get("specificationId"),
            actor_id=receive_in.actorId,
            notes=receive_in.notes or f"Restocked +{receive_in.quantity} {lot.get('unit')} @ ₹{receive_in.unitCost or lot.get('unitCost') or 0.0}"
        )

        await InventoryLotService.sync_material_stock(str(lot["materialId"]))
        return updated_lot

    @staticmethod
    async def adjust_stock(lot_id: str, adjust_in: InventoryLotAdjust) -> dict:
        """
        Manual stock balance adjustment for inventory reconciliation / physical count audit.
        """
        db = get_db()
        if not ObjectId.is_valid(lot_id):
            raise ValueError(f"Invalid Lot ID: '{lot_id}'")

        lot = await db.inventory_lots.find_one({"_id": ObjectId(lot_id)})
        if not lot:
            raise ValueError(f"Lot '{lot_id}' not found")

        prev_on_hand = float(lot.get("quantityOnHand", 0.0))
        q_reserved = float(lot.get("quantityReserved", 0.0))

        if adjust_in.newQuantityOnHand < q_reserved:
            raise ValueError(f"Cannot adjust on-hand ({adjust_in.newQuantityOnHand}) below currently reserved quantity ({q_reserved})")

        new_on_hand = round(adjust_in.newQuantityOnHand, 4)
        delta = round(new_on_hand - prev_on_hand, 4)
        new_status = LotStatus.DEPLETED.value if (new_on_hand == 0 and q_reserved == 0) else (
            LotStatus.AVAILABLE.value if lot.get("status") == LotStatus.DEPLETED.value else lot.get("status")
        )

        now = datetime.utcnow()
        updated_lot = await db.inventory_lots.find_one_and_update(
            {"_id": ObjectId(lot_id)},
            {"$set": {
                "quantityOnHand": new_on_hand,
                "status": new_status,
                "updatedAt": now
            }},
            return_document=True
        )

        # Record in ledger
        await MaterialTransactionService.log_transaction(
            transaction_type=MaterialTransactionType.INVENTORY_ADJUSTMENT,
            material_id=str(lot["materialId"]),
            lot_id=lot_id,
            lot_number=lot.get("lotNumber"),
            quantity=delta,
            previous_balance=prev_on_hand,
            resulting_balance=new_on_hand,
            specification_id=lot.get("specificationId"),
            actor_id=adjust_in.actorId,
            notes=adjust_in.reason
        )

        await InventoryLotService.sync_material_stock(str(lot["materialId"]))
        return updated_lot

    @staticmethod
    async def get_lot_by_id(lot_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(lot_id):
            return None
        return await db.inventory_lots.find_one({"_id": ObjectId(lot_id)})

    @staticmethod
    async def get_lot_by_number(lot_number: str) -> Optional[dict]:
        db = get_db()
        return await db.inventory_lots.find_one({"lotNumber": lot_number})

    @staticmethod
    async def list_lots(
        material_id: Optional[str] = None,
        specification_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[dict]:
        db = get_db()
        query = {}
        if material_id:
            query["materialId"] = material_id
        if specification_id:
            query["specificationId"] = specification_id
        if status:
            query["status"] = status

        lots = []
        async for doc in db.inventory_lots.find(query).sort("receivedDate", -1):
            lots.append(doc)
        return lots

    @staticmethod
    async def migrate_legacy_materials() -> Dict[str, Any]:
        """
        Idempotent migration: For each Material with quantityAvailable > 0 and no existing lots,
        create a default initial lot 'LOT-INIT-{materialCode}' so physical inventory tracking is authoritative.
        """
        db = get_db()
        migrated = 0
        skipped = 0

        async for mat in db.materials.find():
            mat_id = str(mat["_id"])
            mat_code = mat.get("materialCode", "MAT")
            lot_count = await db.inventory_lots.count_documents({"materialId": mat_id})
            
            if lot_count == 0:
                qty_avail = float(mat.get("quantityAvailable", 0.0))
                lot_number = f"LOT-INIT-{mat_code}"
                
                # Check if lot with same lotNumber exists
                exist_lot = await db.inventory_lots.find_one({"lotNumber": lot_number, "materialId": mat_id})
                if not exist_lot:
                    now = datetime.utcnow()
                    lot_doc = {
                        "lotNumber": lot_number,
                        "materialId": mat_id,
                        "specificationId": mat.get("specificationId"),
                        "quantityOnHand": qty_avail,
                        "quantityReserved": 0.0,
                        "unit": mat.get("unit", "sheets"),
                        "supplier": "Initial Factory Stock",
                        "batchNumber": "MIGRATION-V1",
                        "location": "Main Warehouse",
                        "receivedDate": now,
                        "status": LotStatus.AVAILABLE.value if qty_avail > 0 else LotStatus.DEPLETED.value,
                        "createdAt": now,
                        "updatedAt": now
                    }
                    res = await db.inventory_lots.insert_one(lot_doc)
                    lot_id = str(res.inserted_id)

                    if qty_avail > 0:
                        await MaterialTransactionService.log_transaction(
                            transaction_type=MaterialTransactionType.RECEIPT,
                            material_id=mat_id,
                            lot_id=lot_id,
                            lot_number=lot_number,
                            quantity=qty_avail,
                            previous_balance=0.0,
                            resulting_balance=qty_avail,
                            specification_id=mat.get("specificationId"),
                            notes=f"Initial migration lot created from legacy quantityAvailable ({qty_avail})"
                        )

                    await InventoryLotService.sync_material_stock(mat_id)
                    migrated += 1
                else:
                    skipped += 1
            else:
                # Already has lots -> ensure sync
                await InventoryLotService.sync_material_stock(mat_id)
                skipped += 1

        logger.info(f"Inventory migration completed. Migrated: {migrated}, Skipped/Existing: {skipped}")
        return {"migrated": migrated, "skipped": skipped}
