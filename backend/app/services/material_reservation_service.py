import logging
from datetime import datetime
from bson import ObjectId
from typing import List, Optional, Dict, Any, Tuple
from app.core.database import get_db
from app.schemas.material_reservation import ReservationStatus
from app.schemas.material_transaction import MaterialTransactionType, ScrapReasonCode
from app.schemas.work_order import WorkOrderStatus, WorkOrderOperationStatus
from app.schemas.inventory_lot import LotStatus
from app.services.inventory_lot_service import InventoryLotService
from app.services.material_transaction_service import MaterialTransactionService
from app.services.audit_service import AuditService
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)

class MaterialReservationService:
    @staticmethod
    async def allocate_and_reserve(
        work_order_id: str,
        work_order_code: str,
        operation_id: str,
        material_id: str,
        required_qty: float,
        specification_id: Optional[str] = None,
        actor_id: str = "SYSTEM"
    ) -> Tuple[bool, List[dict], float]:
        """
        Allocate inventory across available lots using FEFO/FIFO strategy with atomic concurrency protection.
        Returns: (success: bool, reservations: List[dict], unallocated_qty: float)
        """
        db = get_db()
        now = datetime.utcnow()

        # Query eligible available lots for this material
        query = {
            "materialId": material_id,
            "status": LotStatus.AVAILABLE.value,
            "$or": [
                {"expiryDate": None},
                {"expiryDate": {"$gt": now}}
            ]
        }
        if specification_id:
            query["specificationId"] = specification_id

        # Fetch lots and sort:
        # FEFO for lots with expiryDate, then FIFO by receivedDate, then _id
        lots = []
        async for doc in db.inventory_lots.find(query):
            avail = float(doc.get("quantityOnHand", 0.0)) - float(doc.get("quantityReserved", 0.0))
            if avail > 0.0001:
                doc["_avail"] = avail
                lots.append(doc)

        def sort_key(item):
            exp = item.get("expiryDate") or datetime(2099, 1, 1)
            rec = item.get("receivedDate") or datetime(2000, 1, 1)
            return (exp, rec, str(item["_id"]))

        lots.sort(key=sort_key)

        remaining_needed = round(required_qty, 4)
        created_reservations = []

        for lot in lots:
            if remaining_needed <= 0.0001:
                break

            lot_avail = lot["_avail"]
            qty_to_reserve = round(min(remaining_needed, lot_avail), 4)

            # Atomic conditional update: increment quantityReserved ONLY IF quantityOnHand - quantityReserved >= qty_to_reserve
            lot_id_obj = lot["_id"]
            lot_id_str = str(lot_id_obj)

            # Atomic CAS update
            update_result = await db.inventory_lots.find_one_and_update(
                {
                    "_id": lot_id_obj,
                    "$expr": {
                        "$gte": [
                            {"$subtract": ["$quantityOnHand", "$quantityReserved"]},
                            qty_to_reserve
                        ]
                    }
                },
                {
                    "$inc": {"quantityReserved": qty_to_reserve},
                    "$set": {"updatedAt": now}
                },
                return_document=True
            )

            if update_result:
                # Successfully locked stock in lot!
                res_doc = {
                    "workOrderId": work_order_id,
                    "workOrderCode": work_order_code,
                    "operationId": operation_id,
                    "materialId": material_id,
                    "specificationId": specification_id or lot.get("specificationId"),
                    "lotId": lot_id_str,
                    "lotNumber": lot.get("lotNumber"),
                    "quantityReserved": qty_to_reserve,
                    "quantityConsumed": 0.0,
                    "unitCost": lot.get("unitCost"),
                    "status": ReservationStatus.RESERVED.value,
                    "createdAt": now,
                    "releasedAt": None,
                    "consumedAt": None
                }
                res_insert = await db.material_reservations.insert_one(res_doc)
                res_doc["_id"] = res_insert.inserted_id
                created_reservations.append(res_doc)

                # Record RESERVATION_CREATED in ledger
                await MaterialTransactionService.log_transaction(
                    transaction_type=MaterialTransactionType.RESERVATION_CREATED,
                    material_id=material_id,
                    lot_id=lot_id_str,
                    lot_number=lot.get("lotNumber"),
                    quantity=qty_to_reserve,
                    previous_balance=float(lot.get("quantityOnHand", 0.0)),
                    resulting_balance=float(lot.get("quantityOnHand", 0.0)),
                    specification_id=specification_id or lot.get("specificationId"),
                    work_order_id=work_order_id,
                    work_order_code=work_order_code,
                    operation_id=operation_id,
                    actor_id=actor_id,
                    notes=f"Reserved {qty_to_reserve} {lot.get('unit')} for Operation {operation_id} (WO {work_order_code})"
                )

                remaining_needed = round(remaining_needed - qty_to_reserve, 4)

        success = (remaining_needed <= 0.0001)
        if not success:
            # Shortage! Roll back any partial reservations created in this attempt
            for partial_res in created_reservations:
                p_lot_id = partial_res["lotId"]
                p_qty = partial_res["quantityReserved"]
                p_res_id = partial_res["_id"]

                await db.inventory_lots.update_one(
                    {"_id": ObjectId(p_lot_id)},
                    {"$inc": {"quantityReserved": -p_qty}, "$set": {"updatedAt": datetime.utcnow()}}
                )
                await db.material_reservations.delete_one({"_id": p_res_id})

                # Log rollback in ledger
                await MaterialTransactionService.log_transaction(
                    transaction_type=MaterialTransactionType.RESERVATION_RELEASED,
                    material_id=material_id,
                    lot_id=p_lot_id,
                    lot_number=partial_res["lotNumber"],
                    quantity=-p_qty,
                    previous_balance=0.0,
                    resulting_balance=0.0,
                    work_order_id=work_order_id,
                    work_order_code=work_order_code,
                    operation_id=operation_id,
                    actor_id=actor_id,
                    notes="Released partial reservation due to material shortage"
                )

            # Sync material counters
            await InventoryLotService.sync_material_stock(material_id)
            return False, [], remaining_needed

        # Sync material stock for all touched lots
        await InventoryLotService.sync_material_stock(material_id)
        return True, created_reservations, 0.0

    @staticmethod
    async def reserve_for_work_order(work_order_id: str, actor_id: str = "SYSTEM") -> Dict[str, Any]:
        """
        Validate and reserve materials for all operations in a Work Order.
        If any material is insufficient, puts Work Order into WAITING_FOR_MATERIAL and releases partial locks.
        """
        db = get_db()
        if not ObjectId.is_valid(work_order_id):
            raise ValueError(f"Invalid Work Order ID: '{work_order_id}'")

        wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
        if not wo:
            raise ValueError(f"Work Order '{work_order_id}' not found")

        work_order_code = wo.get("workOrderCode", "WO")
        operations = wo.get("operations", [])

        # Check if already reserved
        existing_res_count = await db.material_reservations.count_documents({
            "workOrderId": work_order_id,
            "status": ReservationStatus.RESERVED.value
        })
        if existing_res_count > 0:
            return {"success": True, "message": "Materials already reserved"}

        all_created_reservations = []
        shortages = []

        for op in operations:
            op_id = op.get("operationId")
            req_mats = op.get("requiredMaterials", [])

            for req in req_mats:
                mat_id = req.get("materialId")
                total_qty = float(req.get("totalRequiredQuantity", 0.0))
                spec_id = req.get("specificationId")

                if not mat_id or total_qty <= 0:
                    continue

                success, res_list, unallocated = await MaterialReservationService.allocate_and_reserve(
                    work_order_id=work_order_id,
                    work_order_code=work_order_code,
                    operation_id=op_id,
                    material_id=mat_id,
                    required_qty=total_qty,
                    specification_id=spec_id,
                    actor_id=actor_id
                )

                if success:
                    all_created_reservations.extend(res_list)
                    req["quantityReserved"] = total_qty
                else:
                    mat_doc = await db.materials.find_one({"_id": ObjectId(mat_id)}) if ObjectId.is_valid(mat_id) else None
                    mat_name = mat_doc.get("name", mat_id) if mat_doc else mat_id
                    shortages.append({
                        "operationId": op_id,
                        "materialId": mat_id,
                        "materialName": mat_name,
                        "requiredQuantity": total_qty,
                        "shortageQuantity": unallocated
                    })
                    break

            if shortages:
                break

        if shortages:
            # Release any successful reservations from preceding operations
            for res in all_created_reservations:
                await db.inventory_lots.update_one(
                    {"_id": ObjectId(res["lotId"])},
                    {"$inc": {"quantityReserved": -float(res["quantityReserved"])}, "$set": {"updatedAt": datetime.utcnow()}}
                )
                await db.material_reservations.delete_one({"_id": res["_id"]})
                await MaterialTransactionService.log_transaction(
                    transaction_type=MaterialTransactionType.RESERVATION_RELEASED,
                    material_id=res["materialId"],
                    lot_id=res["lotId"],
                    lot_number=res["lotNumber"],
                    quantity=-float(res["quantityReserved"]),
                    previous_balance=0.0,
                    resulting_balance=0.0,
                    work_order_id=work_order_id,
                    work_order_code=work_order_code,
                    operation_id=res["operationId"],
                    actor_id=actor_id,
                    notes="Released reservation due to work order material shortage"
                )
                await InventoryLotService.sync_material_stock(res["materialId"])

            # Transition Work Order to WAITING_FOR_MATERIAL
            now = datetime.utcnow()
            shortage_msg = "; ".join([f"{s['materialName']}: missing {s['shortageQuantity']}" for s in shortages])
            await db.work_orders.update_one(
                {"_id": ObjectId(work_order_id)},
                {"$set": {
                    "status": WorkOrderStatus.WAITING_FOR_MATERIAL.value,
                    "updatedAt": now
                }}
            )

            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="SYSTEM",
                action="WORK_ORDER_MATERIAL_SHORTAGE",
                entity_type="work_order",
                entity_id=work_order_id,
                source="MATERIAL_SERVICE",
                metadata={"workOrderCode": work_order_code, "shortages": shortages}
            )

            return {
                "success": False,
                "status": WorkOrderStatus.WAITING_FOR_MATERIAL.value,
                "shortages": shortages,
                "message": f"Material shortage: {shortage_msg}"
            }

        # Update operation requiredMaterials snapshot counters
        now = datetime.utcnow()
        await db.work_orders.update_one(
            {"_id": ObjectId(work_order_id)},
            {"$set": {"operations": operations, "updatedAt": now}}
        )

        # Broadcast MATERIAL_RESERVED event
        try:
            summary = await MaterialReservationService.get_work_order_material_summary(work_order_id)
            await ws_manager.broadcast({
                "type": "MATERIAL_RESERVED",
                "data": {
                    "workOrderId": work_order_id,
                    "workOrderCode": work_order_code,
                    "reservationsCount": len(all_created_reservations),
                    "materialSummary": summary
                }
            })
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast MATERIAL_RESERVED: {ws_err}")

        return {
            "success": True,
            "reservationsCount": len(all_created_reservations),
            "message": "All materials successfully reserved"
        }

    @staticmethod
    async def consume_for_operation(
        work_order_id: str,
        operation_id: str,
        actual_consumed: Optional[float] = None,
        scrap_qty: float = 0.0,
        scrap_reason: Optional[ScrapReasonCode] = None,
        actor_id: str = "SYSTEM"
    ) -> List[dict]:
        """
        Convert active reservations for an operation into actual consumption upon operation completion.
        Atomically decrements physical quantityOnHand and quantityReserved on inventory lots.
        """
        db = get_db()
        now = datetime.utcnow()

        reservations = []
        async for doc in db.material_reservations.find({
            "workOrderId": work_order_id,
            "operationId": operation_id,
            "status": ReservationStatus.RESERVED.value
        }):
            reservations.append(doc)

        if not reservations:
            return []

        consumed_records = []
        wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
        wo_code = wo.get("workOrderCode") if wo else "WO"

        total_reserved = sum(float(r.get("quantityReserved", 0.0)) for r in reservations)
        target_consumed = actual_consumed if actual_consumed is not None else total_reserved

        # Pro-rata consumption if multiple lots were used
        consumption_ratio = (target_consumed / total_reserved) if total_reserved > 0 else 1.0

        for res in reservations:
            res_id = res["_id"]
            lot_id_str = res["lotId"]
            lot_id_obj = ObjectId(lot_id_str)
            qty_res = float(res.get("quantityReserved", 0.0))
            qty_to_consume = round(qty_res * consumption_ratio, 4)
            qty_unused = max(0.0, round(qty_res - qty_to_consume, 4))

            # Fetch lot current balance
            lot = await db.inventory_lots.find_one({"_id": lot_id_obj})
            if not lot:
                continue

            prev_on_hand = float(lot.get("quantityOnHand", 0.0))
            new_on_hand = max(0.0, round(prev_on_hand - qty_to_consume, 4))
            prev_reserved = float(lot.get("quantityReserved", 0.0))
            new_reserved = max(0.0, round(prev_reserved - qty_res, 4))
            new_status = LotStatus.DEPLETED.value if (new_on_hand == 0 and new_reserved == 0) else lot.get("status")

            # Atomically update lot
            await db.inventory_lots.update_one(
                {"_id": lot_id_obj},
                {"$set": {
                    "quantityOnHand": new_on_hand,
                    "quantityReserved": new_reserved,
                    "status": new_status,
                    "updatedAt": now
                }}
            )

            # Update reservation status
            await db.material_reservations.update_one(
                {"_id": res_id},
                {"$set": {
                    "status": ReservationStatus.CONSUMED.value,
                    "quantityConsumed": qty_to_consume,
                    "consumedAt": now,
                    "updatedAt": now
                }}
            )

            # Record CONSUMPTION in ledger
            tx_consume = await MaterialTransactionService.log_transaction(
                transaction_type=MaterialTransactionType.CONSUMPTION,
                material_id=res["materialId"],
                lot_id=lot_id_str,
                lot_number=res["lotNumber"],
                quantity=qty_to_consume,
                previous_balance=prev_on_hand,
                resulting_balance=new_on_hand,
                specification_id=res.get("specificationId"),
                work_order_id=work_order_id,
                work_order_code=wo_code,
                operation_id=operation_id,
                actor_id=actor_id,
                notes=f"Operation {operation_id} completion consumption"
            )
            consumed_records.append(tx_consume)

            # Record SCRAP in ledger if applicable
            if scrap_qty > 0:
                tx_scrap = await MaterialTransactionService.log_transaction(
                    transaction_type=MaterialTransactionType.SCRAP,
                    material_id=res["materialId"],
                    lot_id=lot_id_str,
                    lot_number=res["lotNumber"],
                    quantity=scrap_qty,
                    previous_balance=new_on_hand,
                    resulting_balance=new_on_hand,
                    specification_id=res.get("specificationId"),
                    work_order_id=work_order_id,
                    work_order_code=wo_code,
                    operation_id=operation_id,
                    actor_id=actor_id,
                    scrap_reason=scrap_reason or ScrapReasonCode.OTHER,
                    notes=f"Scrap logged during Operation {operation_id}"
                )
                consumed_records.append(tx_scrap)

            # Sync material aggregate
            await InventoryLotService.sync_material_stock(res["materialId"])

        # Update WorkOrder operations snapshot for consumed quantities & actual costs
        if wo and "operations" in wo:
            ops = wo.get("operations", [])
            for o in ops:
                if o.get("operationId") == operation_id:
                    for req in o.get("requiredMaterials", []):
                        # Sum all consumed for this material in this operation
                        cons_qty = sum(
                            float(r.get("quantity", 0.0))
                            for r in consumed_records
                            if r.get("materialId") == req.get("materialId") and (r.get("transactionType") in ("CONSUMPTION", MaterialTransactionType.CONSUMPTION.value))
                        )
                        req["quantityConsumed"] = round(float(req.get("quantityConsumed", 0.0)) + cons_qty, 4)
                        unit_cost_val = req.get("unitCost") or 0.0
                        req["actualCost"] = round(req["quantityConsumed"] * unit_cost_val, 2)
            await db.work_orders.update_one(
                {"_id": ObjectId(work_order_id)},
                {"$set": {"operations": ops, "updatedAt": now}}
            )

        # Broadcast live MATERIAL_CONSUMED event
        try:
            summary = await MaterialReservationService.get_work_order_material_summary(work_order_id)
            await ws_manager.broadcast({
                "type": "MATERIAL_CONSUMED",
                "data": {
                    "workOrderId": work_order_id,
                    "workOrderCode": wo_code,
                    "operationId": operation_id,
                    "consumedRecords": consumed_records,
                    "scrapQty": scrap_qty,
                    "scrapReason": scrap_reason.value if hasattr(scrap_reason, "value") else str(scrap_reason) if scrap_reason else None,
                    "materialSummary": summary
                }
            })
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast MATERIAL_CONSUMED: {ws_err}")

        return consumed_records

    @staticmethod
    async def release_for_work_order(work_order_id: str, actor_id: str = "SYSTEM") -> int:
        """
        Release all active reservations back to available stock when a Work Order is cancelled or aborted.
        """
        db = get_db()
        now = datetime.utcnow()

        released_count = 0
        async for res in db.material_reservations.find({
            "workOrderId": work_order_id,
            "status": ReservationStatus.RESERVED.value
        }):
            res_id = res["_id"]
            lot_id_str = res["lotId"]
            qty_res = float(res.get("quantityReserved", 0.0))

            # Atomically unlock lot quantity
            await db.inventory_lots.update_one(
                {"_id": ObjectId(lot_id_str)},
                {"$inc": {"quantityReserved": -qty_res}, "$set": {"updatedAt": now}}
            )

            # Mark reservation released
            await db.material_reservations.update_one(
                {"_id": res_id},
                {"$set": {
                    "status": ReservationStatus.RELEASED.value,
                    "releasedAt": now,
                    "updatedAt": now
                }}
            )

            # Record in ledger
            await MaterialTransactionService.log_transaction(
                transaction_type=MaterialTransactionType.RESERVATION_RELEASED,
                material_id=res["materialId"],
                lot_id=lot_id_str,
                lot_number=res["lotNumber"],
                quantity=-qty_res,
                previous_balance=0.0,
                resulting_balance=0.0,
                specification_id=res.get("specificationId"),
                work_order_id=work_order_id,
                work_order_code=res.get("workOrderCode"),
                operation_id=res.get("operationId"),
                actor_id=actor_id,
                notes="Work order cancellation reservation release"
            )

            await InventoryLotService.sync_material_stock(res["materialId"])
            released_count += 1

        return released_count

    @staticmethod
    async def list_reservations(
        work_order_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        lot_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[dict]:
        db = get_db()
        query = {}
        if work_order_id:
            query["workOrderId"] = work_order_id
        if operation_id:
            query["operationId"] = operation_id
        if lot_id:
            query["lotId"] = lot_id
        if status:
            query["status"] = status

        results = []
        async for doc in db.material_reservations.find(query).sort("createdAt", -1):
            results.append(doc)
        return results

    @staticmethod
    async def get_forward_traceability(lot_number: str) -> Dict[str, Any]:
        """
        Forward Traceability: Given a physical Inventory Lot, find all Work Orders, Operations, and Products manufactured.
        """
        db = get_db()
        lot = await db.inventory_lots.find_one({"lotNumber": lot_number})
        if not lot:
            raise ValueError(f"Lot '{lot_number}' not found")

        lot_id = str(lot["_id"])
        material = await db.materials.find_one({"_id": ObjectId(lot["materialId"])})
        specification = await db.material_specifications.find_one({"_id": ObjectId(lot["specificationId"])}) if lot.get("specificationId") else None

        # Find all reservations and ledger entries
        reservations = []
        async for r in db.material_reservations.find({"lotId": lot_id}):
            r["_id"] = str(r["_id"])
            reservations.append(r)

        wo_ids = list({r["workOrderId"] for r in reservations if r.get("workOrderId")})
        work_orders = []
        for wo_id in wo_ids:
            if ObjectId.is_valid(wo_id):
                wo_doc = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
                if wo_doc:
                    prod = await db.products.find_one({"_id": ObjectId(wo_doc["productId"])}) if ObjectId.is_valid(wo_doc.get("productId", "")) else None
                    work_orders.append({
                        "workOrderId": str(wo_doc["_id"]),
                        "workOrderCode": wo_doc.get("workOrderCode"),
                        "status": wo_doc.get("status"),
                        "quantity": wo_doc.get("quantity"),
                        "productCode": prod.get("productCode") if prod else None,
                        "productName": prod.get("name") if prod else None
                    })

        transactions = []
        async for t in db.material_transactions.find({"lotId": lot_id}).sort("timestamp", -1):
            t["_id"] = str(t["_id"])
            transactions.append(t)

        return {
            "lot": {
                "id": lot_id,
                "lotNumber": lot.get("lotNumber"),
                "materialCode": material.get("materialCode") if material else None,
                "materialName": material.get("name") if material else None,
                "specification": specification.get("name") if specification else None,
                "supplier": lot.get("supplier"),
                "batchNumber": lot.get("batchNumber"),
                "heatNumber": lot.get("heatNumber"),
                "quantityOnHand": lot.get("quantityOnHand"),
                "quantityReserved": lot.get("quantityReserved"),
                "unit": lot.get("unit"),
                "status": lot.get("status"),
                "receivedDate": lot.get("receivedDate"),
                "location": lot.get("location")
            },
            "workOrders": work_orders,
            "reservations": reservations,
            "transactions": transactions
        }

    @staticmethod
    async def get_backward_traceability(work_order_id: str) -> Dict[str, Any]:
        """
        Backward Traceability: Given a Work Order, find all operations, raw material lots consumed, suppliers, and heat numbers.
        """
        db = get_db()
        if not ObjectId.is_valid(work_order_id):
            raise ValueError(f"Invalid Work Order ID: '{work_order_id}'")

        wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
        if not wo:
            raise ValueError(f"Work Order '{work_order_id}' not found")

        prod = await db.products.find_one({"_id": ObjectId(wo["productId"])}) if ObjectId.is_valid(wo.get("productId", "")) else None

        reservations = []
        lot_ids = set()
        async for r in db.material_reservations.find({"workOrderId": work_order_id}):
            r["_id"] = str(r["_id"])
            reservations.append(r)
            if r.get("lotId"):
                lot_ids.add(r["lotId"])

        consumed_lots = []
        for l_id in lot_ids:
            if ObjectId.is_valid(l_id):
                lot_doc = await db.inventory_lots.find_one({"_id": ObjectId(l_id)})
                if lot_doc:
                    mat = await db.materials.find_one({"_id": ObjectId(lot_doc["materialId"])}) if ObjectId.is_valid(lot_doc.get("materialId", "")) else None
                    spec = await db.material_specifications.find_one({"_id": ObjectId(lot_doc["specificationId"])}) if lot_doc.get("specificationId") else None
                    consumed_lots.append({
                        "lotId": str(lot_doc["_id"]),
                        "lotNumber": lot_doc.get("lotNumber"),
                        "materialCode": mat.get("materialCode") if mat else None,
                        "materialName": mat.get("name") if mat else None,
                        "specification": spec.get("name") if spec else None,
                        "supplier": lot_doc.get("supplier"),
                        "batchNumber": lot_doc.get("batchNumber"),
                        "heatNumber": lot_doc.get("heatNumber"),
                        "unit": lot_doc.get("unit"),
                        "location": lot_doc.get("location")
                    })

        transactions = []
        async for t in db.material_transactions.find({"workOrderId": work_order_id}).sort("timestamp", -1):
            t["_id"] = str(t["_id"])
            transactions.append(t)

        return {
            "workOrder": {
                "id": str(wo["_id"]),
                "workOrderCode": wo.get("workOrderCode"),
                "status": wo.get("status"),
                "quantity": wo.get("quantity"),
                "productCode": prod.get("productCode") if prod else None,
                "productName": prod.get("name") if prod else None,
                "startedAt": wo.get("startedAt"),
                "completedAt": wo.get("completedAt")
            },
            "consumedLots": consumed_lots,
            "reservations": reservations,
            "transactions": transactions
        }

    @staticmethod
    async def get_work_order_material_summary(work_order_id: str) -> Dict[str, Any]:
        """
        Aggregate clean work order material requirements, lot allocations, live consumption, and costing.
        """
        db = get_db()
        if not ObjectId.is_valid(work_order_id):
            raise ValueError(f"Invalid Work Order ID: '{work_order_id}'")

        wo = await db.work_orders.find_one({"_id": ObjectId(work_order_id)})
        if not wo:
            raise ValueError(f"Work Order '{work_order_id}' not found")

        operations = wo.get("operations", [])
        
        # Fetch active reservations for this WO
        reservations_by_mat = {}
        async for r in db.material_reservations.find({"workOrderId": work_order_id}):
            r["_id"] = str(r["_id"])
            m_id = r["materialId"]
            if m_id not in reservations_by_mat:
                reservations_by_mat[m_id] = []
            reservations_by_mat[m_id].append(r)

        # Aggregate materials across all operations
        materials_agg = {}
        for op in operations:
            op_id = op.get("operationId")
            for req in op.get("requiredMaterials", []):
                mat_id = req.get("materialId")
                if not mat_id:
                    continue

                if mat_id not in materials_agg:
                    mat_doc = await db.materials.find_one({"_id": ObjectId(mat_id)}) if ObjectId.is_valid(mat_id) else None
                    spec_doc = await db.material_specifications.find_one({"_id": ObjectId(req.get("specificationId", ""))}) if ObjectId.is_valid(req.get("specificationId", "")) else None
                    
                    materials_agg[mat_id] = {
                        "materialId": mat_id,
                        "materialCode": mat_doc.get("materialCode") if mat_doc else "MAT",
                        "materialName": req.get("materialName") or (mat_doc.get("name") if mat_doc else "Raw Material"),
                        "specificationId": req.get("specificationId"),
                        "specificationName": req.get("specificationName") or (spec_doc.get("name") if spec_doc else None),
                        "unit": req.get("unit") or (mat_doc.get("unit") if mat_doc else "units"),
                        "unitCost": req.get("unitCost") or (mat_doc.get("unitCost") if mat_doc else None),
                        "requiredQuantity": 0.0,
                        "reservedQuantity": 0.0,
                        "consumedQuantity": 0.0,
                        "remainingQuantity": 0.0,
                        "estimatedCost": 0.0,
                        "actualCost": 0.0,
                        "operations": [],
                        "reservations": []
                    }

                entry = materials_agg[mat_id]
                entry["requiredQuantity"] = round(entry["requiredQuantity"] + float(req.get("totalRequiredQuantity", 0.0)), 4)
                entry["totalRequiredQuantity"] = entry["requiredQuantity"]
                entry["reservedQuantity"] = round(entry["reservedQuantity"] + float(req.get("quantityReserved", 0.0)), 4)
                entry["consumedQuantity"] = round(entry["consumedQuantity"] + float(req.get("quantityConsumed", 0.0)), 4)
                
                op_breakdown_item = {
                    "operationId": op_id,
                    "operationName": op.get("name"),
                    "quantityPerUnit": float(req.get("quantityPerUnit", 1.0)),
                    "workOrderQuantity": float(wo.get("quantity", 1.0)),
                    "requiredQuantity": float(req.get("totalRequiredQuantity", 0.0)),
                    "quantityReserved": float(req.get("quantityReserved", 0.0)),
                    "quantityConsumed": float(req.get("quantityConsumed", 0.0)),
                    "unit": req.get("unit") or entry["unit"]
                }
                entry["operations"].append(op_breakdown_item)
                if "operationBreakdown" not in entry:
                    entry["operationBreakdown"] = []
                entry["operationBreakdown"].append(op_breakdown_item)

        # Attach reservations and calculate costs
        total_estimated_cost = 0.0
        total_actual_cost = 0.0
        has_cost = False

        for mat_id, item in materials_agg.items():
            item["totalRequiredQuantity"] = item["requiredQuantity"]
            res_list = reservations_by_mat.get(mat_id, [])
            item["reservations"] = [
                {
                    "reservationId": str(r["_id"]),
                    "lotId": r["lotId"],
                    "lotNumber": r["lotNumber"],
                    "operationId": r["operationId"],
                    "quantityReserved": r["quantityReserved"],
                    "quantityConsumed": r["quantityConsumed"],
                    "unitCost": r.get("unitCost") or item.get("unitCost"),
                    "status": r["status"]
                }
                for r in res_list
            ]

            # Derive reserved and consumed directly from reservations if available
            if res_list:
                item["reservedQuantity"] = round(sum(r["quantityReserved"] for r in res_list), 4)
                item["consumedQuantity"] = round(sum(r["quantityConsumed"] for r in res_list), 4)
                
                # Also enrich operation breakdowns with actual reservation status
                for op_b in item.get("operationBreakdown", []):
                    op_res = [r for r in res_list if r["operationId"] == op_b["operationId"]]
                    if op_res:
                        op_b["quantityReserved"] = round(sum(r["quantityReserved"] for r in op_res), 4)
                        op_b["quantityConsumed"] = round(sum(r["quantityConsumed"] for r in op_res), 4)
                for op_b in item.get("operations", []):
                    op_res = [r for r in res_list if r["operationId"] == op_b["operationId"]]
                    if op_res:
                        op_b["quantityReserved"] = round(sum(r["quantityReserved"] for r in op_res), 4)
                        op_b["quantityConsumed"] = round(sum(r["quantityConsumed"] for r in op_res), 4)

            item["remainingQuantity"] = max(0.0, round(item["requiredQuantity"] - item["consumedQuantity"], 4))

            # Weighted estimated cost from reservations or standard unitCost
            mat_est_cost = 0.0
            if item["reservations"]:
                for r in item["reservations"]:
                    c = r.get("unitCost") or item.get("unitCost") or 0.0
                    mat_est_cost += (r["quantityReserved"] * c)
            elif item.get("unitCost") is not None:
                mat_est_cost = item["requiredQuantity"] * item["unitCost"]

            item["estimatedCost"] = round(mat_est_cost, 2) if mat_est_cost > 0 else (None if item.get("unitCost") is None else 0.0)

            # Actual cost from consumed reservations
            mat_act_cost = 0.0
            for r in item["reservations"]:
                c = r.get("unitCost") or item.get("unitCost") or 0.0
                mat_act_cost += (r["quantityConsumed"] * c)
            item["actualCost"] = round(mat_act_cost, 2)

            if item["estimatedCost"] is not None:
                total_estimated_cost += item["estimatedCost"]
                total_actual_cost += item["actualCost"]
                has_cost = True

        # Derive overall material status
        wo_status = wo.get("status")
        if wo_status == WorkOrderStatus.WAITING_FOR_MATERIAL.value:
            mat_status = "WAITING_FOR_MATERIAL"
        elif wo_status == WorkOrderStatus.COMPLETED.value:
            mat_status = "COMPLETED"
        else:
            all_req = sum(m["requiredQuantity"] for m in materials_agg.values())
            all_res = sum(m["reservedQuantity"] for m in materials_agg.values())
            all_cons = sum(m["consumedQuantity"] for m in materials_agg.values())
            if all_req > 0 and all_cons >= all_req:
                mat_status = "COMPLETED"
            elif all_cons > 0:
                mat_status = "CONSUMING"
            elif all_res >= all_req and all_req > 0:
                mat_status = "RESERVED"
            elif all_res > 0:
                mat_status = "PARTIALLY_RESERVED"
            else:
                mat_status = "READY"

        target_qty = float(wo.get("quantity", 0.0))
        comp_qty = float(wo.get("quantityCompleted", 0.0)) if wo.get("status") == WorkOrderStatus.COMPLETED.value else 0.0
        # If any completed leaf ops
        if wo.get("status") == WorkOrderStatus.COMPLETED.value:
            comp_qty = target_qty

        return {
            "workOrderId": work_order_id,
            "workOrderCode": wo.get("workOrderCode"),
            "status": wo_status,
            "materialStatus": mat_status,
            "productionTarget": target_qty,
            "productionCompleted": comp_qty,
            "productionRemaining": max(0.0, round(target_qty - comp_qty, 2)),
            "totalEstimatedCost": round(total_estimated_cost, 2) if has_cost else None,
            "totalActualCost": round(total_actual_cost, 2) if has_cost else None,
            "materials": list(materials_agg.values())
        }
