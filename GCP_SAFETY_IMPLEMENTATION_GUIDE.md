# GCP Safety Implementation Guide

**Goal:** Implement the GCP Credit Safety Checklist in 90 minutes. This guide walks through each section with exact click-by-click instructions and code snippets.

---

## TIME ESTIMATE BY SECTION

| Section | Time | Effort | Critical? |
|---------|------|--------|-----------|
| 1.1-1.2: Billing alerts | 15 min | Easy | ✓ YES — DO FIRST |
| 1.3: Quota limits | 10 min | Medium | ✓ YES — Second |
| 1.4-1.5: Test with dry-run | 20 min | Medium | Recommended |
| 2.1-2.3: Config validation | 10 min | Easy | ✓ YES |
| 3.1-3.4: Daily monitoring | 10 min | Medium | Ongoing |
| 4.1-4.3: Escalation setup | 5 min | Easy | For emergencies |
| 5.1-5.3: Kill switches | 5 min | Easy | For emergencies |

**Total: ~90 minutes first-time, then ~5 minutes daily.**

---

## QUICK START (Do This First — 30 Minutes)

### STEP 1: Enable Billing Alerts (10 minutes)

**Go here:** https://console.cloud.google.com/billing/budgets

1. Click **"+ CREATE BUDGET"**
2. Fill in:
   - **Budget name:** `AutoTube-$50-first-warning`
   - **Projects:** Select your AutoTube project
   - **Budget amount:** `50.00` (USD)
   - **Budget period:** `Monthly`
3. Under **Alert threshold**, type: `100`
4. Under **Notifications**, select your email
5. Click **"CREATE"**

**Repeat for $100 and $200 thresholds** (creates 3 alerts total)

**Verify:**
```bash
# After creating, you should see 3 budgets:
# - AutoTube-$50-first-warning
# - AutoTube-$100-escalation
# - AutoTube-$200-CRITICAL
```

### STEP 2: Set Quota Limits (10 minutes)

**Go here:** https://console.cloud.google.com/iam-admin/quotas

1. In the filter, search: `video_generation`
2. Look for: **"Video generation requests per minute"** or similar
3. Click on it
4. Click **"Edit quota"** (pencil icon)
5. Set custom limit to: `300` (requests/day)
   - Calculation: $300 budget ÷ $0.80 per video = 375 max, we set 300 for safety (80%)
6. Click **"NEXT"**
7. Fill in: `This is for AutoTube YouTube automation`
8. Click **"SUBMIT REQUEST"**

**You should get approval within minutes (usually instant).**

### STEP 3: Verify Config is Safe (10 minutes)

**In your project root:**

```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube

# Check 1: Default animation mode should be Ken Burns (safe)
grep "VIDEO_ANIMATION_MODE" config.py
# Expected: default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "ken_burns")
#           NOT: "veo" (that would auto-enable Veo)

# Check 2: Environment variable
echo $VIDEO_ANIMATION_MODE
# Expected: (empty, or "ken_burns")
# NOT: "veo"

# Check 3: Cost tracker exists
test -f agents/gcp_cost_tracker.py && echo "✓ Cost tracker found" || echo "✗ Missing!"

# Check 4: GitHub Actions has correct vars
# Go to: https://github.com/YOUR_USERNAME/autotube/settings/variables
# Should see: GCP_PROJECT_ID, GCP_GCS_BUCKET
# Should NOT see VIDEO_ANIMATION_MODE set to "veo" yet
```

---

## SECTION 1: PRE-DEPLOYMENT CHECKS (Detailed)

### 1.1 Confirm Free Trial Status

**Instructions:**

1. Open: https://console.cloud.google.com/billing/
2. Look at top-left for: **"Free Trial Account"** or **"Pay as you go"**
3. Check remaining credit:
   - Should show: **"$300.00 remaining"** or similar
   - Should NOT show: "Expired" or "No credits"

**If trial is expired:**
```bash
# Follow GCP_MIGRATION_GUIDE.md to create new account
# Then update: .env and GitHub Secrets with new project ID
```

**If credits look wrong:**
- Contact Google Cloud support: https://cloud.google.com/support
- Reference: Your GCP account ID (found in billing settings)

### 1.2 Verify APIs are Enabled

**Instructions:**

1. Open: https://console.cloud.google.com/apis/dashboard
2. Look for these two APIs:

