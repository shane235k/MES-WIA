import pytest
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId

from app.core.database import get_db
from app.services.product_service import ProductService
from app.services.capability_service import CapabilityService
from app.services.machine_service import MachineService
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService
from app.services.work_order_service import WorkOrderService
from app.services.execution_engine import ExecutionEngine
from app.schemas.product import ProductCreate
from app.schemas.capability import CapabilityCreate
from app.schemas.machine import MachineCreate, MachineStatus
from app.schemas.user import UserCreate, UserRole, OperatorAvailability
from app.schemas.workflow import WorkflowCreate
from app.schemas.work_order import WorkOrderCreate, WorkOrderStatus, WorkOrderOperationStatus

@pytest.fixture
async def full_mes_setup():
    db = get_db()
    
    # 1. Product
    prod = await ProductService.create_product(ProductCreate(
        productCode="EXEC-PROD", name="Exec Product", description="Desc"
    ))
    
    # 2. Capabilities
    cap_cut = await CapabilityService.create_capability(CapabilityCreate(
        code="EX_CUT", name="Cutting", description="Laser cutting metals"
    ))
    cap_weld = await CapabilityService.create_capability(CapabilityCreate(
        code="EX_WELD", name="Welding", description="Robotic welding"
    ))
    
    # 3. Machines
    m1 = await MachineService.create_machine(MachineCreate(
        machineCode="M-EX-01", name="Cutter 1", type="CUTTING",
        capabilityIds=[str(cap_cut["_id"])], location="Bay 1",
        processingRate=10.0, rateUnit="units/sec", color="#3B82F6"
    ))
    m2 = await MachineService.create_machine(MachineCreate(
        machineCode="M-EX-02", name="Welder 1", type="WELDING",
        capabilityIds=[str(cap_weld["_id"])], location="Bay 2",
        processingRate=10.0, rateUnit="units/sec", color="#F97316"
    ))
    
    # 4. Users (Supervisor and Operators)
    sup = await UserService.create_user(UserCreate(
        employeeId="SUP-EX-01", name="Supervisor Ex", email="sup.ex@mes.com",
        role=UserRole.SUPERVISOR, department="Management"
    ))
    op1 = await UserService.create_user(UserCreate(
        employeeId="OP-EX-01", name="Operator 1", email="op1.ex@mes.com",
        role=UserRole.OPERATOR, department="Fabrication"
    ))
    op2 = await UserService.create_user(UserCreate(
        employeeId="OP-EX-02", name="Operator 2", email="op2.ex@mes.com",
        role=UserRole.OPERATOR, department="Assembly"
    ))

    # 5. Workflow (OP-10 Cutting -> OP-20 Welding)
    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode="WF-EXEC-01",
        name="Exec Workflow",
        productId=str(prod["_id"]),
        supervisorId=str(sup["_id"]),
        version=1,
        status="ACTIVE",
        operations=[
            {
                "operationId": "OP-10",
                "name": "Cut Step",
                "sequence": 10,
                "requiredCapabilityIds": [str(cap_cut["_id"])],
                "assignedMachineId": str(m1["_id"]),
                "assignedOperatorId": str(op1["_id"]),
                "estimatedDurationSeconds": 1,
                "dependencies": []
            },
            {
                "operationId": "OP-20",
                "name": "Weld Step",
                "sequence": 20,
                "requiredCapabilityIds": [str(cap_weld["_id"])],
                "assignedMachineId": str(m2["_id"]),
                "assignedOperatorId": str(op2["_id"]),
                "estimatedDurationSeconds": 1,
                "dependencies": ["OP-10"]
            }
        ]
    ))

    yield {
        "prod_id": str(prod["_id"]),
        "m1_id": str(m1["_id"]),
        "m2_id": str(m2["_id"]),
        "sup_id": str(sup["_id"]),
        "op1_id": str(op1["_id"]),
        "op2_id": str(op2["_id"]),
        "wf_id": str(wf["_id"]),
        "cap_cut_id": str(cap_cut["_id"]),
        "cap_weld_id": str(cap_weld["_id"])
    }

    # Clean up fixture resources
    await db.machines.update_many({}, {"$set": {"status": MachineStatus.IDLE.value}})
    await WorkflowService.delete_workflow(str(wf["_id"]))
    await MachineService.delete_machine(str(m1["_id"]))
    await MachineService.delete_machine(str(m2["_id"]))
    await UserService.delete_user(str(sup["_id"]))
    await UserService.delete_user(str(op1["_id"]))
    await UserService.delete_user(str(op2["_id"]))
    await CapabilityService.delete_capability(str(cap_cut["_id"]))
    await CapabilityService.delete_capability(str(cap_weld["_id"]))
    await ProductService.delete_product(str(prod["_id"]))

