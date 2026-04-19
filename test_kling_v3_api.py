#!/usr/bin/env python3
"""
Test Kling 3.0 API endpoints (newer version)
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
    print("KLING 3.0 API TEST (v3 endpoints)")
    print(f"{'='*70}\n")

    # Test v3 submission endpoint
    print("[1] Trying v3 submission endpoint: POST /v3/video/text-to-video")
    
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    body = {
        "prompt": "A beautiful sunset over mountains",
        "duration": 5,
        "aspect_ratio": "16:9",
        "model": "kling-v3-pro"
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.klingai.com/v3/video/text-to-video",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=body
            )
        
        print(f"Status: {response.status_code}")
        resp_data = response.json()
        print(f"Response: {json.dumps(resp_data, indent=2)}\n")
        
        if response.status_code == 200 and "data" in resp_data:
            task_id = resp_data["data"].get("task_id")
            print(f"✅ v3 submission works! Task ID: {task_id}\n")
            
            # Try v3 polling endpoint
            if task_id:
                print("[2] Trying v3 polling endpoint: GET /v3/task/{task_id}")
                await asyncio.sleep(3)
                
                now = int(time.time())
                payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
                token = jwt.encode(payload, secret_key, algorithm="HS256")
                
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"https://api.klingai.com/v3/task/{task_id}",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        }
                    )
                
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}\n")
        else:
            print("❌ v3 submission endpoint failed\n")
    
    except Exception as e:
        print(f"❌ Error testing v3: {e}\n")

    # Also test if regular API key auth works (not JWT)
    print("[3] Trying v1 endpoint with simple API key auth (no JWT)")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.klingai.com/v1/videos/text2video",
                headers={
                    "x-api-key": access_key,  # Try simple key auth
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": "A test video",
                    "duration": 5,
                    "aspect_ratio": "16:9",
                    "model": "kling-v2.6-pro"
                }
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}\n")
        
        if response.status_code == 200:
            print("✅ Simple API key auth works!\n")
    except Exception as e:
        print(f"API key auth test error: {e}\n")

    print(f"{'='*70}\n")

asyncio.run(test())
