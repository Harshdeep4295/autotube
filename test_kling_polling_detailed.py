#!/usr/bin/env python3
"""
Test polling in detail to see task progress
"""
import asyncio
import httpx
import jwt
import time
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    access_key = os.getenv("KLING_ACCESS_KEY")
    secret_key = os.getenv("KLING_SECRET_KEY")

    API_BASE = "https://api-singapore.klingai.com"
    
    print(f"\n{'='*70}")
    print("KLING API - DETAILED POLLING TEST")
    print(f"{'='*70}\n")

    # Submit
    print("[1] Submitting task...")
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    body = {
        "model_name": "kling-v2-6",
        "prompt": "A beautiful sunset",
        "duration": "5",
        "mode": "std",
        "aspect_ratio": "16:9"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{API_BASE}/v1/videos/text2video",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=body
        )

    data = response.json()
    task_id = data["data"]["task_id"]
    print(f"✅ Task submitted: {task_id}\n")

    # Poll with detailed tracking
    print("[2] Polling task status every 10 seconds...\n")
    start_time = time.time()
    
    for attempt in range(20):  # Poll for up to 200 seconds
        await asyncio.sleep(10)
        
        now = int(time.time())
        payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{API_BASE}/v1/videos/text2video/{task_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
        
        elapsed = time.time() - start_time
        status_data = response.json().get("data", {})
        task_status = status_data.get("task_status")
        
        print(f"   [{elapsed:3.0f}s] Status: {task_status}")
        
        if task_status == "succeed":
            print(f"\n✅ Task completed!")
            task_result = status_data.get("task_result", {})
            videos = task_result.get("videos", [])
            if videos:
                print(f"   Video URL: {videos[0].get('url', 'N/A')}")
            break
        elif task_status == "failed":
            msg = status_data.get("task_status_msg", "Unknown error")
            print(f"\n❌ Task failed: {msg}")
            break
    else:
        print(f"\n⏱️  Task still processing after 200 seconds")

    print(f"\n{'='*70}\n")

asyncio.run(test())