**API 1: Vertex AI API**
```bash
# Should show: "Enabled" (blue checkmark)
# If shows: "Disabled", click it and click "ENABLE"
# Wait 2-3 minutes for activation
```

**API 2: Cloud Storage API**
```bash
# Should show: "Enabled" (blue checkmark)
# If shows: "Disabled", click it and click "ENABLE"
# Wait 2-3 minutes for activation
```

**Verify both are enabled:**
```bash
# Go to: APIs & Services → Enabled APIs
# Search: "Vertex AI"
# Search: "Cloud Storage"
# Both should be in the list
```

### 1.3-1.4: Test Dry Run (First Time Only)

**This is safe — costs $0, generates video without Veo:**

```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube

# Make sure you're using Ken Burns (free)
export VIDEO_ANIMATION_MODE=ken_burns

# Run a dry-run (no charges)
python orchestrator.py --dry-run --topic "Test Topic"

# Expected output:
# ✅ Script generated
# ✅ Voice synthesized
# ✅ Ken Burns video rendered (no Veo charge)
# ✅ Thumbnail created
# File saved to: outputs/*/video.mp4
```

**If successful:**
- Video should be in `outputs/` folder
- Check logs: `tail -f logs/pipeline_*.log`
- Should see cost tracker at bottom: `Remaining: $300.00`

---

## SECTION 2: CONFIGURATION VALIDATION (Detailed)

### 2.1 Audit config.py

**File:** `/Users/harshdeepsingh/Projects/git_projects/autotube/config.py`

**Critical check — make sure Ken Burns is DEFAULT:**

```python
# ❌ BAD (will charge immediately):
VIDEO_ANIMATION_MODE: str = field(
    default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "veo")
)

# ✅ GOOD (safe default):
VIDEO_ANIMATION_MODE: str = field(
    default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "ken_burns")
)
```

**To verify current config:**
```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube
python3 -c "from config import config; print(f'Default mode: {config.VIDEO_ANIMATION_MODE}')"

# Expected output: Default mode: ken_burns
# If you see: Default mode: veo ← CHANGE IT!
```

**If it says "veo", edit config.py:**
1. Open: `config.py`
2. Find line with: `VIDEO_ANIMATION_MODE`
3. Change: `default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "veo")`
4. To: `default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "ken_burns")`
5. Save and test again

### 2.2 Verify GitHub Actions Variables

**Go to:** https://github.com/YOUR_USERNAME/autotube/settings/variables

**Check these Variables exist:**
- [ ] `GCP_PROJECT_ID` = `autotube-trial-2-abc123` (or your project ID)
- [ ] `GCP_GCS_BUCKET` = `autotube-veo-output-trial` (or your bucket name)
- [ ] `VIDEO_ANIMATION_MODE` = (should be EMPTY or "ken_burns", NOT "veo" yet)

**If VIDEO_ANIMATION_MODE is set to "veo":**
1. Click on it
2. Change value to: `ken_burns`
3. Click **"Update variable"**

### 2.3 Enable Cost Tracking in Logs

**File:** `/Users/harshdeepsingh/Projects/git_projects/autotube/orchestrator.py`

**Verify this code exists near the top:**

```python
from agents.gcp_cost_tracker import GCPCostTracker

class Orchestrator:
    def __init__(self, dry_run: bool = False):
        # ... other init code ...
        self.cost_tracker = GCPCostTracker(initial_credits=300.0)
```

**And near end of run:**

```python
# After rendering each video:
if config.VIDEO_ANIMATION_MODE == "veo":
    self.cost_tracker.log_veo_generation(duration_seconds=8)
    
# At end of pipeline:
print(self.cost_tracker.summary())
```

**If missing, add it manually or contact support.**

---

## SECTION 3: DAILY MONITORING (Set Up Now)

### 3.1 Create Daily Cost Check Script

**Create file:** `/Users/harshdeepsingh/Projects/git_projects/autotube/check_gcp_daily.sh`

