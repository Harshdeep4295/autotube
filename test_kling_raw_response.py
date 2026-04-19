#!/usr/bin/env python3
"""
Test Kling API raw response to see exact format
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
    print("KLING API - RAW RESPONSE TEST")
    print(f"{'='*70}\n")

    # Create JWT token
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    # Make request
    body = {
        "prompt": "A beautiful sunset",
        "duration": 5,
        "aspect_ratio": "16:9",
        "model": "kling-v2.6-pro"
    }

    print(f"Sending POST to: https://api.klingai.com/v1/videos/text2video")
    print(f"Request body:\n{json.dumps(body, indent=2)}\n")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.klingai.com/v1/videos/text2video",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=body
        )

    print(f"Response Status: {response.status_code}")
    print(f"\nRaw Response:\n{response.text}\n")

    if response.status_code == 200:
        try:
            data = response.json()
            print(f"Parsed JSON:\n{json.dumps(data, indent=2)}\n")

            # Show all keys at top level
            print("Top-level keys:", list(data.keys()))

            # Show all keys in 'data' if it exists
            if "data" in data:
                print("Keys in 'data':", list(data["data"].keys()))
                print(f"\nFull 'data' object:\n{json.dumps(data['data'], indent=2)}")
        except:
            print("Could not parse JSON")

    print(f"\n{'='*70}\n")

asyncio.run(test())
