import pytest
from datetime import datetime, timedelta
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.services.machine_health_service import MachineHealthService
from app.ai.predictive_maintenance_planner import AIPredictiveMaintenancePlanner
from app.schemas.machine_health import RiskLevel, DataQuality

@pytest.mark.asyncio
async def test_healthy_machine_metrics_and_high_score():
    """
    Test 1: A machine with stable cycle times and 0 failures receives high health score (>85) and LOW risk.
    """
    db = get_db()
    
    # Create healthy test machine
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-HEALTHY",
        "name": "Healthy CNC Mill",
        "type": "MILLING",
        "status": "IDLE",
        "processingRate": 2.0,
        "rateUnit": "units/sec",
        "location": "Bay 1",
        "availability": True,
        "createdAt": datetime.utcnow()
    })
    mach_id = str(mach_res.inserted_id)

    # Insert 20 consistent completed operations (5.0s each)
    now = datetime.utcnow()
    for i in range(20):
        t_start = now - timedelta(hours=25 - i)
        t_end = t_start + timedelta(seconds=5.0)
        await db.work_orders.insert_one({
            "workOrderCode": f"TEST-WO-HEALTHY-{i}",
            "status": "COMPLETED",
            "quantity": 10.0,
            "operations": [{
                "operationId": "OP-10",
                "assignedMachineId": mach_id,
                "status": "COMPLETED",
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": 5.0,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0
            }]
        })

    assessment = await MachineHealthService.get_machine_health_metrics(mach_id)

    assert assessment.healthScore >= 85
    assert assessment.riskLevel == RiskLevel.LOW
    assert assessment.dataQuality == DataQuality.SUFFICIENT_DATA
    assert assessment.dataPoints == 20
    assert assessment.metrics.cycleTimeDeviationPercent <= 5.0
    assert assessment.metrics.totalFailureCount == 0

@pytest.mark.asyncio
async def test_degrading_cycle_times_lower_health_score():
    """
    Test 2: A machine with progressive cycle time degradation has an elevated cycle deviation and lowered health score.
    """
    db = get_db()
    
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-DEGRADE",
        "name": "Degrading Lathe",
        "type": "CUTTING",
        "status": "IDLE",
        "processingRate": 1.0,
        "rateUnit": "units/sec",
        "location": "Bay 2",
        "availability": True,
        "createdAt": datetime.utcnow()
    })
    mach_id = str(mach_res.inserted_id)

    now = datetime.utcnow()
    # 10 older operations at 5.0s, 10 recent operations degrading up to 12.0s
    for i in range(20):
        dur = 5.0 if i < 10 else (5.0 + (i - 9) * 0.8)
        t_start = now - timedelta(hours=25 - i)
        t_end = t_start + timedelta(seconds=dur)
        await db.work_orders.insert_one({
            "workOrderCode": f"TEST-WO-DEGRADE-{i}",
            "status": "COMPLETED",
            "quantity": 10.0,
            "operations": [{
                "operationId": "OP-10",
                "assignedMachineId": mach_id,
                "status": "COMPLETED",
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": dur,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0
            }]
        })

    assessment = await MachineHealthService.get_machine_health_metrics(mach_id)

    assert assessment.metrics.cycleTimeDeviationPercent > 20.0
    assert assessment.healthScore < 85
    assert assessment.riskLevel in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]

@pytest.mark.asyncio
async def test_insufficient_data_handling():
    """
    Test 3: A machine with fewer than 5 operations returns INSUFFICIENT_DATA and confidence ceiling <= 0.40.
    """
    db = get_db()
    
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-SPARSE",
        "name": "Brand New Machine",
        "type": "DRILLING",
        "status": "IDLE",
        "processingRate": 1.0,
        "rateUnit": "units/sec",
        "location": "Bay 3",
        "availability": True,
        "createdAt": datetime.utcnow()
    })
    mach_id = str(mach_res.inserted_id)

    # Only 2 completed operations
    now = datetime.utcnow()
    for i in range(2):
        t_start = now - timedelta(hours=2 - i)
        t_end = t_start + timedelta(seconds=5.0)
        await db.work_orders.insert_one({
            "workOrderCode": f"TEST-WO-SPARSE-{i}",
            "status": "COMPLETED",
            "quantity": 10.0,
            "operations": [{
                "operationId": "OP-10",
                "assignedMachineId": mach_id,
                "status": "COMPLETED",
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": 5.0,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0
            }]
        })

    assessment = await MachineHealthService.get_machine_health_metrics(mach_id)

    assert assessment.dataQuality == DataQuality.INSUFFICIENT_DATA
    assert assessment.dataPoints == 2
    assert assessment.confidenceCeiling <= 0.40