```bash
#!/bin/bash
# Daily GCP cost check — run every morning

echo "=== GCP Daily Cost Check ==="
echo "Date: $(date)"

# Get latest log
LATEST_LOG=$(ls -t logs/pipeline_*.log 2>/dev/null | head -1)
if [ -z "$LATEST_LOG" ]; then
    echo "No pipeline logs found yet"
    exit 0
fi

echo ""
echo "Latest run:"
echo "File: $LATEST_LOG"

# Extract cost estimate
echo ""
echo "Cost estimate:"
grep "Veo\|Spent\|Remaining" "$LATEST_LOG" | tail -3

# Count videos generated
TOTAL_VIDEOS=$(grep -c "Veo video generated\|video rendered successfully" logs/pipeline_*.log 2>/dev/null || echo "0")
echo ""
echo "Total videos generated: $TOTAL_VIDEOS"

# Estimate remaining
if grep -q "Remaining:" "$LATEST_LOG"; then
    REMAINING=$(grep "Remaining:" "$LATEST_LOG" | tail -1 | grep -oE '\$[0-9.]+' | tail -1)
    echo "Current budget remaining: $REMAINING"
    
    # Alert if low
    if [[ "$REMAINING" =~ \$([0-9]+) ]]; then
        NUM="${BASH_REMATCH[1]}"
        if [ "$NUM" -lt 50 ]; then
            echo ""
            echo "🚨 WARNING: Budget is getting low ($REMAINING remaining)"
            echo "Review spending at: https://console.cloud.google.com/billing/overview"
        fi
    fi
fi
```

**Make it executable:**
```bash
chmod +x /Users/harshdeepsingh/Projects/git_projects/autotube/check_gcp_daily.sh
```

**Test it:**
```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube
./check_gcp_daily.sh
```

### 3.2 Schedule Daily Check (Optional)

**Add to crontab to run every morning at 8 AM:**

```bash
# Open crontab editor
crontab -e

# Add this line:
0 8 * * * cd /Users/harshdeepsingh/Projects/git_projects/autotube && ./check_gcp_daily.sh >> logs/daily_check.log 2>&1
```

**Verify it's scheduled:**
```bash
crontab -l | grep check_gcp
```

---

## SECTION 4: EMERGENCY PROCEDURES (Set Up Kill Switches)

### 4.1 Create Emergency Disable Script

**Create file:** `/Users/harshdeepsingh/Projects/git_projects/autotube/EMERGENCY_DISABLE.sh`

```bash
#!/bin/bash
# EMERGENCY: Disable expensive services immediately
# Use if costs are spiking unexpectedly

set -e

echo "🚨 EMERGENCY GCP DISABLE 🚨"
echo "This will disable Veo and pause GitHub Actions"
echo ""
echo "About to disable:"
echo "1. Set VIDEO_ANIMATION_MODE to 'ken_burns' (stop Veo charges)"
echo "2. Disable GitHub Actions workflow"
echo ""
read -p "Continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted"
    exit 0
fi

echo ""
echo "Step 1: Updating .env to disable Veo..."
sed -i '' 's/VIDEO_ANIMATION_MODE=veo/VIDEO_ANIMATION_MODE=ken_burns/' .env
echo "✓ .env updated: VIDEO_ANIMATION_MODE=ken_burns"

echo ""
echo "Step 2: Instructions to disable GitHub Actions:"
echo "1. Go to: https://github.com/YOUR_USERNAME/autotube/settings/actions"
echo "2. Scroll down to 'Actions default permissions'"
echo "3. Select: 'Disable all'"
echo "4. Or go to Actions tab and click 'Disable workflow' on daily_pipeline.yml"
echo ""
echo "🛑 Veo is now disabled locally"
echo "⚠️  You must manually disable GitHub Actions in the GitHub UI"
```

**Make it executable:**
```bash
chmod +x /Users/harshdeepsingh/Projects/git_projects/autotube/EMERGENCY_DISABLE.sh
```

**To use in emergency:**
```bash
./EMERGENCY_DISABLE.sh
```

---

## SECTION 5: REFERENCE COMMANDS (Bookmark These)

### Frequently Used Commands

