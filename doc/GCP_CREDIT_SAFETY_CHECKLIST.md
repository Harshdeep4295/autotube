# GCP Credit Exhaustion Prevention Checklist

**Purpose:** Prevent the $270 credit burn that happened before. This checklist covers pre-deployment, daily monitoring, and emergency kill switches.

**Status:** Living document — update if you discover new risks or thresholds change.

---

## 1. PRE-DEPLOYMENT CHECKS (Before First Video)

**Timing:** Complete BEFORE you enable `VIDEO_ANIMATION_MODE=veo` in production.

### 1.1 Confirm Free Tier Quotas & Limits

- [ ] **Verify $300 free trial active**
  ```bash
  # Go to: https://console.cloud.google.com/billing/
  # Look for: "Free Trial Account" (NOT "Pay As You Go")
  # Expected: "$300.00" remaining
  ```

- [ ] **Check if trial has expired**
  - If created more than **12 months ago**, trial may have ended
  - After expiration, billing switches to pay-as-you-go (you'll be charged)
  - Fix: Create new account (see GCP_MIGRATION_GUIDE.md)

- [ ] **Confirm free tier quotas**
  ```bash
  # Veo is NOT on free tier — costs $0.10/second
  # Vertex AI API call quota: 100 calls/min (more than enough)
  # Cloud Storage: 5 GB free/month (caching videos is ~300MB/month — within quota)
  ```

- [ ] **Verify APIs are enabled (not quota-limited)**
  - Go to: https://console.cloud.google.com/apis/dashboard
  - Look for: **Vertex AI API** (should show "Enabled")
  - Look for: **Cloud Storage API** (should show "Enabled")
  - [ ] If either shows quota limit warnings, raise quota via IAM & Admin

### 1.2 Set Up Billing Alerts (CRITICAL)

**DO THIS FIRST.** These are your early warning system.

- [ ] **Set $50 budget alert** (first warning)
  1. Go to: https://console.cloud.google.com/billing/budgets
  2. Click **"+ CREATE BUDGET"**
  3. Fill in:
     - Name: `AutoTube-$50-warning`
     - Projects: Select your AutoTube project
     - Budget amount: `$50.00`
     - Alert threshold: `100%` of budget
  4. Click **"CREATE"**
  5. Add email notification: Your email address
  6. Click **"SAVE"**

- [ ] **Set $100 budget alert** (escalation)
  - Repeat above with `$100.00` and name `AutoTube-$100-escalation`

- [ ] **Set $200 budget alert** (critical threshold)
  - Repeat above with `$200.00` and name `AutoTube-$200-CRITICAL`

- [ ] **Enable billing notifications in Gmail**
  - Add GCP billing alerts to Gmail filters (don't mark as spam)
  - Set to: High priority / star

### 1.3 Configure Hard Spend Limits

**These prevent runaway costs if alerts are missed.**

- [ ] **Set up quotas in Google Cloud**
  1. Go to: https://console.cloud.google.com/iam-admin/quotas
  2. Filter: `Vertex AI API`
  3. Find: `video_generation_requests` quota
  4. Click it
  5. Set `Custom limit`: Based on your budget
     - Budget: $300 → Max 375 requests ($0.80/8-sec = 3.75 requests/dollar)
     - **Conservative:** Set to 300 requests (~$240)
  6. Click **"CHANGE QUOTA"**

- [ ] **Alternative: Shut off project if overspend detected**
  - Add to GitHub Actions: Pre-run cost check
  - If spending > $150, skip render job entirely
  - See Section 5 below

### 1.4 Test with --dry-run First (NO CHARGE)

- [ ] **Run local dry-run before enabling on GitHub Actions**
  ```bash
  cd /Users/harshdeepsingh/Projects/git_projects/autotube
  
  # This generates video but does NOT call Veo API
  VIDEO_ANIMATION_MODE=ken_burns python orchestrator.py --dry-run --topic "Test"
  # Expected: Video renders using free Ken Burns (no charges)
  ```

- [ ] **Run with Veo on local machine ONCE to verify setup**
  ```bash
  # This WILL charge $0.80 but confirms everything works
  # Only run this once locally before committing to GitHub Actions
  VIDEO_ANIMATION_MODE=veo python orchestrator.py --dry-run --topic "Test AI"
  
  # Expected output:
  # ✅ Submitting Veo generation: ...
  # ✅ Generation submitted: operations/...
  # ✅ Veo video generated: ... (cost ~$0.80)
  ```

- [ ] **Check GCS bucket for output**
  ```bash
  gsutil ls gs://autotube-veo-output-trial/veo_output/
  # Should list generated .mp4 file
  ```

### 1.5 Use Staging Environment First

- [ ] **Create separate staging project (optional but recommended)**
  - Create second GCP project: `autotube-staging`
  - Lower budget alert: $10
  - Run full pipeline there first for 1 week
  - Only switch to production after successful staging run

- [ ] **If using same project, create separate GCS bucket for testing**
  ```bash
  # Create: autotube-veo-output-staging (separate from production)
  # Use staging bucket for first week of runs
  gsutil mb -p YOUR_PROJECT_ID -l us-central1 gs://autotube-veo-output-staging
  ```

---

## 2. DURING SETUP (Configuration Validation)

### 2.1 Verify Config is Correct (Before Enabling Veo)

- [ ] **Check config.py defaults**
  ```python
  # File: /Users/harshdeepsingh/Projects/git_projects/autotube/config.py
  
  # ❌ WRONG (will burn credits):
  VIDEO_ANIMATION_MODE: str = field(
      default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "veo")  # BAD!
  )
  
  # ✅ RIGHT (safe default):
  VIDEO_ANIMATION_MODE: str = field(
      default_factory=lambda: os.getenv("VIDEO_ANIMATION_MODE", "ken_burns")  # SAFE
  )
  ```

- [ ] **Verify Ken Burns is the default locally**
  ```bash
  python3 -c "from config import config; print(f'Mode: {config.VIDEO_ANIMATION_MODE}')"
  # Expected: Mode: ken_burns (if VIDEO_ANIMATION_MODE not set)
  ```

- [ ] **Verify environment variables are set correctly**
  ```bash
  # Check GitHub Actions secrets/variables
  # Go to: Settings → Secrets and variables → Actions
  
  # Should exist:
  # ✓ GCP_PROJECT_ID (Variable)
  # ✓ GCP_GCS_BUCKET (Variable)
  # ✓ AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON (Secret)
  
  # Video animation mode should be:
  # ✓ VIDEO_ANIMATION_MODE=veo (if you want Veo)
  # OR
  # ✓ VIDEO_ANIMATION_MODE=ken_burns (if using free mode)
  ```

### 2.2 Cost Tracking Setup

- [ ] **Enable cost tracker in orchestrator.py**
  ```bash
  # Check that this exists in orchestrator.py:
  grep -n "GCPCostTracker" /Users/harshdeepsingh/Projects/git_projects/autotube/orchestrator.py
  # Should find import and usage
  ```

- [ ] **Verify logs capture cost estimates**
  ```bash
  # After running a test video, check logs:
  tail -f logs/pipeline_*.log | grep -i "cost\|spent\|remaining"
  
  # Expected output:
  # Veo fast: $0.80 | Spent: $0.80/300.00 (0.3%) | Remaining: $299.20
  ```

### 2.3 Fallback Mode is Enabled

- [ ] **Verify Ken Burns fallback exists in video_agent.py**
  ```bash
  grep -n "ken_burns\|fallback" /Users/harshdeepsingh/Projects/git_projects/autotube/agents/video_agent.py
  
  # Should see fallback logic for when Veo fails
  ```

- [ ] **Test fallback behavior**
  ```bash
  # Simulate Veo failure (comment out Veo code temporarily)
  # Run: python orchestrator.py --dry-run --topic "Test"
  # Should fall back to Ken Burns without error
  ```

---

## 3. DAILY MONITORING (Each Run)

### 3.1 Pre-Run Cost Check (Before Each Pipeline Execution)

**Add this to orchestrator.py if not present:**

```python
def check_gcp_budget_before_run():
    """Check budget before generating videos. Abort if threshold exceeded."""
    try:
        # Read last 10 runs from cost tracker
        tracker = GCPCostTracker()
        spent = tracker.spent
        remaining = 300.0 - spent
        
        if remaining < 10:
            logger.critical(f"🚨 CRITICAL: Only ${remaining:.2f} remaining!")
            logger.critical("Kill switch activated — aborting pipeline")
            sys.exit(1)
        
        if remaining < 50:
            logger.warning(f"⚠️  WARNING: Only ${remaining:.2f} remaining")
            logger.warning(f"Estimated: {tracker.estimate_remaining_videos()} more videos")
        
        logger.info(f"✅ Budget check passed: ${remaining:.2f} remaining")
        return True
        
    except Exception as e:
        logger.warning(f"Could not check budget: {e}")
        return True  # Continue if check fails (don't block)
```

### 3.2 Monitor Logs After Each Run

- [ ] **Check pipeline logs immediately after each run**
  ```bash
  # Get latest log file
  LATEST_LOG=$(ls -t logs/pipeline_*.log | head -1)
  
  # Look for cost estimates
  grep -i "cost\|spent\|veo\|remain" "$LATEST_LOG"
  
  # Example expected output:
  # Veo fast: $0.80 | Spent: $0.80/300.00 (0.3%) | Remaining: $299.20
  ```

- [ ] **Check for Veo API errors (may indicate quota/billing issues)**
  ```bash
  # Look for any Veo failures
  grep -i "veo\|generation failed\|timeout" "$LATEST_LOG"
  
  # If you see "No videos in response" repeatedly → Veo may be having issues
  # If you see "403 Forbidden" → Service account may lack permissions
  ```

### 3.3 Weekly GCP Console Review

**Every Monday morning (or after 7 days of running):**

- [ ] **Check GCP Billing Dashboard**
  1. Go to: https://console.cloud.google.com/billing/overview
  2. Look for:
     - Current month spend (should be < $50 if running only a few days)
     - Trend line (should be gradual, not spiking)
     - Top services (should be "Vertex AI" if using Veo)
  
- [ ] **Verify no unexpected charges**
  ```bash
  # Go to: https://console.cloud.google.com/billing/invoices
  # Look at: Detailed breakdown
  # Expected: Only "Generative AI" (Veo charges)
  # Unexpected: Compute Engine, App Engine, other services
  ```

- [ ] **Spot-check GCS bucket size**
  ```bash
  # Check how much storage is being used
  gsutil du -s gs://autotube-veo-output-trial/
  
  # Expected: < 1 GB (videos are ~50-100MB each)
  # If > 2 GB: Something is wrong, clean up:
  gsutil -m rm -r gs://autotube-veo-output-trial/veo_output/*
  ```

### 3.4 Daily Cost Verification Script

**Create and run this daily:**

```bash
#!/bin/bash
# File: check_gcp_daily.sh

echo "=== GCP Daily Cost Check ==="
echo "Date: $(date)"

# Check spending via logs
LATEST_LOG=$(ls -t logs/pipeline_*.log 2>/dev/null | head -1)
if [ -z "$LATEST_LOG" ]; then
    echo "No logs found yet"
    exit 0
fi

echo ""
echo "Latest run cost estimate:"
grep "Veo\|Spent\|Remaining" "$LATEST_LOG" | tail -5

echo ""
echo "Total videos generated (estimated):"
grep -c "Veo video generated" logs/pipeline_*.log 2>/dev/null || echo "0"

# Check if budget is low
ESTIMATED_REMAINING=$(grep "Remaining:" "$LATEST_LOG" | tail -1 | grep -oE '\$[0-9]+\.[0-9]+' | tail -1)
if [ -n "$ESTIMATED_REMAINING" ]; then
    echo ""
    echo "Current budget: $ESTIMATED_REMAINING"
    if [[ "$ESTIMATED_REMAINING" =~ \$([0-9]+) ]]; then
        REMAINING_NUM="${BASH_REMATCH[1]}"
        if [ "$REMAINING_NUM" -lt 50 ]; then
            echo "🚨 WARNING: Budget is low! Review spending immediately."
        fi
    fi
fi
```

**Run with:**
```bash
chmod +x check_gcp_daily.sh
./check_gcp_daily.sh
```

---

## 4. ESCALATION PROCEDURES (If Costs Spike)

### 4.1 Immediate Response (First Hour)

**If you see a spending alert or costs are higher than expected:**

- [ ] **DO NOT RUN ANOTHER PIPELINE RUN**
  - Disable GitHub Actions workflow immediately
  - Go to: https://github.com/YOUR_REPO/settings/actions
  - Click **"Disable actions"**

- [ ] **Identify the cause (5 minutes)**
  ```bash
  # Check last 3 logs for unusual activity
  for log in $(ls -t logs/pipeline_*.log | head -3); do
      echo "=== $log ==="
      grep -E "Veo|cost|error|timeout" "$log"
  done
  
  # Look for:
  # - Multiple Veo generation retries (indicates failures)
  # - Unexpected service charges (Compute Engine, App Engine, etc.)
  # - API errors (403, 500, quota exceeded)
  ```

- [ ] **Check GCS bucket for unexpected files**
  ```bash
  # Should only have /veo_output/ directory
  gsutil ls -r gs://autotube-veo-output-trial/ | head -20
  
  # If you see unknown directories/files, investigate
  ```

### 4.2 Diagnosis (Next 30 Minutes)

- [ ] **Check GCP Cost Analysis**
  1. Go to: https://console.cloud.google.com/billing/reports
  2. Group by: "Service"
  3. Look at: Last 24 hours
  4. Expected: Only "Vertex AI" charges
  5. Unexpected: Anything else

- [ ] **Review API requests**
  ```bash
  # Go to: https://console.cloud.google.com/monitoring/dashboards
  # Create custom dashboard for Vertex AI API
  # Look for: Request count spike, error rate spike
  ```

- [ ] **Check service account usage**
  1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
  2. Click: `autotube-veo-sa`
  3. Go to: **Activity** tab
  4. Look for: Unusual API calls

### 4.3 Recovery (Next Hour)

**If cause is identified:**

- [ ] **For runaway Veo calls:**
  - Set `VIDEO_ANIMATION_MODE=ken_burns` in GitHub Variables
  - This will prevent further Veo API calls
  - Restart pipeline in dry-run mode only

- [ ] **For unexpected service charges:**
  - Disable the problematic API
  - Go to: https://console.cloud.google.com/apis/dashboard
  - Click on the service
  - Click **"DISABLE"**

- [ ] **For quota exhaustion:**
  - Check quota limits: https://console.cloud.google.com/iam-admin/quotas
  - Reduce daily run count if needed
  - Go to GitHub Actions and modify cron schedule

- [ ] **For storage overages:**
  - Delete old videos from GCS
  - ```bash
  gsutil -m rm -r gs://autotube-veo-output-trial/veo_output/*
    ```

---

## 5. KILL SWITCHES (Disable Expensive Services Immediately)

### 5.1 Emergency: Stop All Spending NOW

**Do this if costs are spiraling:**

```bash
# Option 1: Disable GitHub Actions immediately
# Go to: https://github.com/YOUR_REPO/settings/actions
# Click: "Disable actions"

# Option 2: Disable Vertex AI API (MOST DIRECT)
# Go to: https://console.cloud.google.com/apis/api/aiplatform.googleapis.com
# Click: "DISABLE" button

# Option 3: Disable entire GCP project (nuclear option)
# Go to: https://console.cloud.google.com/iam-admin/projects
# Click on your project
# Click: "SHUT DOWN"
```

### 5.2 Disable Veo (Switch to Ken Burns)

**Temporary workaround if Veo is problematic:**

- [ ] **In GitHub Variables (if using GitHub Actions):**
  1. Go to: Settings → Secrets and variables → Variables
  2. Find: `VIDEO_ANIMATION_MODE`
  3. Change value from `veo` to `ken_burns`
  4. Save

- [ ] **In .env (if running locally):**
  ```bash
  # Change from:
  VIDEO_ANIMATION_MODE=veo
  
  # To:
  VIDEO_ANIMATION_MODE=ken_burns
  
  # Save and test:
  python orchestrator.py --dry-run --topic "Test"
  ```

### 5.3 Reduce Run Frequency

**If you want to limit spending while keeping the system live:**

- [ ] **Reduce from 4 runs/day to 1 run/day:**
  1. Go to: https://github.com/YOUR_REPO/blob/main/.github/workflows/daily_pipeline.yml
  2. Find the `schedule:` section
  3. Delete 3 of the 4 cron entries
  4. Keep only one: `cron: '00 11 * * *'` (once daily)
  5. Commit and push

- [ ] **Or disable specific runs:**
  ```yaml
  # Comment out the schedule entirely:
  # schedule:
  #   - cron: '00 23 * * *'
  #   - cron: '30 5  * * *'
  #   - cron: '00 11 * * *'
  #   - cron: '30 17 * * *'
  
  # Keep only manual trigger:
  on:
    workflow_dispatch:
  ```

---

## 6. BUDGET LIMITS & HARD CAPS

### 6.1 Set Quota Limits in GCP

**These prevent overcharges even if alerts are missed:**

- [ ] **Vertex AI API quotas**
  1. Go to: https://console.cloud.google.com/iam-admin/quotas
  2. Filter: `aiplatform` (Vertex AI)
  3. Find: `video_generation_requests` per minute/day
  4. Click it and set **Custom limit**
  5. Calculate safe limit:
     - Each Veo generation = $0.80 (8 seconds)
     - Budget = $300
     - Safe max = 300 / 0.80 = 375 requests
     - Conservative = 300 requests (80% of budget)
     - **Set custom limit to: 300 requests/day**

- [ ] **Cloud Storage quotas**
  1. Go to: https://console.cloud.google.com/iam-admin/quotas
  2. Filter: `storage` (Cloud Storage)
  3. Find: `storage_bytes_per_project_per_month`
  4. Set to: 10 GB (more than enough for video caching)

### 6.2 Set Up Project-Level Spend Limit

**GCP can automatically disable services when spending limit is hit:**

- [ ] **Configure billing account spend limit**
  1. Go to: https://console.cloud.google.com/billing/budgets
  2. Create budget: `AutoTube-Hard-Cap-$250`
  3. Set alert threshold: `100%`
  4. Add custom action: **"Close billing account" (if available)**
  5. Or set threshold to `90%` and manually review

### 6.3 Monthly Spend Tracking

**Create a simple tracking file:**

```json
{
  "file": "data/gcp_spending.json",
  "structure": {
    "month": "2026-04",
    "budget": 300.00,
    "spent": 15.50,
    "remaining": 284.50,
    "videos_generated": 19,
    "cost_per_video": 0.82,
    "last_checked": "2026-04-26T12:30:00Z"
  }
}
```

**Update weekly:**
```bash
python3 << 'EOF'
import json
from datetime import datetime

tracking = {
    "month": datetime.now().strftime("%Y-%m"),
    "budget": 300.00,
    "spent": 15.50,  # Update from GCP Console
    "remaining": 284.50,
    "videos_generated": 19,  # Count from logs
    "cost_per_video": 0.82,
    "last_checked": datetime.now().isoformat()
}

with open("data/gcp_spending.json", "w") as f:
    json.dump(tracking, f, indent=2)

print(f"Budget: ${tracking['budget']:.2f}")
print(f"Spent: ${tracking['spent']:.2f} ({tracking['spent']/tracking['budget']*100:.1f}%)")
print(f"Remaining: ${tracking['remaining']:.2f}")
print(f"Videos: {tracking['videos_generated']} @ ${tracking['cost_per_video']:.2f} each")
EOF
```

---

## 7. DAILY COST VERIFICATION STEPS (Checklist)

**Do this every morning or after each pipeline run:**

### 7.1 Check Pipeline Logs (5 minutes)

- [ ] **Get latest log**
  ```bash
  LATEST_LOG=$(ls -t logs/pipeline_*.log 2>/dev/null | head -1)
  echo "Latest log: $LATEST_LOG"
  ```

- [ ] **Extract cost info**
  ```bash
  grep -E "Spent:|Remaining:|cost|videos generated" "$LATEST_LOG"
  ```

- [ ] **Expected output example**
  ```
  Veo fast: $0.80 | Spent: $5.60/300.00 (1.9%) | Remaining: $294.40
  Veo video generated: veo_abc123.mp4 (48.2MB, 120s, ~$0.80)
  Remaining videos estimable: 367
  ```

### 7.2 GitHub Actions Status (2 minutes)

- [ ] **Check last workflow run**
  1. Go to: https://github.com/YOUR_REPO/actions
  2. Look at: Latest run in `Daily Pipeline`
  3. Status should be: ✅ Success or ⏭️ Skipped (if queue full)
  4. NOT: ❌ Failed (investigate if failed)

- [ ] **If failed, check error message**
  ```bash
  # Go to Actions → Latest run → Logs
  # Look for keywords:
  # - "Veo" or "generation" → video generation issue
  # - "YouTube" → upload issue
  # - "GCS" or "bucket" → storage issue
  ```

### 7.3 GCP Console Spot Check (3 minutes)

- [ ] **Open GCP Billing Dashboard**
  1. Go to: https://console.cloud.google.com/billing/overview
  2. Look for:
     - Month-to-date spend (top left)
     - Chart should show gradual increase
     - Top services (should be "Vertex AI" ONLY)

- [ ] **Red flags to watch for**
  - Sudden spike in spending
  - Services you didn't enable (Compute Engine, Kubernetes, etc.)
  - High storage costs (should be < $1/month)

### 7.4 Email Alerts (passive — check Gmail)

- [ ] **Check Gmail for budget alerts**
  - Should come from: `billing-noreply@google.com`
  - Filter: "Budget alert for AutoTube"
  - If you see: "$50 threshold reached" → Reduce run frequency
  - If you see: "$100 threshold reached" → Stop pipeline immediately

---

## 8. ALL SERVICES THAT COULD INCUR CHARGES

### 8.1 Services That COST Money

| Service | Cost | How AutoTube Uses | How to Keep Free |
|---------|------|-------------------|------------------|
| **Vertex AI - Veo** | $0.10/second | Video generation | **DISABLED by default** — use Ken Burns instead |
| **Cloud Storage (GCS)** | $0.02/GB/month after 5GB | Backup & caching videos | Clear old videos monthly, keep < 2GB |
| **Vertex AI API calls** | FREE (100/min quota) | API requests | Already free, no action needed |

### 8.2 Services That Should Be DISABLED (Stay Free)

| Service | Cost | Why Disabled | How to Verify |
|---------|------|-------------|---|
| Compute Engine | $0.05+/hour | Not needed — GitHub Actions runs code | Should NOT appear in cost breakdown |
| Kubernetes Engine | $0.15-$1+/hour | Not used | Should NOT appear in cost breakdown |
| App Engine | Variable | Not used | Should NOT appear in cost breakdown |
| BigQuery | $0.025/GB queried | Not used | Should NOT appear in cost breakdown |
| Cloud Run | $0.00002/request | Not used | Should NOT appear in cost breakdown |

**Verification:**
```bash
# Check enabled APIs
# Go to: https://console.cloud.google.com/apis/dashboard
# Should ONLY show:
# ✓ Vertex AI API (enabled)
# ✓ Cloud Storage API (enabled)

# Should NOT show (disable if present):
# ✗ Compute Engine API
# ✗ Kubernetes Engine API
# ✗ App Engine
# ✗ BigQuery API
```

### 8.3 How to Stay 100% Free (Ken Burns Path)

**If you use `VIDEO_ANIMATION_MODE=ken_burns`, costs are:**

| Component | Cost | How It Works |
|-----------|------|-------------|
| **AI Images** | FREE | Pollinations.ai (no auth required, free API) |
| **FFmpeg zoom/pan** | FREE | Local processing (included in GitHub Actions) |
| **Pexels B-roll** | FREE | Pexels API (free tier: 200 req/hour) |
| **edge-tts voiceover** | FREE | Microsoft Edge API (free tier) |
| **Cloud Storage** | FREE (under 5GB) | Local caching only, no cloud backup |
| **YouTube Upload** | FREE | YouTube API v3 (free tier, unlimited) |
| **Total Monthly Cost** | **$0** | Completely free ✓ |

**To verify Ken Burns is running:**
```bash
# Check logs for Ken Burns generation
grep -i "ken_burns\|ffmpeg\|zoompan" logs/pipeline_*.log

# Should see:
# "Ken Burns effect applied"
# "FFmpeg zoompan"
# "Video rendered (Ken Burns)"
```

### 8.4 How to Keep Veo Mode Affordable

**If you want Veo (native video), keep costs low with these rules:**

| Rule | Cost Impact | Action |
|------|------------|--------|
| **Reduce run frequency** | 4x daily → 1x daily | $3.20/day → $0.80/day (~$240/month) |
| **Use Ken Burns fallback** | Limits retries to 1 | Saves $0.80 per failed request |
| **Monitor daily spend** | Early detection | Pause runs if > $10/day |
| **Cache generated videos** | Reuse existing | Save $0.80 per cached hit |
| **Use service account quotas** | Hard cap | Prevents > 300 requests/day |

**Safe Veo configuration:**
```python
# In config.py
VIDEO_ANIMATION_MODE = "veo"  # High quality
PEXELS_CLIPS_PER_VIDEO = 1    # Reduce from 6 to 1 per section (saves retries)
# Run only 1x daily (not 4x) — set in GitHub Actions cron
# Budget alert at $150 (50% of $300)
```

**Cost projections:**
```
Daily run (1x): 1 video × $0.80 = $0.80/day
Weekly: $5.60
Monthly: ~$24
6 months: ~$144 (safe, within $300 budget)
```

---

## 9. TROUBLESHOOTING: Common Cost Escalation Scenarios

### Scenario A: "Veo is generating but costs went from $1 to $50 in 1 day"

**Likely cause:** Retry loop or multiple submissions

**Debug:**
```bash
# Check logs for Veo submissions
grep "Submitting Veo" logs/pipeline_*.log | wc -l
# If > 4, something submitted video 10+ times (BAD)

# Check for retry loops
grep "Veo generation failed\|retrying" logs/pipeline_*.log | wc -l
# If high, Veo is failing repeatedly
```

**Fix:**
1. Set `VIDEO_ANIMATION_MODE=ken_burns` immediately
2. Review `gcp_veo_agent.py` for retry logic (should be 1 attempt max)
3. Check visual_queries in script (may be causing Veo failures)

### Scenario B: "I see charges for services I didn't enable"

**Likely cause:** Accidental API enablement or orphaned resources

**Debug:**
```bash
# List all enabled APIs
# Go to: https://console.cloud.google.com/apis/dashboard
# Look for: Any API you didn't explicitly enable

# Check for lingering VMs or containers
# Go to: https://console.cloud.google.com/compute/instances
# Should be empty (we don't use Compute Engine)
```

**Fix:**
1. Disable unknown APIs immediately
2. Delete any lingering resources
3. Check billing report for the service name
4. File Google Cloud support ticket if you see charges you can't explain

### Scenario C: "GCS bucket is huge, eating into quota"

**Likely cause:** Videos not being deleted after upload

**Debug:**
```bash
# Check bucket size
gsutil du -s gs://autotube-veo-output-trial/
# If > 2GB, something is wrong

# List videos
gsutil ls -r gs://autotube-veo-output-trial/veo_output/ | head -20
```

**Fix:**
```bash
# Delete old videos (safe to delete — they're cached locally)
gsutil -m rm -r gs://autotube-veo-output-trial/veo_output/*

# Verify size dropped
gsutil du -s gs://autotube-veo-output-trial/
```

---

## 10. REFERENCE: Cost Breakdown Example

**After generating 10 videos with Veo:**

```
Budget: $300.00
Spent: $8.00 (10 videos × $0.80 each)
Remaining: $292.00 (97.3% budget remaining)

Cost breakdown:
- Vertex AI Veo: $8.00
- Cloud Storage: < $0.01 (negligible)
- Vertex AI API: $0.00 (free quota)
- Total: $8.00

Run info:
- Videos generated: 10
- Cost per video: $0.80
- Estimated remaining: 365 more videos
- Burn rate: ~$0.80/day (at 1 video/day)
```

---

## 11. QUICK REFERENCE CARD (Laminate This)

```
BUDGET: $300.00 (free trial)
COST PER VIDEO: $0.80 (Veo) or $0.00 (Ken Burns)

THRESHOLDS:
☐ $50 spent → Check logs
☐ $100 spent → Review GCP Console
☐ $200 spent → Reduce run frequency
☐ $250 spent → Stop pipeline

KILL SWITCHES (use if cost spike):
1. Disable GitHub Actions
2. Set VIDEO_ANIMATION_MODE=ken_burns
3. Disable Vertex AI API
4. Contact Google Cloud support

DAILY CHECKLIST (5 minutes):
☐ Check pipeline logs for cost estimate
☐ Verify GitHub Actions ran
☐ Spot-check GCP Billing dashboard
☐ Check Gmail for budget alerts

GCP LINKS (bookmark these):
- Billing: console.cloud.google.com/billing/overview
- Budgets: console.cloud.google.com/billing/budgets
- Quotas: console.cloud.google.com/iam-admin/quotas
- Enabled APIs: console.cloud.google.com/apis/dashboard
```

---

## 12. FEEDBACK & UPDATES

**If you discover new risks or thresholds:**
1. Update this checklist
2. Add entry to Section 9 (Troubleshooting)
3. Commit to repo: `chore: update GCP safety checklist with [new finding]`
4. Share with team

**Last updated:** 2026-04-26
**Status:** ACTIVE — follow religiously
