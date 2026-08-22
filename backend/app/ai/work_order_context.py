import logging
from typing import Dict, Any, List
from bson import ObjectId
from app.core.database import get_db

logger = logging.getLogger(__name__)

class WorkOrderContextBuilder:
    @staticmethod
    async def build_planning_context() -> Dict[str, Any]:
        """
        Builds a sanitized, comprehensive MES planning context for AI Work Order generation.
        Strictly excludes credentials, tokens, secrets, or internal engine state.
        """
        db = get_db()

        # 1. Active Products & Recipes
        products = []
        async for p in db.products.find({"active": {"$ne": False}}):
            prod_id = str(p["_id"])
            p_recipes = []
            for r in p.get("recipes", []):
                p_recipes.append({
                    "recipeId": r.get("recipeId") or f"{p.get('productCode')}:v{r.get('version', 1)}",
                    "version": r.get("version", 1),
                    "status": r.get("status", "DRAFT"),
                    "name": r.get("name", "Standard Recipe"),
                    "steps": [
                        {
                            "stepId": s.get("stepId"),
                            "name": s.get("name"),
                            "sequence": s.get("sequence", 1),
                            "requiredMaterials": s.get("requiredMaterials", []),
                            "dependencies": s.get("dependencies", [])
                        }
                        for s in r.get("steps", [])
                    ]
                })

            products.append({
                "productId": prod_id,
                "productCode": p.get("productCode"),
                "name": p.get("name"),
                "description": p.get("description", ""),
                "unit": p.get("unit", "units"),
                "active": p.get("active", True),
                "recipes": p_recipes
            })

        # 2. Canonical Workflows
        workflows = []
        async for w in db.workflows.find():
            wf_id = str(w["_id"])
            workflows.append({
                "workflowId": wf_id,
                "workflowCode": w.get("workflowCode"),
                "name": w.get("name"),
                "productId": str(w.get("productId", "")),
                "version": w.get("version", 1),
                "status": w.get("status", "ACTIVE"),
                "operations": [
                    {
                        "operationId": op.get("operationId"),
                        "name": op.get("name"),
                        "sequence": op.get("sequence", 1),
                        "requiredMachineType": op.get("requiredMachineType"),
                        "dependencies": op.get("dependencies", []),
                        "requiredMaterials": op.get("requiredMaterials", [])
                    }
                    for op in w.get("operations", [])
                ]
            })

        # 3. Materials Catalog & Specifications
        materials = []
        async for m in db.materials.find():
            mat_id = str(m["_id"])
            materials.append({
                "materialId": mat_id,
                "materialCode": m.get("materialCode"),
                "name": m.get("name"),
                "unit": m.get("unit", "units"),
                "unitCost": m.get("unitCost", 0.0),
                "category": m.get("category", "RAW"),
                "quantityOnHand": m.get("quantityOnHand", 0.0),
                "quantityAvailable": m.get("quantityAvailable", 0.0)
            })

        # 4. Factory Machines
        machines = []
        async for mach in db.machines.find():
            m_id = str(mach["_id"])
            machines.append({
                "machineId": m_id,
                "machineCode": mach.get("machineCode"),
                "name": mach.get("name"),
                "type": mach.get("type"),
                "supportedTypes": mach.get("supportedTypes", []),
                "status": mach.get("status", "IDLE"),
                "processingRate": mach.get("processingRate", 1.0),
                "rateUnit": mach.get("rateUnit", "units/sec"),
                "location": mach.get("location", "Shopfloor")
            })

        # 5. Supervisors and Operators
        supervisors = []
        operators = []
        async for u in db.users.find():
            u_id = str(u["_id"])
            role = u.get("role", "").upper()
            if role == "SUPERVISOR" or "SUPERVISOR" in role:
                supervisors.append({
                    "supervisorId": u_id,
                    "employeeId": u.get("employeeId"),
                    "name": u.get("name"),
                    "role": "SUPERVISOR",
                    "department": u.get("department", "Production")
                })
            if role == "OPERATOR" or "OPERATOR" in role:
                operators.append({
                    "operatorId": u_id,
                    "employeeId": u.get("employeeId"),
                    "name": u.get("name"),
                    "role": "OPERATOR",
                    "availabilityStatus": u.get("availabilityStatus", "AVAILABLE"),
                    "skills": u.get("skills", [])
                })

        return {
            "products": products,
            "workflows": workflows,
            "materials": materials,
            "machines": machines,
            "supervisors": supervisors,
            "operators": operators
        }
