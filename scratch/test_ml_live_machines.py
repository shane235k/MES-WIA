import os
import sys
import asyncio

# Ensure backend package is discoverable regardless of current working directory or IDE execution
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.database import db_manager, get_db  # type: ignore
from app.services.machine_health_service import MachineHealthService  # type: ignore

async def inspect_live_machines():
    print("=" * 65)
    print("      LIVE MES WORKSTATIONS - ML HEALTH & RISK DIAGNOSTICS")
    print("=" * 65)
    
    summaries = await MachineHealthService.get_all_machines_health_summary()
    for s in summaries:
        fail_prob_str = f"{int((s.mlFailureProbability or 0) * 100)}%"
        print(f"[{s.machineCode}] {s.machineName}")
        print(f"     Status: {s.status:8} | Health Score: {s.healthScore}/100 | Risk: {s.riskLevel}")
        print(f"     Cycle Dev: {s.cycleTimeDeviationPercent:+0.1f}% | Rate Eff: {s.processingRateEfficiencyPercent:0.1f}% | ML Fail Prob: {fail_prob_str}")
        print("-" * 65)

async def inspect_m03_detail():
    db = get_db()
    m = await db.machines.find_one({"machineCode": "M-03"})
    if m:
        res = await MachineHealthService.get_machine_health_metrics(str(m["_id"]))
        print("\n" + "=" * 65)
        print("     M-03 DETAILED RANDOM FOREST ML DIAGNOSTICS")
        print("=" * 65)
        ml = res.mlPrediction
        if ml:
            print(f"Model Architecture:  {ml.modelType}")
            print(f"ML Health Score:     {ml.predictedHealthScore}/100")
            print(f"ML Risk Level:       {ml.predictedRiskLevel.value}")
            print(f"Failure Probability: {int(ml.failureProbability * 100)}%")
            print(f"Model Confidence:    {int(ml.modelConfidence * 100)}%")
            print(f"Dominant Driver:     {ml.primaryRiskDriver}")
            print(f"Trained Samples:     {ml.trainedSamplesCount}")
            print("\nFeature Importances:")
            for feat, imp in sorted(ml.featureImportances.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {feat:25}: {imp * 100:5.2f}%")
        
        print("\nHealth Score Breakdown Items:")
        for b in res.healthScoreBreakdown:
            print(f"  [{b.signal}] {b.value} (penalty: -{b.penalty} pts) -> {b.explanation}")

async def main():
    await db_manager.connect()
    try:
        await inspect_live_machines()
        await inspect_m03_detail()
    finally:
        await db_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
