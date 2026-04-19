#!/usr/bin/env python3
"""
Test Kling API polling with the task_id from submission
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
    print("KLING API - POLLING TEST")
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

    # Wait a bit
    print("[2] Waiting 3 seconds before polling...")
    await asyncio.sleep(3)

    # Try polling with /v1/tasks/{task_id}
    print(f"\n[3] Polling with /v1/tasks/{task_id}...")
    now = int(time.time())
    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://api.klingai.com/v1/tasks/{task_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}\n")

    # Try polling with /v1/videos/{task_id}
    print(f"[4] Polling with /v1/videos/{task_id}...")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://api.klingai.com/v1/videos/{task_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}\n")

    print(f"{'='*70}\n")

asyncio.run(test())