```bash
# Check current spending estimate
grep -i "remaining\|spent" logs/pipeline_*.log | tail -5

# Count videos generated with Veo
grep -c "Veo video generated" logs/pipeline_*.log

# Check latest error
tail -50 logs/pipeline_*.log | grep -i "error\|failed\|exception"

# Check GCS bucket size
gsutil du -s gs://autotube-veo-output-trial/

# List all files in GCS
gsutil ls -r gs://autotube-veo-output-trial/ | head -20

# Clear GCS bucket (if needed)
gsutil -m rm -r gs://autotube-veo-output-trial/veo_output/*

# Verify Veo API is working
curl -X POST https://api.cloud.google.com/vertex/v1/video:generate

# Check if GCP credentials are valid
python3 << 'EOF'
import os
from google.oauth2 import service_account
import json

sa_json = os.getenv("AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON")
if not sa_json:
    print("No credentials found")
else:
    try:
        sa_dict = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(sa_dict)
        print(f"✓ Credentials valid for: {sa_dict.get('client_email')}")
    except Exception as e:
        print(f"✗ Credentials invalid: {e}")
EOF
```

---

## SECTION 6: VERIFICATION CHECKLIST

**Before enabling Veo in production, verify all of these:**

- [ ] **Billing alerts set up**
  - [ ] $50 alert created
  - [ ] $100 alert created
  - [ ] $200 alert created
  - [ ] All emails configured

- [ ] **Quota limits set**
  - [ ] Vertex AI API quota set to 300 requests/day
  - [ ] Cloud Storage quota set appropriately

- [ ] **Config safe**
  - [ ] config.py defaults to Ken Burns (not Veo)
  - [ ] GitHub Variables set correctly
  - [ ] Cost tracker imported and used

- [ ] **Tested locally**
  - [ ] Dry run successful (with Ken Burns)
  - [ ] Logs show cost tracking
  - [ ] GCS bucket is accessible

- [ ] **Monitoring set up**
  - [ ] Daily check script created and tested
  - [ ] Understand how to read logs
  - [ ] Know how to check GCP Console

- [ ] **Kill switches ready**
  - [ ] Know how to disable GitHub Actions
  - [ ] EMERGENCY_DISABLE.sh created
  - [ ] Know how to disable Vertex AI API

---

## SECTION 7: WHEN TO ENABLE VEO

**Only enable Veo (native video) AFTER you've completed everything above.**

**To enable Veo:**

1. **In GitHub Variables:** Set `VIDEO_ANIMATION_MODE=veo`
2. **Or in .env (local):** Set `VIDEO_ANIMATION_MODE=veo`
3. **Monitor closely:** First day, run only 1 video (not 4)
4. **Check budget:** After each run, verify cost estimate
5. **Scale slowly:** After 1 week with no surprises, increase frequency

---

## TROUBLESHOOTING

### "I can't find the Billing Alerts page"

**Solution:**
1. Go to: https://console.cloud.google.com/
2. Click hamburger menu (≡) top-left
3. Find: **"Billing"**
4. Click it
5. In left sidebar, click: **"Budgets"**

### "Veo API returns 403 Forbidden"

**Likely cause:** Service account lacks `Vertex AI User` role

**Fix:**
1. Go to: https://console.cloud.google.com/iam-admin/iam
2. Find service account: `autotube-veo-sa@...`
3. Click it
4. Click **"EDIT"**
5. Add role: `Vertex AI User` (search for it)
6. Click **"SAVE"**

### "GCS bucket not found"

**Likely cause:** Bucket name mismatch in env vars

**Fix:**
```bash
# Check what's in .env
grep GCP_GCS_BUCKET .env

# List your actual buckets
gsutil ls

# Make sure they match
# If not, update .env with correct bucket name
```

### "I don't see cost estimates in logs"

**Likely cause:** Cost tracker not being called

**Fix:**
1. Check orchestrator.py has: `from agents.gcp_cost_tracker import GCPCostTracker`
2. Check cost tracker is initialized: `self.cost_tracker = GCPCostTracker()`
3. Check logs are being written after each video
4. Run a test: `python orchestrator.py --dry-run --topic "Test"`

---

## FINAL CHECKLIST (Before Going Live)

- [ ] Billing alerts are set up and verified
- [ ] Quota limits are configured
- [ ] config.py defaults to Ken Burns
- [ ] Dry run test was successful
- [ ] Daily monitoring script is ready
- [ ] EMERGENCY_DISABLE script is ready
- [ ] GitHub Actions workflow is configured
- [ ] I understand how to check GCP spending
- [ ] I know how to disable services if costs spike
- [ ] I've bookmarked the GCP Console links

**You are now safe to enable Veo (or keep using Ken Burns for $0/month).**

---

**Questions?** Check `GCP_CREDIT_SAFETY_CHECKLIST.md` for detailed guidance.

**Last updated:** 2026-04-26
