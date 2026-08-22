import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from bson import ObjectId

from app.core.database import db_manager, get_db
from app.schemas.workflow import WorkflowStatus
from app.schemas.work_order import WorkOrderStatus, WorkOrderOperationStatus
from app.schemas.machine import MachineStatus
from app.schemas.incident import IncidentType, IncidentSeverity, IncidentStatus
from app.schemas.material_reservation import ReservationStatus
from app.services.machine_health_service import MachineHealthService
from app.ai.predictive_maintenance_planner import AIPredictiveMaintenancePlanner

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def seed_low_health_machines():
    """
    Seeds realistic operational degradation, failure incidents, operator warnings,
    and material correlations for M-03 (CRITICAL), M-02 (HIGH), and M-05 (MEDIUM),
    while preserving healthy baselines on other machines.
    """
    logger.info("Connecting to database...")
    await db_manager.connect()
    db = get_db()

    now = datetime.utcnow()

    # 1. Fetch existing machines, users, products, workflows, and materials
    machines_cursor = db.machines.find({})
    machines = await machines_cursor.to_list(100)
    mach_map = {m["machineCode"]: m for m in machines}

    if not machines:
        logger.error("No machines found in database! Please run main seeder first.")
        return

    users = await db.users.find({}).to_list(100)
    sup_user = next((u for u in users if u.get("role") in ["SUPERVISOR", "ADMIN"]), users[0] if users else None)
    op_user = next((u for u in users if u.get("role") == "OPERATOR"), users[0] if users else None)
    sup_id = str(sup_user["_id"]) if sup_user else "SYSTEM"
    op_id = str(op_user["_id"]) if op_user else "SYSTEM"
    op_name = op_user.get("name", "Operator") if op_user else "Operator"

    products = await db.products.find({}).to_list(100)
    prod = products[0] if products else None
    prod_id = str(prod["_id"]) if prod else None

    workflows = await db.workflows.find({}).to_list(100)
    wf = workflows[0] if workflows else None
    wf_id = str(wf["_id"]) if wf else None

    materials = await db.materials.find({}).to_list(100)
    mat_ss = next((m for m in materials if "SS" in m.get("materialCode", "") or "Steel" in m.get("name", "")), materials[0] if materials else None)
    mat_id = str(mat_ss["_id"]) if mat_ss else None

    lots = await db.inventory_lots.find({}).to_list(100)
    lot_bad = next((l for l in lots if "002" in l.get("lotNumber", "")), lots[0] if lots else None)
    lot_id = str(lot_bad["_id"]) if lot_bad else None
    lot_num = lot_bad.get("lotNumber", "LOT-SS304-002") if lot_bad else "LOT-SS304-002"

    specs = await db.material_specifications.find({}).to_list(100)
    spec_id = str(specs[0]["_id"]) if specs else None

    logger.info("Clearing previous maintenance audit events and resetting lastMaintenanceAt on degraded machines...")
    # Clean prior maintenance audit anchors on M-03, M-02, M-05 so true degradation is evaluated
    for code in ["M-03", "M-02", "M-05"]:
        if code in mach_map:
            m_id_str = str(mach_map[code]["_id"])
            await db.audit_events.delete_many({
                "entityId": m_id_str,
                "action": {"$in": ["MACHINE_MAINTENANCE_SCHEDULED", "MACHINE_RECOVERED", "PREDICTIVE_MAINTENANCE_APPROVED"]}
            })
            await db.machines.update_one(
                {"_id": mach_map[code]["_id"]},
                {"$set": {
                    "lastMaintenanceAt": now - timedelta(days=60),
                    "status": MachineStatus.IDLE.value
                }}
            )

    # -------------------------------------------------------------
    # SEED M-03: CRITICAL HEALTH PROFILE (~35/100)
    # -------------------------------------------------------------
    if "M-03" in mach_map:
        m03 = mach_map["M-03"]
        m03_id = str(m03["_id"])
        logger.info("Seeding CRITICAL degradation profile for M-03 (Robotic TIG Welding Station)...")

        # Delete existing demo history for M-03 to have precise metrics
        await db.work_orders.delete_many({"operations.assignedMachineId": m03_id})
        await db.incidents.delete_many({"machineId": m03_id})

        # 14 older nominal operations (10.0s baseline)
        for i in range(14):
            t_start = now - timedelta(days=15 - (i * 0.8), hours=2)
            t_end = t_start + timedelta(seconds=10.0)
            await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-M03-NOM-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_id,
                "workflowId": wf_id,
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-30",
                    "name": "Robotic TIG Welding",
                    "sequence": 1,
                    "assignedMachineId": m03_id,
                    "assignedMachineCode": "M-03",
                    "assignedOperatorId": op_id,
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": 10.0,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

        # 14 recent degraded operations (16.5s duration -> +65% elongation)
        for i in range(14):
            t_start = now - timedelta(days=4 - (i * 0.25), hours=1)
            t_end = t_start + timedelta(seconds=16.5)
            wo_res = await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-M03-DEG-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_id,
                "workflowId": wf_id,
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-30",
                    "name": "Robotic TIG Welding",
                    "sequence": 1,
                    "assignedMachineId": m03_id,
                    "assignedMachineCode": "M-03",
                    "assignedOperatorId": op_id,
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": 16.5,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

            # Link recent degrading runs to problematic material lot
            if mat_id and lot_id:
                await db.material_reservations.insert_one({
                    "workOrderId": str(wo_res.inserted_id),
                    "workOrderCode": f"HIST-WO-M03-DEG-{i+1:02d}",
                    "operationId": "OP-30",
                    "materialId": mat_id,
                    "specificationId": spec_id,
                    "lotId": lot_id,
                    "lotNumber": lot_num,
                    "quantityReserved": 1.0,
                    "quantityConsumed": 1.0,
                    "unitCost": 46.0,
                    "status": ReservationStatus.CONSUMED.value,
                    "createdAt": t_start,
                    "consumedAt": t_end,
                })

        # 2 Failure Incidents in last 7 days (1 in last 24h)
        t_fail_1 = now - timedelta(days=3, hours=4)
        await db.incidents.insert_one({
            "incidentCode": "INC-M03-FAIL-01",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.HIGH.value,
            "status": IncidentStatus.RESOLVED.value,
            "title": "M-03 Solenoid Gas Valve Overheat Trip",
            "description": "Argon gas solenoid valve jammed shut due to thermal overload during high-amperage welding.",
            "machineId": m03_id,
            "machineCode": "M-03",
            "machineType": "WELDING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_fail_1,
            "detectedAt": t_fail_1,
            "resolvedAt": t_fail_1 + timedelta(minutes=65),
            "reportedBy": op_id,
            "resolvedBy": sup_id,
            "resolution": "Cleared valve housing and cooled torch assembly.",
            "createdAt": t_fail_1,
            "updatedAt": t_fail_1 + timedelta(minutes=65),
        })

        t_fail_2 = now - timedelta(hours=14)
        await db.incidents.insert_one({
            "incidentCode": "INC-M03-FAIL-02",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.CRITICAL.value,
            "status": IncidentStatus.RESOLVED.value,
            "title": "M-03 High Frequency Arc Ignition Breakdown",
            "description": "High-frequency ignition circuit failure resulting in repeated arc blowouts on Lot " + lot_num,
            "machineId": m03_id,
            "machineCode": "M-03",
            "machineType": "WELDING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_fail_2,
            "detectedAt": t_fail_2,
            "resolvedAt": t_fail_2 + timedelta(minutes=75),
            "reportedBy": op_id,
            "resolvedBy": sup_id,
            "resolution": "Re-grounded torch return cable and dressed tungsten electrode.",
            "createdAt": t_fail_2,
            "updatedAt": t_fail_2 + timedelta(minutes=75),
        })

        # 2 Unresolved Operator Warnings (PENDING_REVIEW)
        t_warn_1 = now - timedelta(hours=5)
        await db.incidents.insert_one({
            "incidentCode": "INC-M03-WARN-01",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.HIGH.value,
            "status": IncidentStatus.PENDING_REVIEW.value,
            "title": "Operator Report on M-03: Severe torch head vibration and weld bead porosity",
            "description": "Operator noticed erratic mechanical oscillation in servo axis 2 and excessive thermal discoloration.",
            "machineId": m03_id,
            "machineCode": "M-03",
            "machineType": "WELDING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_warn_1,
            "detectedAt": t_warn_1,
            "reportedBy": op_id,
            "createdAt": t_warn_1,
            "updatedAt": t_warn_1,
        })

        t_warn_2 = now - timedelta(hours=2)
        await db.incidents.insert_one({
            "incidentCode": "INC-M03-WARN-02",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.MEDIUM.value,
            "status": IncidentStatus.PENDING_REVIEW.value,
            "title": "Operator Report on M-03: Secondary arc stutter and cycle time exceeding 17 seconds",
            "description": "Welding cycle duration continues to drift upward. Operator requesting urgent maintenance review.",
            "machineId": m03_id,
            "machineCode": "M-03",
            "machineType": "WELDING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_warn_2,
            "detectedAt": t_warn_2,
            "reportedBy": op_id,
            "createdAt": t_warn_2,
            "updatedAt": t_warn_2,
        })

    # -------------------------------------------------------------
    # SEED M-02: HIGH RISK HEALTH PROFILE (~58/100)
    # -------------------------------------------------------------
    if "M-02" in mach_map:
        m02 = mach_map["M-02"]
        m02_id = str(m02["_id"])
        logger.info("Seeding HIGH RISK degradation profile for M-02 (CNC Hydraulic Press Brake)...")

        await db.work_orders.delete_many({"operations.assignedMachineId": m02_id})
        await db.incidents.delete_many({"machineId": m02_id})

        # 12 nominal ops (8.0s baseline)
        for i in range(12):
            t_start = now - timedelta(days=14 - (i * 0.9), hours=3)
            t_end = t_start + timedelta(seconds=8.0)
            await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-M02-NOM-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_id,
                "workflowId": wf_id,
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-20",
                    "name": "Hydraulic Bending",
                    "sequence": 1,
                    "assignedMachineId": m02_id,
                    "assignedMachineCode": "M-02",
                    "assignedOperatorId": op_id,
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": 8.0,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

        # 12 degraded ops (10.6s duration -> +32.5% elongation)
        for i in range(12):
            t_start = now - timedelta(days=4 - (i * 0.3), hours=2)
            t_end = t_start + timedelta(seconds=10.6)
            await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-M02-DEG-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_id,
                "workflowId": wf_id,
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-20",
                    "name": "Hydraulic Bending",
                    "sequence": 1,
                    "assignedMachineId": m02_id,
                    "assignedMachineCode": "M-02",
                    "assignedOperatorId": op_id,
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": 10.6,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

        # 1 Failure incident in 7d (45 min downtime)
        t_fail_m02 = now - timedelta(days=2, hours=6)
        await db.incidents.insert_one({
            "incidentCode": "INC-M02-FAIL-01",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.HIGH.value,
            "status": IncidentStatus.RESOLVED.value,
            "title": "M-02 Hydraulic Proportional Valve Pressure Loss",
            "description": "Hydraulic ram stalled during 90-degree channel bend due to internal seal leakage.",
            "machineId": m02_id,
            "machineCode": "M-02",
            "machineType": "BENDING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_fail_m02,
            "detectedAt": t_fail_m02,
            "resolvedAt": t_fail_m02 + timedelta(minutes=45),
            "reportedBy": op_id,
            "resolvedBy": sup_id,
            "resolution": "Bleed hydraulic lines and tightened proportional valve manifold.",
            "createdAt": t_fail_m02,
            "updatedAt": t_fail_m02 + timedelta(minutes=45),
        })

        # 1 Unresolved Operator Warning
        t_warn_m02 = now - timedelta(hours=6)
        await db.incidents.insert_one({
            "incidentCode": "INC-M02-WARN-01",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.MEDIUM.value,
            "status": IncidentStatus.PENDING_REVIEW.value,
            "title": "Operator Report on M-02: Ram descent jitter and slow return stroke",
            "description": "Tonnage gauge shows pressure fluctuations during final 15mm of stroke.",
            "machineId": m02_id,
            "machineCode": "M-02",
            "machineType": "BENDING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_warn_m02,
            "detectedAt": t_warn_m02,
            "reportedBy": op_id,
            "createdAt": t_warn_m02,
            "updatedAt": t_warn_m02,
        })

    # -------------------------------------------------------------
    # SEED M-05: MEDIUM RISK HEALTH PROFILE (~75/100)
    # -------------------------------------------------------------
    if "M-05" in mach_map:
        m05 = mach_map["M-05"]
        m05_id = str(m05["_id"])
        logger.info("Seeding MEDIUM RISK degradation profile for M-05 (Automated Powder Coating Line)...")

        await db.work_orders.delete_many({"operations.assignedMachineId": m05_id})
        await db.incidents.delete_many({"machineId": m05_id})

        # 12 nominal ops (8.0s baseline)
        for i in range(12):
            t_start = now - timedelta(days=12 - (i * 0.8), hours=2)
            t_end = t_start + timedelta(seconds=8.0)
            await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-M05-NOM-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_id,
                "workflowId": wf_id,
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-50",
                    "name": "Powder Coating",
                    "sequence": 1,
                    "assignedMachineId": m05_id,
                    "assignedMachineCode": "M-05",
                    "assignedOperatorId": op_id,
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": 8.0,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

        # 12 slightly degraded ops (9.3s duration -> +16.2% deviation)
        for i in range(12):
            t_start = now - timedelta(days=3 - (i * 0.25), hours=1)
            t_end = t_start + timedelta(seconds=9.3)
            await db.work_orders.insert_one({
                "workOrderCode": f"HIST-WO-M05-DEG-{i+1:02d}",
                "status": WorkOrderStatus.COMPLETED.value,
                "productId": prod_id,
                "workflowId": wf_id,
                "quantity": 10.0,
                "startedAt": t_start,
                "completedAt": t_end,
                "operations": [{
                    "operationId": "OP-50",
                    "name": "Powder Coating",
                    "sequence": 1,
                    "assignedMachineId": m05_id,
                    "assignedMachineCode": "M-05",
                    "assignedOperatorId": op_id,
                    "status": WorkOrderOperationStatus.COMPLETED.value,
                    "startedAt": t_start,
                    "actualStart": t_start,
                    "actualEnd": t_end,
                    "durationSeconds": 9.3,
                    "inputQuantity": 10.0,
                    "processedQuantity": 10.0,
                    "outputQuantity": 10.0,
                    "quantityCompleted": 10.0,
                    "quantityRejected": 0.0,
                }],
                "createdAt": t_start - timedelta(minutes=10),
                "updatedAt": t_end,
            })

        # 1 Unresolved Warning
        t_warn_m05 = now - timedelta(hours=4)
        await db.incidents.insert_one({
            "incidentCode": "INC-M05-WARN-01",
            "type": IncidentType.MACHINE_FAILURE.value,
            "severity": IncidentSeverity.LOW.value,
            "status": IncidentStatus.PENDING_REVIEW.value,
            "title": "Operator Report on M-05: Spray gun #2 nozzle clogging intermittently",
            "description": "Powder dispersion pattern has minor striping. Recommended nozzle purge at shift change.",
            "machineId": m05_id,
            "machineCode": "M-05",
            "machineType": "PAINTING",
            "operatorId": op_id,
            "operatorName": op_name,
            "reportedAt": t_warn_m05,
            "detectedAt": t_warn_m05,
            "reportedBy": op_id,
            "createdAt": t_warn_m05,
            "updatedAt": t_warn_m05,
        })

    # -------------------------------------------------------------
    # 4. COMPUTE AUTHORITATIVE HEALTH SCORES & SAVE HISTORY RECORDS
    # -------------------------------------------------------------
    logger.info("Computing authoritative health scores and generating AI predictive maintenance assessments...")
    await db.machine_health_records.delete_many({})

    for m in machines:
        m_code = m["machineCode"]
        m_id_str = str(m["_id"])
        
        # Calculate deterministic health assessment
        assessment = await MachineHealthService.get_machine_health_metrics(m_id_str)
        
        # Generate AI predictive assessment
        ai_assessment = await AIPredictiveMaintenancePlanner.assess_machine_health(assessment)
        assessment.aiAssessment = ai_assessment

        # Save to append-only history collection
        await MachineHealthService.save_health_assessment(assessment)
        logger.info(f"✅ {m_code} ({m.get('name')}): Health Score = {assessment.healthScore}/100 | Risk = {assessment.riskLevel.value} | Attention = {assessment.maintenanceAttention} | Window = {ai_assessment.recommendedMaintenanceWindow}")

    await db_manager.disconnect()
    logger.info("✨ Low health machine records seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_low_health_machines())
