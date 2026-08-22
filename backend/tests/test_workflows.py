import pytest
from bson import ObjectId
from app.services.product_service import ProductService
from app.services.capability_service import CapabilityService
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService
from app.schemas.product import ProductCreate
from app.schemas.capability import CapabilityCreate
from app.schemas.user import UserCreate, UserRole
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowStatus

@pytest.fixture
async def shared_resources():
    # Create product, capability, and supervisor for testing workflows
    prod = await ProductService.create_product(ProductCreate(
        productCode="W-PROD", name="WF Test Product", description="Desc"
    ))
    cap = await CapabilityService.create_capability(CapabilityCreate(
        code="WF_CAP", name="WF Test Capability", description="Desc"
    ))
    sup = await UserService.create_user(UserCreate(
        employeeId="SUP-TEST-01",
        name="Test Supervisor",
        email="sup.test@mes.com",
        role=UserRole.SUPERVISOR,
        department="Operations"
    ))
    yield str(prod["_id"]), str(cap["_id"]), str(sup["_id"])
    
    # Clean up
    await ProductService.delete_product(str(prod["_id"]))
    await CapabilityService.delete_capability(str(cap["_id"]))
    await UserService.delete_user(str(sup["_id"]))

@pytest.mark.asyncio
async def test_workflow_validation_scenarios(shared_resources):
    prod_id, cap_id, sup_id = shared_resources
    
    # 1. Invalid Product reference
    invalid_wf = {
        "workflowCode": "WF-INVALID-P",
        "name": "Invalid Product",
        "productId": str(ObjectId()),
        "supervisorId": sup_id,
        "operations": [],
        "status": "DRAFT"
    }
    with pytest.raises(ValueError) as exc:
        await WorkflowService.create_workflow(WorkflowCreate(**invalid_wf))
    assert "does not exist" in str(exc.value)

    # Base valid operation template
    base_op_10 = {
        "operationId": "OP-10",
        "name": "Op 10",
        "sequence": 10,
        "description": "Desc",
        "requiredCapabilityIds": [cap_id],
        "estimatedDurationSeconds": 100,
        "dependencies": [],
        "requiredMaterials": []
    }
    
    # 2. Test duplicate operationId
    dup_wf_data = {
        "workflowCode": "WF-DUP-OP",
        "name": "Dup Op ID",
        "productId": prod_id,
        "supervisorId": sup_id,
        "status": "ACTIVE",
        "operations": [
            base_op_10,
            {**base_op_10, "sequence": 20}
        ]
    }
    with pytest.raises(ValueError) as exc:
        await WorkflowService.create_workflow(WorkflowCreate(**dup_wf_data))
    assert "Duplicate operationId" in str(exc.value)

    # 3. Test self-dependency
    self_dep_wf_data = {
        "workflowCode": "WF-SELF-DEP",
        "name": "Self Dep",
        "productId": prod_id,
        "supervisorId": sup_id,
        "status": "ACTIVE",
        "operations": [
            {**base_op_10, "dependencies": ["OP-10"]}
        ]
    }
    with pytest.raises(ValueError) as exc:
        await WorkflowService.create_workflow(WorkflowCreate(**self_dep_wf_data))
    assert "cannot depend on itself" in str(exc.value)

    # 4. Test invalid dependency reference
    invalid_dep_wf_data = {
        "workflowCode": "WF-INVALID-DEP",
        "name": "Invalid Dep",
        "productId": prod_id,
        "supervisorId": sup_id,
        "status": "ACTIVE",
        "operations": [
            {**base_op_10, "dependencies": ["OP-NOT-EXISTS"]}
        ]
    }
    with pytest.raises(ValueError) as exc:
        await WorkflowService.create_workflow(WorkflowCreate(**invalid_dep_wf_data))
    assert "depends on operation 'OP-NOT-EXISTS' which is not in this workflow" in str(exc.value)

    # 5. Test circular dependency
    circular_wf_data = {
        "workflowCode": "WF-CIRCULAR",
        "name": "Circular",
        "productId": prod_id,
        "supervisorId": sup_id,
        "status": "ACTIVE",
        "operations": [
            {**base_op_10, "operationId": "OP-10", "dependencies": ["OP-20"]},
            {**base_op_10, "operationId": "OP-20", "sequence": 20, "dependencies": ["OP-10"]}
        ]
    }
    with pytest.raises(ValueError) as exc:
        await WorkflowService.create_workflow(WorkflowCreate(**circular_wf_data))
    assert "Circular dependency cycle detected" in str(exc.value)

    # 6. Test invalid capability reference
    invalid_cap_wf_data = {
        "workflowCode": "WF-INVALID-CAP",
        "name": "Invalid Cap",
        "productId": prod_id,
        "supervisorId": sup_id,
        "status": "ACTIVE",
        "operations": [
            {**base_op_10, "requiredCapabilityIds": [str(ObjectId())]}
        ]
    }
    with pytest.raises(ValueError) as exc:
        await WorkflowService.create_workflow(WorkflowCreate(**invalid_cap_wf_data))
    assert "which does not exist" in str(exc.value)

    # 7. Create as DRAFT (Draft allowed to be incomplete)
    draft_wf = await WorkflowService.create_workflow(WorkflowCreate(
        workflowCode="WF-DRAFT-OK",
        name="Valid Draft, Incomplete Op Structure",
        productId=prod_id,
        supervisorId=sup_id,
        status=WorkflowStatus.DRAFT,
        operations=[
            {**base_op_10, "dependencies": ["OP-99"]}
        ]
    ))
    wf_id = str(draft_wf["_id"])
    assert draft_wf["status"] == WorkflowStatus.DRAFT.value

    # 8. Try to activate DRAFT which is invalid -> Should Fail
    with pytest.raises(ValueError) as exc:
        await WorkflowService.activate_workflow(wf_id)
    assert "validation failed" in str(exc.value)

    # 9. Fix operations list to be valid, and then activate
    valid_ops = [
        base_op_10,
        {**base_op_10, "operationId": "OP-20", "sequence": 20, "dependencies": ["OP-10"]}
    ]
    await WorkflowService.update_workflow(wf_id, WorkflowUpdate(operations=valid_ops))
    
    activated = await WorkflowService.activate_workflow(wf_id)
    assert activated["status"] == WorkflowStatus.ACTIVE.value

    # Clean up
    await WorkflowService.delete_workflow(wf_id)
