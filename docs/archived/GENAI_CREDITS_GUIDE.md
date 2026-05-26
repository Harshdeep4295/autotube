# How to Activate & Use GenAI App Builder Credits (₹94,812)

## Step 1: Activate the Credit in GCP Console

### Via Web Browser (Easiest)

1. **Go to:** https://console.cloud.google.com/billing/credits
   
2. **Look for:** "Trial credit for GenAI App Builder"
   - Status: Should show "Available" with ₹94,812.51
   
3. **Click the credit card icon or expand it**
   - You should see a button like "Activate", "Use", or similar
   
4. **Click Activate/Use**
   - Confirm the action
   - It should say "Status: Active" or "In use"

5. **Verify it's linked to your project:**
   - It should show: `autotube-494611` or `My Billing Account`

---

## Step 2: Verify Activation (Command Line)

Run this to confirm:

```bash
gcloud billing accounts describe billingAccounts/0161BB-36A651-A06754 \
  --format=json | jq '.displayName, .open'
```

Expected output:
```
"My Billing Account"
true
```

Then check if credits are showing in your project:

```bash
gcloud billing projects describe projects/autotube-494611 \
  --format=json | jq '.billingAccountName'
```

Expected output:
```
"billingAccounts/0161BB-36A651-A06754"
```

---

## Step 3: How to Use GenAI Credits

### What Services Does It Cover?

✅ **Fully Covered:**
- **Vertex AI APIs** (including Veo 3.1 video generation)
- **Google AI/Gemini APIs** 
- **Cloud AI services**
- **Generative AI Workbench**

✅ **Partially Covered (with restrictions):**
- **Compute Engine** (some machine types)
- **Cloud Storage**
- **BigQuery** (limited)

❌ **NOT Covered:**
- Premium support
- Some legacy services

### The Credit Applies Automatically

Once activated, the credit will:

1. **Auto-apply to all qualifying charges** in this billing account
2. **Deduct from your balance** before charging your card
3. **Show in billing reports** as "Credit applied"

**Example:** Your $35/month bill:
```
Before: You pay ₹2,900 from card
After:  Credit pays ₹2,900, you pay ₹0
```

---

## Step 4: Monitor Credit Usage

### Check Current Balance

#### Via GCP Console:
1. Go to: https://console.cloud.google.com/billing/credits
2. Look at "Remaining value" for "Trial credit for GenAI App Builder"
3. Shows real-time balance

#### Via Command Line:
```bash
gcloud billing budgets list \
  --billing-account=0161BB-36A651-A06754 \
  --format=json
```

---

## Step 5: View Charges & Credits Applied

### See How Credits Are Being Used

1. Go to: **GCP Console → Billing → Cost breakdown**
2. Filter by date range (last 30 days)
3. Look for rows like:
   ```
   Trial credit for GenAI App Builder: -₹1,500 (credit applied)
   Vertex AI (Veo 3.1):                 +₹1,500
   ───────────────────────────────────────────────
   Net charge:                           ₹0
   ```

### View Daily/Hourly Usage

```bash
# Show all charges in the last 7 days
gcloud billing accounts list-budget-updates \
  --billing-account=0161BB-36A651-A06754 \
  --limit=30
```

### Export to CSV for Analysis

1. Go to: **GCP Console → Billing → Cost breakdown**
2. Click "Download CSV" button
3. Open in Excel/Google Sheets to see all charges + credits

---

## Step 6: Understand Credit Expiry

### GenAI App Builder Credit Details

| Aspect | Details |
|--------|---------|
| **Amount** | ₹94,812 (~$1,140 USD) |
| **Expiry** | Usually 12 months from issue date |
| **Check expiry** | Hover over credit in GCP Console |
| **What happens when it expires** | Credit is removed, but you keep paying via card |

**Important:** The credit is **project-agnostic** — it applies to ANY service in your billing account, not just autotube-494611.

---

## Step 7: Set Up Alerts (Recommended)

### Create a Budget Alert

```bash
# Install gcloud if needed
gcloud components install beta

# Create budget alert
gcloud billing budgets create my-autotube-budget \
  --billing-account=0161BB-36A651-A06754 \
  --display-name="AutoTube Monthly Alert" \
  --budget-amount=10000 INR \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```

This sends alerts when:
- ✅ 50% of ₹10,000 spent (₹5,000)
- ✅ 90% of ₹10,000 spent (₹9,000)
- ✅ 100% of ₹10,000 spent (₹10,000)

---

## Step 8: Optimize Spending (Use Credit Wisely)

### Your Monthly Spend Breakdown

```
Vertex AI Veo 3.1:     ₹1,200/month (20 videos × $0.80)
Compute Engine (e2):   ₹1,500/month (24/7 running)
Cloud Storage:         ₹50/month
───────────────────────────────────────
Total:                 ₹2,750/month

With GenAI credit applied:
Cost to you:           ₹0/month (credit covers it)
Days credit lasts:     94,812 ÷ 2,750 = ~34 months ✓
```

### To Maximize Credit Usage:

