import pytest
import pytest_asyncio
from datetime import datetime
from bson import ObjectId
from app.core.database import get_db
from app.services.incident_service import IncidentService
from app.schemas.incident import IncidentStatus, IncidentType

@pytest_asyncio.fixture(autouse=True)
async def setup_test_data():
    db = get_db()
    await db.incidents.delete_many({})
    await db.machines.delete_many({})
    await db.users.delete_many({})
    await db.work_orders.delete_many({})

    # Seed operator with email
    oper_res = await db.users.insert_one({
        "employeeId": "OP-999",
        "email": "carlos.gomez@mes.local",
        "name": "Carlos Gomez",
        "role": "OPERATOR",
        "status": "ACTIVE",
        "availabilityStatus": "AVAILABLE",
        "skills": ["WELDING"],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    oper_id = str(oper_res.inserted_id)

    # Seed machine
    mach_res = await db.machines.insert_one({
        "machineCode": "M-99",
        "name": "Robotic Welder 99",
        "type": "WELDING",
        "status": "OCCUPIED",
        "availability": True,
        "processingRate": 2.0,
        "color": "#EF4444",
        "currentOperatorId": oper_id,
        "currentWorkOrderId": "60f000000000000000000001",
        "currentOperationId": "OP-30",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    mach_id = str(mach_res.inserted_id)

    # Seed work order
    await db.work_orders.insert_one({
        "_id": ObjectId("60f000000000000000000001"),
        "workOrderCode": "WO-9999",
        "status": "IN_PROGRESS",
        "quantity": 10,
        "operations": [
            {
                "operationId": "OP-30",
                "name": "Welding Joint",
                "sequence": 30,
                "assignedMachineId": mach_id,
                "assignedOperatorId": oper_id,
                "status": "IN_PROGRESS"
            }
        ],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    return {"operator_id": oper_id, "machine_id": mach_id}

@pytest.mark.asyncio
async def test_operator_alert_creation_and_context_derivation():
    db = get_db()
    
    # Operator sends alert without explicit machineId
    incident = await IncidentService.create_operator_alert(
        operator_id="OP-999",
        message="Machine M-99 is making an unusual grinding noise"
    )

    assert incident is not None
    assert incident["status"] == IncidentStatus.PENDING_REVIEW.value
    assert incident["type"] == IncidentType.MACHINE_FAILURE.value
    assert incident["incidentCode"].startswith("INC-")
    assert incident["operatorName"] == "Carlos Gomez"
    assert incident["machineCode"] == "M-99"
    assert incident["workOrderCode"] == "WO-9999"
    assert incident["operationId"] == "OP-30"

    # CRITICAL: Machine status must NOT have changed!
    mach = await db.machines.find_one({"machineCode": "M-99"})
    assert mach["status"] == "OCCUPIED"

    # Operation status must NOT have changed!
    wo = await db.work_orders.find_one({"workOrderCode": "WO-9999"})
    assert wo["operations"][0]["status"] == "IN_PROGRESS"

@pytest.mark.asyncio
async def test_operator_alert_invalid_operator():
    with pytest.raises(ValueError) as exc:
        await IncidentService.create_operator_alert(
            operator_id="OP-NONEXISTENT",
            message="Alert message"
        )
    assert "not found" in str(exc.value)
