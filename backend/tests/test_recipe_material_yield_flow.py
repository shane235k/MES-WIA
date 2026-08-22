import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from bson import ObjectId

from app.core.database import get_db
from app.services.material_specification_service import MaterialSpecificationService
from app.services.material_service import MaterialService
from app.services.inventory_lot_service import InventoryLotService
from app.services.material_reservation_service import MaterialReservationService
from app.services.product_service import ProductService
from app.services.machine_service import MachineService
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService
from app.services.work_order_service import WorkOrderService
from app.services.execution_engine import ExecutionEngine

from app.schemas.material_specification import MaterialSpecificationCreate, MaterialForm
from app.schemas.material import MaterialCreate
from app.schemas.inventory_lot import InventoryLotCreate, LotStatus
from app.schemas.product import ProductCreate
from app.schemas.machine import MachineCreate, MachineStatus
from app.schemas.user import UserCreate, UserRole, OperatorAvailability
from app.schemas.workflow import WorkflowCreate
from app.schemas.work_order import WorkOrderCreate, WorkOrderStatus, WorkOrderOperationStatus

@pytest.mark.asyncio
async def test_material_requirement_does_not_multiply_production_yield():
    """
    TEST 1 & 2:
    Recipe:
      Operation 1 (CUTTING): 1 sheet/unit
      Operation 2 (BENDING): 1 sheet/unit
    Work Order: 10 units
    Expected:
      CUTTING requirement = 10
      BENDING requirement = 10
      Total Material requirement = 20 sheets
      Production Target remains = 10 finished products (NEVER 20!)
    """
    db = get_db()
    uid = uuid.uuid4().hex[:6].upper()
    
    # 1. Setup Material
    spec = await MaterialSpecificationService.create_specification(MaterialSpecificationCreate(
        specificationCode=f"SPEC-STL-{uid}",
        name="Steel Sheet Spec",
        category=MaterialForm.SHEET,
        grade="Mild Steel",
        unitOfMeasure="sheets",
        active=True
    ))
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode=f"MAT-STL-{uid}",
        name="Steel Sheet",
        category=MaterialForm.SHEET,
        specificationId=str(spec["_id"]),
        unit="sheets",
        unitCost=50.0
    ))
    mat_id = str(mat["_id"])

    # 2. Setup Product
    prod = await ProductService.create_product(ProductCreate(
        productCode=f"PROD-BRK-{uid}",
        name="Bracket A",
        description="Test Bracket",
        unit="units"
    ))
    prod_id = str(prod["_id"])

    # 3. Setup Workflow with 2 operations each requiring 1 sheet
    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode=f"WF-BRK-{uid}",
        name="Bracket Workflow",
        productId=prod_id,
        operations=[
            {
                "operationId": "OP-CUT",
                "name": "Cutting",
                "sequence": 1,
                "requiredMachineType": "CUTTING",
                "requiredMaterials": [{"materialId": mat_id, "quantity": 1.0, "unit": "sheets"}],
                "dependencies": []
            },
            {
                "operationId": "OP-BEND",
                "name": "Bending",
                "sequence": 2,
                "requiredMachineType": "BENDING",
                "requiredMaterials": [{"materialId": mat_id, "quantity": 1.0, "unit": "sheets"}],
                "dependencies": ["OP-CUT"]
            }
        ]
    ))
    wf_id = str(wf["_id"])

    # 4. Create Work Order of 10 units
    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode=f"WO-BRK-{uid}",
        name="Yield Test Batch",
        productId=prod_id,
        workflowId=wf_id,
        quantity=10.0,
        dueDate=datetime.utcnow() + timedelta(days=5)
    ))
    wo_id = str(wo["_id"])

    # 5. Verify snapshot material requirements and target production quantity
    assert wo["quantity"] == 10.0, "Production target must be 10"
    
    op_cut = next(o for o in wo["operations"] if o["operationId"] == "OP-CUT")
    op_bend = next(o for o in wo["operations"] if o["operationId"] == "OP-BEND")

    assert op_cut["requiredMaterials"][0]["quantityPerUnit"] == 1.0
    assert op_cut["requiredMaterials"][0]["totalRequiredQuantity"] == 10.0
    assert op_bend["requiredMaterials"][0]["quantityPerUnit"] == 1.0
    assert op_bend["requiredMaterials"][0]["totalRequiredQuantity"] == 10.0

    # 6. Verify Material Summary aggregation & operation breakdown
    summary = await MaterialReservationService.get_work_order_material_summary(wo_id)
    assert summary["productionTarget"] == 10.0
    assert len(summary["materials"]) == 1
    steel_summary = summary["materials"][0]
    assert steel_summary["requiredQuantity"] == 20.0, "Total steel required across operations must be 20"
    assert len(steel_summary["operationBreakdown"]) == 2
    assert steel_summary["operationBreakdown"][0]["requiredQuantity"] == 10.0
    assert steel_summary["operationBreakdown"][1]["requiredQuantity"] == 10.0

