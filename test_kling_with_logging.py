#!/usr/bin/env python3
import asyncio
import os
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(name)s] %(message)s')

load_dotenv()

async def test():
    from agents.kling_video_agent import KlingAPIClient

    access_key = os.getenv("KLING_ACCESS_KEY")
    secret_key = os.getenv("KLING_SECRET_KEY")

    print(f"\n{'='*70}")
    print("DIRECT CLIENT TEST WITH LOGGING")
    print(f"{'='*70}\n")

    client = KlingAPIClient(access_key, secret_key)

    try:
        # Submit
        print("[1] Submitting...")
        task_id = await client.submit_text_to_video("A beautiful sunset", duration=5)
        print(f"✅ Task ID: {task_id}\n")
        
        # Poll
        print("[2] Polling until complete...")
        status = await client.poll_until_complete(task_id, timeout_seconds=120)
        print(f"✅ Final status: {status}")
        
        # Download
        if status.get("videos"):
            print(f"\n[3] Downloading video...")
            url = status["videos"][0].get("url")
            print(f"    URL: {url}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()

    print(f"\n{'='*70}\n")

asyncio.run(test())
