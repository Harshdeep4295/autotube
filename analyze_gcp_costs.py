#!/usr/bin/env python3
"""
Query GCP Billing API to get detailed cost breakdown.
Requires: pip install google-cloud-billing google-auth
"""

import os
import json
from datetime import datetime, timedelta
from google.cloud import billing_v1
from google.auth import default

def get_billing_account_id():
    """Get the first active billing account."""
    client = billing_v1.CloudBillingClient()

    # List all billing accounts
    accounts = client.list_billing_accounts()

    for account in accounts:
        if account.open:
            return account.name.split('/')[-1]

    raise ValueError("No active billing account found")

def get_project_costs(project_id, days_back=30):
    """
    Get cost breakdown for a project over the last N days.
    Queries the Cloud Billing API.
    """
    client = billing_v1.CloudBillingClient()

    # Get billing account
    billing_account_id = get_billing_account_id()
    print(f"Using billing account: {billing_account_id}\n")

    # Get project's billing info
    project_name = f"projects/{project_id}"
    try:
        project_billing = client.get_project_billing_info(name=project_name)
        print(f"Project: {project_id}")
        print(f"Billing enabled: {project_billing.billing_enabled}")
        print(f"Billing account: {project_billing.billing_account_name}\n")
    except Exception as e:
        print(f"Error getting project billing info: {e}")
        return

    print("Note: For detailed cost breakdown by service, you need to:")
    print("1. Enable the Cloud Billing Export to BigQuery API")
    print("2. OR check GCP Console → Billing → Cost Breakdown tab\n")

    # Alternative: Check project's recent activity
    print("Checking project resources...")
    list_project_resources(project_id)

def list_project_resources(project_id):
    """List compute, storage, and AI resources to estimate costs."""
    import subprocess

    try:
        # Get Compute Engine instances
        result = subprocess.run(
            f"gcloud compute instances list --project={project_id} --format=json",
            shell=True, capture_output=True, text=True
        )
        instances = json.loads(result.stdout) if result.stdout else []

        if instances:
            print(f"\n📦 Compute Engine Instances: {len(instances)}")
            for inst in instances:
                print(f"  - {inst['name']}: {inst['machineType'].split('/')[-1]}")

        # Get Cloud Storage buckets
        result = subprocess.run(
            f"gcloud storage buckets list --project={project_id} --format=json",
            shell=True, capture_output=True, text=True
        )
        buckets = json.loads(result.stdout) if result.stdout else []

        if buckets:
            print(f"\n💾 Cloud Storage Buckets: {len(buckets)}")
            for bucket in buckets:
                print(f"  - {bucket['name']}")

    except Exception as e:
        print(f"Error listing resources: {e}")

def estimate_veo_cost(videos_per_month=20):
    """Estimate Vertex AI Veo 3.1 costs."""
    cost_per_video = 0.80  # $0.80 per 8-second video

    print(f"\n💡 Vertex AI Veo 3.1 Cost Estimate:")
    print(f"  Cost per video: ${cost_per_video:.2f}")
    print(f"  Videos per month: {videos_per_month}")
    print(f"  Monthly cost: ${cost_per_video * videos_per_month:.2f}")
    print(f"  Annual cost: ${cost_per_video * videos_per_month * 12:.2f}")

def get_billing_export_status(project_id):
    """Check if BigQuery export is enabled (recommended for detailed tracking)."""
    import subprocess

    try:
        result = subprocess.run(
            f"gcloud billing budgets list --billing-account=$(gcloud billing accounts list --format='value(name)' --limit=1) --format=json",
            shell=True, capture_output=True, text=True
        )
        budgets = json.loads(result.stdout) if result.stdout else []

        if budgets:
            print(f"\n📊 Budgets configured: {len(budgets)}")
            for budget in budgets:
                print(f"  - {budget.get('displayName', 'Unnamed')}")
        else:
            print("\n⚠️  No budgets configured. Recommend setting a budget alert!")
    except Exception as e:
        print(f"Note: Could not check budgets: {e}")

def main():
    """Main entry point."""
    # Get project ID from environment or config
    project_id = os.environ.get('GCP_PROJECT_ID')

    if not project_id:
        print("❌ GCP_PROJECT_ID not set. Set it with:")
        print("   export GCP_PROJECT_ID=your-project-id")
        print("   Or pass it as argument: python analyze_gcp_costs.py your-project-id")

        if len(__import__('sys').argv) > 1:
            project_id = __import__('sys').argv[1]
        else:
            return

    print("=" * 60)
    print("GCP Cost Analysis Tool")
    print("=" * 60)

    try:
        get_project_costs(project_id)
        get_billing_export_status(project_id)
        estimate_veo_cost()

        print("\n" + "=" * 60)
        print("📌 Next Steps:")
        print("=" * 60)
        print("1. Check GCP Console → Billing → Cost Breakdown for detailed costs")
        print("2. Enable BigQuery export: Billing → Settings → Export to BigQuery")
        print("3. Set budget alert: Billing → Budgets & alerts → Create budget")
        print("4. Review unused resources: Compute Engine, Cloud Storage, APIs")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("- Ensure you're authenticated: gcloud auth application-default login")
        print("- Verify project ID is correct")
        print("- Check you have Billing Admin role")

if __name__ == "__main__":
    main()