@pytest.mark.asyncio
async def test_material_free_downstream_process_flow():
    """
    TEST 4 & 10L:
    Product: BRACKET-A
    Work Order: 10 units
    Recipe:
      Operation 1 (CUTTING): Steel Sheet 1 sheet/unit, Machine rate = 2 units/sec
      Operation 2 (BENDING): Steel Sheet 1 sheet/unit, Machine rate = 1 unit/sec
      Operation 3 (PROCESS T): Material NONE, Machine rate = 5 units/sec
    Expected:
      CUTTING: input=10, material=10 sheets, output=10
      BENDING: input=10, material=10 sheets, output=10
      PROCESS T: input=10, material=0, output=10, duration = max(3, 10/5) = 3 sec
      Final finished products = 10
      Total steel consumed = 20 sheets
    """
    db = get_db()
    uid = uuid.uuid4().hex[:6].upper()

    # 1. Setup Material & Stock Lot
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode=f"MAT-FLOW-{uid}",
        name="Steel Sheet Flow",
        category=MaterialForm.SHEET,
        unit="sheets",
        unitCost=40.0
    ))
    mat_id = str(mat["_id"])

    await InventoryLotService.create_lot(InventoryLotCreate(
        lotNumber=f"LOT-FLOW-{uid}",
        materialId=mat_id,
        quantityOnHand=100.0,
        unit="sheets",
        unitCost=40.0,
        status=LotStatus.AVAILABLE
    ))

    # 2. Setup Machines with respective processing rates
    m_cut = await MachineService.create_machine(MachineCreate(
        machineCode=f"M-CUT-{uid}",
        name="Cutting Machine 1",
        type="CUTTING",
        location="Bay 1",
        status=MachineStatus.IDLE,
        processingRate=2.0,  # 2 units/sec
        availability=True
    ))
    m_bend = await MachineService.create_machine(MachineCreate(
        machineCode=f"M-BEND-{uid}",
        name="Bending Machine 1",
        type="BENDING",
        location="Bay 2",
        status=MachineStatus.IDLE,
        processingRate=1.0,  # 1 unit/sec
        availability=True
    ))
    m_proc_t = await MachineService.create_machine(MachineCreate(
        machineCode=f"M-PROCT-{uid}",
        name="Process T Inspection",
        type="INSPECTION",
        location="Bay 3",
        status=MachineStatus.IDLE,
        processingRate=5.0,  # 5 units/sec
        availability=True
    ))

    # 3. Setup Operators and Supervisor
    op_user = await UserService.create_user(UserCreate(
        employeeId=f"EMP-FLOW-{uid}",
        name="Flow Operator",
        email=f"flow.{uid.lower()}@example.com",
        department="Fabrication",
        role=UserRole.OPERATOR,
        availabilityStatus=OperatorAvailability.AVAILABLE
    ))
    user_id = str(op_user["_id"])

    sup_user = await UserService.create_user(UserCreate(
        employeeId=f"SUP-FLOW-{uid}",
        name="Flow Supervisor",
        email=f"sup.{uid.lower()}@example.com",
        department="Fabrication",
        role=UserRole.SUPERVISOR,
        availabilityStatus=OperatorAvailability.AVAILABLE
    ))
    sup_id = str(sup_user["_id"])

    # 4. Setup Product & Workflow
    prod = await ProductService.create_product(ProductCreate(
        productCode=f"PROD-FLOW-{uid}",
        name="Bracket Flow Model",
        description="Flow Bracket",
        unit="units"
    ))
    prod_id = str(prod["_id"])

    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode=f"WF-FLOW-{uid}",
        name="Bracket 3-Step Flow",
        productId=prod_id,
        operations=[
            {
                "operationId": "OP-CUT",
                "name": "Cutting",
                "sequence": 1,
                "requiredMachineType": "CUTTING",
                "assignedMachineId": str(m_cut["_id"]),
                "assignedOperatorId": user_id,
                "requiredMaterials": [{"materialId": mat_id, "quantity": 1.0, "unit": "sheets"}],
                "dependencies": []
            },
            {
                "operationId": "OP-BEND",
                "name": "Bending",
                "sequence": 2,
                "requiredMachineType": "BENDING",
                "assignedMachineId": str(m_bend["_id"]),
                "assignedOperatorId": user_id,
                "requiredMaterials": [{"materialId": mat_id, "quantity": 1.0, "unit": "sheets"}],
                "dependencies": ["OP-CUT"]
            },
            {
                "operationId": "OP-PROCT",
                "name": "Process T",
                "sequence": 3,
                "requiredMachineType": "INSPECTION",
                "assignedMachineId": str(m_proc_t["_id"]),
                "assignedOperatorId": user_id,
                "requiredMaterials": [],  # MATERIAL FREE
                "dependencies": ["OP-BEND"]
            }
        ]
    ))
    wf_id = str(wf["_id"])

    # 5. Create Work Order of 10 units
    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode=f"WO-FLOW-{uid}",
        name="Process T Material-Free Flow Test",
        productId=prod_id,
        workflowId=wf_id,
        supervisorId=sup_id,
        quantity=10.0,
        dueDate=datetime.utcnow() + timedelta(days=2)
    ))
    wo_id = str(wo["_id"])

    # Start Work Order
    started_wo = await ExecutionEngine.start_work_order(wo_id)
    assert started_wo["status"] == WorkOrderStatus.IN_PROGRESS.value

    # First evaluate: starts OP-CUT (duration = max(3, 10/2) = 5s)
    await ExecutionEngine.evaluate_execution(wo_id)
    state = await ExecutionEngine.get_execution_state(wo_id)
    op_cut_state = next(o for o in state["operations"] if o["operationId"] == "OP-CUT")
    assert op_cut_state["status"] == WorkOrderOperationStatus.IN_PROGRESS.value
    assert op_cut_state["durationSeconds"] == 5

    # Simulate OP-CUT completion
    await db.work_orders.update_one(
        {"_id": ObjectId(wo_id), "operations.operationId": "OP-CUT"},
        {"$set": {"operations.$.estimatedCompletionAt": datetime.utcnow() - timedelta(seconds=1)}}
    )
    await ExecutionEngine.evaluate_execution(wo_id)

    # Free up operator for next step
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"availabilityStatus": OperatorAvailability.AVAILABLE.value}})

    # OP-BEND starts (duration = max(3, 10/1) = 10s)
    await ExecutionEngine.evaluate_execution(wo_id)
    state = await ExecutionEngine.get_execution_state(wo_id)
    op_bend_state = next(o for o in state["operations"] if o["operationId"] == "OP-BEND")
    assert op_bend_state["status"] == WorkOrderOperationStatus.IN_PROGRESS.value
    assert op_bend_state["durationSeconds"] == 10
    assert op_bend_state["inputQuantity"] == 10.0

    # Simulate OP-BEND completion
    await db.work_orders.update_one(
        {"_id": ObjectId(wo_id), "operations.operationId": "OP-BEND"},
        {"$set": {"operations.$.estimatedCompletionAt": datetime.utcnow() - timedelta(seconds=1)}}
    )
    await ExecutionEngine.evaluate_execution(wo_id)

    # Free up operator for next step
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"availabilityStatus": OperatorAvailability.AVAILABLE.value}})

    # OP-PROCT (Material-free) starts: duration = max(3, int(10/5)) = max(3, 2) = 3s
    await ExecutionEngine.evaluate_execution(wo_id)
    state = await ExecutionEngine.get_execution_state(wo_id)
    op_proct_state = next(o for o in state["operations"] if o["operationId"] == "OP-PROCT")
    assert op_proct_state["status"] == WorkOrderOperationStatus.IN_PROGRESS.value
    assert op_proct_state["durationSeconds"] == 3, "Duration must be max(3, 10/5) = 3s"
    assert op_proct_state["inputQuantity"] == 10.0

    # Simulate OP-PROCT completion
    await db.work_orders.update_one(
        {"_id": ObjectId(wo_id), "operations.operationId": "OP-PROCT"},
        {"$set": {"operations.$.estimatedCompletionAt": datetime.utcnow() - timedelta(seconds=1)}}
    )
    await ExecutionEngine.evaluate_execution(wo_id)

    # Entire work order completed
    final_wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
    assert final_wo["status"] == WorkOrderStatus.COMPLETED.value
    assert final_wo["quantity"] == 10.0, "Production target must remain 10 finished products"

    # Verify material consumption is exactly 20 sheets
    summary = await MaterialReservationService.get_work_order_material_summary(wo_id)
    print("\nDEBUG SUMMARY IN TEST 4:", summary)
    assert summary["productionTarget"] == 10.0
    assert summary["productionCompleted"] == 10.0
    steel_summary = summary["materials"][0]
    assert steel_summary["consumedQuantity"] == 20.0
    assert steel_summary["remainingQuantity"] == 0.0

