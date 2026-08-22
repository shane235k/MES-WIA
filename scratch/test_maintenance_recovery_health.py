import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def test_maintenance_health_restoration():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get machines list
        res = await client.get(f"{BASE_URL}/api/machines")
        machines = res.json()
        print(f"Found {len(machines)} machines")
        
        # Pick M-03 or any machine
        target = next((m for m in machines if m.get("machineCode") == "M-03"), machines[0])
        m_id = str(target.get("id") or target.get("_id"))
        m_code = target.get("machineCode")
        print(f"Testing machine: {m_code} ({m_id})")

        # 2. Check health before maintenance
        h_before = (await client.get(f"{BASE_URL}/api/predictive-maintenance/machines/{m_id}")).json()
        print(f"\n[BEFORE MAINTENANCE]")
        print(f"Status: {h_before['status']}")
        print(f"Health Score: {h_before['healthScore']}/100")
        print(f"Risk Level: {h_before['riskLevel']}")
        print(f"Breakdown Items: {len(h_before['healthScoreBreakdown'])}")
        for b in h_before['healthScoreBreakdown']:
            print(f"  - {b['signal']}: {b['value']} (penalty: -{b['penalty']} pts)")

        # 3. Schedule maintenance (or trigger recovery)
        print(f"\n--- Triggering Maintenance Recovery on {m_code} ---")
        rec_res = await client.post(f"{BASE_URL}/api/machines/{m_id}/recover", params={"actorId": "ADMIN"})
        print(f"Recovery Response: {rec_res.status_code}")

        # 4. Check health immediately after maintenance recovery
        h_after = (await client.get(f"{BASE_URL}/api/predictive-maintenance/machines/{m_id}")).json()
        print(f"\n[AFTER MAINTENANCE RECOVERY]")
        print(f"Status: {h_after['status']}")
        print(f"Health Score: {h_after['healthScore']}/100")
        print(f"Risk Level: {h_after['riskLevel']}")
        print(f"Breakdown Items: {len(h_after['healthScoreBreakdown'])}")
        for b in h_after['healthScoreBreakdown']:
            print(f"  - {b['signal']}: {b['value']} (penalty: -{b['penalty']} pts) -> {b['explanation']}")

        print(f"\nHealth Score Difference: {h_before['healthScore']} -> {h_after['healthScore']} (Increased: {h_after['healthScore'] >= h_before['healthScore']})")
        print("=== TEST COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(test_maintenance_health_restoration())
