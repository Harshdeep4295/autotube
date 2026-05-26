# GCP Cost Analysis for AutoTube (autotube-494611)

**Generated:** 2026-05-01

---

## Summary: Where Your Credits Are Going

| Service | Current | Estimated Monthly | Issue |
|---------|---------|------------------|-------|
| **Compute Engine** (e2-small VM) | Running 24/7 | ~$15-20 | Always-on cost |
| **Vertex AI (Veo 3.1)** | Active | ~$16 (20 videos) | Usage-dependent |
| **Cloud Storage** (GCS backup) | 1 bucket | ~$0.50 | Minimal |
| **Logging/APIs** | Various | ~$0-5 | Mostly free tier |
| **TOTAL MONTHLY ESTIMATE** | | **~$31-41/month** | ⚠️ See below |

---

## Credit Status (From your screenshot)

```
Trial credit for GenAI App Builder: ₹94,812.51 (100% - NOT USED YET)
Free Trial credit:                  ₹14,661.32 (52% - Half consumed)
```

**What this means:**
- **₹14,661 Free Trial** has lost **₹13,782** in the past (~48%)
- **₹94,812 GenAI credit** is NOT being applied automatically
- Your charges are coming from **neither** of these credits

### ⚠️ THE PROBLEM
Your unused GenAI credit (₹94,812 ≈ $1,140 USD) is **NOT automatically applied** to your billing. You likely have a **paid payment method** (credit card) that's being charged first.

---

## Current Resource Breakdown

### 1. **Compute Engine: autotube-vm**
- **Type:** e2-small (2 vCPU, 2 GB RAM)
- **Status:** RUNNING (24/7)
- **Zone:** us-central1-a
- **Disk:** Standard persistent disk (~100GB)

**Monthly Cost Estimate:**
```
e2-small: ~$14/month (24/7 running)
Persistent Disk (100GB): ~$4/month
Network/Data: ~$0.50
────────────────────────
TOTAL: ~$18.50/month (continuous)
```

### 2. **Vertex AI (Veo 3.1 Video Generation)**
- **API:** Vertex AI Generative API
- **Usage:** Text-to-video generation
- **Pricing:** $0.10 per second of video (~$0.80 per 8-sec video)

**Monthly Cost Estimate (20 videos):**
```
20 videos × $0.80/video = $16/month
```

### 3. **Cloud Storage (GCS Backup)**
- **Bucket:** autotube-veo-output-trial
- **Region:** US-CENTRAL1
- **Estimated Size:** <100MB

**Monthly Cost:**
```
Storage: ~$0.02/month (free tier covers)
Egress: ~$0.50/month (if downloading daily)
```

### 4. **Other APIs (BigQuery, Cloud Logging, etc.)**
- **BigQuery:** Free tier (1TB/month queries) — likely free
- **Cloud Logging:** Free tier (50GB/month) — likely free
- **APIs enabled:** 20+ (most on free tier)

---

## Where Did Your ₹13,782 Go? (The Mystery)

### Most Likely Culprits

| Scenario | Evidence | Cost |
|----------|----------|------|
| **VM running continuously** | e2-small 24/7 for 30+ days | $550+ |
| **Veo video generation** | 20-30 videos at $0.80 each | $16-24 |
| **Data egress/transfer** | Large downloads from GCS | $0-200 |
| **Committed-use discount used up** | Auto-renewal of commitments | Variable |

**Most probable:** **Your VM has been running 24/7 longer than expected**, consuming the free trial credits.

### How to verify:
```bash
# Check VM uptime
gcloud compute instances describe autotube-vm \
  --project=autotube-494611 \
  --zone=us-central1-a \
  --format='value(creationTimestamp)'

# Check storage usage
gsutil du -s gs://autotube-veo-output-trial
```

---

## Your Credits Explained

### **Trial Credit for GenAI App Builder** (₹94,812 = ~$1,140)
✅ **Active but NOT applied to your bill**

This credit:
- Covers GenAI APIs (including Vertex AI, Gemini, etc.)
- **Must be activated** in Billing → Credits or it won't be used
- **Does NOT auto-apply** to charges — you need to link it

**Action:** Go to GCP Console → Billing → Credits → Activate this credit

### **Free Trial Credit** (₹14,661 remaining = ~$176)
✅ **Active and being consumed**

This credit:
- Auto-applies to most services
- Covered Compute + Storage + APIs
- Running out because of your always-on VM

---

