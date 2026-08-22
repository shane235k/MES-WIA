import pytest
from datetime import datetime
from bson import ObjectId
from app.core.database import get_db
from app.schemas.user import UserCreate, UserRole, OperatorAvailability
from app.services.user_service import UserService
from app.services.machine_service import MachineService
from app.schemas.machine import MachineCreate, MachineStatus
from app.services.operator_activation_service import OperatorActivationService
from app.services.incident_service import IncidentService
from app.schemas.incident import IncidentStatus

@pytest.fixture
async def operator_activation_setup():
    db = get_db()
    await db.operator_activations.delete_many({})
    await db.users.delete_many({})
    await db.machines.delete_many({})
    await db.incidents.delete_many({})
    await db.work_orders.delete_many({})

    # 1. Create an Operator
    op_user = await UserService.create_user(UserCreate(
        employeeId="OP-001",
        name="Alex Rivera",
        email="alex.rivera@factory.com",
        role=UserRole.OPERATOR,
        department="Assembly Line 1"
    ))
    op_id = str(op_user["_id"])

    # 2. Create Machine M-03
    mach = await MachineService.create_machine(MachineCreate(
        machineCode="M-03",
        name="Robotic Welder 3",
        type="WELDING",
        location="Bay 3",
        processingRate=2.0,
        rateUnit="units/sec",
        color="#F97316"
    ))
    mach_id = str(mach["_id"])

    yield {
        "operator_id": op_id,
        "operator_emp": "OP-001",
        "operator_name": "Alex Rivera",
        "machine_id": mach_id,
        "machine_code": "M-03"
    }

    # Teardown
    await db.operator_activations.delete_many({})
    await db.users.delete_many({})
    await db.machines.delete_many({})
    await db.incidents.delete_many({})

@pytest.mark.asyncio
async def test_operator_activation_full_lifecycle(operator_activation_setup):
    ctx = operator_activation_setup
    db = get_db()

    # 1. Admin generates activation code
    gen_res = await OperatorActivationService.generate_activation_code(ctx["operator_id"], admin_id="ADMIN")
    assert gen_res["status"] == "NOT_ACTIVATED"
    assert gen_res["operatorEmployeeId"] == ctx["operator_emp"]
    assert gen_res["activationCode"].startswith("ACT-OP001-")
    activation_id = gen_res["id"]
    code = gen_res["activationCode"]

    # 2. Operator enters activation code on client
    sub_res = await OperatorActivationService.submit_activation(code, client_info={"os": "Windows", "version": "1.0.0"})
    assert sub_res["status"] == "PENDING"
    assert sub_res["sessionToken"] is not None
    session_token = sub_res["sessionToken"]

    # 3. Check status while pending
    status_res = await OperatorActivationService.get_activation_status(session_token)
    assert status_res["status"] == "PENDING"

    # Context request should fail while pending
    with pytest.raises(PermissionError):
        await OperatorActivationService.get_operator_context(session_token)

    # 4. Admin approves the activation
    appr_res = await OperatorActivationService.approve_activation(activation_id, admin_id="ADMIN-SUPER")
    assert appr_res["status"] == "APPROVED"
    assert appr_res["approvedBy"] == "ADMIN-SUPER"

    # 5. Operator context should now succeed (unassigned initially)
    context = await OperatorActivationService.get_operator_context(session_token)
    assert context["operator"]["operatorId"] == ctx["operator_emp"]
    assert context["operator"]["name"] == ctx["operator_name"]
    assert context["activationStatus"] == "APPROVED"
    assert context["assignment"] is None

    # 6. Assign operator and machine to active operation
    await db.machines.update_one(
        {"_id": ObjectId(ctx["machine_id"])},
        {"$set": {
            "status": MachineStatus.OCCUPIED.value,
            "currentOperatorId": ctx["operator_id"],
            "currentOperationId": "OP-30",
            "currentWorkOrderId": "WO-9999",
            "currentWorkOrderCode": "WO-9999"
        }}
    )

    context_assigned = await OperatorActivationService.get_operator_context(session_token)
    assert context_assigned["assignment"] is not None
    assert context_assigned["assignment"]["machineCode"] == "M-03"
    assert context_assigned["assignment"]["machineName"] == "Robotic Welder 3"

    # 7. Operator submits a problem report
    alert_incident = await IncidentService.create_operator_alert(
        operator_id=ctx["operator_id"],
        message="Machine M-03 has stopped working unexpectedly",
        machine_id=ctx["machine_id"]
    )
    assert alert_incident["status"] == IncidentStatus.PENDING_REVIEW.value
    assert alert_incident["machineCode"] == "M-03"

    # Machine must NOT automatically become DOWN
    mach_doc = await db.machines.find_one({"_id": ObjectId(ctx["machine_id"])})
    assert mach_doc["status"] != MachineStatus.DOWN.value

    # 8. Operator views their own submitted reports
    my_reports = await IncidentService.get_operator_reports(ctx["operator_id"])
    assert len(my_reports) >= 1
    assert my_reports[0]["status"] == IncidentStatus.PENDING_REVIEW.value

    # 9. Admin confirms failure -> Machine becomes DOWN
    confirmed_res = await IncidentService.confirm_failure(
        incident_id=alert_incident["id"],
        admin_id="ADMIN"
    )
    assert confirmed_res["incident"]["status"] == IncidentStatus.ACTION_REQUIRED.value

    # Check updated reports for operator
    my_reports_updated = await IncidentService.get_operator_reports(ctx["operator_id"])
    assert my_reports_updated[0]["status"] == IncidentStatus.ACTION_REQUIRED.value

    # 10. Admin revokes operator activation
    rev_res = await OperatorActivationService.revoke_activation(activation_id, admin_id="ADMIN")
    assert rev_res["status"] == "REVOKED"

    # Context request should now be blocked
    with pytest.raises(PermissionError):
        await OperatorActivationService.get_operator_context(session_token)
