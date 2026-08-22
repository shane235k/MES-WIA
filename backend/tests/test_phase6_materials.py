import pytest
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId

from app.core.database import get_db
from app.services.material_specification_service import MaterialSpecificationService
from app.services.material_service import MaterialService
from app.services.inventory_lot_service import InventoryLotService
from app.services.material_reservation_service import MaterialReservationService
from app.services.material_transaction_service import MaterialTransactionService
from app.services.product_service import ProductService
from app.services.capability_service import CapabilityService
from app.services.machine_service import MachineService
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService
from app.services.work_order_service import WorkOrderService
from app.services.execution_engine import ExecutionEngine

from app.schemas.material_specification import MaterialSpecificationCreate, MaterialSpecificationUpdate, MaterialForm
from app.schemas.material import MaterialCreate
from app.schemas.inventory_lot import InventoryLotCreate, InventoryLotReceive, InventoryLotAdjust, LotStatus
from app.schemas.material_transaction import MaterialTransactionType, ScrapReasonCode
from app.schemas.product import ProductCreate, ProductRecipe, RecipeStep
from app.schemas.capability import CapabilityCreate
from app.schemas.machine import MachineCreate
from app.schemas.user import UserCreate, UserRole
from app.schemas.workflow import WorkflowCreate
from app.schemas.work_order import WorkOrderCreate, WorkOrderStatus

@pytest.mark.asyncio
async def test_material_specification_crud():
    # 1. Create Specification
    spec_data = {
        "specificationCode": "TEST-SPEC-SS304",
        "name": "SS304 Sheet 2mm",
        "category": MaterialForm.SHEET,
        "grade": "SS304",
        "dimensions": {"thicknessMm": 2.0, "widthMm": 1000.0, "lengthMm": 2000.0},
        "densityGcm3": 7.93,
        "unitOfMeasure": "sheets",
        "active": True
    }
    created = await MaterialSpecificationService.create_specification(MaterialSpecificationCreate(**spec_data))
    assert created["specificationCode"] == "TEST-SPEC-SS304"
    spec_id = str(created["_id"])

    # 2. Duplicate constraint
    with pytest.raises(ValueError) as exc:
        await MaterialSpecificationService.create_specification(MaterialSpecificationCreate(**spec_data))
    assert "already exists" in str(exc.value)

    # 3. Get & List
    fetched = await MaterialSpecificationService.get_specification_by_id(spec_id)
    assert fetched["grade"] == "SS304"
    lst = await MaterialSpecificationService.list_specifications(category="SHEET")
    assert len(lst) >= 1

    # 4. Update
    updated = await MaterialSpecificationService.update_specification(
        spec_id, MaterialSpecificationUpdate(grade="SS304L")
    )
    assert updated["grade"] == "SS304L"

    # 5. Delete
    deleted = await MaterialSpecificationService.delete_specification(spec_id)
    assert deleted is True

@pytest.mark.asyncio
async def test_inventory_lot_lifecycle_and_balance():
    # Setup parent material
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode="MAT-LOT-TEST", name="Lot Test Steel", unit="sheets", quantityAvailable=0, reorderLevel=10
    ))
    mat_id = str(mat["_id"])

    # 1. Create Lot 1
    lot1 = await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber="LOT-TEST-001",
        materialId=mat_id,
        quantityOnHand=100.0,
        unit="sheets",
        supplier="Vendor A",
        location="Bay 1"
    ))
    lot1_id = str(lot1["_id"])
    assert lot1["quantityOnHand"] == 100.0

    # 2. Duplicate Lot Number + Material ID check
    with pytest.raises(ValueError) as exc:
        await InventoryLotService.create_lot(InventoryLotCreate(
            lotNumber="LOT-TEST-001",
            materialId=mat_id,
            quantityOnHand=50.0,
            unit="sheets"
        ))
    assert "already exists" in str(exc.value)

    # 3. Derived quantityAvailable check on material
    parent_mat = await MaterialService.get_material_by_id(mat_id)
    assert parent_mat["quantityOnHand"] == 100.0
    assert parent_mat["quantityAvailable"] == 100.0

    # 4. Receive additional stock into lot
    rec = await InventoryLotService.receive_stock(
        lot1_id, InventoryLotReceive(quantity=50.0, notes="Batch delivery")
    )
    assert rec["quantityOnHand"] == 150.0
    parent_mat = await MaterialService.get_material_by_id(mat_id)
    assert parent_mat["quantityAvailable"] == 150.0

    # 5. Adjust stock
    adj = await InventoryLotService.adjust_stock(
        lot1_id, InventoryLotAdjust(newQuantityOnHand=140.0, reason="Cycle count scrap loss")
    )
    assert adj["quantityOnHand"] == 140.0
    parent_mat = await MaterialService.get_material_by_id(mat_id)
    assert parent_mat["quantityAvailable"] == 140.0