@pytest.mark.asyncio
async def test_multiple_operations_never_multiply_finished_product_yield():
    """
    TEST 5:
    A 2-operation recipe and a 5-operation recipe with identical 10 unit work orders
    must both produce exactly 10 finished products.
    """
    db = get_db()
    uid = uuid.uuid4().hex[:6].upper()

    prod = await ProductService.create_product(ProductCreate(
        productCode=f"PROD-5OP-{uid}",
        name="Multi-Op Widget",
        description="Multi-op widget description",
        unit="units"
    ))
    prod_id = str(prod["_id"])

    # 5-operation workflow
    wf_ops = []
    prev_dep = []
    for i in range(1, 6):
        op_id = f"OP-{i*10}"
        wf_ops.append({
            "operationId": op_id,
            "name": f"Step {i}",
            "sequence": i,
            "requiredMachineType": "GENERIC",
            "requiredMaterials": [],
            "dependencies": list(prev_dep)
        })
        prev_dep = [op_id]

    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode=f"WF-5OP-{uid}",
        name="5-Op Widget Workflow",
        productId=prod_id,
        operations=wf_ops
    ))
    wf_id = str(wf["_id"])

    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode=f"WO-5OP-{uid}",
        name="5-Op Batch",
        productId=prod_id,
        workflowId=wf_id,
        quantity=10.0,
        dueDate=datetime.utcnow() + timedelta(days=1)
    ))

    assert wo["quantity"] == 10.0
    assert len(wo["operations"]) == 5
    summary = await MaterialReservationService.get_work_order_material_summary(str(wo["_id"]))
    assert summary["productionTarget"] == 10.0
