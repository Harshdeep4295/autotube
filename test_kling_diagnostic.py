#!/usr/bin/env python3
"""
KLING API DIAGNOSTIC TEST
Tests the Kling API directly to identify the exact issue.
"""
import os
import asyncio
import json
from dotenv import load_dotenv

load_dotenv()

async def test_kling_api():
    print("\n" + "="*70)
    print("KLING API DIAGNOSTIC TEST")
    print("="*70)

    # Check credentials
    access_key = os.getenv("KLING_ACCESS_KEY", "")
    secret_key = os.getenv("KLING_SECRET_KEY", "")

    print(f"\n[1] Checking credentials...")
    if not access_key or not secret_key:
        print(f"❌ Missing credentials!")
        print(f"   ACCESS_KEY: {'SET' if access_key else 'NOT SET'}")
        print(f"   SECRET_KEY: {'SET' if secret_key else 'NOT SET'}")
        return
    print(f"✅ Credentials found")

    # Import and test
    print(f"\n[2] Importing Kling generator...")
    try:
        from agents.kling_video_agent import KlingVideoGenerator
        print(f"✅ Import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return

    # Initialize
    print(f"\n[3] Initializing KlingVideoGenerator...")
    try:
        generator = KlingVideoGenerator()
        print(f"✅ Generator initialized")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return

    # Test submission
    print(f"\n[4] Testing API submission...")
    test_prompt = "A beautiful sunset over mountains with golden light"
    print(f"   Prompt: {test_prompt}")

    try:
        from agents.kling_video_agent import KlingAPIClient
        client = KlingAPIClient(access_key, secret_key)

        print(f"   Sending request to: POST https://api.klingai.com/v1/videos/text2video")
        task_id = await client.submit_text_to_video(test_prompt, duration=5)
        print(f"✅ Submission successful!")
        print(f"   Task ID: {task_id}")
        print(f"   Task ID type: {type(task_id)}")
        print(f"   Task ID length: {len(str(task_id))}")

        # Try polling
        print(f"\n[5] Testing task status polling...")
        print(f"   Getting status for task: {task_id}")
        print(f"   Polling: GET https://api.klingai.com/v1/tasks/{task_id}")

        try:
            status = await client.get_task_status(task_id)
            print(f"✅ Polling successful!")
            print(f"   Status response: {json.dumps(status, indent=2)}")
        except Exception as poll_error:
            print(f"❌ Polling failed: {poll_error}")
            print(f"\n   This usually means:")
            print(f"   1. Account doesn't have credits/quota")
            print(f"   2. Task ID format is wrong")
            print(f"   3. Polling endpoint format is wrong")
            print(f"   4. API changed response format")

            # Try to get more details
            print(f"\n[6] Attempting detailed error diagnosis...")
            print(f"   Checking if credits are available...")
            try:
                # Make a test request to see actual error response
                import httpx
                token = client.auth.get_token()
                async with httpx.AsyncClient(timeout=10) as http_client:
                    url = f"https://api.klingai.com/v1/tasks/{task_id}"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                    print(f"   Making request with headers: {list(headers.keys())}")
                    resp = await http_client.get(url, headers=headers)
                    print(f"   Response status: {resp.status_code}")
                    print(f"   Response body: {resp.text}")
            except Exception as detail_error:
                print(f"   Could not get details: {detail_error}")

        await client.close()

    except Exception as e:
        print(f"❌ Submission failed: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n" + "="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_kling_api())
