import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Ensure backend package is discoverable regardless of working directory
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from app.core.database import db_manager, get_db  # type: ignore
    from app.schemas.workflow import WorkflowStatus  # type: ignore
    from app.schemas.work_order import WorkOrderStatus, WorkOrderPriority, WorkOrderOperationStatus  # type: ignore
    from app.schemas.machine import MachineStatus  # type: ignore
    from app.schemas.user import UserRole, OperatorAvailability, UserStatus  # type: ignore
    from app.schemas.material_specification import MaterialForm  # type: ignore
    from app.schemas.inventory_lot import LotStatus  # type: ignore
    from app.schemas.material_transaction import MaterialTransactionType  # type: ignore
    from app.schemas.operator_activation import ActivationStatus  # type: ignore
except ImportError:
    from backend.app.core.database import db_manager, get_db  # type: ignore
    from backend.app.schemas.workflow import WorkflowStatus  # type: ignore
    from backend.app.schemas.work_order import WorkOrderStatus, WorkOrderPriority, WorkOrderOperationStatus  # type: ignore
    from backend.app.schemas.machine import MachineStatus  # type: ignore
    from backend.app.schemas.user import UserRole, OperatorAvailability, UserStatus  # type: ignore
    from backend.app.schemas.material_specification import MaterialForm  # type: ignore
    from backend.app.schemas.inventory_lot import LotStatus  # type: ignore
    from backend.app.schemas.material_transaction import MaterialTransactionType  # type: ignore
    from backend.app.schemas.operator_activation import ActivationStatus  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_static")

# Collections representing transient execution state that MUST be cleared for a clean static baseline
RUNTIME_DYNAMIC_COLLECTIONS = [
    "executions",
    "execution_events",
    "incidents",
    "ai_operations",
    "ai_work_order_sessions",
    "machine_health_records",
    "material_reservations",
]