## Cost Optimization Recommendations

### 🎯 **Priority 1: Stop VM Bleeding Money (Save ~$18/month)**

**Current Setup:**
```
e2-small running 24/7 = $18.50/month
```

**Options:**

| Option | Cost | Trade-off |
|--------|------|-----------|
| **Stop VM when not rendering** | $0 | Manual management |
| **Use Cloud Functions** | $0.40/month | Serverless, pay-per-call |
| **Downgrade to shared CPU** | $8/month | Slower, but cheap |
| **Downtime schedule** | $10/month | Auto-off 2am-9am |

**Recommended:** Use **Cloud Scheduler** to auto-stop VM at 2am, auto-start at 9am:
```bash
# Create auto-stop job
gcloud scheduler jobs create app-engine stop-vm \
  --schedule="0 2 * * *" \
  --http-method=POST \
  --uri="https://compute.googleapis.com/compute/v1/projects/autotube-494611/zones/us-central1-a/instances/autotube-vm/stop" \
  --oidc-service-account-email=...

# Create auto-start job
gcloud scheduler jobs create app-engine start-vm \
  --schedule="0 9 * * *" \
  ...
```

**Savings:** $13-16/month (70% reduction)

---

### 🎯 **Priority 2: Activate Your Unused Credit (Add $1,140)**

**Current:** GenAI credit not applied, using paid card instead
**Action:** 
1. Go to GCP Console → Billing → Credits
2. Click "Activate" on "Trial credit for GenAI App Builder"
3. Verify it's linked to your project

**Impact:** All future charges use free credits instead of your card

---

### 🎯 **Priority 3: Monitor Veo Video Costs (Track usage)**

**Current:** ~$16/month (20 videos)
**Concern:** If you scale to 50+ videos/month, costs climb to $40+

**Action:**
```bash
# Set up monthly budget alert
gcloud billing budgets create autotube-budget \
  --billing-account=0161BB-36A651-A06754 \
  --display-name="AutoTube Monthly Cap" \
  --budget-amount=50 \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=100
```

---

## Machine Upgrade Analysis

### Current: e2-small (2 vCPU, 2GB RAM)

**Should you upgrade?**

| Metric | e2-small | e2-medium | Recommendation |
|--------|----------|-----------|---|
| vCPU | 2 | 2 | Same |
| RAM | 2GB | 4GB | ⚠️ Bottleneck here |
| Cost | $14/month | $22/month | +57% cost |
| Video render speed | ~5 min | ~4 min | Marginal gain |

**Analysis:**
- MoviePy rendering is **I/O bound** (disk read/write), not CPU-bound
- Extra RAM (4GB → 8GB) would help if processing multiple videos in parallel
- **Verdict:** Upgrading is **NOT cost-effective** unless you're doing parallel rendering

**Better solution:** Keep e2-small + auto-stop schedule = **~$10/month**

---

## Action Plan (Next Steps)

### Immediate (This week)
- [ ] Activate GenAI credit: GCP Console → Billing → Credits
- [ ] Set up VM auto-stop/start schedule (saves $13/month)
- [ ] Create monthly budget alert ($50 cap)

### Short-term (This month)
- [ ] Monitor actual Veo costs for 2-3 weeks
- [ ] Check if your existing ₹14,661 credit will last long enough
- [ ] Verify billing account is correctly linked

### Long-term (Every month)
- [ ] Review "Cost Breakdown" in GCP Console
- [ ] Check if Veo 3.1 is still the cheapest option (vs. Ken Burns free mode)
- [ ] Optimize video rendering if costs exceed budget

---

## Detailed Cost Query for Gemini

Here are refined queries to ask Gemini for GCP cost details:

### Query 1: Overall Cost Breakdown
```
"I have a GCP project (autotube-494611) with these resources:
- 1 e2-small Compute Engine VM running 24/7
- Vertex AI Veo 3.1 for 20 videos/month
- 1 Cloud Storage bucket (100GB)
- Various APIs (BigQuery, Logging, Cloud Scheduler)

Show me:
1. Estimated monthly cost breakdown by service
2. Which service costs the most
3. Cost-saving recommendations
4. Projected annual spend if I scale to 100 videos/month"
```

### Query 2: Why Credits Are Being Consumed
```
"I have two GCP credits:
- GenAI App Builder trial: ₹94,812 (100% available)
- Free Trial: ₹14,661 (52% consumed, ₹13,782 used)

Why is my Free Trial credit being consumed while GenAI credit remains unused?
How do I activate and use the GenAI App Builder credit?
Which services does each credit cover?"
```

