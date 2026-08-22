import pytest
from datetime import datetime
from bson import ObjectId
from unittest.mock import patch, AsyncMock

from app.core.database import get_db
from app.schemas.user import UserCreate, UserRole, OperatorAvailability
from app.services.user_service import UserService
from app.services.machine_service import MachineService
from app.schemas.machine import MachineCreate, MachineStatus
from app.services.incident_service import IncidentService
from app.services.work_order_service import WorkOrderService
from app.services.product_service import ProductService
from app.services.workflow_service import WorkflowService
from app.schemas.product import ProductCreate
from app.schemas.workflow import WorkflowCreate, WorkflowOperation
from app.schemas.work_order import WorkOrderCreate, WorkOrderPriority
from app.ai.schemas import (
    AILifecycleStatus, AIInvestigationFinding, AIActionPlan,
    AIOllamaVerification, AIToolAction
)
from app.ai.tool_registry import validate_tool_call
from app.ai.tool_executor import ToolExecutor
from app.ai.orchestrator import AIOrchestrator
from app.ai.gemini_client import gemini_client
from app.ai.ollama_verifier import ollama_verifier

@pytest.fixture
async def ai_incident_fixture():
    db = get_db()
    await db.ai_operations.delete_many({})
    await db.incidents.delete_many({})
    await db.machines.delete_many({})
    await db.work_orders.delete_many({})
    await db.workflows.delete_many({})
    await db.products.delete_many({})
    await db.users.delete_many({})
    await db.execution_events.delete_many({})

    # 1. Create Supervisor & Operator
    sup = await UserService.create_user(UserCreate(
        employeeId="SUP-001", name="Sarah Connor", email="sarah@factory.com", role=UserRole.SUPERVISOR, department="Assembly"
    ))
    op_user = await UserService.create_user(UserCreate(
        employeeId="OP-001", name="Alex Rivera", email="alex@factory.com", role=UserRole.OPERATOR, department="Assembly"
    ))

    # 2. Create Primary Machine (M-03) and Backup Machine (M-04)
    m3 = await MachineService.create_machine(MachineCreate(
        machineCode="M-03", name="Robotic Welder 3", type="WELDING", location="Bay 3", processingRate=2.0
    ))
    m4 = await MachineService.create_machine(MachineCreate(
        machineCode="M-04", name="Backup Welder 4", type="WELDING", location="Bay 4", processingRate=2.0
    ))

    # 3. Create Product & Workflow
    prod = await ProductService.create_product(ProductCreate(
        productCode="BRACKET-A", name="Steel Bracket A", description="Standard bracket", unit="pcs"
    ))
    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode="BRACKET-WF-01",
        name="Welding Workflow",
        productId=str(prod["_id"]),
        supervisorId=str(sup["_id"]),
        operations=[
            WorkflowOperation(
                operationId="OP-30",
                name="Robotic Welding",
                sequence=10,
                requiredMachineType="WELDING",
                assignedMachineId=str(m3["_id"]),
                assignedOperatorId=str(op_user["_id"]),
                estimatedDurationSeconds=20
            )
        ]
    ))

    # 4. Create Work Order
    wo = await WorkOrderService.create_work_order(WorkOrderCreate(
        workOrderCode="WO-1001",
        productId=str(prod["_id"]),
        workflowId=str(wf["_id"]),
        workflowVersion=1,
        supervisorId=str(sup["_id"]),
        quantity=20.0,
        dueDate=datetime.utcnow(),
        priority=WorkOrderPriority.HIGH
    ))

    # 5. Create Operator Incident Alert
    inc = await IncidentService.create_operator_alert(
        operator_id=str(op_user["_id"]),
        message="Machine M-03 has stopped working suddenly during welding.",
        machine_id=str(m3["_id"])
    )

    yield {
        "incident_id": inc["id"],
        "incident_code": inc["incidentCode"],
        "machine_id": str(m3["_id"]),
        "machine_code": "M-03",
        "backup_machine_id": str(m4["_id"]),
        "backup_machine_code": "M-04",
        "work_order_id": str(wo["_id"]),
        "work_order_code": "WO-1001",
        "operator_id": str(op_user["_id"])
    }

    await db.ai_operations.delete_many({})
    await db.incidents.delete_many({})
    await db.machines.delete_many({})
    await db.work_orders.delete_many({})
    await db.workflows.delete_many({})
    await db.products.delete_many({})
    await db.users.delete_many({})

@pytest.mark.asyncio
async def test_tool_registry_validation():
    # 1. Valid tool call
    valid, err = validate_tool_call("pause_operation", {"workOrderId": "WO-1001", "operationId": "OP-30"})
    assert valid is True
    assert err is None

    # 2. Invalid tool name rejected
    invalid_name, err_name = validate_tool_call("delete_database_now", {})
    assert invalid_name is False
    assert "not in the safe registered tool catalog" in err_name

    # 3. Missing mandatory parameters rejected
    missing_param, err_param = validate_tool_call("pause_operation", {"workOrderId": "WO-1001"})
    assert missing_param is False
    assert "missing mandatory parameter 'operationId'" in err_param

