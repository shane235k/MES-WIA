import pytest
import pytest_asyncio
from datetime import datetime
from bson import ObjectId
from app.core.database import get_db
from app.services.incident_service import IncidentService
from app.schemas.incident import IncidentStatus

@pytest_asyncio.fixture(autouse=True)
async def setup_test_incidents():
    db = get_db()
    await db.incidents.delete_many({})
    await db.machines.delete_many({})
    await db.users.delete_many({})
    await db.work_orders.delete_many({})

    # Seed supervisor & operator with unique emails
    sup_res = await db.users.insert_one({
        "employeeId": "SUP-001",
        "email": "elena.rostova@mes.local",
        "name": "Elena Rostova",
        "role": "SUPERVISOR",
        "status": "ACTIVE",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })
    oper_res = await db.users.insert_one({
        "employeeId": "OP-001",
        "email": "alex.rivera@mes.local",
        "name": "Alex Rivera",
        "role": "OPERATOR",
        "status": "ACTIVE",
        "availabilityStatus": "AVAILABLE",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    # Seed machine
    mach_res = await db.machines.insert_one({
        "machineCode": "M-03",
        "name": "Welding Station 03",
        "type": "WELDING",
        "status": "OCCUPIED",
        "processingRate": 1.5,
        "color": "#F59E0B",
        "currentOperatorId": str(oper_res.inserted_id),
        "currentWorkOrderId": "60f000000000000000000002",
        "currentOperationId": "OP-30",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    # Seed work order
    wo_res = await db.work_orders.insert_one({
        "_id": ObjectId("60f000000000000000000002"),
        "workOrderCode": "WO-1001",
        "status": "IN_PROGRESS",
        "supervisorId": str(sup_res.inserted_id),
        "quantity": 10,
        "operations": [
            {
                "operationId": "OP-30",
                "name": "Welding Frame",
                "sequence": 30,
                "assignedMachineId": str(mach_res.inserted_id),
                "assignedOperatorId": str(oper_res.inserted_id),
                "status": "IN_PROGRESS",
                "dependencies": []
            },
            {
                "operationId": "OP-40",
                "name": "Quality Inspection",
                "sequence": 40,
                "status": "PENDING",
                "dependencies": ["OP-30"]
            }
        ],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    })

    return {
        "machine_id": str(mach_res.inserted_id),
        "operator_id": str(oper_res.inserted_id),
        "work_order_id": str(wo_res.inserted_id)
    }

@pytest.mark.asyncio
async def test_admin_dismiss_incident():
    db = get_db()
    
    # 1. Operator reports alert
    incident = await IncidentService.create_operator_alert(
        operator_id="OP-001",
        message="Minor vibration on M-03"
    )
    inc_id = incident["id"]

    # 2. Admin dismisses report
    dismissed = await IncidentService.dismiss_incident(
        incident_id=inc_id,
        reason="Checked sensor; within normal tolerance"
    )
    assert dismissed["status"] == IncidentStatus.DISMISSED.value
    assert dismissed["dismissalReason"] == "Checked sensor; within normal tolerance"

    # Machine must remain unchanged
    mach = await db.machines.find_one({"machineCode": "M-03"})
    assert mach["status"] == "OCCUPIED"

@pytest.mark.asyncio
async def test_admin_confirm_and_resolve_incident(setup_test_incidents):
    db = get_db()
    
    # 1. Create alert
    incident = await IncidentService.create_operator_alert(
        operator_id="OP-001",
        message="M-03 motor stalled"
    )
    inc_id = incident["id"]

    # 2. Admin confirms failure
    result = await IncidentService.confirm_failure(incident_id=inc_id, admin_id="ADMIN")
    assert result["incident"]["status"] == IncidentStatus.ACTION_REQUIRED.value
    assert result["machine"]["status"] == "DOWN"

    # Machine in DB is DOWN
    mach = await db.machines.find_one({"machineCode": "M-03"})
    assert mach["status"] == "DOWN"

    # Active operation is INTERRUPTED
    wo = await db.work_orders.find_one({"workOrderCode": "WO-1001"})
    assert wo["operations"][0]["status"] == "INTERRUPTED"

    # 3. Retrieve deep context
    context = await IncidentService.get_incident_context(inc_id)
    assert context is not None
    assert context["incident"]["incidentCode"] == incident["incidentCode"]
    assert context["machine"]["machineCode"] == "M-03"
    assert context["workOrder"]["workOrderCode"] == "WO-1001"
    assert len(context["downstreamOperations"]) == 1
    assert context["downstreamOperations"][0]["operationId"] == "OP-40"

    # 4. Admin resolves incident
    resolved = await IncidentService.resolve_incident(
        incident_id=inc_id,
        resolution="Replaced motor fuse and verified calibration"
    )
    assert resolved["status"] == IncidentStatus.RESOLVED.value
    assert resolved["resolution"] == "Replaced motor fuse and verified calibration"

    # Machine returns to IDLE
    mach_recovered = await db.machines.find_one({"machineCode": "M-03"})
    assert mach_recovered["status"] == "IDLE"
    assert mach_recovered["currentIncidentId"] is None

@pytest.mark.asyncio
async def test_admin_schedule_incident_maintenance():
    db = get_db()
    
    incident = await IncidentService.create_operator_alert(
        operator_id="OP-001",
        message="Spindle overheated on M-03"
    )
    inc_id = incident["id"]

    # Confirm failure
    await IncidentService.confirm_failure(incident_id=inc_id, admin_id="ADMIN")

    # Schedule maintenance
    maint_res = await IncidentService.schedule_incident_maintenance(
        incident_id=inc_id,
        duration_minutes=20,
        resolution="Replacing thermal paste and cooling fan",
        admin_id="ADMIN"
    )
    assert maint_res["status"] == IncidentStatus.ACTION_REQUIRED.value
    assert maint_res["maintenanceDurationMinutes"] == 20
    assert maint_res["maintenanceEstimatedEnd"] is not None

    # Check machine status is MAINTENANCE
    mach = await db.machines.find_one({"machineCode": "M-03"})
    assert mach["status"] == "MAINTENANCE"
    assert mach["maintenanceDurationMinutes"] == 20
    assert mach["maintenanceEstimatedEnd"] is not None
