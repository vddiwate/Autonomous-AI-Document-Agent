import asyncio
import os
import time
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

TEST_CASE_1_STANDARD = {
    "name": "Test Case 1: Standard Business Request",
    "description": "Standard business requirement for enterprise database migration with clear scope.",
    "payload": {
        "request": (
            "Draft a formal Project Plan for migrating legacy on-premise Oracle databases "
            "to managed PostgreSQL on AWS. Include architectural scope, timeline roadmap matrix, "
            "and operational risk governance."
        )
    }
}

TEST_CASE_2_COMPLEX = {
    "name": "Test Case 2: Complex / Ambiguous Request with Conflicting Constraints",
    "description": "Ambiguous request with missing parameters, conflicting goals (near-zero budget vs 99.999% uptime), tech stack ambiguity, and typos requiring autonomous assumptions.",
    "payload": {
        "request": (
            "We need an urgent system overhaul ASAP with almost zero budget and 99.999% high availability uptime, "
            "but team is fighting between microservices vs monolith, and management hasn't picked AWS, Azure or GCP yet. "
            "Write the complete executive strategic plan document mw."
        )
    }
}

async def execute_test(test_data: dict, client: httpx.AsyncClient):
    print("\n" + "=" * 80)
    print(f"RUNNING: {test_data['name'].upper()}")
    print(f"Description: {test_data['description']}")
    print("-" * 80)
    print(f"User Prompt:\n\"{test_data['payload']['request']}\"")
    print("-" * 80)

    start_time = time.time()
    try:
        response = await client.post(
            f"{BASE_URL}/agent",
            json=test_data["payload"],
            timeout=180.0
        )
    except httpx.ConnectError:
        print(f"[ERROR] Could not connect to {BASE_URL}. Ensure 'python run.py' is running!")
        return False
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return False

    elapsed = round(time.time() - start_time, 2)
    print(f"\n[HTTP Status]   : {response.status_code}")
    print(f"[Total Latency] : {elapsed} seconds")

    if response.status_code != 200:
        print(f"[FAILED] Server Error Response: {response.text}")
        return False

    data = response.json()
    plan = data.get("plan", {})
    critic = data.get("critic_review", {})
    doc = data.get("document", {})

    print("\n--- [1. AUTONOMOUS PLANNING & ASSUMPTIONS] ---")
    print(f"Document Title  : {plan.get('document_title')}")
    print(f"Document Type   : {plan.get('document_type')}")
    print(f"Is Ambiguous    : {plan.get('is_ambiguous')}")
    print(f"Assumptions Formulated ({len(plan.get('assumptions', []))} total):")
    for idx, a in enumerate(plan.get("assumptions", []), 1):
        print(f"  [{idx}] {a}")

    print("\n--- [2. DYNAMIC TODO EXECUTION LIST] ---")
    tasks = plan.get("tasks", [])
    print(f"Scheduled Tasks : {len(tasks)}")
    for t in tasks:
        print(f"  Task #{t.get('id')} [{t.get('status').upper()}]: '{t.get('title')}' | Tool: '{t.get('tool')}'")

    print("\n--- [3. CRITIC REFLECTION & QA REPORT] ---")
    print(f"Passed          : {critic.get('passed')}")
    print(f"Evaluation Notes: {critic.get('notes')}")

    print("\n--- [4. OUTPUT ARTIFACT (WORD DOCUMENT)] ---")
    print(f"Filename        : {doc.get('filename')}")
    print(f"Download URL    : {doc.get('download_url')}")
    print(f"File Size       : {doc.get('file_size_bytes')} bytes")

    # Verify document download
    download_url = doc.get("download_url")
    if download_url:
        dl_resp = await client.get(download_url)
        if dl_resp.status_code == 200 and len(dl_resp.content) > 0:
            print(f"[VERIFIED] Document verified and downloadable ({len(dl_resp.content)} bytes received).")
        else:
            print(f"[WARNING] Document download returned status {dl_resp.status_code}")

    print("=" * 80)
    return True

async def main():
    print("=" * 80)
    print("AUTONOMOUS DOCUMENT AGENT - TWO MANDATORY ASSIGNMENT TEST CASES")
    print("=" * 80)
    print(f"Target Server: {BASE_URL}")

    async with httpx.AsyncClient() as client:
        # Check health first
        try:
            h = await client.get(f"{BASE_URL}/health", timeout=5.0)
            print(f"Server Health Status: {h.json().get('status')} | Model: {h.json().get('configured_model')}")
        except Exception:
            print(f"[ERROR] Server at {BASE_URL} is not reachable. Please start it using 'python run.py'!")
            return

        # Execute Test 1: Standard Business Request
        t1_ok = await execute_test(TEST_CASE_1_STANDARD, client)

        # Brief cooldown between test cases to respect API token rates
        print("\nPacing delay (5s) before next test case...")
        await asyncio.sleep(5.0)

        # Execute Test 2: Complex Ambiguous Request
        t2_ok = await execute_test(TEST_CASE_2_COMPLEX, client)

        print("\n" + "=" * 80)
        print("TEST SUITE SUMMARY:")
        print(f"Test Case 1 (Standard) : {'PASS' if t1_ok else 'FAIL'}")
        print(f"Test Case 2 (Complex)  : {'PASS' if t2_ok else 'FAIL'}")
        print("Generated Word documents are ready in 'storage/generated_docs/' folder.")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
