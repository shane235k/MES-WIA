import pytest
from datetime import datetime
from bson import ObjectId
from app.services.product_service import ProductService
from app.services.capability_service import CapabilityService
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService
from app.services.work_order_service import WorkOrderService
from app.schemas.product import ProductCreate
from app.schemas.capability import CapabilityCreate
from app.schemas.user import UserCreate, UserRole
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.schemas.work_order import WorkOrderCreate, WorkOrderStatus

@pytest.fixture
async def setup_wo_resources():
    # Setup Product, Capability, Supervisor, and Workflow
    prod = await ProductService.create_product(ProductCreate(
        productCode="WO-PROD", name="WO Product", description="Desc"
    ))
    cap = await CapabilityService.create_capability(CapabilityCreate(
        code="WO_CAP", name="WO Capability", description="Desc"
    ))
    sup = await UserService.create_user(UserCreate(
        employeeId="SUP-WO-01",
        name="WO Supervisor",
        email="sup.wo@mes.com",
        role=UserRole.SUPERVISOR,
        department="Production"
    ))
    
    # Create valid active workflow
    wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode="WF-WO-TEMPLATE",
        name="WO Template Process",
        productId=str(prod["_id"]),
        supervisorId=str(sup["_id"]),
        version=1,
        status="ACTIVE",
        operations=[
            {
                "operationId": "OP-10",
                "name": "Step 10",
                "sequence": 10,
                "description": "Desc",
                "requiredCapabilityIds": [str(cap["_id"])],
                "estimatedDurationSeconds": 100,
                "dependencies": [],
                "requiredMaterials": []
            },
            {
                "operationId": "OP-20",
                "name": "Step 20",
                "sequence": 20,
                "description": "Desc",
                "requiredCapabilityIds": [str(cap["_id"])],
                "estimatedDurationSeconds": 200,
                "dependencies": ["OP-10"],
                "requiredMaterials": []
            }
        ]
    ))
    
    yield str(prod["_id"]), str(cap["_id"]), str(sup["_id"]), str(wf["_id"])
    
    # Cleanup
    await WorkflowService.delete_workflow(str(wf["_id"]))
    await UserService.delete_user(str(sup["_id"]))
    await ProductService.delete_product(str(prod["_id"]))
    await CapabilityService.delete_capability(str(cap["_id"]))

@pytest.mark.asyncio
async def test_work_order_creation_and_cloning(setup_wo_resources):
    prod_id, cap_id, sup_id, wf_id = setup_wo_resources
    
    # 1. Create Work Order
    wo_data = {
        "workOrderCode": "WO-TEST-99",
        "productId": prod_id,
        "workflowId": wf_id,
        "workflowVersion": 1,
        "supervisorId": sup_id,
        "quantity": 50.0,
        "priority": "HIGH",
        "dueDate": datetime.utcnow(),
        "status": "PLANNED"
    }
    
    created_wo = await WorkOrderService.create_work_order(WorkOrderCreate(**wo_data))
    assert created_wo["workOrderCode"] == "WO-TEST-99"
    wo_id = str(created_wo["_id"])
    
    # Verify execution-specific operations were cloned
    ops = created_wo["operations"]
    assert len(ops) == 2
    
    # Verify initial task state logic:
    # OP-10 has no dependencies, should be READY
    op10 = next(o for o in ops if o["operationId"] == "OP-10")
    assert op10["status"] == "READY"
    
    # OP-20 has dependency OP-10, should be PENDING
    op20 = next(o for o in ops if o["operationId"] == "OP-20")
    assert op20["status"] == "PENDING"

    # 2. Verify duplicate code constraint
    with pytest.raises(ValueError) as exc:
        await WorkOrderService.create_work_order(WorkOrderCreate(**wo_data))
    assert "already exists" in str(exc.value)

    # 3. Verify Version Preservation
    new_ops = [
        {
            "operationId": "OP-NEW-10",
            "name": "Step New 10",
            "sequence": 10,
            "description": "Desc",
            "requiredCapabilityIds": [cap_id],
            "estimatedDurationSeconds": 100,
            "dependencies": []
        }
    ]
    await WorkflowService.update_workflow(wf_id, WorkflowUpdate(operations=new_ops))
    
    fetched_wo = await WorkOrderService.get_work_order_by_id(wo_id)
    assert fetched_wo is not None
    assert len(fetched_wo["operations"]) == 2
    assert fetched_wo["operations"][0]["operationId"] == "OP-10"
    
    # Clean up
    await WorkOrderService.delete_work_order(wo_id)