**Option A: Keep Current Setup** (Best quality)
- ✓ Use Veo 3.1 ($16/month)
- ✓ VM runs 24/7
- ✓ Credit lasts: ~34 months
- ❌ Most expensive

**Option B: Add VM Auto-Stop** (Recommended)
- ✓ Use Veo 3.1 ($16/month)
- ✓ Stop VM 6h/day
- ✓ Credit lasts: ~50 months
- ✅ Same quality, lower cost

**Option C: Switch to Ken Burns** (Free video mode)
- ✓ Use Ken Burns ($0/month)
- ✓ VM runs 24/7
- ✓ Credit lasts: ~190 months (15+ years!)
- ⚠️ Lower video quality (but still good)

---

## Common Issues & Solutions

### Issue 1: Credit Not Showing as Active

**Symptom:** Shows "Available" but not "In use"

**Solution:**
1. Go to: https://console.cloud.google.com/billing/credits
2. Look for a button "Activate" or "Accept"
3. Click it and confirm
4. Wait 5-10 minutes for propagation
5. Refresh the page

### Issue 2: Charges Still Coming From Card

**Symptom:** Credit balance unchanged, card being charged

**Causes & Solutions:**

| Cause | Fix |
|-------|-----|
| Credit not activated | Activate it (step 1 above) |
| Charges are from non-covered services | Check which services are covered |
| Multiple billing accounts | Ensure billing account is correct |
| Credit expired | Check expiry date, request new one |

**To verify credit is being applied:**
```bash
# Check last 10 charges
gcloud billing accounts list-budget-updates \
  --billing-account=0161BB-36A651-A06754 \
  --limit=10 \
  --format=json | jq '.[]'
```

Look for entries like:
```
"displayName": "Trial credit for GenAI App Builder"
"amount": -1500  # Negative = credit applied
```

### Issue 3: Credit Balance Not Updating

**Symptom:** Balance shows ₹94,812 but you're not seeing charges deducted

**Reason:** Charges are batched (processed daily/hourly, not real-time)

**Solution:**
1. Wait 24 hours for charges to process
2. Check balance again
3. Should show: ₹94,812 - (charges from last 24h)

---

## Quick Reference: Credit Status Check

Run this one command to see everything:

```bash
cat << 'EOF' > check_credits.sh
#!/bin/bash
PROJECT_ID="autotube-494611"
BILLING_ACCOUNT="0161BB-36A651-A06754"

echo "=== GCP CREDITS STATUS ==="
echo ""
echo "Billing Account:"
gcloud billing accounts describe $BILLING_ACCOUNT \
  --format='table(displayName, open)'

echo ""
echo "Project Billing:"
gcloud billing projects describe projects/$PROJECT_ID \
  --format='table(name, billingEnabled, billingAccountName)'

echo ""
echo "Credits:"
gcloud billing accounts describe $BILLING_ACCOUNT \
  --format=json | jq '.creditNotes[] | {displayName, creditType, creditAmount, remainingAmount}'

echo ""
echo "✓ If credit shows "remainingAmount" > 0, it's active and ready to use!"
EOF

chmod +x check_credits.sh
./check_credits.sh
```

---

## Timeline Summary

```
Today (May 1):
  ✓ Activate GenAI credit (₹94,812)
  ✓ Verify it's linked to billing account
  ✓ Charges start applying to credit

Within 24 hours:
  ✓ Check cost breakdown to confirm credit is deducting
  ✓ View balance in GCP Console

By June 1:
  ✓ Optimize costs if needed (VM auto-stop, Ken Burns, etc.)
  ✓ Set up monthly budget alert

By July 15:
  ✓ Free Trial expires
  ✓ GenAI credit continues (12-month expiry)
  ✓ Your spending shifts from Free Trial → GenAI credit
  ✓ After GenAI credit expires → card charges begin
```

---

## Final Checklist

- [ ] Go to GCP Console → Billing → Credits
- [ ] Click "Activate" on "Trial credit for GenAI App Builder"
- [ ] Confirm it shows "Active" or "In use"
- [ ] Wait 5-10 minutes for propagation
- [ ] Refresh the page
- [ ] Check that ₹94,812 is now associated with your billing account
- [ ] Go to Cost breakdown and verify charges are being deducted
- [ ] Set up a monthly budget alert ($50 or ₹4,000)
- [ ] Bookmark this guide for reference

---

## Support & Questions

**Need help?**

1. **GCP Billing Docs:** https://cloud.google.com/docs/billing
2. **Credits Help:** https://cloud.google.com/free/docs/gcp-free-tier
3. **Contact GCP Support:** GCP Console → Help → Support

**For your specific setup:**
- Vertex AI Pricing: https://cloud.google.com/vertex-ai/pricing
- Compute Engine Pricing: https://cloud.google.com/compute/pricing

---

**Last updated:** 2026-05-01  
**Your Project:** autotube-494611  
**Your Credits:** ₹94,812 (GenAI App Builder) + ₹14,661 (Free Trial)  
**Total Free Spend:** ~₹109,473 (~$1,315)