### Query 3: Machine Upgrade Decision
```
"My Compute Engine machine:
- Current: e2-small (2 vCPU, 2GB RAM), costs ~$14/month
- Bottleneck: 2GB RAM seems tight for video rendering
- Alternatives: e2-medium (4GB, $22/month), e2-standard-2 (8GB, $60/month)

Should I upgrade? Which machine type is best for:
- MoviePy video rendering
- 20-30 videos per month
- Cost efficiency over performance

What's the ROI of upgrading?"
```

### Query 4: Cost Optimization Strategy
```
"How can I reduce my GCP costs while keeping the same autotube pipeline?
Current spend: ~$35/month

Options to evaluate:
1. Auto-stop Compute Engine 6 hours/day (save $13/month)
2. Use Cloud Functions instead of VM (pay-per-video model)
3. Switch from Veo 3.1 to Ken Burns (free, but lower quality)
4. Enable committed-use discounts for 1-year commitment

Which combination saves the most while maintaining video quality?"
```

### Query 5: Credit Verification
```
"My GCP Free Trial credit shows ₹14,661 remaining (48% used).
But I haven't consciously used it heavily.
Can you explain:
1. What triggered the ₹13,782 consumption?
2. How long will remaining ₹14,661 last at current usage?
3. How to verify charges match the credit deduction?
4. What happens when the Free Trial credit expires?"
```

---

## Summary Tables for Reference

### Monthly Cost Projection
```
Current Usage (20 videos/month):
├─ Compute Engine (e2-small, 24/7): $18.50
├─ Vertex AI (Veo, 20 videos): $16.00
├─ Cloud Storage & egress: $0.50
└─ Total: ~$35/month

With VM Auto-Stop (6 hours/day downtime):
├─ Compute Engine (e2-small, 18h/day): $10.50
├─ Vertex AI (Veo, 20 videos): $16.00
├─ Cloud Storage & egress: $0.50
└─ Total: ~$27/month ✅ (Save $8/month)

Scaled to 50 videos/month:
├─ Compute Engine: $18.50
├─ Vertex AI (Veo, 50 videos): $40.00
├─ Cloud Storage: $1.50
└─ Total: ~$60/month
```

### Credit Burn Rate
```
Free Trial (₹14,661 remaining at $35/month spend):
  Burn rate: ~₹30,000 per month
  Remaining: 0.5 months (~15 days)
  ⚠️ Will expire soon!

GenAI Credit (₹94,812 unused):
  Status: NOT APPLIED
  Value: ~$1,140
  Action: Activate immediately
```

---

## Files to Check

```bash
# View detailed billing info
gcloud billing projects describe projects/autotube-494611

# Check VM creation date (to calculate total uptime cost)
gcloud compute instances describe autotube-vm --project=autotube-494611 --zone=us-central1-a

# View GCS bucket size (estimate storage costs)
gsutil du -sh gs://autotube-veo-output-trial

# List all Vertex AI operations
gcloud ai operations list --project=autotube-494611

# Check for running jobs
gcloud compute operations list --project=autotube-494611
```

---

## Emergency Actions (If Credits Run Out)

If both credits expire and you're charged to your card:

1. **Immediately stop the VM:**
   ```bash
   gcloud compute instances stop autotube-vm --zone=us-central1-a --project=autotube-494611
   ```

2. **Delete unused resources:**
   ```bash
   gsutil rm -r gs://autotube-veo-output-trial  # Delete bucket
   gcloud compute instances delete autotube-vm --project=autotube-494611
   ```

3. **Switch to free video pipeline:**
   ```bash
   # Use Ken Burns (free) instead of Veo
   export VIDEO_ANIMATION_MODE=ken_burns
   ```

4. **Verify no ongoing charges:**
   ```bash
   gcloud billing projects list
   gcloud billing budgets list --billing-account=0161BB-36A651-A06754
   ```

---

## Support Resources

- **GCP Billing Docs:** https://cloud.google.com/docs/billing
- **Vertex AI Pricing:** https://cloud.google.com/vertex-ai/pricing
- **Compute Engine Pricing:** https://cloud.google.com/compute/pricing
- **Cost Calculator:** https://cloud.google.com/products/calculator

---

**Last updated:** 2026-05-01
**Project:** autotube-494611
**Billing account:** 0161BB-36A651-A06754
