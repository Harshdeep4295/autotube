#!/usr/bin/env python3
"""
Test Kling API polling with longer initial wait
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
    print("KLING API - POLLING TEST WITH LONG WAIT")
    print(f"{'='*70}\n")

    # First submit
    print("[1] Submitting video generation task...")
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
        "model": "kling-v2.6-pro"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.klingai.com/v1/videos/text2video",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=body
        )

    data = response.json()
    task_id = data["data"]["task_id"]
    print(f"✅ Task submitted: {task_id}")
    print(f"   Task status: {data['data']['task_status']}\n")

    # Wait progressively longer and try polling
    for wait_time in [5, 10, 15, 20, 30]:
        print(f"[*] Waiting {wait_time} seconds before polling...")
        await asyncio.sleep(wait_time)

        now = int(time.time())
        payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://api.klingai.com/v1/videos/{task_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )

        print(f"   After {wait_time}s wait: Status {response.status_code}")
        if response.status_code != 404:
            print(f"   Response: {response.text}\n")
            break
        else:
            print(f"   Still 404\n")

    print(f"{'='*70}\n")

asyncio.run(test())