@pytest.mark.asyncio
async def test_mtbf_and_mttr_calculation():
    """
    Test 4: MTBF and MTTR are calculated accurately from operating time and failure downtime.
    """
    db = get_db()
    
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-RELIABILITY",
        "name": "Press Workstation",
        "type": "BENDING",
        "status": "IDLE",
        "processingRate": 1.0,
        "rateUnit": "units/sec",
        "location": "Bay 4",
        "availability": True,
        "createdAt": datetime.utcnow()
    })
    mach_id = str(mach_res.inserted_id)

    # 10 completed operations (100 seconds total operating time)
    now = datetime.utcnow()
    for i in range(10):
        t_start = now - timedelta(hours=15 - i)
        t_end = t_start + timedelta(seconds=10.0)
        await db.work_orders.insert_one({
            "workOrderCode": f"TEST-WO-REL-{i}",
            "status": "COMPLETED",
            "quantity": 10.0,
            "operations": [{
                "operationId": "OP-10",
                "assignedMachineId": mach_id,
                "status": "COMPLETED",
                "startedAt": t_start,
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": 10.0,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0
            }]
        })

    # 2 failure incidents (30 min and 60 min downtime = 5400s total downtime)
    t_inc1 = now - timedelta(days=2)
    await db.incidents.insert_one({
        "incidentCode": "TEST-INC-1",
        "type": "MACHINE_FAILURE",
        "machineId": mach_id,
        "machineCode": "TEST-M-RELIABILITY",
        "detectedAt": t_inc1,
        "resolvedAt": t_inc1 + timedelta(minutes=30),
        "status": "RESOLVED"
    })

    t_inc2 = now - timedelta(days=1)
    await db.incidents.insert_one({
        "incidentCode": "TEST-INC-2",
        "type": "MACHINE_FAILURE",
        "machineId": mach_id,
        "machineCode": "TEST-M-RELIABILITY",
        "detectedAt": t_inc2,
        "resolvedAt": t_inc2 + timedelta(minutes=60),
        "status": "RESOLVED"
    })

    assessment = await MachineHealthService.get_machine_health_metrics(mach_id)

    assert assessment.metrics.totalFailureCount == 2
    assert assessment.metrics.totalOperatingSeconds == 100.0
    # MTBF = 100s / 2 failures = 50.0s
    assert assessment.metrics.mtbfSeconds == 50.0
    # MTTR = (1800s + 3600s) / 2 = 2700.0s
    assert assessment.metrics.mttrSeconds == 2700.0

@pytest.mark.asyncio
async def test_material_correlation_detection():
    """
    Test 5: Machine failures linked to specific materials and lots are identified with correlation phrasing.
    """
    db = get_db()

    mat_res = await db.materials.insert_one({
        "materialCode": "MAT-SS304-TEST",
        "name": "Stainless Steel 304",
        "type": "SHEET"
    })
    mat_id = str(mat_res.inserted_id)

    spec_res = await db.material_specifications.insert_one({
        "specificationCode": "SPEC-SS304-2MM",
        "name": "SS304 2mm Sheet",
        "grade": "SS304",
        "thicknessMm": 2.0
    })
    spec_id = str(spec_res.inserted_id)

    lot_res = await db.inventory_lots.insert_one({
        "lotNumber": "LOT-TEST-999",
        "materialId": mat_id,
        "specificationId": spec_id,
        "supplier": "Apex Metals Corp",
        "quantityOnHand": 100.0
    })
    lot_id = str(lot_res.inserted_id)

    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-MATCORR",
        "name": "Plasma Cutter",
        "type": "CUTTING",
        "status": "IDLE",
        "processingRate": 1.0,
        "availability": True
    })
    mach_id = str(mach_res.inserted_id)

    # Create work order and reservation
    wo_res = await db.work_orders.insert_one({
        "workOrderCode": "WO-TEST-MATCORR",
        "status": "COMPLETED",
        "quantity": 10.0,
        "operations": [{
            "operationId": "OP-10",
            "assignedMachineId": mach_id,
            "status": "COMPLETED",
            "durationSeconds": 10.0,
            "actualStart": datetime.utcnow() - timedelta(hours=2),
            "actualEnd": datetime.utcnow() - timedelta(hours=1),
            "inputQuantity": 10.0,
            "processedQuantity": 10.0
        }]
    })
    wo_id = str(wo_res.inserted_id)

    await db.material_reservations.insert_one({
        "workOrderId": wo_id,
        "operationId": "OP-10",
        "materialId": mat_id,
        "lotId": lot_id,
        "specificationId": spec_id,
        "quantityReserved": 1.0,
        "status": "CONSUMED"
    })

    # Create incident on this work order
    await db.incidents.insert_one({
        "incidentCode": "INC-TEST-MATCORR-1",
        "type": "MACHINE_FAILURE",
        "machineId": mach_id,
        "machineCode": "TEST-M-MATCORR",
        "workOrderId": wo_id,
        "operationId": "OP-10",
        "detectedAt": datetime.utcnow() - timedelta(hours=1),
        "status": "RESOLVED"
    })

    assessment = await MachineHealthService.get_machine_health_metrics(mach_id)

    assert len(assessment.metrics.problematicMaterials) > 0
    mat_corr = assessment.metrics.problematicMaterials[0]
    assert mat_corr.materialName == "Stainless Steel 304"
    assert mat_corr.lotNumber == "LOT-TEST-999"
    assert mat_corr.supplier == "Apex Metals Corp"
    assert "Potential correlation detected" in mat_corr.observation
    assert "not confirmed causation" in mat_corr.observation

