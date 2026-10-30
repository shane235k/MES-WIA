import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta

from app.main import app
from app.core.database import get_db
from app.services.ml_health_service import MachineHealthMLService
from app.schemas.machine_health import RiskLevel

@pytest.mark.asyncio
async def test_ml_model_metadata_and_feature_importances():
    """
    Test 1: Verify Random Forest model metadata, feature importances, and hyper-parameters.
    """
    meta = MachineHealthMLService.get_model_metadata()
    assert meta["algorithm"] == "Random Forest (scikit-learn)"
    assert meta["classificationTrees"] == 100
    assert meta["regressionTrees"] == 100
    assert len(meta["features"]) == 9
    assert meta["trainedSamples"] > 0
    assert "LOW" in meta["targetClasses"]
    assert "CRITICAL" in meta["targetClasses"]

    # Verify feature importances are normalized and positive
    importances = [f["importance"] for f in meta["features"]]
    assert all(i >= 0.0 for i in importances)
    assert sum(importances) > 0.0

@pytest.mark.asyncio
async def test_ml_inference_healthy_vs_critical():
    """
    Test 2: Verify that healthy telemetry classifies as LOW risk with high score,
    while severe degradation classifies as CRITICAL with high failure probability.
    """
    # 1. Healthy machine
    healthy_pred = MachineHealthMLService.predict(
        cycle_deviation_pct=2.0,
        rate_efficiency_pct=98.0,
        failures_24h=0,
        failures_7d=0,
        downtime_pct=1.0,
        unresolved_warnings=0,
        total_operating_seconds=15000.0,
        days_since_maint=10.0,
        incident_count=0
    )
    assert healthy_pred.predictedRiskLevel == RiskLevel.LOW
    assert healthy_pred.predictedHealthScore >= 85
    assert healthy_pred.failureProbability <= 0.15
    assert "nominal" in healthy_pred.primaryRiskDriver.lower()

    # 2. Critical degrading machine (e.g., M-03 welding torch overheat)
    critical_pred = MachineHealthMLService.predict(
        cycle_deviation_pct=65.0,
        rate_efficiency_pct=60.0,
        failures_24h=2,
        failures_7d=3,
        downtime_pct=25.0,
        unresolved_warnings=2,
        total_operating_seconds=45000.0,
        days_since_maint=65.0,
        incident_count=5
    )
    assert critical_pred.predictedRiskLevel in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    assert critical_pred.predictedHealthScore <= 55
    assert critical_pred.failureProbability >= 0.70
    assert "Cycle Time Elongation" in critical_pred.primaryRiskDriver or "Failure" in critical_pred.primaryRiskDriver

@pytest.mark.asyncio
async def test_ml_rest_api_endpoints():
    """
    Test 3: REST API integration tests for /api/predictive-maintenance/ml/ endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /ml/info
        info_res = await client.get("/api/predictive-maintenance/ml/info")
        assert info_res.status_code == 200
        info = info_res.json()
        assert info["algorithm"] == "Random Forest (scikit-learn)"
        assert len(info["features"]) == 9

        # POST /ml/simulate (Healthy simulation)
        sim_res = await client.post("/api/predictive-maintenance/ml/simulate", json={
            "cycleDeviationPercent": 0.0,
            "rateEfficiencyPercent": 100.0,
            "failures24h": 0,
            "failures7d": 0,
            "downtimePercent": 0.0,
            "unresolvedWarnings": 0,
            "totalOperatingHours": 50.0,
            "daysSinceLastMaintenance": 14.0,
            "historicalIncidentCount": 0
        })
        assert sim_res.status_code == 200
        sim = sim_res.json()
        assert sim["predictedRiskLevel"] == "LOW"
        assert sim["predictedHealthScore"] >= 85
        assert sim["failureProbability"] <= 0.15

        # POST /ml/simulate (Critical simulation)
        sim_crit = await client.post("/api/predictive-maintenance/ml/simulate", json={
            "cycleDeviationPercent": 75.0,
            "rateEfficiencyPercent": 50.0,
            "failures24h": 2,
            "failures7d": 4,
            "downtimePercent": 30.0,
            "unresolvedWarnings": 3,
            "totalOperatingHours": 500.0,
            "daysSinceLastMaintenance": 90.0,
            "historicalIncidentCount": 6
        })
        assert sim_crit.status_code == 200
        sim_c = sim_crit.json()
        assert sim_c["predictedRiskLevel"] in ["HIGH", "CRITICAL"]
        assert sim_c["failureProbability"] >= 0.75

        # POST /ml/retrain
        retrain_res = await client.post("/api/predictive-maintenance/ml/retrain", params={"actorId": "ADMIN"})
        assert retrain_res.status_code == 200
        assert retrain_res.json()["success"] is True

@pytest.mark.asyncio
async def test_machine_detail_contains_ml_prediction():
    """
    Test 4: Verify that fetching /api/predictive-maintenance/machines/{id}
    returns the mlPrediction payload and diagnostic breakdown item.
    """
    db = get_db()
    # Create test machine
    m_res = await db.machines.insert_one({
        "machineCode": "TEST-ML-M01",
        "name": "ML Inspection CNC",
        "type": "MILLING",
        "status": "IDLE",
        "processingRate": 1.5,
        "rateUnit": "units/sec",
        "availability": True,
        "createdAt": datetime.utcnow()
    })
    m_id = str(m_res.inserted_id)

    # Insert 15 completed operations
    now = datetime.utcnow()
    for i in range(15):
        t_start = now - timedelta(hours=15 - i)
        t_end = t_start + timedelta(seconds=6.6)
        await db.work_orders.insert_one({
            "workOrderCode": f"TEST-WO-ML-{i}",
            "status": "COMPLETED",
            "quantity": 10.0,
            "operations": [{
                "operationId": "OP-10",
                "assignedMachineId": m_id,
                "status": "COMPLETED",
                "actualStart": t_start,
                "actualEnd": t_end,
                "durationSeconds": 6.6,
                "inputQuantity": 10.0,
                "processedQuantity": 10.0
            }]
        })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/predictive-maintenance/machines/{m_id}")
        assert res.status_code == 200
        data = res.json()

        assert "mlPrediction" in data
        assert data["mlPrediction"] is not None
        assert data["mlPrediction"]["modelType"].startswith("RandomForest")
        assert "failureProbability" in data["mlPrediction"]
        assert "featureImportances" in data["mlPrediction"]

        # Check breakdown has ML item
        signals = [b["signal"] for b in data["healthScoreBreakdown"]]
        assert "ML_RANDOM_FOREST_DIAGNOSTIC" in signals
