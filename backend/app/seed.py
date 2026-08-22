import asyncio
import logging
import argparse
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.core.database import db_manager, get_db
from app.schemas.workflow import WorkflowStatus
from app.schemas.work_order import WorkOrderStatus, WorkOrderPriority, WorkOrderOperationStatus
from app.schemas.machine import MachineStatus
from app.schemas.user import UserRole, OperatorAvailability, UserStatus
from app.schemas.material_specification import MaterialForm
from app.schemas.inventory_lot import LotStatus
from app.schemas.material_reservation import ReservationStatus
from app.schemas.material_transaction import MaterialTransactionType
from app.schemas.incident import IncidentType, IncidentSeverity, IncidentStatus
from app.services.machine_health_service import MachineHealthService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROTECTED_COLLECTIONS = {"users", "user_profiles"}

RESET_COLLECTIONS = [
    "capabilities",
    "machines",
    "material_specifications",
    "materials",
    "inventory_lots",
    "material_reservations",
    "material_transactions",
    "products",
    "workflows",
    "work_orders",
    "executions",
    "execution_events",
    "incidents",
    "audit_events",
    "ai_operations",
    "ai_work_order_sessions",
    "machine_health_records",
    "operator_activations",
]

async def run_seed(reset_demo: bool = False):
    logger.info("Initializing database connection...")
    await db_manager.connect()
    db = get_db()

    # -------------------------------------------------------------
    # 1. USER DATA PRESERVATION & PRE-RESET AUDIT
    # -------------------------------------------------------------
    logger.info("Verifying user accounts in database...")
    pre_users_cursor = db.users.find({})
    pre_users_list = await pre_users_cursor.to_list(200)
    pre_users_snapshot = {}
    for u in pre_users_list:
        uid = str(u["_id"])
        pre_users_snapshot[uid] = {
            "employeeId": u.get("employeeId"),
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role"),
            "department": u.get("department"),
            "status": u.get("status"),
            "availabilityStatus": u.get("availabilityStatus"),
        }
    logger.info(f"Discovered {len(pre_users_snapshot)} existing user account(s) to protect.")

    # -------------------------------------------------------------
    # 2. CONTROLLED OPERATIONAL RESET (IF REQUESTED)
    # -------------------------------------------------------------
    if reset_demo:
        logger.info("==================================================")
        logger.info("EXECUTING CONTROLLED DEMONSTRATION RESET")
        logger.info("==================================================")

        for col in RESET_COLLECTIONS:
            # Absolute Safety Assertion
            if col in PROTECTED_COLLECTIONS:
                raise PermissionError(
                    f"CRITICAL SAFETY VIOLATION: Refusing to reset protected collection '{col}'!"
                )
            del_result = await db[col].delete_many({})
            logger.info(f"Reset '{col}': Removed {del_result.deleted_count} document(s).")

        # Re-ensure database indexes
        logger.info("Re-creating all collection indexes...")
        await db_manager.create_indexes()

        # Immediate User Integrity Check Post-Reset
        post_users_count = await db.users.count_documents({})
        if post_users_count != len(pre_users_snapshot):
            raise AssertionError(
                f"FATAL: User collection count mismatch after reset! Expected {len(pre_users_snapshot)}, found {post_users_count}."
            )
        logger.info("User preservation verified: 100% of user records intact.")

    # -------------------------------------------------------------
    # 3. DISCOVER / ENSURE CORE USER MAP
    # -------------------------------------------------------------
    # If the database had no users at all (e.g. brand new install), seed standard initial accounts
    if len(pre_users_snapshot) == 0:
        logger.info("No users found in fresh database. Seeding initial baseline accounts...")
        init_users = [
            {"employeeId": "OP-001", "name": "Alex Rivera", "email": "alex.rivera@mes.com", "role": UserRole.OPERATOR.value, "department": "Fabrication", "status": UserStatus.ACTIVE.value, "availabilityStatus": OperatorAvailability.AVAILABLE.value},
            {"employeeId": "OP-002", "name": "Beatriz Vance", "email": "beatriz.vance@mes.com", "role": UserRole.OPERATOR.value, "department": "Assembly", "status": UserStatus.ACTIVE.value, "availabilityStatus": OperatorAvailability.AVAILABLE.value},
            {"employeeId": "OP-003", "name": "Carlos Chen", "email": "carlos.chen@mes.com", "role": UserRole.OPERATOR.value, "department": "Finishing", "status": UserStatus.ACTIVE.value, "availabilityStatus": OperatorAvailability.AVAILABLE.value},
            {"employeeId": "OP-004", "name": "David Kim", "email": "david.kim@mes.com", "role": UserRole.OPERATOR.value, "department": "Quality", "status": UserStatus.ACTIVE.value, "availabilityStatus": OperatorAvailability.AVAILABLE.value},
            {"employeeId": "SUP-001", "name": "Elena Rostova", "email": "elena.rostova@mes.com", "role": UserRole.SUPERVISOR.value, "department": "Plant Management", "status": UserStatus.ACTIVE.value, "availabilityStatus": OperatorAvailability.AVAILABLE.value},
        ]
        for u in init_users:
            u["createdAt"] = datetime.utcnow()
            u["updatedAt"] = datetime.utcnow()
            await db.users.insert_one(u)

    user_map = {}
    users_cursor = db.users.find({})
    async for u in users_cursor:
        emp_id = u.get("employeeId")
        if emp_id:
            user_map[emp_id] = str(u["_id"])

    sup_id = user_map.get("SUP-001") or list(user_map.values())[0]
    op1_id = user_map.get("OP-001") or list(user_map.values())[0]
    op2_id = user_map.get("OP-002") or list(user_map.values())[0]
    op3_id = user_map.get("OP-003") or list(user_map.values())[0]
    op4_id = user_map.get("OP-004") or list(user_map.values())[0]

    # -------------------------------------------------------------
    # 4. SEED CAPABILITIES
    # -------------------------------------------------------------
    logger.info("Seeding manufacturing capabilities...")
    capabilities_data = [
        {"code": "CUTTING", "name": "Laser & Plasma Cutting", "description": "High-precision CNC cutting of raw sheet metal into component profiles."},
        {"code": "BENDING", "name": "CNC Press Brake Forming", "description": "Precision multi-angle forming and bending of sheet metal parts."},
        {"code": "WELDING", "name": "Robotic TIG & MIG Welding", "description": "High-integrity structural and seam welding of metal subassemblies."},
        {"code": "MILLING", "name": "5-Axis CNC Precision Milling", "description": "Subtractive high-tolerance machining, surfacing, and drilling."},
        {"code": "PAINTING", "name": "Electrostatic Powder Coating", "description": "Surface preparation and durable protective powder coating."},
        {"code": "INSPECTION", "name": "Coordinate Measuring & QA", "description": "Dimensional metrology, optical inspection, and weld integrity testing."},
    ]
    cap_ids = {}
    for cap in capabilities_data:
        existing = await db.capabilities.find_one({"code": cap["code"]})
        if not existing:
            cap["createdAt"] = datetime.utcnow()
            cap["updatedAt"] = datetime.utcnow()
            res = await db.capabilities.insert_one(cap)
            cap_ids[cap["code"]] = str(res.inserted_id)
        else:
            cap_ids[cap["code"]] = str(existing["_id"])

    # -------------------------------------------------------------
    # 5. SEED MACHINES (7 REALISTIC EQUIPMENT UNITS)
    # -------------------------------------------------------------
    logger.info("Seeding factory workstations and machines...")
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
            "currentOperatorId": None,
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
            "currentOperatorId": None,
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
            "currentOperatorId": None,
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
            "currentOperatorId": None,
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
            "currentOperatorId": None,
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
            "currentOperatorId": None,
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
            "currentOperatorId": None,
        },
    ]

    mach_ids = {}
    for mach in machines_data:
        existing = await db.machines.find_one({"machineCode": mach["machineCode"]})
        if not existing:
            mach["createdAt"] = datetime.utcnow()
            mach["updatedAt"] = datetime.utcnow()
            res = await db.machines.insert_one(mach)
            mach_ids[mach["machineCode"]] = str(res.inserted_id)
        else:
            mach_ids[mach["machineCode"]] = str(existing["_id"])
            await db.machines.update_one({"_id": existing["_id"]}, {"$set": mach})

    # -------------------------------------------------------------
    # 6. SEED PHASE 6 MATERIAL SPECIFICATIONS & MATERIALS
    # -------------------------------------------------------------
    logger.info("Seeding Phase 6 material specifications and catalog...")
    specs_data = [
        {
            "specificationCode": "SPEC-SS304-2MM",
            "name": "Stainless Steel 304 2mm Sheet",
            "category": MaterialForm.SHEET.value,
            "grade": "SS304",
            "dimensions": {"thicknessMm": 2.0, "widthMm": 1250.0, "lengthMm": 2500.0},
            "densityGcm3": 8.0,
            "unitOfMeasure": "sheets",
            "active": True,
        },
        {
            "specificationCode": "SPEC-MS-2MM",
            "name": "Mild Steel 2mm Cold-Rolled Sheet",
            "category": MaterialForm.SHEET.value,
            "grade": "MILD_STEEL",
            "dimensions": {"thicknessMm": 2.0, "widthMm": 1250.0, "lengthMm": 2500.0},
            "densityGcm3": 7.85,
            "unitOfMeasure": "sheets",
            "active": True,
        },
        {
            "specificationCode": "SPEC-AL-3MM",
            "name": "Aluminum 6061-T6 3mm Sheet",
            "category": MaterialForm.SHEET.value,
            "grade": "AL6061-T6",
            "dimensions": {"thicknessMm": 3.0, "widthMm": 1000.0, "lengthMm": 2000.0},
            "densityGcm3": 2.7,
            "unitOfMeasure": "sheets",
            "active": True,
        },
        {
            "specificationCode": "SPEC-WIRE-ER70S",
            "name": "ER70S-6 Solid MIG/TIG Welding Wire 1.2mm",
            "category": MaterialForm.WIRE.value,
            "grade": "ER70S-6",
            "dimensions": {"diameterMm": 1.2},
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

    spec_ids = {}
    for s in specs_data:
        existing = await db.material_specifications.find_one({"specificationCode": s["specificationCode"]})
        if not existing:
            s["createdAt"] = datetime.utcnow()
            s["updatedAt"] = datetime.utcnow()
            res = await db.material_specifications.insert_one(s)
            spec_ids[s["specificationCode"]] = str(res.inserted_id)
        else:
            spec_ids[s["specificationCode"]] = str(existing["_id"])

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
            "quantityOnHand": 800.0,
            "quantityReserved": 20.0,
            "quantityAvailable": 780.0,
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
            "quantityOnHand": 250.0,
            "quantityReserved": 20.0,
            "quantityAvailable": 230.0,
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
            "name": "Industrial Matte Black Powder Canister",
            "unit": "canisters",
            "specificationId": spec_ids["SPEC-PAINT-BLK"],
            "category": "POWDER",
            "grade": "POLYESTER_TGIC",
            "reorderLevel": 5.0,
            "unitCost": 85.0,
            "active": True,
            "quantityOnHand": 50.0,
            "quantityReserved": 0.0,
            "quantityAvailable": 50.0,
        },
    ]

    mat_ids = {}
    for mat in materials_data:
        existing = await db.materials.find_one({"materialCode": mat["materialCode"]})
        if not existing:
            mat["createdAt"] = datetime.utcnow()
            mat["updatedAt"] = datetime.utcnow()
            res = await db.materials.insert_one(mat)
            mat_ids[mat["materialCode"]] = str(res.inserted_id)
        else:
            mat_ids[mat["materialCode"]] = str(existing["_id"])
            await db.materials.update_one({"_id": existing["_id"]}, {"$set": mat})

    # -------------------------------------------------------------
    # 7. SEED PHYSICAL INVENTORY LOTS (FIFO / FEFO & TRACEABILITY)
    # -------------------------------------------------------------
    logger.info("Seeding physical inventory lots with supplier and metallurgical heat traceability...")
    lots_data = [
        {
            "lotNumber": "LOT-SS304-001",
            "materialId": mat_ids["MAT-SS304-SHEET"],
            "specificationId": spec_ids["SPEC-SS304-2MM"],
            "quantityOnHand": 500.0,
            "quantityReserved": 20.0,
            "unit": "sheets",
            "supplier": "Apex Metals Corp",
            "batchNumber": "BAT-2026-08A",
            "heatNumber": "H-304-001",
            "location": "Rack A-01",
            "receivedDate": datetime.utcnow() - timedelta(days=20),
            "unitCost": 45.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-SS304-002",
            "materialId": mat_ids["MAT-SS304-SHEET"],
            "specificationId": spec_ids["SPEC-SS304-2MM"],
            "quantityOnHand": 300.0,
            "quantityReserved": 0.0,
            "unit": "sheets",
            "supplier": "Vanguard Alloys Ltd",
            "batchNumber": "BAT-2026-08B",
            "heatNumber": "H-304-002",
            "location": "Rack A-02",
            "receivedDate": datetime.utcnow() - timedelta(days=5),
            "unitCost": 46.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-MS-001",
            "materialId": mat_ids["MAT-MS-SHEET"],
            "specificationId": spec_ids["SPEC-MS-2MM"],
            "quantityOnHand": 400.0,
            "quantityReserved": 0.0,
            "unit": "sheets",
            "supplier": "Titan Steel Mills",
            "batchNumber": "BAT-MS-91",
            "heatNumber": "H-MS-11",
            "location": "Rack B-01",
            "receivedDate": datetime.utcnow() - timedelta(days=15),
            "unitCost": 28.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-AL-001",
            "materialId": mat_ids["MAT-AL6061-SHEET"],
            "specificationId": spec_ids["SPEC-AL-3MM"],
            "quantityOnHand": 250.0,
            "quantityReserved": 20.0,
            "unit": "sheets",
            "supplier": "AeroAlloy Global",
            "batchNumber": "BAT-AL-44",
            "heatNumber": "H-AL-88",
            "location": "Rack C-01",
            "receivedDate": datetime.utcnow() - timedelta(days=10),
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
            "supplier": "WeldCraft Ind",
            "batchNumber": "BAT-WC-01",
            "heatNumber": "H-W-55",
            "location": "Bay W-01",
            "receivedDate": datetime.utcnow() - timedelta(days=25),
            "unitCost": 35.0,
            "status": LotStatus.AVAILABLE.value,
        },
        {
            "lotNumber": "LOT-PAINT-001",
            "materialId": mat_ids["MAT-PAINT-BLACK"],
            "specificationId": spec_ids["SPEC-PAINT-BLK"],
            "quantityOnHand": 50.0,
            "quantityReserved": 0.0,
            "unit": "canisters",
            "supplier": "PolyCoat Solutions",
            "batchNumber": "BAT-PC-99",
            "location": "Rack P-01",
            "receivedDate": datetime.utcnow() - timedelta(days=30),
            "unitCost": 85.0,
            "status": LotStatus.AVAILABLE.value,
        },
    ]

    lot_ids = {}
    for lot in lots_data:
        existing = await db.inventory_lots.find_one({"lotNumber": lot["lotNumber"]})
        if not existing:
            lot["createdAt"] = datetime.utcnow()
            lot["updatedAt"] = datetime.utcnow()
            res = await db.inventory_lots.insert_one(lot)
            lot_ids[lot["lotNumber"]] = str(res.inserted_id)
        else:
            lot_ids[lot["lotNumber"]] = str(existing["_id"])
            await db.inventory_lots.update_one({"_id": existing["_id"]}, {"$set": lot})

    # Initial Material Receipt Transactions in Ledger
    for lot_num, lot_id in lot_ids.items():
        tx_exists = await db.material_transactions.find_one({"transactionId": f"TX-INIT-{lot_num}"})
        if not tx_exists:
            matching_lot = next(l for l in lots_data if l["lotNumber"] == lot_num)
            await db.material_transactions.insert_one({
                "transactionId": f"TX-INIT-{lot_num}",
                "transactionType": MaterialTransactionType.RECEIPT.value,
                "materialId": matching_lot["materialId"],
                "specificationId": matching_lot["specificationId"],
                "lotId": lot_id,
                "lotNumber": lot_num,
                "quantity": matching_lot["quantityOnHand"],
                "previousBalance": 0.0,
                "resultingBalance": matching_lot["quantityOnHand"],
                "actorId": sup_id,
                "actorType": "SUPERVISOR",
                "timestamp": matching_lot["receivedDate"],
                "notes": f"Initial physical receipt into warehouse from {matching_lot.get('supplier', 'Vendor')}.",
            })

    # -------------------------------------------------------------
    # 8. SEED PRODUCTS & RECIPES (1 FINISHED UNIT = ACCUMULATED CONSUMPTION)
    # -------------------------------------------------------------
    logger.info("Seeding engineering products and canonical manufacturing recipes...")

    # Product 1: BRACKET-A
    # Step 10: CUTTING consumes 1 sheet SS304
    # Step 20: BENDING consumes 1 sheet SS304
    # Step 30: WELDING consumes 0 sheets
    # Step 40: INSPECTION consumes 0 sheets
    # Total Material = 2 sheets / finished unit
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
        "createdAt": datetime.utcnow() - timedelta(days=60),
        "updatedAt": datetime.utcnow() - timedelta(days=60),
    }

    # Product 2: ENCLOSURE-B
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
                "description": "Apply electrostatic protective powder coat.",
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
                "description": "Verify paint mil thickness and door alignment.",
                "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                "requiredMachineType": "INSPECTION",
                "estimatedQuantityRate": 2.5,
                "unit": "pcs",
                "dependencies": ["STEP-40"],
                "requiredMaterials": [],
            },
        ],
        "createdAt": datetime.utcnow() - timedelta(days=60),
        "updatedAt": datetime.utcnow() - timedelta(days=60),
    }

    # Product 3: CHASSIS-C
    recipe_chassis_c = {
        "recipeId": "RECIPE-CHASSIS-C-V1",
        "recipeName": "CHASSIS-C Aerospace Aluminum Chassis Recipe",
        "version": 1,
        "status": "ACTIVE",
        "steps": [
            {
                "stepId": "STEP-10",
                "sequence": 1,
                "name": "Plate Waterjet/Laser Blanking",
                "description": "Cut perimeter of aluminum chassis from 3mm AL6061 sheet.",
                "requiredCapabilityIds": [cap_ids["CUTTING"]],
                "requiredMachineType": "CUTTING",
                "estimatedQuantityRate": 2.0,
                "unit": "pcs",
                "dependencies": [],
                "requiredMaterials": [
                    {"materialId": mat_ids["MAT-AL6061-SHEET"], "specificationId": spec_ids["SPEC-AL-3MM"], "quantity": 1.0, "unit": "sheets"}
                ],
            },
            {
                "stepId": "STEP-20",
                "sequence": 2,
                "name": "5-Axis Pocket & Bore Milling",
                "description": "Mill weight-reduction pockets, mounting bosses, and bearing bores.",
                "requiredCapabilityIds": [cap_ids["MILLING"]],
                "requiredMachineType": "MILLING",
                "estimatedQuantityRate": 0.8,
                "unit": "pcs",
                "dependencies": ["STEP-10"],
                "requiredMaterials": [],
            },
            {
                "stepId": "STEP-30",
                "sequence": 3,
                "name": "Mounting Tab Bending",
                "description": "Form connector mounting flanges.",
                "requiredCapabilityIds": [cap_ids["BENDING"]],
                "requiredMachineType": "BENDING",
                "estimatedQuantityRate": 1.5,
                "unit": "pcs",
                "dependencies": ["STEP-20"],
                "requiredMaterials": [],
            },
            {
                "stepId": "STEP-40",
                "sequence": 4,
                "name": "Aerospace Metrology QA",
                "description": "CMM verification of critical bore positions within 0.02mm.",
                "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                "requiredMachineType": "INSPECTION",
                "estimatedQuantityRate": 2.5,
                "unit": "pcs",
                "dependencies": ["STEP-30"],
                "requiredMaterials": [],
            },
        ],
        "createdAt": datetime.utcnow() - timedelta(days=60),
        "updatedAt": datetime.utcnow() - timedelta(days=60),
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

    prod_ids = {}
    for p in products_data:
        existing = await db.products.find_one({"productCode": p["productCode"]})
        if not existing:
            p["createdAt"] = datetime.utcnow()
            p["updatedAt"] = datetime.utcnow()
            res = await db.products.insert_one(p)
            prod_ids[p["productCode"]] = str(res.inserted_id)
        else:
            prod_ids[p["productCode"]] = str(existing["_id"])
            await db.products.update_one({"_id": existing["_id"]}, {"$set": p})

    # -------------------------------------------------------------
    # 9. SEED WORKFLOWS (EXECUTABLE DAGs DERIVED FROM RECIPES)
    # -------------------------------------------------------------
    logger.info("Seeding production workflows derived from engineering recipes...")
    workflows_data = [
        {
            "workflowCode": "WF-BRACKET-A",
            "name": "BRACKET-A Standard Manufacturing Route",
            "productId": prod_ids["BRACKET-A"],
            "recipeId": "RECIPE-BRACKET-A-V1",
            "supervisorId": sup_id,
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
                    "assignedOperatorId": op1_id,
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
                    "assignedOperatorId": op2_id,
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
                    "assignedOperatorId": op3_id,
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
                    "assignedOperatorId": op4_id,
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
            "supervisorId": sup_id,
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
                    "assignedOperatorId": op1_id,
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
                    "assignedOperatorId": op2_id,
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
                    "assignedOperatorId": op3_id,
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
                    "assignedOperatorId": op3_id,
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
                    "assignedOperatorId": op4_id,
                    "estimatedDurationSeconds": 15,
                    "dependencies": ["OP-40"],
                    "requiredMaterials": [],
                },
            ],
            "createdBy": "SYSTEM",
        },
        {
            "workflowCode": "WF-CHASSIS-C",
            "name": "CHASSIS-C High-Precision Machining Route",
            "productId": prod_ids["CHASSIS-C"],
            "recipeId": "RECIPE-CHASSIS-C-V1",
            "supervisorId": sup_id,
            "version": 1,
            "status": WorkflowStatus.ACTIVE.value,
            "operations": [
                {
                    "operationId": "OP-10",
                    "name": "Plate Waterjet/Laser Blanking",
                    "sequence": 1,
                    "requiredCapabilityIds": [cap_ids["CUTTING"]],
                    "requiredMachineType": "CUTTING",
                    "assignedMachineId": mach_ids["M-01"],
                    "assignedOperatorId": op1_id,
                    "estimatedDurationSeconds": 15,
                    "dependencies": [],
                    "requiredMaterials": [{"materialId": mat_ids["MAT-AL6061-SHEET"], "specificationId": spec_ids["SPEC-AL-3MM"], "quantity": 1.0, "unit": "sheets"}],
                },
                {
                    "operationId": "OP-20",
                    "name": "5-Axis Pocket & Bore Milling",
                    "sequence": 2,
                    "requiredCapabilityIds": [cap_ids["MILLING"]],
                    "requiredMachineType": "MILLING",
                    "assignedMachineId": mach_ids["M-04"],
                    "assignedOperatorId": op1_id,
                    "estimatedDurationSeconds": 45,
                    "dependencies": ["OP-10"],
                    "requiredMaterials": [],
                },
                {
                    "operationId": "OP-30",
                    "name": "Mounting Tab Bending",
                    "sequence": 3,
                    "requiredCapabilityIds": [cap_ids["BENDING"]],
                    "requiredMachineType": "BENDING",
                    "assignedMachineId": mach_ids["M-02"],
                    "assignedOperatorId": op2_id,
                    "estimatedDurationSeconds": 18,
                    "dependencies": ["OP-20"],
                    "requiredMaterials": [],
                },
                {
                    "operationId": "OP-40",
                    "name": "Aerospace Metrology QA",
                    "sequence": 4,
                    "requiredCapabilityIds": [cap_ids["INSPECTION"]],
                    "requiredMachineType": "INSPECTION",
                    "assignedMachineId": mach_ids["M-06"],
                    "assignedOperatorId": op4_id,
                    "estimatedDurationSeconds": 15,
                    "dependencies": ["OP-30"],
                    "requiredMaterials": [],
                },
            ],
            "createdBy": "SYSTEM",
        },
    ]

    wf_ids = {}
    for wf in workflows_data:
        existing = await db.workflows.find_one({"workflowCode": wf["workflowCode"], "version": wf["version"]})
        if not existing:
            wf["createdAt"] = datetime.utcnow()
            wf["updatedAt"] = datetime.utcnow()
            res = await db.workflows.insert_one(wf)
            wf_ids[wf["workflowCode"]] = str(res.inserted_id)
        else:
            wf_ids[wf["workflowCode"]] = str(existing["_id"])
            await db.workflows.update_one({"_id": existing["_id"]}, {"$set": wf})

    # -------------------------------------------------------------
    # 10. SEED REALISTIC WORK ORDERS ACROSS LIFECYCLE STATES
    # -------------------------------------------------------------
    logger.info("Seeding realistic Work Orders across lifecycle states...")
    now = datetime.utcnow()

    # WO-1001: COMPLETED (Target Qty: 25 BRACKET-A -> 50 SS304 sheets consumed)
    # Processing rates: M-01 (2.0 u/s -> ~13s), M-02 (1.5 u/s -> ~17s), M-03 (1.0 u/s -> ~25s), M-06 (2.5 u/s -> ~10s)
    t_wo1001_start = now - timedelta(days=2, hours=6)
    t_op10_start = t_wo1001_start
    t_op10_end = t_op10_start + timedelta(seconds=13)
    t_op20_start = t_op10_end + timedelta(minutes=5)
    t_op20_end = t_op20_start + timedelta(seconds=17)
    t_op30_start = t_op20_end + timedelta(minutes=5)
    t_op30_end = t_op30_start + timedelta(seconds=25)
    t_op40_start = t_op30_end + timedelta(minutes=5)
    t_op40_end = t_op40_start + timedelta(seconds=10)
    t_wo1001_end = t_op40_end

    wo_1001_doc = {
        "workOrderCode": "WO-1001",
        "name": "Production Batch - Structural Brackets (25 Units)",
        "productId": prod_ids["BRACKET-A"],
        "workflowId": wf_ids["WF-BRACKET-A"],
        "workflowVersion": 1,
        "supervisorId": sup_id,
        "quantity": 25.0,
        "priority": WorkOrderPriority.HIGH.value,
        "dueDate": now + timedelta(days=3),
        "status": WorkOrderStatus.COMPLETED.value,
        "startedAt": t_wo1001_start,
        "completedAt": t_wo1001_end,
        "createdBy": sup_id,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Laser Profile Cutting",
                "sequence": 1,
                "assignedMachineId": mach_ids["M-01"],
                "assignedOperatorId": op1_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_op10_start,
                "actualStart": t_op10_start,
                "actualEnd": t_op10_end,
                "durationSeconds": 13,
                "inputQuantity": 25.0,
                "processedQuantity": 25.0,
                "outputQuantity": 25.0,
                "scrapQuantity": 0.0,
                "quantityCompleted": 25.0,
                "quantityRejected": 0.0,
                "requiredMaterials": [
                    {
                        "materialId": mat_ids["MAT-SS304-SHEET"],
                        "specificationId": spec_ids["SPEC-SS304-2MM"],
                        "materialName": "Stainless Steel 304 Sheet (2mm)",
                        "specificationName": "Stainless Steel 304 2mm Sheet",
                        "unit": "sheets",
                        "quantityPerUnit": 1.0,
                        "totalRequiredQuantity": 25.0,
                        "quantityReserved": 0.0,
                        "quantityConsumed": 25.0,
                        "unitCost": 45.0,
                        "estimatedCost": 1125.0,
                        "actualCost": 1125.0,
                    }
                ],
            },
            {
                "operationId": "OP-20",
                "name": "Press Brake Flange Bending",
                "sequence": 2,
                "assignedMachineId": mach_ids["M-02"],
                "assignedOperatorId": op2_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_op20_start,
                "actualStart": t_op20_start,
                "actualEnd": t_op20_end,
                "durationSeconds": 17,
                "inputQuantity": 25.0,
                "processedQuantity": 25.0,
                "outputQuantity": 25.0,
                "scrapQuantity": 0.0,
                "quantityCompleted": 25.0,
                "quantityRejected": 0.0,
                "dependencies": ["OP-10"],
                "requiredMaterials": [
                    {
                        "materialId": mat_ids["MAT-SS304-SHEET"],
                        "specificationId": spec_ids["SPEC-SS304-2MM"],
                        "materialName": "Stainless Steel 304 Sheet (2mm)",
                        "specificationName": "Stainless Steel 304 2mm Sheet",
                        "unit": "sheets",
                        "quantityPerUnit": 1.0,
                        "totalRequiredQuantity": 25.0,
                        "quantityReserved": 0.0,
                        "quantityConsumed": 25.0,
                        "unitCost": 45.0,
                        "estimatedCost": 1125.0,
                        "actualCost": 1125.0,
                    }
                ],
            },
            {
                "operationId": "OP-30",
                "name": "Robotic TIG Gusset Welding",
                "sequence": 3,
                "assignedMachineId": mach_ids["M-03"],
                "assignedOperatorId": op3_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_op30_start,
                "actualStart": t_op30_start,
                "actualEnd": t_op30_end,
                "durationSeconds": 25,
                "inputQuantity": 25.0,
                "processedQuantity": 25.0,
                "outputQuantity": 25.0,
                "scrapQuantity": 0.0,
                "quantityCompleted": 25.0,
                "quantityRejected": 0.0,
                "dependencies": ["OP-20"],
                "requiredMaterials": [],
            },
            {
                "operationId": "OP-40",
                "name": "Final Metrology & QA Inspection",
                "sequence": 4,
                "assignedMachineId": mach_ids["M-06"],
                "assignedOperatorId": op4_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_op40_start,
                "actualStart": t_op40_start,
                "actualEnd": t_op40_end,
                "durationSeconds": 10,
                "inputQuantity": 25.0,
                "processedQuantity": 25.0,
                "outputQuantity": 25.0,
                "scrapQuantity": 0.0,
                "quantityCompleted": 25.0,
                "quantityRejected": 0.0,
                "dependencies": ["OP-30"],
                "requiredMaterials": [],
            },
        ],
        "createdAt": t_wo1001_start - timedelta(hours=2),
        "updatedAt": t_wo1001_end,
    }

    # Insert WO-1001 and create genealogy records
    wo1001_res = await db.work_orders.insert_one(wo_1001_doc)
    wo1001_id = str(wo1001_res.inserted_id)

    # Material Reservations for WO-1001 (CONSUMED)
    res_1001_op10 = {
        "workOrderId": wo1001_id,
        "workOrderCode": "WO-1001",
        "operationId": "OP-10",
        "materialId": mat_ids["MAT-SS304-SHEET"],
        "specificationId": spec_ids["SPEC-SS304-2MM"],
        "lotId": lot_ids["LOT-SS304-001"],
        "lotNumber": "LOT-SS304-001",
        "quantityReserved": 25.0,
        "quantityConsumed": 25.0,
        "unitCost": 45.0,
        "status": ReservationStatus.CONSUMED.value,
        "createdAt": t_wo1001_start,
        "consumedAt": t_wo1001_start + timedelta(minutes=45),
    }
    res_1001_op20 = {
        "workOrderId": wo1001_id,
        "workOrderCode": "WO-1001",
        "operationId": "OP-20",
        "materialId": mat_ids["MAT-SS304-SHEET"],
        "specificationId": spec_ids["SPEC-SS304-2MM"],
        "lotId": lot_ids["LOT-SS304-001"],
        "lotNumber": "LOT-SS304-001",
        "quantityReserved": 25.0,
        "quantityConsumed": 25.0,
        "unitCost": 45.0,
        "status": ReservationStatus.CONSUMED.value,
        "createdAt": t_wo1001_start,
        "consumedAt": t_wo1001_start + timedelta(minutes=95),
    }
    await db.material_reservations.insert_one(res_1001_op10)
    await db.material_reservations.insert_one(res_1001_op20)

    # Transactions for WO-1001
    await db.material_transactions.insert_one({
        "transactionId": "TX-WO1001-OP10-CONS",
        "transactionType": MaterialTransactionType.CONSUMPTION.value,
        "materialId": mat_ids["MAT-SS304-SHEET"],
        "specificationId": spec_ids["SPEC-SS304-2MM"],
        "lotId": lot_ids["LOT-SS304-001"],
        "lotNumber": "LOT-SS304-001",
        "workOrderId": wo1001_id,
        "workOrderCode": "WO-1001",
        "operationId": "OP-10",
        "quantity": 25.0,
        "previousBalance": 550.0,
        "resultingBalance": 525.0,
        "actorId": op1_id,
        "actorType": "OPERATOR",
        "timestamp": t_wo1001_start + timedelta(minutes=45),
        "notes": "Full lot consumption for WO-1001 Laser Profile Cutting.",
    })
    await db.material_transactions.insert_one({
        "transactionId": "TX-WO1001-OP20-CONS",
        "transactionType": MaterialTransactionType.CONSUMPTION.value,
        "materialId": mat_ids["MAT-SS304-SHEET"],
        "specificationId": spec_ids["SPEC-SS304-2MM"],
        "lotId": lot_ids["LOT-SS304-001"],
        "lotNumber": "LOT-SS304-001",
        "workOrderId": wo1001_id,
        "workOrderCode": "WO-1001",
        "operationId": "OP-20",
        "quantity": 25.0,
        "previousBalance": 525.0,
        "resultingBalance": 500.0,
        "actorId": op2_id,
        "actorType": "OPERATOR",
        "timestamp": t_wo1001_start + timedelta(minutes=95),
        "notes": "Full lot consumption for WO-1001 Press Brake Flange Bending.",
    })

    # WO-1002: IN_PROGRESS (15 ENCLOSURE-B, executing OP-20 BENDING on M-02)
    t_wo1002_start = now - timedelta(hours=1, minutes=30)
    wo_1002_doc = {
        "workOrderCode": "WO-1002",
        "name": "Production Batch - Industrial Enclosures (15 Units)",
        "productId": prod_ids["ENCLOSURE-B"],
        "workflowId": wf_ids["WF-ENCLOSURE-B"],
        "workflowVersion": 1,
        "supervisorId": sup_id,
        "quantity": 15.0,
        "priority": WorkOrderPriority.NORMAL.value,
        "dueDate": now + timedelta(days=2),
        "status": WorkOrderStatus.IN_PROGRESS.value,
        "startedAt": t_wo1002_start,
        "createdBy": sup_id,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Mild Steel Blank Cutting",
                "sequence": 1,
                "assignedMachineId": mach_ids["M-01"],
                "assignedOperatorId": op1_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_wo1002_start,
                "actualStart": t_wo1002_start,
                "actualEnd": t_wo1002_start + timedelta(seconds=8),
                "durationSeconds": 8,
                "inputQuantity": 15.0,
                "processedQuantity": 15.0,
                "outputQuantity": 15.0,
                "quantityCompleted": 15.0,
                "quantityRejected": 0.0,
            },
            {
                "operationId": "OP-20",
                "name": "Enclosure Box Bending",
                "sequence": 2,
                "assignedMachineId": mach_ids["M-02"],
                "assignedOperatorId": op2_id,
                "status": WorkOrderOperationStatus.IN_PROGRESS.value,
                "startedAt": now - timedelta(minutes=30),
                "actualStart": now - timedelta(minutes=30),
                "inputQuantity": 15.0,
                "processedQuantity": 8.0,
                "outputQuantity": 8.0,
                "quantityCompleted": 8.0,
                "quantityRejected": 0.0,
                "dependencies": ["OP-10"],
            },
            {
                "operationId": "OP-30",
                "name": "Corner Seam Welding",
                "sequence": 3,
                "assignedMachineId": mach_ids["M-03"],
                "assignedOperatorId": op3_id,
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 15.0,
                "dependencies": ["OP-20"],
            },
            {
                "operationId": "OP-40",
                "name": "Black Powder Coating",
                "sequence": 4,
                "assignedMachineId": mach_ids["M-05"],
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 15.0,
                "dependencies": ["OP-30"],
            },
            {
                "operationId": "OP-50",
                "name": "Coating & Seal Inspection",
                "sequence": 5,
                "assignedMachineId": mach_ids["M-06"],
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 15.0,
                "dependencies": ["OP-40"],
            },
        ],
        "createdAt": t_wo1002_start - timedelta(hours=1),
        "updatedAt": now,
    }
    wo1002_res = await db.work_orders.insert_one(wo_1002_doc)
    wo1002_id = str(wo1002_res.inserted_id)

    # Set M-02 to OCCUPIED on WO-1002
    await db.machines.update_one(
        {"_id": ObjectId(mach_ids["M-02"])},
        {"$set": {
            "status": MachineStatus.OCCUPIED.value,
            "currentWorkOrderId": wo1002_id,
            "currentWorkOrderCode": "WO-1002",
            "currentOperationId": "OP-20",
            "currentOperatorId": op2_id,
        }}
    )

    # WO-1003: PLANNED (20 CHASSIS-C, AL6061 reserved)
    wo_1003_doc = {
        "workOrderCode": "WO-1003",
        "name": "Production Batch - Aerospace Chassis (20 Units)",
        "productId": prod_ids["CHASSIS-C"],
        "workflowId": wf_ids["WF-CHASSIS-C"],
        "workflowVersion": 1,
        "supervisorId": sup_id,
        "quantity": 20.0,
        "priority": WorkOrderPriority.HIGH.value,
        "dueDate": now + timedelta(days=5),
        "status": WorkOrderStatus.PLANNED.value,
        "createdBy": sup_id,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Plate Waterjet/Laser Blanking",
                "sequence": 1,
                "assignedMachineId": mach_ids["M-01"],
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 20.0,
                "requiredMaterials": [
                    {
                        "materialId": mat_ids["MAT-AL6061-SHEET"],
                        "specificationId": spec_ids["SPEC-AL-3MM"],
                        "materialName": "Aluminum 6061-T6 Plate (3mm)",
                        "unit": "sheets",
                        "quantityPerUnit": 1.0,
                        "totalRequiredQuantity": 20.0,
                        "quantityReserved": 20.0,
                        "quantityConsumed": 0.0,
                    }
                ],
            },
            {
                "operationId": "OP-20",
                "name": "5-Axis Pocket & Bore Milling",
                "sequence": 2,
                "assignedMachineId": mach_ids["M-04"],
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 20.0,
                "dependencies": ["OP-10"],
            },
            {
                "operationId": "OP-30",
                "name": "Mounting Tab Bending",
                "sequence": 3,
                "assignedMachineId": mach_ids["M-02"],
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 20.0,
                "dependencies": ["OP-20"],
            },
            {
                "operationId": "OP-40",
                "name": "Aerospace Metrology QA",
                "sequence": 4,
                "assignedMachineId": mach_ids["M-06"],
                "status": WorkOrderOperationStatus.PENDING.value,
                "inputQuantity": 20.0,
                "dependencies": ["OP-30"],
            },
        ],
        "createdAt": now - timedelta(hours=4),
        "updatedAt": now,
    }
    wo1003_res = await db.work_orders.insert_one(wo_1003_doc)
    wo1003_id = str(wo1003_res.inserted_id)

    # Material Reservation for WO-1003 (RESERVED)
    await db.material_reservations.insert_one({
        "workOrderId": wo1003_id,
        "workOrderCode": "WO-1003",
        "operationId": "OP-10",
        "materialId": mat_ids["MAT-AL6061-SHEET"],
        "specificationId": spec_ids["SPEC-AL-3MM"],
        "lotId": lot_ids["LOT-AL-001"],
        "lotNumber": "LOT-AL-001",
        "quantityReserved": 20.0,
        "quantityConsumed": 0.0,
        "unitCost": 60.0,
        "status": ReservationStatus.RESERVED.value,
        "createdAt": now - timedelta(hours=4),
    })

    # WO-1004: WAITING_FOR_MATERIAL (10 BRACKET-A)
    wo_1004_doc = {
        "workOrderCode": "WO-1004",
        "name": "Rush Batch - Structural Brackets (10 Units)",
        "productId": prod_ids["BRACKET-A"],
        "workflowId": wf_ids["WF-BRACKET-A"],
        "workflowVersion": 1,
        "supervisorId": sup_id,
        "quantity": 10.0,
        "priority": WorkOrderPriority.URGENT.value,
        "dueDate": now + timedelta(days=1),
        "status": WorkOrderStatus.WAITING_FOR_MATERIAL.value,
        "createdBy": sup_id,
        "operations": [
            {
                "operationId": "OP-10",
                "name": "Laser Profile Cutting",
                "sequence": 1,
                "assignedMachineId": mach_ids["M-01"],
                "status": WorkOrderOperationStatus.WAITING_FOR_MATERIAL.value,
                "waitingReason": "Awaiting lot inspection clearance on SS304 alloy lot.",
                "inputQuantity": 10.0,
            }
        ],
        "createdAt": now - timedelta(hours=1),
        "updatedAt": now,
    }
    await db.work_orders.insert_one(wo_1004_doc)

    # -------------------------------------------------------------
    # 11. SEED HISTORICAL EXECUTION TELEMETRY FOR MACHINE HEALTH
    # -------------------------------------------------------------
    logger.info("Seeding historical completed operations and cycle telemetry...")

    # A. M-01 (Healthy Control): 28 operations over 14 days, stable 5.0s +- 0.2s duration
    for i in range(28):
        t_start = now - timedelta(days=14 - (i * 0.5), hours=2)
        dur = round(4.9 + (i % 3) * 0.1, 2)
        t_end = t_start + timedelta(seconds=dur)
        await db.work_orders.insert_one({
            "workOrderCode": f"HIST-WO-M01-{i+1:02d}",
            "status": WorkOrderStatus.COMPLETED.value,
            "productId": prod_ids["BRACKET-A"],
            "workflowId": wf_ids["WF-BRACKET-A"],
            "quantity": 10.0,
            "startedAt": t_start,
            "completedAt": t_end,
            "operations": [{
                "operationId": "OP-10",
                "name": "Laser Profile Cutting",
                "sequence": 1,
                "assignedMachineId": mach_ids["M-01"],
                "assignedOperatorId": op1_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": dur,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0,
                "outputQuantity": 10.0,
                "quantityCompleted": 10.0,
                "quantityRejected": 0.0,
            }],
            "createdAt": t_start - timedelta(minutes=10),
            "updatedAt": t_end,
        })

    # B. M-02 (Medium Risk): 18 operations over 10 days, slight variance 6.0s to 8.2s, 1 past failure
    for i in range(18):
        t_start = now - timedelta(days=10 - (i * 0.5), hours=3)
        dur = round(6.0 + (i * 0.12), 2)
        t_end = t_start + timedelta(seconds=dur)
        await db.work_orders.insert_one({
            "workOrderCode": f"HIST-WO-M02-{i+1:02d}",
            "status": WorkOrderStatus.COMPLETED.value,
            "productId": prod_ids["BRACKET-A"],
            "workflowId": wf_ids["WF-BRACKET-A"],
            "quantity": 10.0,
            "startedAt": t_start,
            "completedAt": t_end,
            "operations": [{
                "operationId": "OP-20",
                "name": "Press Brake Flange Bending",
                "sequence": 2,
                "assignedMachineId": mach_ids["M-02"],
                "assignedOperatorId": op2_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": dur,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0,
                "outputQuantity": 10.0,
                "quantityCompleted": 10.0,
                "quantityRejected": 0.0,
            }],
            "createdAt": t_start - timedelta(minutes=10),
            "updatedAt": t_end,
        })

    # M-02 1 historical failure incident (6 days ago, 10-minute minor recalibration)
    t_inc_m02 = now - timedelta(days=6)
    await db.incidents.insert_one({
        "incidentCode": "INC-HIST-M02-1",
        "type": IncidentType.MACHINE_FAILURE.value,
        "severity": IncidentSeverity.LOW.value,
        "status": IncidentStatus.RESOLVED.value,
        "title": "M-02 Hydraulic Backgauge Sensor Drift",
        "description": "Minor optical sensor alignment calibration required on press brake backgauge.",
        "machineId": mach_ids["M-02"],
        "machineCode": "M-02",
        "machineType": "BENDING",
        "operatorId": op2_id,
        "operatorName": "Beatriz Vance",
        "reportedAt": t_inc_m02,
        "detectedAt": t_inc_m02,
        "resolvedAt": t_inc_m02 + timedelta(minutes=10),
        "reportedBy": op2_id,
        "resolvedBy": sup_id,
        "resolution": "Cleaned optical sensor lens and zero-referenced backgauge.",
        "createdAt": t_inc_m02,
        "updatedAt": t_inc_m02 + timedelta(minutes=10),
    })

    # C. M-03 (High Risk Demo): 26 operations, progressive degradation (10.0s -> 18.8s), 2 failures, 1 alert
    m03_durations = [
        10.0, 10.1, 10.0, 10.2, 10.3, 10.5, 10.7, 11.0, 11.4, 11.9,
        12.5, 13.0, 13.6, 14.2, 14.8, 15.3, 15.9, 16.5, 17.0, 17.5,
        18.0, 18.2, 18.4, 18.5, 18.6, 18.8
    ]
    for i, dur in enumerate(m03_durations):
        t_start = now - timedelta(days=7 - (i * 0.25), hours=1)
        t_end = t_start + timedelta(seconds=dur)
        hist_wo_code = f"HIST-WO-M03-{i+1:02d}"
        
        hist_wo_res = await db.work_orders.insert_one({
            "workOrderCode": hist_wo_code,
            "status": WorkOrderStatus.COMPLETED.value,
            "productId": prod_ids["BRACKET-A"],
            "workflowId": wf_ids["WF-BRACKET-A"],
            "quantity": 10.0,
            "startedAt": t_start,
            "completedAt": t_end,
            "operations": [{
                "operationId": "OP-30",
                "name": "Robotic TIG Gusset Welding",
                "sequence": 3,
                "assignedMachineId": mach_ids["M-03"],
                "assignedOperatorId": op3_id,
                "status": WorkOrderOperationStatus.COMPLETED.value,
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": dur,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0,
                "outputQuantity": 10.0,
                "quantityCompleted": 10.0,
                "quantityRejected": 0.0,
            }],
            "createdAt": t_start - timedelta(minutes=10),
            "updatedAt": t_end,
        })
        hist_wo_id = str(hist_wo_res.inserted_id)

        # For the last 4 degrading runs, link to LOT-SS304-002 for genuine Phase 6 material correlation
        if i >= 22:
            await db.material_reservations.insert_one({
                "workOrderId": hist_wo_id,
                "workOrderCode": hist_wo_code,
                "operationId": "OP-30",
                "materialId": mat_ids["MAT-SS304-SHEET"],
                "specificationId": spec_ids["SPEC-SS304-2MM"],
                "lotId": lot_ids["LOT-SS304-002"],
                "lotNumber": "LOT-SS304-002",
                "quantityReserved": 1.0,
                "quantityConsumed": 1.0,
                "unitCost": 46.0,
                "status": ReservationStatus.CONSUMED.value,
                "createdAt": t_start,
                "consumedAt": t_end,
            })

    # M-03 Historical Failure 1 (4 days ago, 50 min downtime)
    t_inc_m03_1 = now - timedelta(days=4, hours=3)
    await db.incidents.insert_one({
        "incidentCode": "INC-HIST-M03-1",
        "type": IncidentType.MACHINE_FAILURE.value,
        "severity": IncidentSeverity.HIGH.value,
        "status": IncidentStatus.RESOLVED.value,
        "title": "M-03 Shielding Gas Flow Disruption",
        "description": "Argon gas solenoid valve stuck in closed position during welding cycle.",
        "machineId": mach_ids["M-03"],
        "machineCode": "M-03",
        "machineType": "WELDING",
        "operatorId": op3_id,
        "operatorName": "Carlos Chen",
        "reportedAt": t_inc_m03_1,
        "detectedAt": t_inc_m03_1,
        "resolvedAt": t_inc_m03_1 + timedelta(minutes=50),
        "reportedBy": op3_id,
        "resolvedBy": sup_id,
        "resolution": "Replaced gas solenoid valve and purge-tested gas lines.",
        "createdAt": t_inc_m03_1,
        "updatedAt": t_inc_m03_1 + timedelta(minutes=50),
    })

    # M-03 Historical Failure 2 (1 day ago, 35 min downtime, correlated with LOT-SS304-002)
    t_inc_m03_2 = now - timedelta(days=1, hours=4)
    await db.incidents.insert_one({
        "incidentCode": "INC-HIST-M03-2",
        "type": IncidentType.MACHINE_FAILURE.value,
        "severity": IncidentSeverity.HIGH.value,
        "status": IncidentStatus.RESOLVED.value,
        "title": "M-03 High Thermal Trip / Arc Instability",
        "description": "High-frequency arc ignition failed repeatedly while welding bracket subassembly from Lot LOT-SS304-002.",
        "machineId": mach_ids["M-03"],
        "machineCode": "M-03",
        "machineType": "WELDING",
        "workOrderId": hist_wo_id,
        "workOrderCode": hist_wo_code,
        "operationId": "OP-30",
        "operatorId": op3_id,
        "operatorName": "Carlos Chen",
        "reportedAt": t_inc_m03_2,
        "detectedAt": t_inc_m03_2,
        "resolvedAt": t_inc_m03_2 + timedelta(minutes=35),
        "reportedBy": op3_id,
        "resolvedBy": sup_id,
        "resolution": "Dressed tungsten electrode tip and cleaned collet body.",
        "createdAt": t_inc_m03_2,
        "updatedAt": t_inc_m03_2 + timedelta(minutes=35),
    })

    # M-03 Active Operator Alert (3 hours ago, PENDING_REVIEW)
    t_warn_m03 = now - timedelta(hours=3)
    await db.incidents.insert_one({
        "incidentCode": "INC-DEMO-M03-WARN",
        "type": IncidentType.MACHINE_FAILURE.value,
        "severity": IncidentSeverity.MEDIUM.value,
        "status": IncidentStatus.PENDING_REVIEW.value,
        "title": "Operator Alert on M-03: Excessive torch vibration and uneven bead formation",
        "description": "Operator Carlos Chen observed erratic arc wander and cycle duration extending past 15 seconds.",
        "machineId": mach_ids["M-03"],
        "machineCode": "M-03",
        "machineType": "WELDING",
        "operatorId": op3_id,
        "operatorName": "Carlos Chen",
        "reportedAt": t_warn_m03,
        "detectedAt": t_warn_m03,
        "reportedBy": op3_id,
        "createdAt": t_warn_m03,
        "updatedAt": t_warn_m03,
    })

    # Other machines (M-04, M-05, M-06, M-07): 12 completed operations each
    for m_code, dur_nom, m_type, cap_key in [
        ("M-04", 12.0, "MILLING", "MILLING"),
        ("M-05", 8.0, "PAINTING", "PAINTING"),
        ("M-06", 4.0, "INSPECTION", "INSPECTION"),
        ("M-07", 10.0, "MULTI_PURPOSE", "CUTTING"),
    ]:
        for i in range(12):
            t_start = now - timedelta(days=6 - (i * 0.5), hours=2)
            t_end = t_start + timedelta(seconds=dur_nom)
            await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-{m_code}-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_ids["BRACKET-A"],
                "workflowId": wf_ids["WF-BRACKET-A"],
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-10",
                    "name": f"{m_type} Operation",
                    "sequence": 1,
                    "assignedMachineId": mach_ids[m_code],
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": dur_nom,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

    # -------------------------------------------------------------
    # 12. GENERATE REAL APPEND-ONLY MACHINE HEALTH ASSESSMENTS
    # -------------------------------------------------------------
    logger.info("Computing real deterministic machine health scores from telemetry...")
    m01_health = await MachineHealthService.get_machine_health_metrics(mach_ids["M-01"])
    await MachineHealthService.save_health_assessment(m01_health)
    logger.info(f"M-01 Evaluated Health: Score={m01_health.healthScore}/100, Risk={m01_health.riskLevel.value}")

    m02_health = await MachineHealthService.get_machine_health_metrics(mach_ids["M-02"])
    await MachineHealthService.save_health_assessment(m02_health)
    logger.info(f"M-02 Evaluated Health: Score={m02_health.healthScore}/100, Risk={m02_health.riskLevel.value}")

    m03_health = await MachineHealthService.get_machine_health_metrics(mach_ids["M-03"])
    await MachineHealthService.save_health_assessment(m03_health)
    logger.info(f"M-03 Evaluated Health: Score={m03_health.healthScore}/100, Risk={m03_health.riskLevel.value}, Cycle Degradation=+{m03_health.metrics.cycleTimeDeviationPercent}%")

    # -------------------------------------------------------------
    # 13. FINAL DATABASE CONSISTENCY & USER PRESERVATION CHECK
    # -------------------------------------------------------------
    logger.info("Running complete database integrity and user preservation check...")
    
    # Check 1: User preservation check
    final_users_cursor = db.users.find({})
    final_users_list = await final_users_cursor.to_list(200)
    final_user_ids = {str(u["_id"]): u for u in final_users_list}

    for uid, original in pre_users_snapshot.items():
        if uid not in final_user_ids:
            raise AssertionError(f"FATAL INTEGRITY FAILURE: Pre-existing user ID {uid} was deleted during reset!")
        current = final_user_ids[uid]
        if current.get("employeeId") != original["employeeId"]:
            raise AssertionError(f"FATAL INTEGRITY FAILURE: User {uid} employeeId changed from {original['employeeId']} to {current.get('employeeId')}!")

    # Check 2: Stock balance consistency
    async for lot_doc in db.inventory_lots.find({}):
        on_hand = lot_doc.get("quantityOnHand", 0.0)
        reserved = lot_doc.get("quantityReserved", 0.0)
        if on_hand < 0 or reserved < 0:
            raise AssertionError(f"Negative stock detected on lot {lot_doc.get('lotNumber')}")
        if reserved > on_hand:
            raise AssertionError(f"Reserved quantity exceeds on-hand stock on lot {lot_doc.get('lotNumber')}")

    # Check 3: Material reference integrity
    async for res_doc in db.material_reservations.find({}):
        m_id = res_doc.get("materialId")
        if not await db.materials.find_one({"_id": ObjectId(m_id)}):
            raise AssertionError(f"Orphan material reference in reservation {res_doc.get('_id')}")

    logger.info("All integrity and consistency checks passed successfully (100% PASS).")
    await db_manager.disconnect()
    logger.info("Database seeding completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adaptive MES Database Seeder")
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Perform controlled reset of operational/demo collections before seeding (users are preserved)."
    )
    args = parser.parse_args()
    asyncio.run(run_seed(reset_demo=args.reset_demo))