async def seed_static_resources():
    """
    Instantiates pure static master baseline data for the Manufacturing Execution System (MES).
    Includes:
      1. User Accounts & Operator Roles
      2. Operator Terminal Activation Pairing Codes
      3. Manufacturing Capabilities
      4. Factory Workstations & Physical Machines (All IDLE & 100% Healthy)
      5. Material Specifications (Metallurgical & Chemical grades)
      6. Raw Materials Catalog
      7. Warehouse Inventory Lots (Available stock with Opening Balance Ledger)
      8. Finished Products with Engineering BOM Recipes
      9. Production Workflows (Executable DAGs)
      10. Clean Production Work Orders (All in pure PLANNED status, 0 running timer)
    
    Excludes all transient runtime artifacts (execution logs, incidents, simulated degradations).
    """
    logger.info("Connecting to MongoDB database...")
    await db_manager.connect()
    db = get_db()

    logger.info("=" * 70)
    logger.info("   ADAPTIVE MES - INITIALIZING PURE STATIC BASELINE")
    logger.info("=" * 70)

    # -------------------------------------------------------------
    # 0. PURGE TRANSIENT RUNTIME STATE (CLEAN BASELINE GUARANTEE)
    # -------------------------------------------------------------
    logger.info("[STEP 0] Purging dynamic execution logs, runtime incidents, and temporary states...")
    for col in RUNTIME_DYNAMIC_COLLECTIONS:
        res = await db[col].delete_many({})
        logger.info(f"   Cleared dynamic collection '{col}': {res.deleted_count} record(s) removed.")

    # Re-create all database unique and lookup indexes
    await db_manager.create_indexes()

    now = datetime.utcnow()

    # -------------------------------------------------------------
    # 1. SEED USERS (ADMIN, SUPERVISOR, OPERATORS, QA)
    # -------------------------------------------------------------
    logger.info("[STEP 1] Seeding factory personnel and user accounts...")
    users_data = [
        {
            "employeeId": "ADM-001",
            "name": "System Administrator",
            "email": "admin@mes.factory",
            "role": UserRole.ADMIN.value,
            "department": "Plant Management",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
        {
            "employeeId": "SUP-001",
            "name": "Elena Rostova",
            "email": "elena.rostova@mes.factory",
            "role": UserRole.SUPERVISOR.value,
            "department": "Plant Operations",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
        {
            "employeeId": "OP-001",
            "name": "Alex Rivera",
            "email": "alex.rivera@mes.factory",
            "role": UserRole.OPERATOR.value,
            "department": "Bay A - Laser Fabrication",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
        {
            "employeeId": "OP-002",
            "name": "Beatriz Vance",
            "email": "beatriz.vance@mes.factory",
            "role": UserRole.OPERATOR.value,
            "department": "Bay A - CNC Forming",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
        {
            "employeeId": "OP-003",
            "name": "Carlos Chen",
            "email": "carlos.chen@mes.factory",
            "role": UserRole.OPERATOR.value,
            "department": "Bay B - Robotic Welding",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
        {
            "employeeId": "OP-004",
            "name": "David Kim",
            "email": "david.kim@mes.factory",
            "role": UserRole.OPERATOR.value,
            "department": "Bay D - Quality Metrology",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
        {
            "employeeId": "QA-001",
            "name": "Marcus Vance",
            "email": "marcus.vance@mes.factory",
            "role": UserRole.OPERATOR.value,
            "department": "Quality Assurance",
            "status": UserStatus.ACTIVE.value,
            "availabilityStatus": OperatorAvailability.AVAILABLE.value,
            "activeOperationId": None,
            "activeWorkOrderId": None,
            "activeMachineId": None,
        },
    ]

    user_ids: Dict[str, str] = {}
    for u in users_data:
        emp_code = u["employeeId"]
        existing = await db.users.find_one({"employeeId": emp_code})
        if not existing:
            u_doc = dict(u)
            u_doc["createdAt"] = now
            u_doc["updatedAt"] = now
            res = await db.users.insert_one(u_doc)
            user_ids[emp_code] = str(res.inserted_id)
        else:
            await db.users.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "name": u["name"],
                    "department": u["department"],
                    "status": UserStatus.ACTIVE.value,
                    "availabilityStatus": OperatorAvailability.AVAILABLE.value,
                    "activeOperationId": None,
                    "activeWorkOrderId": None,
                    "activeMachineId": None,
                    "updatedAt": now
                }}
            )
            user_ids[emp_code] = str(existing["_id"])

    logger.info(f"   Seeded {len(user_ids)} system users (Admin, Supervisor, Operators, QA).")

    # -------------------------------------------------------------
    # 2. SEED OPERATOR TERMINAL ACTIVATION CODES
    # -------------------------------------------------------------
    logger.info("[STEP 2] Seeding desktop operator terminal activation codes...")
    activation_codes = [
        {"code": "ACT-OP001-ALPHA1", "empId": "OP-001", "name": "Alex Rivera"},
        {"code": "ACT-OP002-BRAVO2", "empId": "OP-002", "name": "Beatriz Vance"},
        {"code": "ACT-OP003-CHARL3", "empId": "OP-003", "name": "Carlos Chen"},
        {"code": "ACT-OP004-DELTA4", "empId": "OP-004", "name": "David Kim"},
    ]

    for act in activation_codes:
        await db.operator_activations.update_one(
            {"activationCode": act["code"]},
            {"$set": {
                "activationCode": act["code"],
                "operatorId": user_ids[act["empId"]],
                "operatorEmployeeId": act["empId"],
                "operatorName": act["name"],
                "status": ActivationStatus.NOT_ACTIVATED.value,
                "sessionToken": None,
                "requestedAt": None,
                "approvedAt": None,
                "approvedBy": None,
                "createdAt": now,
                "updatedAt": now
            }},
            upsert=True
        )
    logger.info("   Seeded 4 pre-configured terminal pairing codes (ACT-OP001-ALPHA1 ...).")

    # -------------------------------------------------------------
    # 3. SEED MANUFACTURING CAPABILITIES
    # -------------------------------------------------------------
    logger.info("[STEP 3] Seeding factory manufacturing capabilities...")
    capabilities_data = [
        {"code": "CUTTING", "name": "Laser & Plasma Cutting", "description": "High-precision CNC cutting of raw sheet metal into component profiles."},
        {"code": "BENDING", "name": "CNC Press Brake Forming", "description": "Multi-axis hydraulic forming and stiffening flange bending."},
        {"code": "WELDING", "name": "Robotic TIG & MIG Welding", "description": "High-integrity structural and hermetic seam welding."},
        {"code": "MILLING", "name": "5-Axis High-Speed CNC Milling", "description": "Subtractive high-tolerance pocket milling, surfacing, and drilling."},
        {"code": "PAINTING", "name": "Electrostatic Powder Coating", "description": "Surface pre-treatment and durable electrostatic powder coating."},
        {"code": "INSPECTION", "name": "Coordinate Metrology & QA", "description": "Coordinate Measuring Machine (CMM) dimensional QA & optical verification."},
    ]

    cap_ids: Dict[str, str] = {}
    for cap in capabilities_data:
        existing = await db.capabilities.find_one({"code": cap["code"]})
        if not existing:
            c_doc: Dict[str, Any] = dict(cap)
            c_doc["createdAt"] = now
            c_doc["updatedAt"] = now
            res = await db.capabilities.insert_one(c_doc)
            cap_ids[cap["code"]] = str(res.inserted_id)
        else:
            cap_ids[cap["code"]] = str(existing["_id"])
    logger.info(f"   Seeded {len(cap_ids)} standard factory capabilities.")

    # -------------------------------------------------------------
    # 4. SEED MACHINES & WORKSTATIONS (ALL IDLE, 100 HEALTH)
    # -------------------------------------------------------------
    logger.info("[STEP 4] Seeding physical workstations (All IDLE & Healthy)...")
    machines_data = [
        {
            "machineCode": "M-01",
            "name": "Fiber Laser Cutting System",
            "type": "CUTTING",
            "supportedTypes": [],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["CUTTING"]],
            "location": "Bay A - Fabrication",
            "availability": True,
            "processingRate": 2.0,
            "rateUnit": "units/sec",
            "color": "#3B82F6",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
            "supportedForms": ["SHEET"],
            "supportedGrades": ["SS304", "MILD_STEEL", "AL6061"],
            "minThicknessMm": 0.5,
            "maxThicknessMm": 12.0,
        },
        {
            "machineCode": "M-02",
            "name": "CNC Hydraulic Press Brake",
            "type": "BENDING",
            "supportedTypes": [],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["BENDING"]],
            "location": "Bay A - Forming",
            "availability": True,
            "processingRate": 1.5,
            "rateUnit": "units/sec",
            "color": "#10B981",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
            "supportedForms": ["SHEET"],
            "supportedGrades": ["SS304", "MILD_STEEL", "AL6061"],
            "minThicknessMm": 0.5,
            "maxThicknessMm": 8.0,
        },
        {
            "machineCode": "M-03",
            "name": "Robotic TIG Welding Station",
            "type": "WELDING",
            "supportedTypes": [],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["WELDING"]],
            "location": "Bay B - Assembly",
            "availability": True,
            "processingRate": 1.0,
            "rateUnit": "units/sec",
            "color": "#F59E0B",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
            "supportedForms": ["SHEET", "WIRE"],
            "supportedGrades": ["SS304", "MILD_STEEL"],
        },
        {
            "machineCode": "M-04",
            "name": "5-Axis High-Speed CNC Mill",
            "type": "MILLING",
            "supportedTypes": [],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["MILLING"]],
            "location": "Bay B - Machining",
            "availability": True,
            "processingRate": 0.8,
            "rateUnit": "units/sec",
            "color": "#F97316",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
            "supportedForms": ["SHEET", "BAR"],
            "supportedGrades": ["AL6061", "SS304"],
        },
        {
            "machineCode": "M-05",
            "name": "Automated Powder Coating Line",
            "type": "PAINTING",
            "supportedTypes": [],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["PAINTING"]],
            "location": "Bay C - Finishing",
            "availability": True,
            "processingRate": 1.2,
            "rateUnit": "units/sec",
            "color": "#EC4899",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
            "supportedForms": ["SHEET", "CUSTOM"],
        },
        {
            "machineCode": "M-06",
            "name": "Coordinate Metrology QA Station",
            "type": "INSPECTION",
            "supportedTypes": [],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["INSPECTION"]],
            "location": "Bay D - Quality",
            "availability": True,
            "processingRate": 2.5,
            "rateUnit": "units/sec",
            "color": "#06B6D4",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
        },
        {
            "machineCode": "M-07",
            "name": "Modular Backup Fabrication Unit",
            "type": "MULTI_PURPOSE",
            "supportedTypes": ["CUTTING", "BENDING"],
            "status": MachineStatus.IDLE.value,
            "capabilityIds": [cap_ids["CUTTING"], cap_ids["BENDING"]],
            "location": "Bay A - Auxiliary",
            "availability": True,
            "processingRate": 1.0,
            "rateUnit": "units/sec",
            "color": "#84CC16",
            "currentOperationId": None,
            "currentWorkOrderId": None,
            "currentWorkOrderCode": None,
            "currentOperatorId": None,
            "currentIncidentId": None,
        },
    ]

    mach_ids: Dict[str, str] = {}
    for mach in machines_data:
        m_code = mach["machineCode"]
        existing = await db.machines.find_one({"machineCode": m_code})
        mach_doc = dict(mach)
        mach_doc["updatedAt"] = now
        if not existing:
            mach_doc["createdAt"] = now
            res = await db.machines.insert_one(mach_doc)
            mach_ids[m_code] = str(res.inserted_id)
        else:
            await db.machines.update_one({"_id": existing["_id"]}, {"$set": mach_doc})
            mach_ids[m_code] = str(existing["_id"])
    logger.info(f"   Seeded {len(mach_ids)} machines (M-01 through M-07) in pure IDLE state.")

    # -------------------------------------------------------------
    # 5. SEED MATERIAL SPECIFICATIONS
    # -------------------------------------------------------------
    logger.info("[STEP 5] Seeding raw material metallurgical & chemical specifications...")
    specs_data = [
        {
            "specificationCode": "SPEC-SS304-2MM",
            "name": "Stainless Steel 304 Sheet (2mm Cold-Rolled)",
            "category": MaterialForm.SHEET.value,
            "grade": "SS304",
            "dimensions": {"thickness": 2.0, "width": 1250.0, "length": 2500.0},
            "unitOfMeasure": "sheets",
            "active": True,
        },
        {
            "specificationCode": "SPEC-MS-2MM",
            "name": "Mild Steel Cold-Rolled Sheet (2mm CR4)",
            "category": MaterialForm.SHEET.value,
            "grade": "MILD_STEEL",
            "dimensions": {"thickness": 2.0, "width": 1000.0, "length": 2000.0},
            "unitOfMeasure": "sheets",
            "active": True,
        },
        {
            "specificationCode": "SPEC-AL-3MM",
            "name": "Aluminum 6061-T6 Plate (3mm Aerospace Grade)",
            "category": MaterialForm.SHEET.value,
            "grade": "AL6061-T6",
            "dimensions": {"thickness": 3.0, "width": 1200.0, "length": 2400.0},
            "unitOfMeasure": "sheets",
            "active": True,
        },
        {
            "specificationCode": "SPEC-WIRE-ER70S",
            "name": "ER70S-6 High-Strength TIG Welding Wire Spool",
            "category": MaterialForm.WIRE.value,
            "grade": "ER70S-6",
            "dimensions": {"diameter": 1.2},
            "unitOfMeasure": "spools",
            "active": True,
        },
        {
            "specificationCode": "SPEC-PAINT-BLK",
            "name": "High-Durability Industrial Matte Black Powder",
            "category": MaterialForm.POWDER.value,
            "grade": "POLYESTER_TGIC",
            "dimensions": {},
            "unitOfMeasure": "canisters",
            "active": True,
        },
    ]

    spec_ids: Dict[str, str] = {}
    for s in specs_data:
        code = s["specificationCode"]
        existing = await db.material_specifications.find_one({"specificationCode": code})
        s_doc = dict(s)
        s_doc["updatedAt"] = now
        if not existing:
            s_doc["createdAt"] = now
            res = await db.material_specifications.insert_one(s_doc)
            spec_ids[code] = str(res.inserted_id)
        else:
            await db.material_specifications.update_one({"_id": existing["_id"]}, {"$set": s_doc})
            spec_ids[code] = str(existing["_id"])
    logger.info(f"   Seeded {len(spec_ids)} material engineering specifications.")

    # -------------------------------------------------------------
    # 6. SEED RAW MATERIALS CATALOG
    # -------------------------------------------------------------
    logger.info("[STEP 6] Seeding raw materials inventory catalog...")
    materials_data = [
        {
            "materialCode": "MAT-SS304-SHEET",
            "name": "Stainless Steel 304 Sheet (2mm)",
            "unit": "sheets",
            "specificationId": spec_ids["SPEC-SS304-2MM"],
            "category": "SHEET",
            "grade": "SS304",
            "reorderLevel": 50.0,
            "unitCost": 45.0,
            "active": True,
            "quantityOnHand": 500.0,
            "quantityReserved": 0.0,
            "quantityAvailable": 500.0,
        },
        {
            "materialCode": "MAT-MS-SHEET",
            "name": "Mild Steel Cold-Rolled Sheet (2mm)",
            "unit": "sheets",
            "specificationId": spec_ids["SPEC-MS-2MM"],
            "category": "SHEET",
            "grade": "MILD_STEEL",
            "reorderLevel": 40.0,
            "unitCost": 28.0,
            "active": True,
            "quantityOnHand": 400.0,
            "quantityReserved": 0.0,
            "quantityAvailable": 400.0,
        },
        {
            "materialCode": "MAT-AL6061-SHEET",
            "name": "Aluminum 6061-T6 Plate (3mm)",
            "unit": "sheets",
            "specificationId": spec_ids["SPEC-AL-3MM"],
            "category": "SHEET",
            "grade": "AL6061-T6",
            "reorderLevel": 30.0,
            "unitCost": 60.0,
            "active": True,
            "quantityOnHand": 300.0,
            "quantityReserved": 0.0,
            "quantityAvailable": 300.0,
        },
        {
            "materialCode": "MAT-WELD-WIRE",
            "name": "ER70S-6 Welding Wire Spool",
            "unit": "spools",
            "specificationId": spec_ids["SPEC-WIRE-ER70S"],
            "category": "WIRE",
            "grade": "ER70S-6",
            "reorderLevel": 10.0,
            "unitCost": 35.0,
            "active": True,
            "quantityOnHand": 100.0,
            "quantityReserved": 0.0,
            "quantityAvailable": 100.0,
        },
        {
            "materialCode": "MAT-PAINT-BLACK",
            "name": "Industrial Matte Black Powder Coating",
            "unit": "canisters",
            "specificationId": spec_ids["SPEC-PAINT-BLK"],
            "category": "POWDER",
            "grade": "POLYESTER_TGIC",
            "reorderLevel": 15.0,
            "unitCost": 55.0,
            "active": True,
            "quantityOnHand": 80.0,
            "quantityReserved": 0.0,
            "quantityAvailable": 80.0,
        },
    ]

    mat_ids: Dict[str, str] = {}
    for mat in materials_data:
        m_code = mat["materialCode"]
        existing = await db.materials.find_one({"materialCode": m_code})
        mat_doc = dict(mat)
        mat_doc["updatedAt"] = now
        if not existing:
            mat_doc["createdAt"] = now
            res = await db.materials.insert_one(mat_doc)
            mat_ids[m_code] = str(res.inserted_id)
        else:
            await db.materials.update_one({"_id": existing["_id"]}, {"$set": mat_doc})
            mat_ids[m_code] = str(existing["_id"])
    logger.info(f"   Seeded {len(mat_ids)} tracked raw materials with stock availability.")

    # -------------------------------------------------------------
    # 7. SEED PHYSICAL INVENTORY LOTS & INITIAL OPENING TRANSACTIONS
    # -------------------------------------------------------------
    logger.info("[STEP 7] Seeding warehouse inventory lots and opening ledger receipts...")
    # Wipe old material transactions to ensure clean baseline ledger
    await db.material_transactions.delete_many({})

    lots_data = [
        {
            "lotNumber": "LOT-SS304-001",
            "materialId": mat_ids["MAT-SS304-SHEET"],
            "specificationId": spec_ids["SPEC-SS304-2MM"],
            "quantityOnHand": 500.0,
            "quantityReserved": 0.0,
            "unit": "sheets",
            "supplier": "Apex Precision Metals Ltd.",
            "batchNumber": "BAT-2026-SS-01",
            "heatNumber": "H-9821A",
            "location": "Warehouse Bay 1 - Rack A1",
            "receivedDate": now - timedelta(days=14),
            "expiryDate": now + timedelta(days=365),
            "unitCost": 45.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-MS-001",
            "materialId": mat_ids["MAT-MS-SHEET"],
            "specificationId": spec_ids["SPEC-MS-2MM"],
            "quantityOnHand": 400.0,
            "quantityReserved": 0.0,
            "unit": "sheets",
            "supplier": "Global Steel Corp",
            "batchNumber": "BAT-2026-MS-01",
            "heatNumber": "H-4410B",
            "location": "Warehouse Bay 2 - Rack B1",
            "receivedDate": now - timedelta(days=20),
            "expiryDate": now + timedelta(days=365),
            "unitCost": 28.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-AL-001",
            "materialId": mat_ids["MAT-AL6061-SHEET"],
            "specificationId": spec_ids["SPEC-AL-3MM"],
            "quantityOnHand": 300.0,
            "quantityReserved": 0.0,
            "unit": "sheets",
            "supplier": "AeroAlloy Dynamics",
            "batchNumber": "BAT-2026-AL-01",
            "heatNumber": "H-1205C",
            "location": "Warehouse Bay 3 - Rack C1",
            "receivedDate": now - timedelta(days=10),
            "expiryDate": now + timedelta(days=365),
            "unitCost": 60.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-WIRE-001",
            "materialId": mat_ids["MAT-WELD-WIRE"],
            "specificationId": spec_ids["SPEC-WIRE-ER70S"],
            "quantityOnHand": 100.0,
            "quantityReserved": 0.0,
            "unit": "spools",
            "supplier": "WeldTech Consumables",
            "batchNumber": "BAT-2026-WT-01",
            "heatNumber": "H-8820W",
            "location": "Tool Crib - Shelf 4",
            "receivedDate": now - timedelta(days=30),
            "expiryDate": now + timedelta(days=500),
            "unitCost": 35.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-PAINT-001",
            "materialId": mat_ids["MAT-PAINT-BLACK"],
            "specificationId": spec_ids["SPEC-PAINT-BLK"],
            "quantityOnHand": 80.0,
            "quantityReserved": 0.0,
            "unit": "canisters",
            "supplier": "DuraCoat Polymers",
            "batchNumber": "BAT-2026-DC-01",
            "heatNumber": "H-7711P",
            "location": "Chemical Storage Room B",
            "receivedDate": now - timedelta(days=25),
            "expiryDate": now + timedelta(days=180),
            "unitCost": 55.0,
            "status": LotStatus.AVAILABLE.value,
        },
    ]

    lot_ids: Dict[str, str] = {}
    for lot in lots_data:
        lot_num = lot["lotNumber"]
        existing = await db.inventory_lots.find_one({"lotNumber": lot_num})
        lot_doc = dict(lot)
        lot_doc["updatedAt"] = now
        if not existing:
            lot_doc["createdAt"] = now
            res = await db.inventory_lots.insert_one(lot_doc)
            lot_ids[lot_num] = str(res.inserted_id)
        else:
            await db.inventory_lots.update_one({"_id": existing["_id"]}, {"$set": lot_doc})
            lot_ids[lot_num] = str(existing["_id"])

        # Create opening balance audit ledger receipt
        await db.material_transactions.insert_one({
            "transactionId": f"TX-INIT-{lot_num}",
            "transactionType": MaterialTransactionType.RECEIPT.value,
            "materialId": lot["materialId"],
            "specificationId": lot["specificationId"],
            "lotId": lot_ids[lot_num],
            "lotNumber": lot_num,
            "workOrderId": None,
            "workOrderCode": None,
            "operationId": None,
            "quantity": lot["quantityOnHand"],
            "previousBalance": 0.0,
            "resultingBalance": lot["quantityOnHand"],
            "actorId": user_ids["SUP-001"],
            "actorType": "SUPERVISOR",
            "timestamp": lot["receivedDate"],
            "notes": f"Initial physical warehouse receipt from {lot['supplier']}.",
        })
    logger.info(f"   Seeded {len(lot_ids)} physical inventory lots with opening ledger transactions.")

    # -------------------------------------------------------------
    # 8. SEED PRODUCTS & CANONICAL ENGINEERING RECIPES
    # -------------------------------------------------------------
    logger.info("[STEP 8] Seeding engineering products and canonical BOM recipes...")

    recipe_bracket_a = {
        "recipeId": "RECIPE-BRACKET-A-V1",
        "recipeName": "BRACKET-A Heavy Duty Fabrication Recipe",
        "version": 1,
        "status": "ACTIVE",
        "steps": [
            {
                "stepId": "STEP-10",
                "sequence": 1,
                "name": "Laser Profile Cutting",
                "description": "Cut bracket base and gusset profiles from 2mm SS304 sheet.",
                "requiredCapabilityIds": [cap_ids["CUTTING"]],
                "requiredMachineType": "CUTTING",
                "estimatedQuantityRate": 2.0,
                "unit": "pcs",
                "dependencies": [],
                "requiredMaterials": [
                    {
                        "materialId": mat_ids["MAT-SS304-SHEET"],
                        "specificationId": spec_ids["SPEC-SS304-2MM"],
                        "quantity": 1.0,
                        "unit": "sheets",
                    }
                ],
            },
            {
                "stepId": "STEP-20",
                "sequence": 2,
                "name": "Press Brake Flange Bending",
                "description": "Form 90-degree stiffening flanges and mounting tabs.",
                "requiredCapabilityIds": [cap_ids["BENDING"]],
                "requiredMachineType": "BENDING",
                "estimatedQuantityRate": 1.5,
                "unit": "pcs",
                "dependencies": ["STEP-10"],
                "requiredMaterials": [
                    {
                        "materialId": mat_ids["MAT-SS304-SHEET"],
                        "specificationId": spec_ids["SPEC-SS304-2MM"],
                        "quantity": 1.0,
                        "unit": "sheets",
                    }
                ],
            },
            {
                "stepId": "STEP-30",
                "sequence": 3,
                "name": "Robotic TIG Gusset Welding",
                "description": "Fillet weld gusset plates to base channel.",
                "requiredCapabilityIds": [cap_ids["WELDING"]],
                "requiredMachineType": "WELDING",
                "estimatedQuantityRate": 1.0,
                "unit": "pcs",
                "dependencies": ["STEP-20"],
                "requiredMaterials": [],
            },
            {
                "stepId": "STEP-40",
                "sequence": 4,
                "name": "Final Metrology & QA Inspection",
                "description": "Check dimensional tolerances, hole centers, and weld penetration.",
                "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                "requiredMachineType": "INSPECTION",
                "estimatedQuantityRate": 2.5,
                "unit": "pcs",
                "dependencies": ["STEP-30"],
                "requiredMaterials": [],
            },
        ],
        "createdAt": now - timedelta(days=60),
        "updatedAt": now - timedelta(days=60),
    }

    recipe_enclosure_b = {
        "recipeId": "RECIPE-ENCLOSURE-B-V1",
        "recipeName": "ENCLOSURE-B Industrial Enclosure Recipe",
        "version": 1,
        "status": "ACTIVE",
        "steps": [
            {
                "stepId": "STEP-10",
                "sequence": 1,
                "name": "Mild Steel Blank Cutting",
                "description": "Cut enclosure panels and access door blanks.",
                "requiredCapabilityIds": [cap_ids["CUTTING"]],
                "requiredMachineType": "CUTTING",
                "estimatedQuantityRate": 2.0,
                "unit": "pcs",
                "dependencies": [],
                "requiredMaterials": [
                    {"materialId": mat_ids["MAT-MS-SHEET"], "specificationId": spec_ids["SPEC-MS-2MM"], "quantity": 1.0, "unit": "sheets"}
                ],
            },
            {
                "stepId": "STEP-20",
                "sequence": 2,
                "name": "Enclosure Box Bending",
                "description": "Form 4-side box enclosure with gasket lip.",
                "requiredCapabilityIds": [cap_ids["BENDING"]],
                "requiredMachineType": "BENDING",
                "estimatedQuantityRate": 1.5,
                "unit": "pcs",
                "dependencies": ["STEP-10"],
                "requiredMaterials": [],
            },
            {
                "stepId": "STEP-30",
                "sequence": 3,
                "name": "Corner Seam Welding",
                "description": "Weld corner seams for IP65 dust/water resistance.",
                "requiredCapabilityIds": [cap_ids["WELDING"]],
                "requiredMachineType": "WELDING",
                "estimatedQuantityRate": 1.0,
                "unit": "pcs",
                "dependencies": ["STEP-20"],
                "requiredMaterials": [],
            },
            {
                "stepId": "STEP-40",
                "sequence": 4,
                "name": "Black Powder Coating",
                "description": "Electrostatic coat exterior box and access panel.",
                "requiredCapabilityIds": [cap_ids["PAINTING"]],
                "requiredMachineType": "PAINTING",
                "estimatedQuantityRate": 1.2,
                "unit": "pcs",
                "dependencies": ["STEP-30"],
                "requiredMaterials": [
                    {"materialId": mat_ids["MAT-PAINT-BLACK"], "specificationId": spec_ids["SPEC-PAINT-BLK"], "quantity": 0.1, "unit": "canisters"}
                ],
            },
            {
                "stepId": "STEP-50",
                "sequence": 5,
                "name": "Coating & Seal Inspection",
                "description": "Film thickness gauge and IP seal audit.",
                "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                "requiredMachineType": "INSPECTION",
                "estimatedQuantityRate": 2.5,
                "unit": "pcs",
                "dependencies": ["STEP-40"],
                "requiredMaterials": [],
            },
        ],
        "createdAt": now - timedelta(days=60),
        "updatedAt": now - timedelta(days=60),
    }

    recipe_chassis_c = {
        "recipeId": "RECIPE-CHASSIS-C-V1",
        "recipeName": "CHASSIS-C Lightweight Avionics Chassis Recipe",
        "version": 1,
        "status": "ACTIVE",
        "steps": [
            {
                "stepId": "STEP-10",
                "sequence": 1,
                "name": "5-Axis High-Speed Pocket Milling",
                "description": "Subtractive milling of weight-reduction ribbing from solid AL6061 plate.",
                "requiredCapabilityIds": [cap_ids["MILLING"]],
                "requiredMachineType": "MILLING",
                "estimatedQuantityRate": 0.8,
                "unit": "pcs",
                "dependencies": [],
                "requiredMaterials": [
                    {"materialId": mat_ids["MAT-AL6061-SHEET"], "specificationId": spec_ids["SPEC-AL-3MM"], "quantity": 1.0, "unit": "sheets"}
                ],
            },
            {
                "stepId": "STEP-20",
                "sequence": 2,
                "name": "Precision Flange Forming",
                "description": "Form avionics connector flanges.",
                "requiredCapabilityIds": [cap_ids["BENDING"]],
                "requiredMachineType": "BENDING",
                "estimatedQuantityRate": 1.5,
                "unit": "pcs",
                "dependencies": ["STEP-10"],
                "requiredMaterials": [],
            },
            {
                "stepId": "STEP-30",
                "sequence": 3,
                "name": "CMM 3D Coordinate Inspection",
                "description": "Verify true positional tolerance of avionics standoff pins.",
                "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                "requiredMachineType": "INSPECTION",
                "estimatedQuantityRate": 2.5,
                "unit": "pcs",
                "dependencies": ["STEP-20"],
                "requiredMaterials": [],
            },
        ],
        "createdAt": now - timedelta(days=60),
        "updatedAt": now - timedelta(days=60),
    }

    products_data = [
        {
            "productCode": "BRACKET-A",
            "name": "Heavy-Duty Structural Mounting Bracket",
            "description": "Stainless steel mounting bracket for structural vibration damping.",
            "unit": "pcs",
            "active": True,
            "recipes": [recipe_bracket_a],
        },
        {
            "productCode": "ENCLOSURE-B",
            "name": "NEMA-4X Sealed Industrial Enclosure",
            "description": "Powder-coated mild steel electrical enclosure with gasket seals.",
            "unit": "pcs",
            "active": True,
            "recipes": [recipe_enclosure_b],
        },
        {
            "productCode": "CHASSIS-C",
            "name": "Aerospace Lightweight Avionics Chassis",
            "description": "Precision 5-axis milled aluminum chassis for avionics hardware.",
            "unit": "pcs",
            "active": True,
            "recipes": [recipe_chassis_c],
        },
    ]

    prod_ids: Dict[str, str] = {}
    for p in products_data:
        p_code = p["productCode"]
        existing = await db.products.find_one({"productCode": p_code})
        p_doc = dict(p)
        p_doc["updatedAt"] = now
        if not existing:
            p_doc["createdAt"] = now
            res = await db.products.insert_one(p_doc)
            prod_ids[p_code] = str(res.inserted_id)
        else:
            await db.products.update_one({"_id": existing["_id"]}, {"$set": p_doc})
            prod_ids[p_code] = str(existing["_id"])
    logger.info(f"   Seeded {len(prod_ids)} catalog products with active recipes & BOMs.")

    # -------------------------------------------------------------
    # 9. SEED WORKFLOWS (EXECUTABLE DAGs DERIVED FROM RECIPES)
    # -------------------------------------------------------------
    logger.info("[STEP 9] Seeding production DAG workflows...")
    workflows_data = [
        {
            "workflowCode": "WF-BRACKET-A",
            "name": "BRACKET-A Standard Manufacturing Route",
            "productId": prod_ids["BRACKET-A"],
            "recipeId": "RECIPE-BRACKET-A-V1",
            "supervisorId": user_ids["SUP-001"],
            "version": 1,
            "status": WorkflowStatus.ACTIVE.value,
            "operations": [
                {
                    "operationId": "OP-10",
                    "name": "Laser Profile Cutting",
                    "sequence": 1,
                    "description": "Cut bracket base and gusset profiles.",
                    "requiredCapabilityIds": [cap_ids["CUTTING"]],
                    "requiredMachineType": "CUTTING",
                    "assignedMachineId": mach_ids["M-01"],
                    "assignedOperatorId": user_ids["OP-001"],
                    "estimatedDurationSeconds": 15,
                    "dependencies": [],
                    "requiredMaterials": [{"materialId": mat_ids["MAT-SS304-SHEET"], "specificationId": spec_ids["SPEC-SS304-2MM"], "quantity": 1.0, "unit": "sheets"}],
                },
                {
                    "operationId": "OP-20",
                    "name": "Press Brake Flange Bending",
                    "sequence": 2,
                    "description": "Form 90-degree stiffening flanges.",
                    "requiredCapabilityIds": [cap_ids["BENDING"]],
                    "requiredMachineType": "BENDING",
                    "assignedMachineId": mach_ids["M-02"],
                    "assignedOperatorId": user_ids["OP-002"],
                    "estimatedDurationSeconds": 18,
                    "dependencies": ["OP-10"],
                    "requiredMaterials": [{"materialId": mat_ids["MAT-SS304-SHEET"], "specificationId": spec_ids["SPEC-SS304-2MM"], "quantity": 1.0, "unit": "sheets"}],
                },
                {
                    "operationId": "OP-30",
                    "name": "Robotic TIG Gusset Welding",
                    "sequence": 3,
                    "description": "Fillet weld gusset plates.",
                    "requiredCapabilityIds": [cap_ids["WELDING"]],
                    "requiredMachineType": "WELDING",
                    "assignedMachineId": mach_ids["M-03"],
                    "assignedOperatorId": user_ids["OP-003"],
                    "estimatedDurationSeconds": 25,
                    "dependencies": ["OP-20"],
                    "requiredMaterials": [],
                },
                {
                    "operationId": "OP-40",
                    "name": "Final Metrology & QA Inspection",
                    "sequence": 4,
                    "description": "QA inspection of dimensional tolerances.",
                    "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                    "requiredMachineType": "INSPECTION",
                    "assignedMachineId": mach_ids["M-06"],
                    "assignedOperatorId": user_ids["OP-004"],
                    "estimatedDurationSeconds": 10,
                    "dependencies": ["OP-30"],
                    "requiredMaterials": [],
                },
            ],
            "createdBy": "SYSTEM",
        },
        {
            "workflowCode": "WF-ENCLOSURE-B",
            "name": "ENCLOSURE-B Standard Route",
            "productId": prod_ids["ENCLOSURE-B"],
            "recipeId": "RECIPE-ENCLOSURE-B-V1",
            "supervisorId": user_ids["SUP-001"],
            "version": 1,
            "status": WorkflowStatus.ACTIVE.value,
            "operations": [
                {
                    "operationId": "OP-10",
                    "name": "Mild Steel Blank Cutting",
                    "sequence": 1,
                    "requiredCapabilityIds": [cap_ids["CUTTING"]],
                    "requiredMachineType": "CUTTING",
                    "assignedMachineId": mach_ids["M-01"],
                    "assignedOperatorId": user_ids["OP-001"],
                    "estimatedDurationSeconds": 20,
                    "dependencies": [],
                    "requiredMaterials": [{"materialId": mat_ids["MAT-MS-SHEET"], "specificationId": spec_ids["SPEC-MS-2MM"], "quantity": 1.0, "unit": "sheets"}],
                },
                {
                    "operationId": "OP-20",
                    "name": "Enclosure Box Bending",
                    "sequence": 2,
                    "requiredCapabilityIds": [cap_ids["BENDING"]],
                    "requiredMachineType": "BENDING",
                    "assignedMachineId": mach_ids["M-02"],
                    "assignedOperatorId": user_ids["OP-002"],
                    "estimatedDurationSeconds": 25,
                    "dependencies": ["OP-10"],
                    "requiredMaterials": [],
                },
                {
                    "operationId": "OP-30",
                    "name": "Corner Seam Welding",
                    "sequence": 3,
                    "requiredCapabilityIds": [cap_ids["WELDING"]],
                    "requiredMachineType": "WELDING",
                    "assignedMachineId": mach_ids["M-03"],
                    "assignedOperatorId": user_ids["OP-003"],
                    "estimatedDurationSeconds": 30,
                    "dependencies": ["OP-20"],
                    "requiredMaterials": [],
                },
                {
                    "operationId": "OP-40",
                    "name": "Black Powder Coating",
                    "sequence": 4,
                    "requiredCapabilityIds": [cap_ids["PAINTING"]],
                    "requiredMachineType": "PAINTING",
                    "assignedMachineId": mach_ids["M-05"],
                    "assignedOperatorId": user_ids["OP-003"],
                    "estimatedDurationSeconds": 35,
                    "dependencies": ["OP-30"],
                    "requiredMaterials": [{"materialId": mat_ids["MAT-PAINT-BLACK"], "specificationId": spec_ids["SPEC-PAINT-BLK"], "quantity": 0.1, "unit": "canisters"}],
                },
                {
                    "operationId": "OP-50",
                    "name": "Coating & Seal Inspection",
                    "sequence": 5,
                    "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                    "requiredMachineType": "INSPECTION",
                    "assignedMachineId": mach_ids["M-06"],
                    "assignedOperatorId": user_ids["OP-004"],
                    "estimatedDurationSeconds": 15,
                    "dependencies": ["OP-40"],
                    "requiredMaterials": [],
                },
            ],
            "createdBy": "SYSTEM",
        },
        {
            "workflowCode": "WF-CHASSIS-C",
            "name": "CHASSIS-C Aerospace Milling Route",
            "productId": prod_ids["CHASSIS-C"],
            "recipeId": "RECIPE-CHASSIS-C-V1",
            "supervisorId": user_ids["SUP-001"],
            "version": 1,
            "status": WorkflowStatus.ACTIVE.value,
            "operations": [
                {
                    "operationId": "OP-10",
                    "name": "5-Axis High-Speed Pocket Milling",
                    "sequence": 1,
                    "requiredCapabilityIds": [cap_ids["MILLING"]],
                    "requiredMachineType": "MILLING",
                    "assignedMachineId": mach_ids["M-04"],
                    "assignedOperatorId": user_ids["OP-002"],
                    "estimatedDurationSeconds": 45,
                    "dependencies": [],
                    "requiredMaterials": [{"materialId": mat_ids["MAT-AL6061-SHEET"], "specificationId": spec_ids["SPEC-AL-3MM"], "quantity": 1.0, "unit": "sheets"}],
                },
                {
                    "operationId": "OP-20",
                    "name": "Precision Flange Forming",
                    "sequence": 2,
                    "requiredCapabilityIds": [cap_ids["BENDING"]],
                    "requiredMachineType": "BENDING",
                    "assignedMachineId": mach_ids["M-02"],
                    "assignedOperatorId": user_ids["OP-002"],
                    "estimatedDurationSeconds": 20,
                    "dependencies": ["OP-10"],
                    "requiredMaterials": [],
                },
                {
                    "operationId": "OP-30",
                    "name": "CMM 3D Coordinate Inspection",
                    "sequence": 3,
                    "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                    "requiredMachineType": "INSPECTION",
                    "assignedMachineId": mach_ids["M-06"],
                    "assignedOperatorId": user_ids["OP-004"],
                    "estimatedDurationSeconds": 20,
                    "dependencies": ["OP-20"],
                    "requiredMaterials": [],
                },
            ],
            "createdBy": "SYSTEM",
        },
    ]

    wf_ids: Dict[str, str] = {}
    for wf in workflows_data:
        w_code = wf["workflowCode"]
        existing = await db.workflows.find_one({"workflowCode": w_code, "version": wf["version"]})
        wf_doc = dict(wf)
        wf_doc["updatedAt"] = now
        if not existing:
            wf_doc["createdAt"] = now
            res = await db.workflows.insert_one(wf_doc)
            wf_ids[w_code] = str(res.inserted_id)
        else:
            await db.workflows.update_one({"_id": existing["_id"]}, {"$set": wf_doc})
            wf_ids[w_code] = str(existing["_id"])
    logger.info(f"   Seeded {len(wf_ids)} production workflows (WF-BRACKET-A, WF-ENCLOSURE-B, WF-CHASSIS-C).")

    # -------------------------------------------------------------
    # 10. SEED PRODUCTION WORK ORDERS (ALL IN PURE PLANNED STATUS)
    # -------------------------------------------------------------
    logger.info("[STEP 10] Seeding master production orders (All in PLANNED status)...")
    # Wipe old work orders to prevent stale executions
    await db.work_orders.delete_many({})

    # Work Order 1: BRACKET-A Production Run (25 units)
    wo_1001_ops = [
        {
            "operationId": "OP-10",
            "name": "Laser Profile Cutting",
            "sequence": 1,
            "assignedMachineId": mach_ids["M-01"],
            "assignedOperatorId": user_ids["OP-001"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 13,
            "inputQuantity": 25.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": [],
            "requiredMaterials": [
                {
                    "materialId": mat_ids["MAT-SS304-SHEET"],
                    "specificationId": spec_ids["SPEC-SS304-2MM"],
                    "materialName": "Stainless Steel 304 Sheet (2mm)",
                    "specificationName": "Stainless Steel 304 Sheet (2mm Cold-Rolled)",
                    "unit": "sheets",
                    "quantityPerUnit": 1.0,
                    "totalRequiredQuantity": 25.0,
                    "quantityReserved": 0.0,
                    "quantityConsumed": 0.0,
                    "unitCost": 45.0,
                    "estimatedCost": 1125.0,
                    "actualCost": 0.0,
                }
            ],
        },
        {
            "operationId": "OP-20",
            "name": "Press Brake Flange Bending",
            "sequence": 2,
            "assignedMachineId": mach_ids["M-02"],
            "assignedOperatorId": user_ids["OP-002"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 17,
            "inputQuantity": 25.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-10"],
            "requiredMaterials": [
                {
                    "materialId": mat_ids["MAT-SS304-SHEET"],
                    "specificationId": spec_ids["SPEC-SS304-2MM"],
                    "materialName": "Stainless Steel 304 Sheet (2mm)",
                    "specificationName": "Stainless Steel 304 Sheet (2mm Cold-Rolled)",
                    "unit": "sheets",
                    "quantityPerUnit": 1.0,
                    "totalRequiredQuantity": 25.0,
                    "quantityReserved": 0.0,
                    "quantityConsumed": 0.0,
                    "unitCost": 45.0,
                    "estimatedCost": 1125.0,
                    "actualCost": 0.0,
                }
            ],
        },
        {
            "operationId": "OP-30",
            "name": "Robotic TIG Gusset Welding",
            "sequence": 3,
            "assignedMachineId": mach_ids["M-03"],
            "assignedOperatorId": user_ids["OP-003"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 25,
            "inputQuantity": 25.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-20"],
            "requiredMaterials": [],
        },
        {
            "operationId": "OP-40",
            "name": "Final Metrology & QA Inspection",
            "sequence": 4,
            "assignedMachineId": mach_ids["M-06"],
            "assignedOperatorId": user_ids["OP-004"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 10,
            "inputQuantity": 25.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-30"],
            "requiredMaterials": [],
        },
    ]

    wo_1001_doc = {
        "workOrderCode": "WO-1001",
        "name": "Mounting Bracket Production Run - Batch A1",
        "productId": prod_ids["BRACKET-A"],
        "workflowId": wf_ids["WF-BRACKET-A"],
        "workflowVersion": 1,
        "supervisorId": user_ids["SUP-001"],
        "quantity": 25.0,
        "priority": WorkOrderPriority.HIGH.value,
        "dueDate": now + timedelta(days=5),
        "status": WorkOrderStatus.PLANNED.value,
        "startedAt": None,
        "completedAt": None,
        "createdBy": "SUP-001",
        "operations": wo_1001_ops,
        "createdAt": now - timedelta(hours=2),
        "updatedAt": now,
    }
    await db.work_orders.insert_one(wo_1001_doc)

    # Work Order 2: ENCLOSURE-B Industrial Enclosure (15 units)
    wo_1002_ops = [
        {
            "operationId": "OP-10",
            "name": "Mild Steel Blank Cutting",
            "sequence": 1,
            "assignedMachineId": mach_ids["M-01"],
            "assignedOperatorId": user_ids["OP-001"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 15,
            "inputQuantity": 15.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": [],
            "requiredMaterials": [
                {
                    "materialId": mat_ids["MAT-MS-SHEET"],
                    "specificationId": spec_ids["SPEC-MS-2MM"],
                    "materialName": "Mild Steel Cold-Rolled Sheet (2mm)",
                    "specificationName": "Mild Steel Cold-Rolled Sheet (2mm CR4)",
                    "unit": "sheets",
                    "quantityPerUnit": 1.0,
                    "totalRequiredQuantity": 15.0,
                    "quantityReserved": 0.0,
                    "quantityConsumed": 0.0,
                    "unitCost": 28.0,
                    "estimatedCost": 420.0,
                    "actualCost": 0.0,
                }
            ],
        },
        {
            "operationId": "OP-20",
            "name": "Enclosure Box Bending",
            "sequence": 2,
            "assignedMachineId": mach_ids["M-02"],
            "assignedOperatorId": user_ids["OP-002"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 20,
            "inputQuantity": 15.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-10"],
            "requiredMaterials": [],
        },
        {
            "operationId": "OP-30",
            "name": "Corner Seam Welding",
            "sequence": 3,
            "assignedMachineId": mach_ids["M-03"],
            "assignedOperatorId": user_ids["OP-003"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 25,
            "inputQuantity": 15.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-20"],
            "requiredMaterials": [],
        },
        {
            "operationId": "OP-40",
            "name": "Black Powder Coating",
            "sequence": 4,
            "assignedMachineId": mach_ids["M-05"],
            "assignedOperatorId": user_ids["OP-003"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 30,
            "inputQuantity": 15.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-30"],
            "requiredMaterials": [
                {
                    "materialId": mat_ids["MAT-PAINT-BLACK"],
                    "specificationId": spec_ids["SPEC-PAINT-BLK"],
                    "materialName": "Industrial Matte Black Powder Coating",
                    "specificationName": "High-Durability Industrial Matte Black Powder",
                    "unit": "canisters",
                    "quantityPerUnit": 0.1,
                    "totalRequiredQuantity": 1.5,
                    "quantityReserved": 0.0,
                    "quantityConsumed": 0.0,
                    "unitCost": 55.0,
                    "estimatedCost": 82.5,
                    "actualCost": 0.0,
                }
            ],
        },
        {
            "operationId": "OP-50",
            "name": "Coating & Seal Inspection",
            "sequence": 5,
            "assignedMachineId": mach_ids["M-06"],
            "assignedOperatorId": user_ids["OP-004"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 15,
            "inputQuantity": 15.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-40"],
            "requiredMaterials": [],
        },
    ]

    wo_1002_doc = {
        "workOrderCode": "WO-1002",
        "name": "NEMA-4X Sealed Control Enclosure Batch",
        "productId": prod_ids["ENCLOSURE-B"],
        "workflowId": wf_ids["WF-ENCLOSURE-B"],
        "workflowVersion": 1,
        "supervisorId": user_ids["SUP-001"],
        "quantity": 15.0,
        "priority": WorkOrderPriority.NORMAL.value,
        "dueDate": now + timedelta(days=7),
        "status": WorkOrderStatus.PLANNED.value,
        "startedAt": None,
        "completedAt": None,
        "createdBy": "SUP-001",
        "operations": wo_1002_ops,
        "createdAt": now - timedelta(hours=1),
        "updatedAt": now,
    }
    await db.work_orders.insert_one(wo_1002_doc)

    # Work Order 3: CHASSIS-C Avionics Chassis (10 units)
    wo_1003_ops = [
        {
            "operationId": "OP-10",
            "name": "5-Axis High-Speed Pocket Milling",
            "sequence": 1,
            "assignedMachineId": mach_ids["M-04"],
            "assignedOperatorId": user_ids["OP-002"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 30,
            "inputQuantity": 10.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": [],
            "requiredMaterials": [
                {
                    "materialId": mat_ids["MAT-AL6061-SHEET"],
                    "specificationId": spec_ids["SPEC-AL-3MM"],
                    "materialName": "Aluminum 6061-T6 Plate (3mm)",
                    "specificationName": "Aluminum 6061-T6 Plate (3mm Aerospace Grade)",
                    "unit": "sheets",
                    "quantityPerUnit": 1.0,
                    "totalRequiredQuantity": 10.0,
                    "quantityReserved": 0.0,
                    "quantityConsumed": 0.0,
                    "unitCost": 60.0,
                    "estimatedCost": 600.0,
                    "actualCost": 0.0,
                }
            ],
        },
        {
            "operationId": "OP-20",
            "name": "Precision Flange Forming",
            "sequence": 2,
            "assignedMachineId": mach_ids["M-02"],
            "assignedOperatorId": user_ids["OP-002"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 15,
            "inputQuantity": 10.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-10"],
            "requiredMaterials": [],
        },
        {
            "operationId": "OP-30",
            "name": "CMM 3D Coordinate Inspection",
            "sequence": 3,
            "assignedMachineId": mach_ids["M-06"],
            "assignedOperatorId": user_ids["OP-004"],
            "status": WorkOrderOperationStatus.PENDING.value,
            "durationSeconds": 15,
            "inputQuantity": 10.0,
            "processedQuantity": 0.0,
            "outputQuantity": 0.0,
            "scrapQuantity": 0.0,
            "quantityCompleted": 0.0,
            "quantityRejected": 0.0,
            "dependencies": ["OP-20"],
            "requiredMaterials": [],
        },
    ]

    wo_1003_doc = {
        "workOrderCode": "WO-1003",
        "name": "Aerospace Lightweight Avionics Chassis Run",
        "productId": prod_ids["CHASSIS-C"],
        "workflowId": wf_ids["WF-CHASSIS-C"],
        "workflowVersion": 1,
        "supervisorId": user_ids["SUP-001"],
        "quantity": 10.0,
        "priority": WorkOrderPriority.NORMAL.value,
        "dueDate": now + timedelta(days=10),
        "status": WorkOrderStatus.PLANNED.value,
        "startedAt": None,
        "completedAt": None,
        "createdBy": "SUP-001",
        "operations": wo_1003_ops,
        "createdAt": now - timedelta(minutes=30),
        "updatedAt": now,
    }
    await db.work_orders.insert_one(wo_1003_doc)

    logger.info("   Seeded 3 clean Production Orders (WO-1001, WO-1002, WO-1003) in PLANNED status.")

    # -------------------------------------------------------------
    # 11. BASELINE INTEGRITY SUMMARY REPORT
    # -------------------------------------------------------------
    logger.info("=" * 70)
    logger.info("       STATIC BASELINE VERIFICATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"   Users:                  {await db.users.count_documents({})} registered personnel")
    logger.info(f"   Terminal Pairings:      {await db.operator_activations.count_documents({})} active pairing codes")
    logger.info(f"   Capabilities:           {await db.capabilities.count_documents({})} capabilities")
    logger.info(f"   Workstations (IDLE):    {await db.machines.count_documents({'status': 'IDLE'})} / {await db.machines.count_documents({})} machines")
    logger.info(f"   Material Specs:         {await db.material_specifications.count_documents({})} specifications")
    logger.info(f"   Raw Materials:          {await db.materials.count_documents({})} items")
    logger.info(f"   Inventory Lots:         {await db.inventory_lots.count_documents({'status': 'AVAILABLE'})} available lots")
    logger.info(f"   Catalog Products:       {await db.products.count_documents({})} discrete products")
    logger.info(f"   Executable Workflows:   {await db.workflows.count_documents({'status': 'ACTIVE'})} active DAG routes")
    logger.info(f"   Production Orders:      {await db.work_orders.count_documents({'status': 'PLANNED'})} PLANNED work orders")
    logger.info(f"   Runtime Incidents:      {await db.incidents.count_documents({})} (Clean)")
    logger.info(f"   Live Execution Events:  {await db.execution_events.count_documents({})} (Clean)")
    logger.info("=" * 70)
    logger.info("STATIC BASELINE SEEDING SUCCESSFULLY COMPLETED!")
    logger.info("=" * 70)

    await db_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(seed_static_resources())
