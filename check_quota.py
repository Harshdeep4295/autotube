#!/usr/bin/env python3
"""
Quick Gemini API quota checker.
Run anytime to see if quota is available.

Usage:
    python check_quota.py
"""

import os
import sys
import re
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

def check_gemini_quota():
    """Check if Gemini API quota is available."""

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("❌ GEMINI_API_KEY not set in .env")
        sys.exit(1)

    client = genai.Client(api_key=gemini_key)

    print("🔍 Checking Gemini API quota...\n")

    try:
        # Minimal request to test quota
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="ok",
            config=types.GenerateContentConfig(max_output_tokens=5)
        )

        print("✅ QUOTA AVAILABLE\n")
        print(f"Response: {response.text}")
        print("\nYou can now use the API for:")
        print("  • Script generation (Claude fallback)")
        print("  • Veo 3.1 video generation")
        print("  • Any other Gemini API calls\n")

        if hasattr(response, 'usage_metadata'):
            print(f"📊 Usage this request:")
            print(f"   Input tokens: {response.usage_metadata.input_token_count}")
            print(f"   Output tokens: {response.usage_metadata.output_token_count}\n")

        return True

    except Exception as e:
        error_msg = str(e)

        if "429" in error_msg:
            print("❌ QUOTA EXHAUSTED\n")

            # Try to extract retry time
            match = re.search(r'Retry in\s+([\d.]+)\s*s', error_msg)
            if match:
                retry_secs = float(match.group(1))
                print(f"⏳ Per-minute limit reset in: ~{retry_secs:.0f} seconds")

            # Check for daily reset time
            if "retry in" in error_msg.lower():
                match = re.search(r'(\d+)\s*(?:hours?|h)', error_msg)
                if match:
                    hours = int(match.group(1))
                    print(f"🕐 Daily quota reset in: ~{hours} hours\n")

            print("Cannot use API until quota resets.\n")
            print("Options:")
            print("  1. Wait for daily quota reset (~24 hours)")
            print("  2. Use YouTube Shorts for manual Veo 3.1 testing (unlimited)")
            print("  3. Upgrade to paid Gemini API tier\n")

            return False

        else:
            print(f"❌ ERROR: {error_msg[:200]}\n")
            return False

if __name__ == "__main__":
    check_gemini_quota()
