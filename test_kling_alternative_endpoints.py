#!/usr/bin/env python3
"""
Try alternative polling endpoints
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

    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    body = {
        "prompt": "A test video",
        "duration": 5,
        "aspect_ratio": "16:9",
        "model": "kling-v2.6-pro"
    }

    # Submit
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.klingai.com/v1/videos/text2video",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=body
        )

    data = response.json().get("data", {})
    task_id = data["task_id"]
    request_id = response.json().get("request_id")
    
    print(f"Task ID: {task_id}")
    print(f"Request ID: {request_id}\n")

    await asyncio.sleep(5)

    # Try different endpoints
    endpoints = [
        f"/v1/videos/{task_id}",
        f"/v1/tasks/{task_id}",
        f"/v1/video/{task_id}",
        f"/v1/task/{task_id}",
        f"/v1/videos/task/{task_id}",
        f"/v1/videos/status/{task_id}",
        f"/v1/videos/query/{task_id}",
        f"/v1/request/{request_id}",
    ]

    for endpoint in endpoints:
        now = int(time.time())
        payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"https://api.klingai.com{endpoint}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )
            
            print(f"{endpoint}: {response.status_code}")
            if response.status_code != 404:
                print(f"  → {response.text}\n")
        except Exception as e:
            print(f"{endpoint}: ERROR - {e}")

asyncio.run(test())
