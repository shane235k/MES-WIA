import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from app.core.database import get_db
from app.services.machine_service import MachineService
from app.services.execution_engine import ExecutionEngine
from app.schemas.machine import MachineStatus

@pytest_asyncio.fixture(autouse=True)
async def setup_failure_test_data():
    db = get_db()
    await db.incidents.delete_many({})
    await db.machines.delete_many({})
    await db.users.delete_many({})
    await db.work_orders.delete_many({})
    await db.execution_events.delete_many({})
    await db.audit_events.delete_many({})

    # Seed operator with email
    oper_res = await db.users.insert_one({
        "employeeId": "OP-002",
        "email": "david.chen@mes.local",
        "name": "David Chen",
        "role": "OPERATOR",
        "status": "ACTIVE",
        "availabilityStatus": "ASSIGNED",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    # Seed machine
    mach_res = await db.machines.insert_one({
        "machineCode": "M-05",
        "name": "Bending Station 05",
        "type": "BENDING",
        "status": "OCCUPIED",
        "availability": True,
        "processingRate": 1.0,
        "color": "#10B981",
        "currentOperatorId": str(oper_res.inserted_id),
        "currentWorkOrderId": "60f000000000000000000005",
        "currentOperationId": "OP-20",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    # Seed work order with active operation
    await db.work_orders.insert_one({
        "_id": ObjectId("60f000000000000000000005"),
        "workOrderCode": "WO-5001",
        "status": "IN_PROGRESS",
        "quantity": 10,
        "operations": [
            {
                "operationId": "OP-20",
                "name": "Bending Flange",
                "sequence": 20,
                "assignedMachineId": str(mach_res.inserted_id),
                "assignedOperatorId": str(oper_res.inserted_id),
                "status": "IN_PROGRESS",
                "dependencies": []
            }
        ],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    return {
        "machine_id": str(mach_res.inserted_id),
        "operator_id": str(oper_res.inserted_id)
    }

@pytest.mark.asyncio
async def test_fail_running_machine_and_propagate(setup_failure_test_data):
    db = get_db()
    mach_id = setup_failure_test_data["machine_id"]
    oper_id = setup_failure_test_data["operator_id"]

    # 1. Authoritatively fail machine
    res = await MachineService.fail_machine(
        machine_id=mach_id,
        reason="Hydraulic pressure loss",
        actor_id="ADMIN"
    )

    assert res["machine"]["status"] == MachineStatus.DOWN.value
    assert res["incidentCode"].startswith("INC-")

    # 2. Check machine DB state
    mach = await db.machines.find_one({"_id": ObjectId(mach_id)})
    assert mach["status"] == "DOWN"
    assert mach["currentIncidentId"] is not None

    # 3. Check operation was marked INTERRUPTED
    wo = await db.work_orders.find_one({"_id": ObjectId("60f000000000000000000005")})
    assert wo["operations"][0]["status"] == "INTERRUPTED"
    assert "Hydraulic" in wo["operations"][0]["waitingReason"] or "failed" in wo["operations"][0]["waitingReason"]

    # 4. Check operator was released to AVAILABLE
    oper = await db.users.find_one({"_id": ObjectId(oper_id)})
    assert oper["availabilityStatus"] == "AVAILABLE"

    # 5. Check execution event recorded
    events = []
    async for ev in db.execution_events.find({"eventType": "OPERATION_INTERRUPTED"}):
        events.append(ev)
    assert len(events) >= 1
    assert events[0]["machineCode"] == "M-05"

    # 6. Verify duplicate failure throws error
    with pytest.raises(ValueError) as exc:
        await MachineService.fail_machine(machine_id=mach_id, reason="Another failure")
    assert "already in DOWN state" in str(exc.value)

@pytest.mark.asyncio
async def test_down_machine_blocks_new_operations(setup_failure_test_data):
    db = get_db()
    mach_id = setup_failure_test_data["machine_id"]

    # Fail machine
    await MachineService.fail_machine(machine_id=mach_id, reason="Maintenance breakdown")

    # Create new work order waiting for this machine
    wo_res = await db.work_orders.insert_one({
        "workOrderCode": "WO-5002",
        "status": "IN_PROGRESS",
        "quantity": 5,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Bending Sheet",
                "sequence": 10,
                "assignedMachineId": mach_id,
                "status": "READY",
                "dependencies": []
            }
        ],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    # Insert execution record
    await db.executions.insert_one({
        "workOrderId": str(wo_res.inserted_id),
        "status": "IN_PROGRESS",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    # Evaluate execution loop
    await ExecutionEngine.evaluate_execution(str(wo_res.inserted_id))

    # Operation must enter WAITING_FOR_RESOURCE with DOWN reason citing the incident
    wo = await db.work_orders.find_one({"_id": wo_res.inserted_id})
    assert wo["operations"][0]["status"] == "WAITING_FOR_RESOURCE"
    assert "DOWN" in wo["operations"][0]["waitingReason"]

@pytest.mark.asyncio
async def test_auto_failover_to_available_backup_machine():
    db = get_db()
    await db.incidents.delete_many({})
    await db.machines.delete_many({})
    await db.users.delete_many({})
    await db.work_orders.delete_many({})

    # Seed 2 machines of same type CUTTING
    mach1_res = await db.machines.insert_one({
        "machineCode": "M-01",
        "name": "Laser Cutter 1",
        "type": "CUTTING",
        "status": "OCCUPIED",
        "availability": True,
        "processingRate": 1.0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    mach1_id = str(mach1_res.inserted_id)

    mach2_res = await db.machines.insert_one({
        "machineCode": "M-02",
        "name": "Laser Cutter 2 (Backup)",
        "type": "CUTTING",
        "status": "IDLE",
        "availability": True,
        "processingRate": 1.0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    mach2_id = str(mach2_res.inserted_id)

    # Seed work order running on M-01
    wo_res = await db.work_orders.insert_one({
        "workOrderCode": "WO-7001",
        "status": "IN_PROGRESS",
        "quantity": 10,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Laser Sheet Cutting",
                "sequence": 10,
                "assignedMachineId": mach1_id,
                "status": "IN_PROGRESS",
                "dependencies": []
            }
        ],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    wo_id = str(wo_res.inserted_id)

    # Link machine 1 to this operation
    await db.machines.update_one(
        {"_id": mach1_res.inserted_id},
        {"$set": {"currentWorkOrderId": wo_id, "currentOperationId": "OP-10"}}
    )

    # Fail machine 1
    await MachineService.fail_machine(machine_id=mach1_id, reason="Optic failure on M-01")

    # Verify operation was automatically rerouted to M-02 (Backup)
    wo = await db.work_orders.find_one({"_id": wo_res.inserted_id})
    op = wo["operations"][0]
    assert op["assignedMachineId"] == mach2_id
    assert op["assignedMachineCode"] == "M-02"
    assert op["status"] == "READY"
    assert "Auto-rerouted" in op["waitingReason"]
