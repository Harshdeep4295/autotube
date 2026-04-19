#!/usr/bin/env python3
"""
Get full submission response and analyze all fields
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
        "prompt": "A beautiful sunset",
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

    print("FULL SUBMISSION RESPONSE:")
    print(json.dumps(response.json(), indent=2))
    
    data = response.json().get("data", {})
    print(f"\nAll fields in 'data':")
    for key in data.keys():
        print(f"  - {key}: {data[key]}")

asyncio.run(test())