@pytest.mark.asyncio
async def test_fifo_fefo_and_multi_lot_reservation():
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode="MAT-ALLOC-TEST", name="Allocation Material", unit="sheets", quantityAvailable=0, reorderLevel=10
    ))
    mat_id = str(mat["_id"])

    now = datetime.utcnow()
    # Lot 1: Expiring in 2 days (FEFO priority)
    lot1 = await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber="LOT-FEFO-01",
        materialId=mat_id,
        quantityOnHand=40.0,
        unit="sheets",
        expiryDate=now + timedelta(days=2),
        receivedDate=now - timedelta(days=5)
    ))
    # Lot 2: Expiring in 10 days
    lot2 = await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber="LOT-FEFO-02",
        materialId=mat_id,
        quantityOnHand=60.0,
        unit="sheets",
        expiryDate=now + timedelta(days=10),
        receivedDate=now - timedelta(days=10)
    ))

    # Allocate 70 sheets (Requires 40 from Lot 1 + 30 from Lot 2)
    success, reservations, unallocated = await MaterialReservationService.allocate_and_reserve(
        work_order_id="66c000000000000000000001",
        work_order_code="WO-ALLOC-01",
        operation_id="OP-10",
        material_id=mat_id,
        required_qty=70.0
    )

    assert success is True
    assert len(reservations) == 2
    assert reservations[0]["lotNumber"] == "LOT-FEFO-01"
    assert reservations[0]["quantityReserved"] == 40.0
    assert reservations[1]["lotNumber"] == "LOT-FEFO-02"
    assert reservations[1]["quantityReserved"] == 30.0
    assert unallocated == 0.0

    # Verify material aggregated counters
    parent_mat = await MaterialService.get_material_by_id(mat_id)
    assert parent_mat["quantityOnHand"] == 100.0
    assert parent_mat["quantityReserved"] == 70.0
    assert parent_mat["quantityAvailable"] == 30.0

@pytest.mark.asyncio
async def test_insufficient_inventory_and_rollback():
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode="MAT-SHORT-TEST", name="Shortage Test", unit="sheets", quantityAvailable=0, reorderLevel=10
    ))
    mat_id = str(mat["_id"])

    await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber="LOT-SHORT-01",
        materialId=mat_id,
        quantityOnHand=20.0,
        unit="sheets"
    ))

    # Request 50 sheets when only 20 exist
    success, reservations, unallocated = await MaterialReservationService.allocate_and_reserve(
        work_order_id="66c000000000000000000002",
        work_order_code="WO-SHORT-01",
        operation_id="OP-10",
        material_id=mat_id,
        required_qty=50.0
    )

    assert success is False
    assert len(reservations) == 0
    assert unallocated == 30.0

    # Ensure no partial reservation remained locked
    parent_mat = await MaterialService.get_material_by_id(mat_id)
    assert parent_mat["quantityReserved"] == 0.0
    assert parent_mat["quantityAvailable"] == 20.0

@pytest.mark.asyncio
async def test_consumption_and_append_only_ledger():
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode="MAT-LEDGER-TEST", name="Ledger Test", unit="sheets", quantityAvailable=0, reorderLevel=10
    ))
    mat_id = str(mat["_id"])

    lot = await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber="LOT-LEDGER-01",
        materialId=mat_id,
        quantityOnHand=100.0,
        unit="sheets"
    ))

    wo_id = "66c000000000000000000003"
    # 1. Reserve 50 sheets
    success, res_list, _ = await MaterialReservationService.allocate_and_reserve(
        work_order_id=wo_id,
        work_order_code="WO-LEDGER-01",
        operation_id="OP-10",
        material_id=mat_id,
        required_qty=50.0
    )
    assert success is True

    # 2. Consume for operation (Actual consumed: 48, Scrap: 2)
    consumed_txs = await MaterialReservationService.consume_for_operation(
        work_order_id=wo_id,
        operation_id="OP-10",
        actual_consumed=48.0,
        scrap_qty=2.0,
        scrap_reason=ScrapReasonCode.DIMENSIONAL_DEFECT
    )
    assert len(consumed_txs) == 2  # 1 CONSUMPTION + 1 SCRAP

    # 3. Check lot balance: 100 - 48 = 52 on hand, 0 reserved
    updated_lot = await InventoryLotService.get_lot_by_id(str(lot["_id"]))
    assert updated_lot["quantityOnHand"] == 52.0
    assert updated_lot["quantityReserved"] == 0.0

    # 4. Check ledger contains all transactions in sequence
    txs = await MaterialTransactionService.list_transactions(material_id=mat_id)
    tx_types = [t["transactionType"] for t in txs]
    assert "RECEIPT" in tx_types
    assert "RESERVATION_CREATED" in tx_types
    assert "CONSUMPTION" in tx_types
    assert "SCRAP" in tx_types

