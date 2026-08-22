import logging
from datetime import datetime
from bson import ObjectId
from typing import List, Optional, Tuple
from app.core.database import get_db
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowStatus
from app.schemas.user import UserRole
from app.services.audit_service import AuditService
from app.services.machine_service import MachineService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

class WorkflowService:
    @staticmethod
    def generate_default_workflow_code(product_code: str) -> str:
        """
        Generate a readable, deterministic default workflow code e.g. BRACKET-A-WF-20260821-143522.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        clean_code = product_code.upper().replace(" ", "_")
        return f"{clean_code}-WF-{timestamp}"

    @staticmethod
    async def validate_workflow_operations(productId: str, operations: List[dict], supervisorId: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Runs comprehensive validation on a list of workflow operations.
        Returns (is_valid, list_of_error_messages).
        """
        errors = []
        db = get_db()

        # 1. Validate Product ID exists
        if not ObjectId.is_valid(productId):
            errors.append(f"Product ID '{productId}' has an invalid format")
        else:
            product = await db.products.find_one({"_id": ObjectId(productId)})
            if not product:
                errors.append(f"Product with ID '{productId}' does not exist")

        # 2. Validate Supervisor
        if supervisorId:
            if not ObjectId.is_valid(supervisorId):
                errors.append(f"Supervisor ID '{supervisorId}' has an invalid format")
            else:
                supervisor = await db.users.find_one({"_id": ObjectId(supervisorId)})
                if not supervisor:
                    errors.append(f"Supervisor with ID '{supervisorId}' does not exist")
                elif supervisor.get("role") not in [UserRole.SUPERVISOR.value, UserRole.ADMIN.value]:
                    errors.append(f"User '{supervisor.get('name')}' ({supervisor.get('role')}) is not eligible as a Supervisor")

        if not operations:
            errors.append("Workflow must contain at least one operation to be activated")
            return False, errors

        op_ids = set()
        
        # 3. Basic operation parameter & resource checks
        for idx, op in enumerate(operations):
            op_id = op.get("operationId")
            seq = op.get("sequence")
            duration = op.get("estimatedDurationSeconds", 0)
            required_caps = op.get("requiredCapabilityIds", [])
            assigned_mach = op.get("assignedMachineId")
            assigned_op = op.get("assignedOperatorId")
            
            if not op_id:
                errors.append(f"Operation at index {idx} is missing 'operationId'")
                continue
                
            if op_id in op_ids:
                errors.append(f"Duplicate operationId '{op_id}' found in operations")
            op_ids.add(op_id)
            
            if seq is None or seq <= 0:
                errors.append(f"Operation '{op_id}' has an invalid sequence '{seq}'. Must be positive.")
            
            if duration is not None and duration <= 0:
                errors.append(f"Operation '{op_id}' has an invalid duration '{duration}'. Must be positive.")
                
            # Validate required capability references
            for cap_id in required_caps:
                if not ObjectId.is_valid(cap_id):
                    errors.append(f"Operation '{op_id}' lists invalid capability ID format: '{cap_id}'")
                    continue
                exists = await db.capabilities.find_one({"_id": ObjectId(cap_id)})
                if not exists:
                    errors.append(f"Operation '{op_id}' requires capability ID '{cap_id}' which does not exist")

            # Validate assigned machine if specified
            if assigned_mach:
                if not ObjectId.is_valid(assigned_mach):
                    errors.append(f"Operation '{op_id}' has invalid machine ID format: '{assigned_mach}'")
                else:
                    mach = await db.machines.find_one({"_id": ObjectId(assigned_mach)})
                    if not mach:
                        errors.append(f"Operation '{op_id}' assigned machine ID '{assigned_mach}' does not exist")

            # Validate assigned operator if specified
            if assigned_op:
                if not ObjectId.is_valid(assigned_op):
                    errors.append(f"Operation '{op_id}' has invalid operator ID format: '{assigned_op}'")
                else:
                    oper = await db.users.find_one({"_id": ObjectId(assigned_op)})
                    if not oper:
                        errors.append(f"Operation '{op_id}' assigned operator ID '{assigned_op}' does not exist")
                    elif oper.get("role") != UserRole.OPERATOR.value:
                        errors.append(f"Assigned user '{oper.get('name')}' is not an Operator")

        # Stop early if basic structure is broken
        if errors:
            return False, errors

        # 4. Dependency validation & Self-dependency checks
        graph = {}
        for op in operations:
            op_id = op["operationId"]
            deps = op.get("dependencies", [])
            graph[op_id] = deps
            
            for dep in deps:
                if dep == op_id:
                    errors.append(f"Operation '{op_id}' cannot depend on itself (self-dependency)")
                elif dep not in op_ids:
                    errors.append(f"Operation '{op_id}' depends on operation '{dep}' which is not in this workflow")

        if errors:
            return False, errors

        # 5. Circular Dependency Checks using DFS Path Trace
        visited = set()
        rec_stack = set()
        cycle_nodes = []

        def dfs_find_cycle(node) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in graph:
                    continue
                if neighbor not in visited:
                    if dfs_find_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    cycle_nodes.append(neighbor)
                    cycle_nodes.append(node)
                    return True
            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if dfs_find_cycle(node):
                    cycle_path = " -> ".join(reversed(cycle_nodes))
                    errors.append(f"Circular dependency cycle detected: {cycle_path}")
                    break

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    async def auto_assign_resources(operations: List[dict]) -> List[dict]:
        """
        Auto-assign available compatible machines and operators for workflow operations.
        """
        db = get_db()
        all_machines = await MachineService.list_machines()
        all_operators = await UserService.list_operators(only_available=False)
        
        assigned_ops = []
        assigned_operator_ids = set()
        
        for op in operations:
            op_copy = dict(op)
            req_caps = op_copy.get("requiredCapabilityIds", [])
            req_type = op_copy.get("requiredMachineType")
            
            # Find compatible machine if not assigned
            if not op_copy.get("assignedMachineId"):
                for mach in all_machines:
                    mach_caps = mach.get("capabilityIds", [])
                    mach_type = mach.get("type", "")
                    
                    cap_match = all(c in mach_caps for c in req_caps) if req_caps else True
                    type_match = (mach_type.upper() == req_type.upper()) if req_type else True
                    
                    if cap_match and type_match:
                        op_copy["assignedMachineId"] = str(mach["_id"])
                        break
                        
            # Find available operator if not assigned
            if not op_copy.get("assignedOperatorId"):
                for oper in all_operators:
                    oper_id = str(oper["_id"])
                    if oper_id not in assigned_operator_ids:
                        op_copy["assignedOperatorId"] = oper_id
                        assigned_operator_ids.add(oper_id)
                        break
                # If all operators used, assign first available operator
                if not op_copy.get("assignedOperatorId") and all_operators:
                    op_copy["assignedOperatorId"] = str(all_operators[0]["_id"])

            assigned_ops.append(op_copy)
            
        return assigned_ops

    @staticmethod
    async def create_workflow(workflow_in: WorkflowCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check compound unique constraint: workflowCode + version
        existing = await db.workflows.find_one({
            "workflowCode": workflow_in.workflowCode,
            "version": workflow_in.version
        })
        if existing:
            raise ValueError(f"Workflow with code '{workflow_in.workflowCode}' and version {workflow_in.version} already exists")

        # Validate Product ID format
        if not ObjectId.is_valid(workflow_in.productId):
            raise ValueError(f"Invalid Product ID format: '{workflow_in.productId}'")
            
        product = await db.products.find_one({"_id": ObjectId(workflow_in.productId)})
        if not product:
            raise ValueError(f"Product with ID '{workflow_in.productId}' does not exist")

        # Validate Supervisor ID if provided
        if workflow_in.supervisorId:
            if not ObjectId.is_valid(workflow_in.supervisorId):
                raise ValueError(f"Invalid Supervisor ID format: '{workflow_in.supervisorId}'")
            supervisor = await db.users.find_one({"_id": ObjectId(workflow_in.supervisorId)})
            if not supervisor:
                raise ValueError(f"Supervisor with ID '{workflow_in.supervisorId}' does not exist")
            if supervisor.get("role") not in [UserRole.SUPERVISOR.value, UserRole.ADMIN.value]:
                raise ValueError(f"User '{supervisor.get('name')}' is not eligible as a Supervisor")

        operations_dict = [op.model_dump() for op in workflow_in.operations]
        if workflow_in.status == WorkflowStatus.ACTIVE:
            is_valid, errors = await WorkflowService.validate_workflow_operations(
                workflow_in.productId, operations_dict, workflow_in.supervisorId
            )
            if not is_valid:
                raise ValueError(f"Workflow operations validation failed: {', '.join(errors)}")

        workflow_data = workflow_in.model_dump()
        workflow_data["createdAt"] = datetime.utcnow()
        workflow_data["updatedAt"] = datetime.utcnow()
        
        result = await db.workflows.insert_one(workflow_data)
        workflow_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="WORKFLOW_CREATED",
            entity_type="workflow",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={
                "workflowCode": workflow_in.workflowCode,
                "version": workflow_in.version,
                "supervisorId": workflow_in.supervisorId,
                "status": workflow_in.status.value
            }
        )
        return workflow_data

    @staticmethod
    async def get_workflow_by_id(wf_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(wf_id):
            return None
        return await db.workflows.find_one({"_id": ObjectId(wf_id)})

    @staticmethod
    async def list_workflows(product_id: Optional[str] = None) -> List[dict]:
        db = get_db()
        query = {}
        if product_id:
            query["productId"] = product_id
            
        workflows = []
        async for doc in db.workflows.find(query):
            workflows.append(doc)
        return workflows

    @staticmethod
    async def update_workflow(wf_id: str, wf_update: WorkflowUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(wf_id):
            return None
            
        existing_wf = await db.workflows.find_one({"_id": ObjectId(wf_id)})
        if not existing_wf:
            return None

        update_data = wf_update.model_dump(exclude_unset=True)
        if not update_data:
            return existing_wf

        target_status = update_data.get("status", existing_wf["status"])
        target_productId = update_data.get("productId", existing_wf["productId"])
        target_supervisorId = update_data.get("supervisorId", existing_wf.get("supervisorId"))
        target_ops = update_data.get("operations", existing_wf["operations"])
        
        serialized_ops = []
        for op in target_ops:
            if hasattr(op, "model_dump"):
                serialized_ops.append(op.model_dump())
            else:
                serialized_ops.append(op)

        if target_status == WorkflowStatus.ACTIVE:
            is_valid, errors = await WorkflowService.validate_workflow_operations(
                target_productId, serialized_ops, target_supervisorId
            )
            if not is_valid:
                raise ValueError(f"Workflow operations validation failed: {', '.join(errors)}")

        update_data["updatedAt"] = datetime.utcnow()
        if "operations" in update_data:
            update_data["operations"] = serialized_ops

        result = await db.workflows.find_one_and_update(
            {"_id": ObjectId(wf_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="WORKFLOW_UPDATED",
                entity_type="workflow",
                entity_id=str(wf_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys()), "status": target_status}
            )
        return result

    @staticmethod
    async def activate_workflow(wf_id: str, actor_id: str = "SYSTEM") -> dict:
        """
        Performs full operation validation on a workflow template and sets status to ACTIVE.
        """
        db = get_db()
        if not ObjectId.is_valid(wf_id):
            raise ValueError(f"Invalid workflow ID format: '{wf_id}'")
            
        workflow = await db.workflows.find_one({"_id": ObjectId(wf_id)})
        if not workflow:
            raise ValueError(f"Workflow with ID '{wf_id}' does not exist")
            
        is_valid, errors = await WorkflowService.validate_workflow_operations(
            workflow["productId"], workflow["operations"], workflow.get("supervisorId")
        )
        if not is_valid:
            raise ValueError(f"Workflow operations validation failed: {', '.join(errors)}")
            
        updated = await db.workflows.find_one_and_update(
            {"_id": ObjectId(wf_id)},
            {"$set": {"status": WorkflowStatus.ACTIVE.value, "updatedAt": datetime.utcnow()}},
            return_document=True
        )
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="WORKFLOW_ACTIVATED",
            entity_type="workflow",
            entity_id=str(wf_id),
            source="ADMIN",
            metadata={"workflowCode": workflow["workflowCode"], "version": workflow["version"]}
        )
        return updated

    @staticmethod
    async def delete_workflow(wf_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(wf_id):
            return False
            
        result = await db.workflows.delete_one({"_id": ObjectId(wf_id)})
        deleted = result.deleted_count > 0
        if deleted:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="WORKFLOW_DELETED",
                entity_type="workflow",
                entity_id=str(wf_id),
                source="ADMIN"
            )
        return deleted
