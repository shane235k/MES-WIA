import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

async def test_feedback_loop():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Get an active incident or create one
        inc_res = await client.get(f"{BASE_URL}/api/incidents")
        incidents = inc_res.json()
        print(f"Found {len(incidents)} incidents")
        if not incidents:
            print("No incidents found")
            return
        
        target_inc = incidents[0]
        inc_id = target_inc.get("id") or target_inc.get("_id")
        print(f"Testing incident {inc_id} ({target_inc.get('incidentCode')})")

        # 2. Start investigation
        print("--- Step 1: Start Investigation ---")
        inv_res = await client.post(f"{BASE_URL}/api/ai/investigate/{inc_id}", json={"requestedBy": "ADMIN"})
        print(f"Investigate status: {inv_res.status_code}")
        ai_op = inv_res.json()
        op_id = ai_op.get("id") or ai_op.get("_id")
        print(f"AI Operation ID: {op_id}")
        print(f"Initial Finding: {ai_op.get('investigation', {}).get('summary')}")

        # 3. Generate Action Plan
        print("--- Step 2: Generate Action Plan ---")
        plan_res = await client.post(f"{BASE_URL}/api/ai/operations/{op_id}/generate-action-plan")
        print(f"Plan status: {plan_res.status_code}")
        ai_op = plan_res.json()
        print(f"Tool calls: {len(ai_op.get('toolCalls') or [])}")

        # 4. Verify with Ollama
        print("--- Step 3: Verify with Ollama ---")
        ver_res = await client.post(f"{BASE_URL}/api/ai/operations/{op_id}/verify-ollama")
        print(f"Verification status: {ver_res.status_code}")
        ai_op = ver_res.json()
        ver = ai_op.get("ollamaVerification", {})
        print(f"Ollama Result Status: {ver.get('status')}")
        print(f"Ollama Explanation: {ver.get('explanation')}")

        # 5. Reinvestigate with Feedback (The new capability!)
        print("--- Step 4: Send Feedback to Gemini & Re-Analyze ---")
        refine_res = await client.post(f"{BASE_URL}/api/ai/operations/{op_id}/reinvestigate-with-feedback")
        print(f"Reinvestigate status: {refine_res.status_code}")
        refined_op = refine_res.json()
        print(f"Refined Status: {refined_op.get('status')}")
        print(f"Refined Finding: {refined_op.get('investigation', {}).get('summary')}")
        print(f"Refined Recommendation: {refined_op.get('investigation', {}).get('recommendation')}")
        print(f"Downstream action plan reset: {refined_op.get('actionPlan') is None}")

        # 6. Generate New Corrected Action Plan
        print("--- Step 5: Generate New Action Plan From Refined Findings ---")
        new_plan_res = await client.post(f"{BASE_URL}/api/ai/operations/{op_id}/generate-action-plan")
        print(f"New Plan status: {new_plan_res.status_code}")
        new_ai_op = new_plan_res.json()
        print(f"New Tool Calls Count: {len(new_ai_op.get('toolCalls') or [])}")
        for i, tc in enumerate(new_ai_op.get('toolCalls') or []):
            print(f"   [{i+1}] {tc.get('tool')}: {tc.get('parameters')}")

        print("=== FEEDBACK LOOP TEST COMPLETED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(test_feedback_loop())
