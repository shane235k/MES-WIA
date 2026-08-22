import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from bson import ObjectId

from app.core.database import get_db
from app.services.product_service import ProductService
from app.services.workflow_service import WorkflowService
from app.services.material_service import MaterialService
from app.services.material_specification_service import MaterialSpecificationService
from app.services.machine_service import MachineService
from app.services.user_service import UserService
from app.services.work_order_service import WorkOrderService
from app.services.ai_work_order_service import AIWorkOrderService
from app.ai.work_order_planner import AIWorkOrderPlanner
from app.ai.work_order_context import WorkOrderContextBuilder

from app.schemas.product import ProductCreate
from app.schemas.workflow import WorkflowCreate
from app.schemas.material import MaterialCreate
from app.schemas.material_specification import MaterialSpecificationCreate, MaterialForm
from app.schemas.machine import MachineCreate, MachineStatus
from app.schemas.user import UserCreate, UserRole, OperatorAvailability
from app.schemas.work_order import WorkOrderStatus, WorkOrderPriority

@pytest.mark.asyncio
async def test_ai_work_order_lifecycle_and_validation():
    """
    Comprehensive verification of the AI Work Order planning assistant and validation adapter.
    """
    db = get_db()
    uid = uuid.uuid4().hex[:6].upper()

    # 1. Setup Material Specification & Material
    spec = await MaterialSpecificationService.create_specification(MaterialSpecificationCreate(
        specificationCode=f"SPEC-AI-{uid}",
        name="Steel Sheet AI",
        category=MaterialForm.SHEET,
        grade="Mild Steel",
        unitOfMeasure="sheets",
        active=True
    ))
    mat = await MaterialService.create_material(MaterialCreate(
        materialCode=f"MAT-AI-{uid}",
        name="Steel Sheet AI",
        category=MaterialForm.SHEET,
        specificationId=str(spec["_id"]),
        unit="sheets",
        unitCost=50.0
    ))
    mat_id = str(mat["_id"])

    # 2. Setup Machine
    mach = await MachineService.create_machine(MachineCreate(
        machineCode=f"M-AI-{uid}",
        name="AI Laser Cutter",
        type="CUTTING",
        location="Bay 1",
        status=MachineStatus.IDLE,
        processingRate=2.0,
        availability=True
    ))
    mach_id = str(mach["_id"])

    # 3. Setup Supervisor and Operator
    sup = await UserService.create_user(UserCreate(
        employeeId=f"SUP-AI-{uid}",
        name="Elena Rostova",
        email=f"sup.{uid.lower()}@example.com",
        department="Fabrication",
        role=UserRole.SUPERVISOR,
        availabilityStatus=OperatorAvailability.AVAILABLE
    ))
    sup_id = str(sup["_id"])

    oper = await UserService.create_user(UserCreate(
        employeeId=f"OPR-AI-{uid}",
        name="Marcus Vance",
        email=f"opr.{uid.lower()}@example.com",
        department="Fabrication",
        role=UserRole.OPERATOR,
        availabilityStatus=OperatorAvailability.AVAILABLE
    ))
    oper_id = str(oper["_id"])

    # 4. Setup Product & Canonical Workflow
    prod = await ProductService.create_product(ProductCreate(
        productCode=f"BRACKET-{uid}",
        name="Industrial Bracket A",
        description="High precision bracket",
        unit="units"
    ))
    prod_id = str(prod["_id"])

    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode=f"WF-BRACKET-{uid}",
        name="Bracket Fabrication",
        productId=prod_id,
        operations=[
            {
                "operationId": "OP-CUT",
                "name": "Cutting",
                "sequence": 1,
                "requiredMachineType": "CUTTING",
                "assignedMachineId": mach_id,
                "assignedOperatorId": oper_id,
                "requiredMaterials": [{"materialId": mat_id, "quantity": 1.0, "unit": "sheets"}],
                "dependencies": []
            },
            {
                "operationId": "OP-BEND",
                "name": "Bending",
                "sequence": 2,
                "requiredMachineType": "CUTTING",
                "assignedMachineId": mach_id,
                "assignedOperatorId": oper_id,
                "requiredMaterials": [{"materialId": mat_id, "quantity": 1.0, "unit": "sheets"}],
                "dependencies": ["OP-CUT"]
            }
        ]
    ))
    wf_id = str(wf["_id"])

    # -------------------------------------------------------------
    # TEST 1: Session creation
    # -------------------------------------------------------------
    session_res = await AIWorkOrderService.create_session(user_id="ADMIN")
    session_id = session_res["sessionId"]
    assert session_id.startswith("ai-wosess-")
    assert session_res["status"] == "COLLECTING_REQUIREMENTS"

    # -------------------------------------------------------------
    # TEST 2: User gives partial info: "Manufacture 50 BRACKET-..."
    # -------------------------------------------------------------
    resp1 = await AIWorkOrderService.process_user_message(
        session_id=session_id,
        message=f"I want to manufacture 50 BRACKET-{uid} units."
    )
    assert resp1.status == "NEEDS_INFORMATION"
    assert "workflowId" in resp1.missingFields or "supervisorId" in resp1.missingFields
    assert resp1.collectedFields["productId"] == prod_id
    assert resp1.collectedFields["quantity"] == 50.0

    # -------------------------------------------------------------
    # TEST 3: User confirms workflow: "Use workflow WF-BRACKET-..."
    # -------------------------------------------------------------
    resp2 = await AIWorkOrderService.process_user_message(
        session_id=session_id,
        message=f"Use workflow WF-BRACKET-{uid}."
    )
    assert resp2.status == "NEEDS_INFORMATION"
    assert "supervisorId" in resp2.missingFields
    assert resp2.collectedFields["workflowId"] == wf_id

    # -------------------------------------------------------------
    # TEST 4: User assigns supervisor: "Assign Elena Rostova"
    # -------------------------------------------------------------
    resp3 = await AIWorkOrderService.process_user_message(
        session_id=session_id,
        message=f"Assign Elena Rostova as supervisor."
    )
    # AI now generates optional batch name confirmation
    assert resp3.status in ["OPTIONAL_CONFIRMATION", "READY"]
    assert resp3.collectedFields["supervisorId"] == sup_id

    # -------------------------------------------------------------
    # TEST 5: User accepts suggested batch name
    # -------------------------------------------------------------
    resp4 = await AIWorkOrderService.process_user_message(
        session_id=session_id,
        message="Yes, use suggested batch name."
    )
    assert resp4.status == "READY"
    assert resp4.draft is not None
    draft = resp4.draft

    # Verify Draft properties
    assert draft.productId == prod_id
    assert draft.workflowId == wf_id
    assert draft.quantity == 50.0
    assert draft.supervisorId == sup_id
    assert len(draft.operations) == 2
    assert len(draft.materialRequirements) == 1
    assert draft.materialRequirements[0].quantityPerUnit == 2.0  # (1 sheet OP-CUT + 1 sheet OP-BEND)
    assert draft.materialRequirements[0].totalRequiredQuantity == 100.0  # 50 units * 2 sheets = 100 sheets
    assert draft.totalEstimatedCost == 5000.0  # 100 sheets * ₹50

    # -------------------------------------------------------------
    # TEST 6: Hallucinated / Invalid Entity Rejection
    # -------------------------------------------------------------
    fake_draft = draft.model_dump()
    fake_draft["productId"] = str(ObjectId())  # Non-existent Product
    with pytest.raises(ValueError, match="does not exist in MES catalog"):
        await AIWorkOrderService.validate_draft(fake_draft)

    fake_draft2 = draft.model_dump()
    fake_draft2["supervisorId"] = oper_id  # Assigned user is an OPERATOR, not SUPERVISOR
    with pytest.raises(ValueError, match="does not have the SUPERVISOR role"):
        await AIWorkOrderService.validate_draft(fake_draft2)

    fake_draft3 = draft.model_dump()
    fake_draft3["quantity"] = -10
    with pytest.raises(ValueError, match="greater than 0"):
        await AIWorkOrderService.validate_draft(fake_draft3)

    # -------------------------------------------------------------
    # TEST 7: User edits quantity before final creation (50 -> 75)
    # -------------------------------------------------------------
    edited_draft = draft.model_dump()
    edited_draft["quantity"] = 75.0
    edited_draft["workOrderCode"] = f"WO-AI-EDITED-{uid}"

    val_result = await AIWorkOrderService.validate_draft(edited_draft)
    assert val_result["valid"] is True
    assert val_result["quantity"] == 75.0

    # -------------------------------------------------------------
    # TEST 8: Authoritative Creation via WorkOrderService
    # -------------------------------------------------------------
    created_wo = await AIWorkOrderService.create_work_order_from_draft(edited_draft, actor_id="AI_PLANNER")
    assert created_wo["workOrderCode"] == f"WO-AI-EDITED-{uid}"
    assert created_wo["quantity"] == 75.0
    assert created_wo["status"] == WorkOrderStatus.PLANNED.value
    assert len(created_wo["operations"]) == 2
    assert created_wo["operations"][0]["requiredMaterials"][0]["totalRequiredQuantity"] == 75.0
    assert created_wo["operations"][1]["requiredMaterials"][0]["totalRequiredQuantity"] == 75.0

    # -------------------------------------------------------------
    # TEST 9: AI did NOT automatically start execution
    # -------------------------------------------------------------
    wo_in_db = await db.work_orders.find_one({"_id": ObjectId(created_wo["_id"])})
    assert wo_in_db["status"] == WorkOrderStatus.PLANNED.value
    assert wo_in_db.get("startedAt") is None

    # Verify machine is still IDLE (not occupied)
    mach_in_db = await db.machines.find_one({"_id": ObjectId(mach_id)})
    assert mach_in_db["status"] == MachineStatus.IDLE.value

