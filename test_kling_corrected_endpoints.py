#!/usr/bin/env python3
"""
Test Kling API with CORRECTED endpoints (official documentation)
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

    print(f"\n{'='*70}")
    print("KLING API - CORRECTED ENDPOINTS TEST")
    print(f"{'='*70}\n")

    # NEW correct domain
    API_BASE = "https://api-singapore.klingai.com"
    
    print(f"[1] Submitting with NEW domain: {API_BASE}/v1/videos/text2video")
    
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    body = {
        "model_name": "kling-v2-6",
        "prompt": "A beautiful sunset over mountains with golden light",
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

    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}\n")

    if response.status_code == 200 and "data" in data:
        task_id = data["data"].get("task_id")
        print(f"✅ Submission successful! Task ID: {task_id}\n")
        
        # Wait for replication
        print("[2] Waiting 5 seconds for task to replicate on servers...")
        await asyncio.sleep(5)
        
        # Poll with CORRECT endpoint
        print(f"[3] Polling with CORRECT endpoint: {API_BASE}/v1/videos/text2video/{task_id}")
        
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
        
        print(f"Status: {response.status_code}")
        resp_data = response.json()
        print(f"Response: {json.dumps(resp_data, indent=2)}\n")
        
        if response.status_code == 200:
            status = resp_data.get("data", {}).get("task_status")
            print(f"✅✅✅ POLLING WORKS! Task status: {status}")
        else:
            print(f"❌ Polling failed with status {response.status_code}")
    else:
        print(f"❌ Submission failed")

    print(f"\n{'='*70}\n")

asyncio.run(test())
