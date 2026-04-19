#!/usr/bin/env python3
"""Quick test of Kling AI integration"""
import asyncio
import os
from agents.kling_video_agent import KlingVideoGenerator

async def test_kling():
    """Test Kling video generation"""
    # Check credentials
    access_key = os.getenv("KLING_ACCESS_KEY")
    secret_key = os.getenv("KLING_SECRET_KEY")

    if not access_key or not secret_key:
        print("❌ Missing KLING_ACCESS_KEY or KLING_SECRET_KEY")
        return False

    print("✅ Credentials found")

    # Initialize generator
    try:
        generator = KlingVideoGenerator()
        print("✅ Generator initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False

    # Test generation
    prompt = "A serene white egret glides over paddy fields at sunrise"
    print(f"\n📹 Testing generation with prompt: {prompt[:50]}...")

    try:
        result = await generator.generate(prompt, section_idx=0, duration=5)
        if result:
            print(f"✅ Generation succeeded: {result}")
            return True
        else:
            print("⚠️ Generation returned None (quota or policy issue)")
            return False
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return False
    finally:
        await generator.client.close()

if __name__ == "__main__":
    success = asyncio.run(test_kling())
    exit(0 if success else 1)