@pytest.mark.asyncio
async def test_ai_custom_name_rejection_and_custom_name_assignment():
    """
    Tests custom name scenario: user rejects AI suggestion and provides their own custom name.
    """
    db = get_db()
    uid = uuid.uuid4().hex[:6].upper()

    sup = await UserService.create_user(UserCreate(
        employeeId=f"SUP-AI2-{uid}",
        name="David Kim",
        email=f"sup2.{uid.lower()}@example.com",
        department="Assembly",
        role=UserRole.SUPERVISOR,
        availabilityStatus=OperatorAvailability.AVAILABLE
    ))
    sup_id = str(sup["_id"])

    prod = await ProductService.create_product(ProductCreate(
        productCode=f"WIDGET-{uid}",
        name="Precision Widget",
        description="Widget for testing",
        unit="units"
    ))
    prod_id = str(prod["_id"])

    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode=f"WF-WIDGET-{uid}",
        name="Widget Assembly",
        productId=prod_id,
        operations=[
            {
                "operationId": "OP-ASSY",
                "name": "Assembly",
                "sequence": 1,
                "requiredMachineType": "GENERIC",
                "dependencies": []
            }
        ]
    ))
    wf_id = str(wf["_id"])

    # Start session and provide full info in one prompt
    session_res = await AIWorkOrderService.create_session()
    sess_id = session_res["sessionId"]

    # Provide custom name directly: "Manufacture 20 WIDGET-... workflow WF-WIDGET-... supervisor David Kim call it Friday Urgent Rush"
    resp = await AIWorkOrderService.process_user_message(
        session_id=sess_id,
        message=f"Manufacture 20 WIDGET-{uid} units with workflow WF-WIDGET-{uid} and supervisor David Kim, call it Friday Urgent Rush."
    )
    assert resp.status == "READY"
    assert resp.draft is not None
    assert resp.draft.name == "Friday Urgent Rush"
    assert resp.draft.quantity == 20.0