@pytest.mark.asyncio
async def test_traceability_forward_and_backward():
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode="MAT-TRACE-01", name="Trace Metal", unit="sheets", quantityAvailable=0, reorderLevel=10
    ))
    mat_id = str(mat["_id"])

    lot = await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber="LOT-TRACE-777",
        materialId=mat_id,
        quantityOnHand=200.0,
        supplier="Acme Specialty Metals",
        batchNumber="BATCH-777-X",
        heatNumber="HEAT-HT-9999",
        unit="sheets"
    ))

    # Create Product, Workflow, Work Order
    prod = await ProductService.create_product(ProductCreate(
        productCode="PROD-TRACE", name="Traceable Enclosure", description="Precision chassis"
    ))
    sup = await UserService.create_user(UserCreate(
        employeeId="SUP-TR-01", name="Trace Supervisor", email="suptr@mes.com", role=UserRole.SUPERVISOR, department="Eng"
    ))
    op1 = await UserService.create_user(UserCreate(
        employeeId="OP-TR-01", name="Trace Operator", email="optr@mes.com", role=UserRole.OPERATOR, department="Fab"
    ))
    mach = await MachineService.create_machine(MachineCreate(
        machineCode="M-TR-01", name="Trace Cutter", type="CUTTING", location="Bay 1", processingRate=5.0
    ))

    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode="WF-TRACE-01",
        name="Trace Workflow",
        productId=str(prod["_id"]),
        supervisorId=str(sup["_id"]),
        version=1,
        status="ACTIVE",
        operations=[{
            "operationId": "OP-10",
            "name": "Laser Profile",
            "sequence": 10,
            "requiredMachineType": "CUTTING",
            "assignedMachineId": str(mach["_id"]),
            "assignedOperatorId": str(op1["_id"]),
            "estimatedDurationSeconds": 1,
            "requiredMaterials": [{"materialId": mat_id, "quantity": 0.5}],
            "dependencies": []
        }]
    ))

    # Create Work Order for 100 units (Requires 0.5 * 100 = 50 sheets)
    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode="WO-TRACE-99",
        name="Trace Batch",
        productId=str(prod["_id"]),
        workflowId=str(wf["_id"]),
        workflowVersion=1,
        supervisorId=str(sup["_id"]),
        quantity=100.0,
        dueDate=datetime.utcnow() + timedelta(days=5)
    ))
    wo_id = str(wo["_id"])

    # Verify requiredMaterials snapshot in WorkOrderOperation
    assert len(wo["operations"][0]["requiredMaterials"]) == 1
    assert wo["operations"][0]["requiredMaterials"][0]["totalRequiredQuantity"] == 50.0

    # Start Work Order (Triggers automatic reservation)
    await ExecutionEngine.start_work_order(wo_id)

    # 1. Forward Traceability Test (Lot -> WO)
    fwd = await MaterialReservationService.get_forward_traceability("LOT-TRACE-777")
    assert fwd["lot"]["supplier"] == "Acme Specialty Metals"
    assert fwd["lot"]["heatNumber"] == "HEAT-HT-9999"
    assert len(fwd["workOrders"]) == 1
    assert fwd["workOrders"][0]["workOrderCode"] == "WO-TRACE-99"

    # 2. Backward Traceability Test (WO -> Consumed Lots)
    bkwd = await MaterialReservationService.get_backward_traceability(wo_id)
    assert bkwd["workOrder"]["workOrderCode"] == "WO-TRACE-99"
    assert len(bkwd["consumedLots"]) == 1
    assert bkwd["consumedLots"][0]["lotNumber"] == "LOT-TRACE-777"
    assert bkwd["consumedLots"][0]["heatNumber"] == "HEAT-HT-9999"

@pytest.mark.asyncio
async def test_legacy_material_migration_idempotent():
    db = get_db()
    # Insert legacy material directly without lots
    raw_legacy = {
        "materialCode": "LEGACY-COPPER-1MM",
        "name": "Legacy Copper Foil",
        "unit": "meters",
        "quantityAvailable": 350.0,
        "reorderLevel": 50.0,
        "active": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    res = await db.materials.insert_one(raw_legacy)
    legacy_id = str(res.inserted_id)

    # Run migration pass 1
    res1 = await InventoryLotService.migrate_legacy_materials()
    assert res1["migrated"] >= 1

    # Verify lot created
    migrated_lot = await db.inventory_lots.find_one({"lotNumber": "LOT-INIT-LEGACY-COPPER-1MM"})
    assert migrated_lot is not None
    assert migrated_lot["quantityOnHand"] == 350.0

    # Run migration pass 2 (Idempotency check: must not duplicate stock)
    res2 = await InventoryLotService.migrate_legacy_materials()
    assert res2["migrated"] == 0

    lot_count = await db.inventory_lots.count_documents({"lotNumber": "LOT-INIT-LEGACY-COPPER-1MM"})
    assert lot_count == 1
