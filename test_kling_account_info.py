#!/usr/bin/env python3
"""
Check account info and available endpoints
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

    # Try various account/info endpoints
    endpoints = [
        "/v1/account/info",
        "/v1/user/info",
        "/v1/user/credits",
        "/v1/user/balance",
        "/v1/account",
        "/v1/auth/verify",
        "/v1/videos",  # List all videos/tasks
        "/v1/tasks",   # List all tasks
    ]

    print("Testing account/info endpoints:\n")
    
    for endpoint in endpoints:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"https://api.klingai.com{endpoint}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )
            
            print(f"GET {endpoint}")
            print(f"  Status: {response.status_code}")
            if response.status_code < 400:
                try:
                    data = response.json()
                    print(f"  Response: {json.dumps(data, indent=2)}")
                except:
                    print(f"  Response: {response.text}")
            print()
        except Exception as e:
            print(f"GET {endpoint}: ERROR - {e}\n")

asyncio.run(test())