@pytest.mark.asyncio
async def test_predictive_maintenance_planner_and_fallback():
    """
    Test 6: AIPredictiveMaintenancePlanner generates valid structured assessment without hallucinations.
    """
    db = get_db()
    
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-PLANNER",
        "name": "Planner Test Station",
        "type": "WELDING",
        "status": "IDLE",
        "processingRate": 1.0,
        "availability": True
    })
    mach_id = str(mach_res.inserted_id)

    assessment = await MachineHealthService.get_machine_health_metrics(mach_id)
    ai_result = await AIPredictiveMaintenancePlanner.assess_machine_health(assessment)

    assert ai_result.summary is not None
    assert len(ai_result.summary) > 5
    assert ai_result.failureMode is not None
    assert ai_result.diagnosisConfidence >= 0.0 and ai_result.diagnosisConfidence <= 1.0
    assert len(ai_result.findings) > 0
    assert len(ai_result.recommendedActions) > 0
    assert ai_result.recommendedMaintenanceWindow in ["IMMEDIATE", "WITHIN_24_HOURS", "NEXT_SCHEDULED_SHIFT", "ROUTINE"]

@pytest.mark.asyncio
async def test_append_only_history_records():
    """
    Test 7: Health assessments are saved to db.machine_health_records in append-only fashion.
    """
    db = get_db()
    
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-HISTORY",
        "name": "History Test Station",
        "type": "CUTTING",
        "status": "IDLE",
        "processingRate": 1.0,
        "availability": True
    })
    mach_id = str(mach_res.inserted_id)

    assessment1 = await MachineHealthService.get_machine_health_metrics(mach_id)
    assessment1.healthScore = 90
    await MachineHealthService.save_health_assessment(assessment1)

    assessment2 = await MachineHealthService.get_machine_health_metrics(mach_id)
    assessment2.healthScore = 82
    await MachineHealthService.save_health_assessment(assessment2)

    history = await MachineHealthService.get_health_history(mach_id)

    assert len(history) >= 2
    assert history[0]["healthScore"] == 90
    assert history[1]["healthScore"] == 82

@pytest.mark.asyncio
async def test_rest_api_endpoints_and_action_approval():
    """
    Test 8: REST endpoints work cleanly and maintenance action requires valid parameters and Admin approval.
    """
    db = get_db()
    
    mach_res = await db.machines.insert_one({
        "machineCode": "TEST-M-API",
        "name": "API Test Machine",
        "type": "CUTTING",
        "status": "IDLE",
        "processingRate": 1.5,
        "availability": True
    })
    mach_id = str(mach_res.inserted_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # GET /api/predictive-maintenance/machines
        res_list = await ac.get("/api/predictive-maintenance/machines")
        assert res_list.status_code == 200
        summaries = res_list.json()
        assert any(s["machineCode"] == "TEST-M-API" for s in summaries)

        # GET /api/predictive-maintenance/machines/{machine_id}
        res_detail = await ac.get(f"/api/predictive-maintenance/machines/{mach_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["machineCode"] == "TEST-M-API"
        assert "healthScore" in detail

        # POST /api/predictive-maintenance/machines/{machine_id}/assess
        res_assess = await ac.post(f"/api/predictive-maintenance/machines/{mach_id}/assess")
        assert res_assess.status_code == 200
        assess_data = res_assess.json()
        assert assess_data["aiAssessment"] is not None

        # POST /api/predictive-maintenance/machines/{machine_id}/approve-action
        res_approve = await ac.post(
            f"/api/predictive-maintenance/machines/{mach_id}/approve-action",
            json={
                "tool": "schedule_maintenance",
                "parameters": {
                    "durationMinutes": 30,
                    "reason": "Test preventive maintenance schedule"
                },
                "adminId": "TEST_ADMIN"
            }
        )
        assert res_approve.status_code == 200
        approve_data = res_approve.json()
        assert approve_data["success"] is True

        # Verify machine status transitioned to MAINTENANCE
        updated_mach = await db.machines.find_one({"_id": ObjectId(mach_id)})
        assert updated_mach["status"] == "MAINTENANCE"
        assert updated_mach["maintenanceDurationMinutes"] == 30