@pytest.mark.asyncio
async def test_execution_lifecycle_and_auto_promotion(full_mes_setup):
    ctx = full_mes_setup
    db = get_db()
    
    # 1. Create Work Order
    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode="WO-EXEC-TEST-01",
        productId=ctx["prod_id"],
        workflowId=ctx["wf_id"],
        workflowVersion=1,
        supervisorId=ctx["sup_id"],
        quantity=5.0,
        priority="HIGH",
        dueDate=datetime.utcnow()
    ))
    wo_id = str(wo["_id"])

    # 2. Start Work Order
    state = await ExecutionEngine.start_work_order(wo_id)
    assert state["status"] == WorkOrderStatus.IN_PROGRESS.value
    
    # OP-10 should be IN_PROGRESS, OP-20 should be PENDING
    op10 = next(o for o in state["operations"] if o["operationId"] == "OP-10")
    assert op10["status"] == WorkOrderOperationStatus.IN_PROGRESS.value
    assert op10["machineCode"] == "M-EX-01"
    assert op10["machineColor"] == "#3B82F6"
    assert op10["remainingSeconds"] > 0
    
    # Machine M1 should be OCCUPIED, Operator OP1 should be ASSIGNED
    m1_doc = await db.machines.find_one({"_id": ObjectId(ctx["m1_id"])})
    assert m1_doc["status"] == MachineStatus.OCCUPIED.value
    op1_doc = await db.users.find_one({"_id": ObjectId(ctx["op1_id"])})
    assert op1_doc["availabilityStatus"] == OperatorAvailability.ASSIGNED.value

    # 3. Simulate passage of time so OP-10 completes
    await db.work_orders.update_one(
        {"_id": ObjectId(wo_id), "operations.operationId": "OP-10"},
        {"$set": {"operations.$.estimatedCompletionAt": datetime.utcnow() - timedelta(seconds=1)}}
    )
    
    # Run engine evaluation tick
    await ExecutionEngine.evaluate_execution(wo_id)
    
    # Re-fetch state
    updated_state = await ExecutionEngine.get_execution_state(wo_id)
    
    # OP-10 should be COMPLETED, OP-20 should have automatically started!
    op10_done = next(o for o in updated_state["operations"] if o["operationId"] == "OP-10")
    assert op10_done["status"] == WorkOrderOperationStatus.COMPLETED.value
    
    op20_active = next(o for o in updated_state["operations"] if o["operationId"] == "OP-20")
    assert op20_active["status"] == WorkOrderOperationStatus.IN_PROGRESS.value
    
    # Machine M1 released -> IDLE, Operator OP1 released -> AVAILABLE
    m1_released = await db.machines.find_one({"_id": ObjectId(ctx["m1_id"])})
    assert m1_released["status"] == MachineStatus.IDLE.value
    op1_released = await db.users.find_one({"_id": ObjectId(ctx["op1_id"])})
    assert op1_released["availabilityStatus"] == OperatorAvailability.AVAILABLE.value
    
    # Machine M2 occupied -> OCCUPIED
    m2_occ = await db.machines.find_one({"_id": ObjectId(ctx["m2_id"])})
    assert m2_occ["status"] == MachineStatus.OCCUPIED.value

    # 4. Simulate completion of OP-20
    await db.work_orders.update_one(
        {"_id": ObjectId(wo_id), "operations.operationId": "OP-20"},
        {"$set": {"operations.$.estimatedCompletionAt": datetime.utcnow() - timedelta(seconds=1)}}
    )
    await ExecutionEngine.evaluate_execution(wo_id)
    
    # Entire Work Order should now be COMPLETED!
    final_state = await ExecutionEngine.get_execution_state(wo_id)
    assert final_state["status"] == WorkOrderStatus.COMPLETED.value
    assert final_state["execution"]["status"] == "COMPLETED"

    # 5. Check execution_events stream in MongoDB
    events_count = await db.execution_events.count_documents({"workOrderId": wo_id})
    assert events_count >= 6

    # Clean up
    await WorkOrderService.delete_work_order(wo_id)

@pytest.mark.asyncio
async def test_waiting_for_resource_state(full_mes_setup):
    ctx = full_mes_setup
    db = get_db()

    # Pre-occupy Machine M1 with another mock task
    await db.machines.update_one(
        {"_id": ObjectId(ctx["m1_id"])},
        {"$set": {"status": MachineStatus.OCCUPIED.value}}
    )

    # Create Work Order
    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode="WO-WAIT-TEST-01",
        productId=ctx["prod_id"],
        workflowId=ctx["wf_id"],
        workflowVersion=1,
        supervisorId=ctx["sup_id"],
        quantity=5.0,
        priority="NORMAL",
        dueDate=datetime.utcnow()
    ))
    wo_id = str(wo["_id"])

    # Start Work Order -> should not crash or block, OP-10 enters WAITING_FOR_RESOURCE
    state = await ExecutionEngine.start_work_order(wo_id)
    assert state["status"] == WorkOrderStatus.IN_PROGRESS.value
    
    op10 = next(o for o in state["operations"] if o["operationId"] == "OP-10")
    assert op10["status"] == WorkOrderOperationStatus.WAITING_FOR_RESOURCE.value
    assert "Machine M-EX-01 is OCCUPIED" in op10["waitingReason"]

    # Now make M1 IDLE (freed up)
    await db.machines.update_one(
        {"_id": ObjectId(ctx["m1_id"])},
        {"$set": {"status": MachineStatus.IDLE.value}}
    )

    # Evaluate execution -> OP-10 should automatically transition to IN_PROGRESS!
    await ExecutionEngine.evaluate_execution(wo_id)
    updated_state = await ExecutionEngine.get_execution_state(wo_id)
    op10_updated = next(o for o in updated_state["operations"] if o["operationId"] == "OP-10")
    assert op10_updated["status"] == WorkOrderOperationStatus.IN_PROGRESS.value

    # Clean up
    await WorkOrderService.delete_work_order(wo_id)
