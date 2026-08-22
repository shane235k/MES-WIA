import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from app.core.database import get_db
from app.services.work_order_service import WorkOrderService
from app.services.material_reservation_service import MaterialReservationService
from app.services.inventory_lot_service import InventoryLotService
from app.schemas.material_reservation import ReservationStatus
from app.schemas.work_order import WorkOrderStatus, WorkOrderCreate, WorkOrderOperationStatus
from app.schemas.workflow import WorkflowCreate, WorkflowStatus

@pytest.mark.asyncio
async def test_recipe_bom_inheritance_and_work_order_costing():
    """
    Test end-to-end BOM flow:
    1. Create specification & material with unitCost.
    2. Receive 2 inventory lots with unit costs.
    3. Define Product Recipe with required materials.
    4. Create Workflow inheriting recipe BOM.
    5. Schedule Work Order: verify scaled snapshot & estimated cost.
    6. Query GET /api/work-orders/{id}/materials summary.
    7. Reserve materials: verify FIFO lot allocation and lot unit costs.
    8. Consume materials: verify actual cost calculation and lot decrement.
    """
    db = get_db()
    suffix = str(int(datetime.utcnow().timestamp()))

    # 1. Create Specification
    spec_code = f"SPEC-61-TEST-{suffix}"
    spec_doc = {
        "specificationCode": spec_code,
        "name": f"Test High-Grade Steel ({suffix})",
        "category": "SHEET",
        "grade": "SS316L",
        "dimensions": {"thicknessMm": 3.0, "widthMm": 1000.0, "lengthMm": 2000.0},
        "densityGcm3": 8.0,
        "unitOfMeasure": "sheets",
        "active": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    spec_res = await db.material_specifications.insert_one(spec_doc)
    spec_id = str(spec_res.inserted_id)

    # 2. Create Material
    mat_code = f"MAT-61-{suffix}"
    mat_doc = {
        "materialCode": mat_code,
        "name": f"3mm SS316L Sheet ({suffix})",
        "unit": "sheets",
        "quantityAvailable": 0.0,
        "quantityOnHand": 0.0,
        "quantityReserved": 0.0,
        "reorderLevel": 10.0,
        "active": True,
        "specificationId": spec_id,
        "category": "SHEET",
        "grade": "SS316L",
        "unitCost": 600.0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    mat_res = await db.materials.insert_one(mat_doc)
    mat_id = str(mat_res.inserted_id)

    # 3. Receive Two Lots with FIFO timestamps and unit costs
    lot1_num = f"LOT-61-A-{suffix}"
    lot1_doc = {
        "lotNumber": lot1_num,
        "materialId": mat_id,
        "specificationId": spec_id,
        "quantityOnHand": 50.0,
        "quantityReserved": 0.0,
        "unit": "sheets",
        "unitCost": 600.0,
        "supplier": "Vendor Alpha",
        "location": "Bay A",
        "receivedDate": datetime.utcnow() - timedelta(days=2),
        "status": "AVAILABLE",
        "createdAt": datetime.utcnow() - timedelta(days=2),
        "updatedAt": datetime.utcnow() - timedelta(days=2)
    }
    await db.inventory_lots.insert_one(lot1_doc)

    lot2_num = f"LOT-61-B-{suffix}"
    lot2_doc = {
        "lotNumber": lot2_num,
        "materialId": mat_id,
        "specificationId": spec_id,
        "quantityOnHand": 100.0,
        "quantityReserved": 0.0,
        "unit": "sheets",
        "unitCost": 650.0,
        "supplier": "Vendor Beta",
        "location": "Bay B",
        "receivedDate": datetime.utcnow() - timedelta(days=1),
        "status": "AVAILABLE",
        "createdAt": datetime.utcnow() - timedelta(days=1),
        "updatedAt": datetime.utcnow() - timedelta(days=1)
    }
    await db.inventory_lots.insert_one(lot2_doc)

    await InventoryLotService.sync_material_stock(mat_id)

    # 4. Create Product with Recipe BOM
    prod_code = f"PROD-61-{suffix}"
    prod_doc = {
        "productCode": prod_code,
        "name": f"Industrial Enclosure ({suffix})",
        "description": "Sheet metal enclosure box",
        "unit": "pcs",
        "active": True,
        "recipes": [
            {
                "recipeId": f"RECIPE-{prod_code}-V1",
                "recipeName": f"{prod_code}:v1",
                "version": 1,
                "status": "ACTIVE",
                "steps": [
                    {
                        "stepId": "STEP-10",
                        "sequence": 10,
                        "name": "Precision CNC Laser Cutting",
                        "requiredMachineType": "CUTTING",
                        "estimatedQuantityRate": 1.0,
                        "dependencies": [],
                        "requiredMaterials": [
                            {
                                "materialId": mat_id,
                                "specificationId": spec_id,
                                "quantity": 0.5, # 0.5 sheets per finished enclosure
                                "unit": "sheets"
                            }
                        ]
                    },
                    {
                        "stepId": "STEP-20",
                        "sequence": 20,
                        "name": "Hydraulic Press Bending",
                        "requiredMachineType": "BENDING",
                        "estimatedQuantityRate": 1.0,
                        "dependencies": ["STEP-10"],
                        "requiredMaterials": []
                    }
                ]
            }
        ],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    prod_res = await db.products.insert_one(prod_doc)
    prod_id = str(prod_res.inserted_id)

    # 5. Create Workflow inheriting Recipe BOM
    wf_code = f"WF-61-{suffix}"
    wf_doc = {
        "workflowCode": wf_code,
        "name": f"Workflow {prod_code}",
        "productId": prod_id,
        "version": 1,
        "status": WorkflowStatus.ACTIVE.value,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Precision CNC Laser Cutting",
                "sequence": 10,
                "requiredMachineType": "CUTTING",
                "estimatedDurationSeconds": 10,
                "dependencies": [],
                "requiredMaterials": [
                    {
                        "materialId": mat_id,
                        "specificationId": spec_id,
                        "quantity": 0.5,
                        "unit": "sheets"
                    }
                ]
            },
            {
                "operationId": "OP-20",
                "name": "Hydraulic Press Bending",
                "sequence": 20,
                "requiredMachineType": "BENDING",
                "estimatedDurationSeconds": 10,
                "dependencies": ["OP-10"],
                "requiredMaterials": []
            }
        ],
        "createdBy": "TEST",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    wf_res = await db.workflows.insert_one(wf_doc)
    wf_id = str(wf_res.inserted_id)

    # 6. Schedule Work Order for batch size of 120 finished enclosures
    # Required raw material = 120 * 0.5 = 60 sheets.
    # Estimated Cost = 60 * 600 = ₹36,000.
    wo_in = WorkOrderCreate(
        workOrderCode=f"WO-61-{suffix}",
        name=f"Batch WO-61-{suffix}",
        productId=prod_id,
        workflowId=wf_id,
        workflowVersion=1,
        quantity=120,
        priority="HIGH",
        dueDate=datetime.utcnow() + timedelta(days=2)
    )

    created_wo = await WorkOrderService.create_work_order(wo_in)
    wo_id = str(created_wo["_id"])

    # Verify Snapshot Scaling in WorkOrder operations
    op10 = next(o for o in created_wo["operations"] if o["operationId"] == "OP-10")
    assert len(op10["requiredMaterials"]) == 1
    snap = op10["requiredMaterials"][0]
    assert snap["materialId"] == mat_id
    assert snap["quantityPerUnit"] == 0.5
    assert snap["totalRequiredQuantity"] == 60.0
    assert snap["quantityReserved"] == 0.0
    assert snap["quantityConsumed"] == 0.0
    assert snap["unitCost"] == 600.0
    assert snap["estimatedCost"] == 36000.0

    # 7. Check Aggregated Work Order Material Summary Endpoint
    summary = await MaterialReservationService.get_work_order_material_summary(wo_id)
    assert summary["workOrderId"] == wo_id
    assert summary["materialStatus"] == "READY"
    assert summary["totalEstimatedCost"] == 36000.0
    assert summary["totalActualCost"] == 0.0
    assert len(summary["materials"]) == 1
    mat_summary = summary["materials"][0]
    assert mat_summary["requiredQuantity"] == 60.0
    assert mat_summary["reservedQuantity"] == 0.0
    assert mat_summary["remainingQuantity"] == 60.0

    # 8. Reserve Materials for Work Order
    # Needs 60 sheets. Lot 1 has 50 sheets (FIFO). Lot 2 has 100 sheets.
    # Split: Lot 1 (50 sheets @ ₹600) + Lot 2 (10 sheets @ ₹650).
    res_result = await MaterialReservationService.reserve_for_work_order(wo_id, actor_id="TEST")
    assert res_result["success"] is True
    assert res_result["reservationsCount"] == 2

    # Verify Reservations in DB
    reservations = await MaterialReservationService.list_reservations(work_order_id=wo_id)
    assert len(reservations) == 2
    r_lot1 = next(r for r in reservations if r["lotNumber"] == lot1_num)
    r_lot2 = next(r for r in reservations if r["lotNumber"] == lot2_num)
    assert r_lot1["quantityReserved"] == 50.0
    assert r_lot1["unitCost"] == 600.0
    assert r_lot2["quantityReserved"] == 10.0
    assert r_lot2["unitCost"] == 650.0

    # Check Updated Material Summary after reservation
    summary_reserved = await MaterialReservationService.get_work_order_material_summary(wo_id)
    assert summary_reserved["materialStatus"] == "RESERVED"
    assert summary_reserved["materials"][0]["reservedQuantity"] == 60.0
    assert len(summary_reserved["materials"][0]["reservations"]) == 2

    # 9. Live Consumption upon Operation OP-10 Completion
    consumed_txs = await MaterialReservationService.consume_for_operation(
        work_order_id=wo_id,
        operation_id="OP-10",
        actor_id="OP-001"
    )
    assert len(consumed_txs) == 2

    # Verify Lot Physical Balances Decremented
    updated_lot1 = await InventoryLotService.get_lot_by_id(r_lot1["lotId"])
    updated_lot2 = await InventoryLotService.get_lot_by_id(r_lot2["lotId"])
    assert updated_lot1["quantityOnHand"] == 0.0 # 50 - 50 = 0
    assert updated_lot1["quantityReserved"] == 0.0
    assert updated_lot2["quantityOnHand"] == 90.0 # 100 - 10 = 90
    assert updated_lot2["quantityReserved"] == 0.0

    # Check Summary after Consumption
    summary_consumed = await MaterialReservationService.get_work_order_material_summary(wo_id)
    assert summary_consumed["materials"][0]["consumedQuantity"] == 60.0
    assert summary_consumed["materials"][0]["remainingQuantity"] == 0.0
    # Actual cost = (50 * 600) + (10 * 650) = 30000 + 6500 = 36500
    assert summary_consumed["totalActualCost"] == 36500.0

    # Clean up test documents
    await db.material_specifications.delete_one({"_id": ObjectId(spec_id)})
    await db.materials.delete_one({"_id": ObjectId(mat_id)})
    await db.inventory_lots.delete_many({"materialId": mat_id})
    await db.products.delete_one({"_id": ObjectId(prod_id)})
    await db.workflows.delete_one({"_id": ObjectId(wf_id)})
    await db.work_orders.delete_one({"_id": ObjectId(wo_id)})
    await db.material_reservations.delete_many({"workOrderId": wo_id})
    await db.material_transactions.delete_many({"workOrderId": wo_id})
