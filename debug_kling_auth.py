#!/usr/bin/env python3
"""Debug Kling authentication"""
import os
import json
import jwt
import time
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("=" * 60)
print("KLING AUTHENTICATION DEBUG")
print("=" * 60)

# Step 1: Check credentials exist
access_key = os.getenv("KLING_ACCESS_KEY")
secret_key = os.getenv("KLING_SECRET_KEY")

print("\n1️⃣  CHECKING CREDENTIALS:")
if not access_key:
    print("   ❌ KLING_ACCESS_KEY not set")
else:
    print(f"   ✅ KLING_ACCESS_KEY found: {access_key[:10]}...")

if not secret_key:
    print("   ❌ KLING_SECRET_KEY not set")
else:
    print(f"   ✅ KLING_SECRET_KEY found: {secret_key[:10]}...")

if not access_key or not secret_key:
    print("\n⚠️  Missing credentials. Set them:")
    print("   export KLING_ACCESS_KEY=ak_xxxxx")
    print("   export KLING_SECRET_KEY=sk_xxxxx")
    exit(1)

# Step 2: Test JWT token generation
print("\n2️⃣  TESTING JWT TOKEN GENERATION:")
now = int(time.time())
payload = {
    "iss": access_key,
    "exp": now + 1800,
    "nbf": now - 5
}

try:
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    print(f"   ✅ JWT token generated")
    print(f"   Token: {token[:50]}...")
except Exception as e:
    print(f"   ❌ JWT generation failed: {e}")
    exit(1)

# Step 3: Test API request
print("\n3️⃣  TESTING API REQUEST:")
import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient(timeout=10) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Try minimal request format first
        body = {
            "prompt": "A beautiful sunset over mountains with golden light",
            "duration": 5,
            "aspect_ratio": "16:9",
            "model": "kling-v3-pro"
        }

        print(f"   URL: https://api.klingai.com/v1/videos/text2video")
        print(f"   Headers: {list(headers.keys())}")
        print(f"   Body: {json.dumps(body, indent=2)}")
        print(f"   Prompt length: {len(body.get('prompt', ''))}")
        print(f"   Prompt value: '{body.get('prompt', '')}'")

        try:
            response = await client.post(
                "https://api.klingai.com/v1/videos/text2video",
                headers=headers,
                json=body
            )

            print(f"\n   Response Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS! Task ID: {data.get('data', {}).get('task_id')}")
            elif response.status_code == 401:
                print(f"   ❌ 401 UNAUTHORIZED")
                print(f"   Response: {response.text}")
                print(f"\n   Possible causes:")
                print(f"   1. Access Key is wrong")
                print(f"   2. Secret Key is wrong")
                print(f"   3. Keys are not in correct format (ak_xxx and sk_xxx)")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text}")

        except Exception as e:
            print(f"   ❌ Request failed: {e}")

asyncio.run(test_api())

print("\n" + "=" * 60)
print("NEXT STEPS:")
print("=" * 60)
print("1. Verify your API keys at: https://app.klingai.com/global/dev")
print("2. Keys should start with 'ak_' and 'sk_'")
print("3. Make sure you copied the ENTIRE key (sometimes cut off)")
print("4. If keys look wrong, create NEW ones in Kling dashboard")
print("=" * 60)
