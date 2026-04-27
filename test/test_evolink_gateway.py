#!/usr/bin/env python3
"""
Test Kling API via EvoLink gateway (official)
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
    print("KLING API via EVOLINK GATEWAY TEST")
    print(f"{'='*70}\n")

    # Test EvoLink submission endpoint
    print("[1] Trying EvoLink submission: POST /v1/videos/generations")
    
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
        "aspect_ratio": "16:9"
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.evolink.ai/v1/videos/generations",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=body
            )
        
        print(f"Status: {response.status_code}")
        resp_text = response.text
        print(f"Response: {resp_text}\n")
        
        if response.status_code == 200:
            try:
                resp_data = json.loads(resp_text)
                task_id = resp_data.get("data", {}).get("task_id")
                print(f"✅ EvoLink submission works! Task ID: {task_id}\n")
                
                # Try EvoLink polling endpoint
                if task_id:
                    print("[2] Trying EvoLink polling: GET /v1/tasks/{task_id}")
                    await asyncio.sleep(3)
                    
                    now = int(time.time())
                    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
                    token = jwt.encode(payload, secret_key, algorithm="HS256")
                    
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.get(
                            f"https://api.evolink.ai/v1/tasks/{task_id}",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"
                            }
                        )
                    
                    print(f"Status: {response.status_code}")
                    print(f"Response: {response.text}\n")
                    
                    if response.status_code == 200:
                        print("✅ EvoLink polling works!\n")
                    else:
                        print("❌ EvoLink polling failed\n")
            except json.JSONDecodeError:
                print("Could not parse JSON response\n")
    except Exception as e:
        print(f"Error: {e}\n")

    print(f"{'='*70}\n")

asyncio.run(test())
