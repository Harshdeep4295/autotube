#!/bin/bash
# setup_gcp_alerts.sh — Quick GCP cost optimization setup
# Run: ./setup_gcp_alerts.sh

PROJECT_ID="autotube-494611"
BILLING_ACCOUNT="0161BB-36A651-A06754"
ZONE="us-central1-a"
VM_NAME="autotube-vm"

set -e

echo "================================================"
echo "AutoTube — GCP Cost Optimization Setup"
echo "================================================"
echo ""

# 1. Check current project
echo "✓ Project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# 2. Check VM status
echo ""
echo "📊 CURRENT VM STATUS:"
echo "================================================"
gcloud compute instances describe $VM_NAME --zone=$ZONE \
  --format='table(name, machineType.machine_type(), status, creationTimestamp)'

# 3. Create monthly budget alert
echo ""
echo "💰 SETTING UP MONTHLY BUDGET ALERT ($50 cap)..."
echo "================================================"

BUDGET_NAME="autotube-monthly-budget"

if gcloud billing budgets describe $BUDGET_NAME --billing-account=$BILLING_ACCOUNT >/dev/null 2>&1; then
  echo "⚠️  Budget already exists: $BUDGET_NAME"
else
  gcloud billing budgets create $BUDGET_NAME \
    --billing-account=$BILLING_ACCOUNT \
    --display-name="AutoTube Monthly Spend Cap" \
    --budget-amount=50 USD \
    --threshold-rule=percent=50 \
    --threshold-rule=percent=90 \
    --threshold-rule=percent=100 \
    --threshold-rule=percent=110 && \
  echo "✓ Budget created: $BUDGET_NAME"
fi

# 4. VM auto-stop schedule (optional)
echo ""
echo "⏰ OPTIONAL: Set up VM auto-stop at 2am IST (weekly)?"
echo "================================================"
echo "This will save ~$13/month by stopping the VM overnight"
echo ""
read -p "Create auto-stop schedule? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  SCHEDULER_JOB="stop-autotube-vm-2am"

  if gcloud scheduler jobs describe $SCHEDULER_JOB --location=us-central1 >/dev/null 2>&1; then
    echo "⚠️  Scheduler job already exists: $SCHEDULER_JOB"
  else
    echo "Creating Cloud Scheduler job to stop VM at 2am IST (8:30pm UTC)..."

    # Create service account for scheduler
    SA_NAME="autotube-scheduler-sa"
    if ! gcloud iam service-accounts describe $SA_NAME@$PROJECT_ID.iam.gserviceaccount.com >/dev/null 2>&1; then
      gcloud iam service-accounts create $SA_NAME \
        --display-name="AutoTube Cloud Scheduler SA" && \
      echo "✓ Service account created: $SA_NAME"
    else
      echo "✓ Service account exists: $SA_NAME"
    fi

    # Grant permissions
    gcloud compute instances add-iam-policy-binding $VM_NAME \
      --zone=$ZONE \
      --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
      --role="roles/compute.instanceAdmin.v1" 2>/dev/null && \
    echo "✓ IAM permissions granted"

    # Create scheduler job
    gcloud scheduler jobs create compute-engine-stop $SCHEDULER_JOB \
      --location=us-central1 \
      --schedule="30 20 * * *" \
      --timezone="UTC" \
      --http-method=POST \
      --uri="https://compute.googleapis.com/compute/v1/projects/$PROJECT_ID/zones/$ZONE/instances/$VM_NAME/stop" \
      --oidc-service-account-email="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
      --oidc-token-audience="https://compute.googleapis.com/" && \
    echo "✓ Scheduler job created: $SCHEDULER_JOB"
  fi

  # Optional: Create start job
  echo ""
  read -p "Also create auto-start at 9am IST (3:30am UTC)? (y/n) " -n 1 -r
  echo ""

  if [[ $REPLY =~ ^[Yy]$ ]]; then
    START_JOB="start-autotube-vm-9am"

    gcloud scheduler jobs create compute-engine-start $START_JOB \
      --location=us-central1 \
      --schedule="30 3 * * *" \
      --timezone="UTC" \
      --http-method=POST \
      --uri="https://compute.googleapis.com/compute/v1/projects/$PROJECT_ID/zones/$ZONE/instances/$VM_NAME/start" \
      --oidc-service-account-email="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
      --oidc-token-audience="https://compute.googleapis.com/" 2>/dev/null && \
    echo "✓ Auto-start job created: $START_JOB"
  fi
fi

# 5. Check current credits
echo ""
echo "💳 CHECKING CREDITS..."
echo "================================================"
gcloud billing accounts describe $BILLING_ACCOUNT \
  --format='table(displayName, open)' && \
echo ""
echo "⚠️  IMPORTANT: Check GCP Console → Billing → Credits"
echo "   Activate 'Trial credit for GenAI App Builder' (₹94,812)"
echo ""

# 6. Summary
echo ""
echo "================================================"
echo "✓ SETUP COMPLETE!"
echo "================================================"
echo ""
echo "📋 Next Steps:"
echo "   1. Go to GCP Console → Billing → Credits"
echo "   2. Activate 'Trial credit for GenAI App Builder'"
echo "   3. Check monthly cost in Billing → Cost Breakdown"
echo "   4. Review budget alerts in Billing → Budgets"
echo ""
echo "💰 Cost Savings:"
echo "   - VM auto-stop: Save ~$13-16/month"
echo "   - GenAI credit: Use ₹94,812 (~$1,140) instead of card"
echo ""
echo "📖 See GCP_COST_ANALYSIS.md for detailed report"
echo ""
