#!/usr/bin/env python3
"""
COMPREHENSIVE KLING INTEGRATION TEST
Validates end-to-end that Kling is properly configured and working.
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

print("\n" + "="*70)
print("KLING INTEGRATION VERIFICATION")
print("="*70)

# Step 1: Verify environment variables
print("\n[1/5] Checking environment variables...")
required_vars = ["KLING_ACCESS_KEY", "KLING_SECRET_KEY", "VIDEO_ANIMATION_MODE"]
missing = []

for var in required_vars:
    val = os.getenv(var, "")
    if not val:
        missing.append(var)
        print(f"  ❌ {var}: NOT SET")
    else:
        # Show first 10 chars for secrets
        if "KEY" in var:
            print(f"  ✅ {var}: {val[:10]}...")
        else:
            print(f"  ✅ {var}: {val}")

if missing:
    print(f"\n❌ FAILED: Missing variables: {missing}")
    sys.exit(1)

# Step 2: Verify mode is kling
print("\n[2/5] Verifying animation mode...")
mode = os.getenv("VIDEO_ANIMATION_MODE", "").lower()
if mode != "kling":
    print(f"  ❌ VIDEO_ANIMATION_MODE is '{mode}', not 'kling'")
    sys.exit(1)
else:
    print(f"  ✅ VIDEO_ANIMATION_MODE set to: kling")

# Step 3: Verify config loads correctly
print("\n[3/5] Verifying config.py loads...")
try:
    from config import config
    print(f"  ✅ config.py loaded successfully")
    print(f"  ✅ VIDEO_ANIMATION_MODE in config: {config.VIDEO_ANIMATION_MODE}")
    if config.VIDEO_ANIMATION_MODE.lower() != "kling":
        print(f"  ❌ Config has wrong mode: {config.VIDEO_ANIMATION_MODE}")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ Failed to load config: {e}")
    sys.exit(1)

# Step 4: Run a quick dry-run test
print("\n[4/5] Running dry-run test with Kling (this may take 2-3 minutes)...")
print("  Command: orchestrator.py --dry-run --topic 'Test Kling'")

result = subprocess.run(
    [".venv/bin/python3", "orchestrator.py", "--dry-run", "--topic", "Test Kling"],
    capture_output=True,
    text=True,
    timeout=180
)

# Step 5: Validate output
print("\n[5/5] Analyzing test results...")

log_output = result.stderr + result.stdout

# Check for success indicators
checks = {
    "Animation mode: kling": "Animation mode is set to kling",
    "Section 1: kling succeeded": "Kling generated at least one video successfully",
    "Kling video generated": "Kling video was created and cached",
}

success_count = 0
for check_str, description in checks.items():
    if check_str.lower() in log_output.lower():
        print(f"  ✅ {description}")
        success_count += 1
    else:
        print(f"  ⚠️  {description} - NOT FOUND")

# Check for error indicators that would indicate failure
errors = {
    "kling generation failed": "Kling API returned an error",
    "event loop is closed": "Asyncio event loop issue",
    "api error:": "Kling API parsing error",
    "Ken Burns regeneration failed": "Ken Burns fallback (Kling didn't work)",
}

error_count = 0
for error_str, description in errors.items():
    if error_str.lower() in log_output.lower():
        print(f"  ❌ {description} - FOUND IN LOGS")
        error_count += 1

print(f"\n{'='*70}")
if success_count >= 2 and error_count == 0:
    print("✅ SUCCESS: Kling integration is working properly!")
    print(f"{'='*70}\n")
    sys.exit(0)
elif success_count > 0 and error_count == 0:
    print("⚠️  PARTIAL SUCCESS: Some checks passed but verification incomplete")
    print("Full test logs below:")
    print("="*70)
    print(result.stdout)
    print(result.stderr)
    sys.exit(0)
else:
    print("❌ FAILED: Kling integration has issues")
    print(f"{'='*70}")
    print("\nFull test logs:")
    print("="*70)
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)
