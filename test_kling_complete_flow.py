#!/usr/bin/env python3
"""
Test complete Kling flow: submit → poll until complete → download
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    print(f"\n{'='*70}")
    print("KLING API - COMPLETE FLOW TEST (submit → poll → download)")
    print(f"{'='*70}\n")

    from agents.kling_video_agent import KlingVideoGenerator

    access_key = os.getenv("KLING_ACCESS_KEY")
    secret_key = os.getenv("KLING_SECRET_KEY")

    if not access_key or not secret_key:
        print("❌ Missing credentials")
        return

    print("[1] Initializing Kling generator...")
    try:
        generator = KlingVideoGenerator()
        print("✅ Generator initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return

    # Test with actual generation
    print("[2] Submitting video generation request...")
    prompt = "A serene white egret gliding over paddy fields at sunset with golden light"
    
    try:
        result = await generator.generate(prompt, section_idx=0, duration=5)
        
        if result:
            print(f"\n✅✅✅ SUCCESS! Video generated and cached")
            print(f"   Path: {result}")
            size_mb = os.path.getsize(result) / (1024*1024)
            print(f"   File size: {size_mb:.2f}MB")
        else:
            print(f"\n⚠️  Generation returned None")

    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await generator.close()

    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(test())