@pytest.mark.asyncio
async def test_ai_investigation_and_action_plan_flow(ai_incident_fixture):
    ctx = ai_incident_fixture
    db = get_db()

    # 1. Trigger AI Investigation
    op_result = await AIOrchestrator.start_investigation(ctx["incident_id"], requested_by="ADMIN")
    assert op_result["status"] == AILifecycleStatus.AI_INVESTIGATION_READY.value
    assert op_result["investigation"] is not None
    assert "M-03" in op_result["investigation"]["summary"] or len(op_result["investigation"]["observations"]) > 0
    ai_op_id = op_result["id"]

    # 2. Verify Audit Trail record
    audit_rec = await db.audit_events.find_one({"action": "AI_INVESTIGATION_COMPLETED"})
    assert audit_rec is not None

    # 3. Attempt execution before action plan approval -> MUST FAIL
    with pytest.raises(ValueError):
        await AIOrchestrator.approve_and_execute(ai_op_id, admin_id="ADMIN")

    # 4. Generate Action Plan
    plan_result = await AIOrchestrator.generate_action_plan(ai_op_id, requested_by="ADMIN")
    assert plan_result["status"] == AILifecycleStatus.AI_ACTION_PLAN_READY.value
    assert plan_result["actionPlan"] is not None
    assert len(plan_result["toolCalls"]) >= 2

    # Verify tool calls map strictly to safe registry
    for action in plan_result["toolCalls"]:
        is_valid, _ = validate_tool_call(action["tool"], action["parameters"])
        assert is_valid is True

    # 5. Optional Ollama Verification
    verify_result = await AIOrchestrator.verify_with_ollama(ai_op_id, requested_by="ADMIN")
    assert verify_result["status"] == AILifecycleStatus.AI_VERIFICATION_COMPLETE.value
    assert verify_result["ollamaVerification"] is not None
    assert verify_result["ollamaVerification"]["status"] in ["VALID", "INVALID", "UNAVAILABLE"]

    # 6. Admin Approval & Execution
    exec_result = await AIOrchestrator.approve_and_execute(ai_op_id, admin_id="ADMIN")
    assert exec_result["status"] == AILifecycleStatus.AI_EXECUTION_COMPLETE.value
    assert exec_result["approvedBy"] == "ADMIN"
    assert len(exec_result["executionResults"]) >= 2

    # 7. Verify Machine and Work Order state transitions
    mach_doc = await db.machines.find_one({"_id": ObjectId(ctx["machine_id"])})
    assert mach_doc["status"] in [MachineStatus.DOWN.value, MachineStatus.MAINTENANCE.value]

    # Check work order operation was rerouted or paused
    wo_doc = await db.work_orders.find_one({"_id": ObjectId(ctx["work_order_id"])})
    op_30 = next(o for o in wo_doc["operations"] if o["operationId"] == "OP-30")
    assert op_30["status"] in ["PAUSED", "READY", "IN_PROGRESS"]

@pytest.mark.asyncio
async def test_ollama_verification_mocking(ai_incident_fixture):
    ctx = ai_incident_fixture
    op_result = await AIOrchestrator.start_investigation(ctx["incident_id"], requested_by="ADMIN")
    ai_op_id = op_result["id"]
    await AIOrchestrator.generate_action_plan(ai_op_id, requested_by="ADMIN")

    import httpx
    # Mock Ollama returning explicit VALID
    mock_resp_valid = httpx.Response(
        status_code=200,
        json={"response": '{"status": "VALID", "explanation": "Tools faithfully pause OP-30 and failover to M-04.", "invalidSteps": []}'}
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp_valid
        v_res = await AIOrchestrator.verify_with_ollama(ai_op_id, requested_by="ADMIN")
        assert v_res["ollamaVerification"]["status"] == "VALID"
        assert "faithfully" in v_res["ollamaVerification"]["explanation"]

    # Mock Ollama returning explicit INVALID
    mock_resp_invalid = httpx.Response(
        status_code=200,
        json={"response": '{"status": "INVALID", "explanation": "Action sequence contains mismatched step.", "invalidSteps": ["step 2"]}'}
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp_invalid
        v_res2 = await AIOrchestrator.verify_with_ollama(ai_op_id, requested_by="ADMIN")
        assert v_res2["ollamaVerification"]["status"] == "INVALID"
        assert len(v_res2["ollamaVerification"]["invalidSteps"]) == 1

@pytest.mark.asyncio
async def test_execution_failure_stops_sequence(ai_incident_fixture):
    ctx = ai_incident_fixture
    db = get_db()

    op_result = await AIOrchestrator.start_investigation(ctx["incident_id"], requested_by="ADMIN")
    ai_op_id = op_result["id"]
    await AIOrchestrator.generate_action_plan(ai_op_id, requested_by="ADMIN")

    # Inject an invalid tool parameter into the saved toolCalls
    await db.ai_operations.update_one(
        {"_id": ObjectId(ai_op_id)},
        {"$set": {
            "toolCalls": [
                {
                    "tool": "pause_operation",
                    "version": "1.0",
                    "parameters": {"workOrderId": "NON_EXISTENT_WO_9999", "operationId": "OP-30"},
                    "reason": "Test fail",
                    "expectedEffect": "Fail"
                }
            ]
        }}
    )

    with pytest.raises(Exception):
        await AIOrchestrator.approve_and_execute(ai_op_id, admin_id="ADMIN")

    failed_doc = await db.ai_operations.find_one({"_id": ObjectId(ai_op_id)})
    assert failed_doc["status"] == AILifecycleStatus.AI_EXECUTION_FAILED.value
    assert failed_doc["failureReason"] is not None
