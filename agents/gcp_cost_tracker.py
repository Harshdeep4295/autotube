"""
GCP credit usage monitoring and alerting
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Pricing (as of April 2026)
VEO_FAST_COST_PER_SEC = 0.10  # $0.80/8-sec video
COST_LOG_FILE = "data/gcp_cost_log.json"


class GCPCostTracker:
    """Track credit usage against $300 budget (persists to JSON)"""

    def __init__(self, initial_credits: float = 300.0):
        self.initial_credits = initial_credits
        self.spent = 0.0
        self.operations = []
        self._load_from_file()

    def _load_from_file(self):
        """Load historical costs from JSON file"""
        try:
            if Path(COST_LOG_FILE).exists():
                with open(COST_LOG_FILE, 'r') as f:
                    data = json.load(f)
                    self.spent = data.get('total_spent', 0.0)
                    self.operations = data.get('operations', [])
                    logger.info(f"Loaded cost history: ${self.spent:.2f} spent across {len(self.operations)} operations")
        except Exception as e:
            logger.warning(f"Could not load cost history: {e}")

    def _save_to_file(self):
        """Persist costs to JSON file"""
        try:
            Path("data").mkdir(exist_ok=True)
            with open(COST_LOG_FILE, 'w') as f:
                json.dump({
                    'total_spent': self.spent,
                    'operations': self.operations,
                    'last_updated': datetime.utcnow().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save cost history: {e}")

    def log_veo_generation(
        self,
        duration_seconds: int = 8,
        variant: str = "fast"
    ):
        """Log Veo generation cost"""
        if variant == "fast":
            cost = duration_seconds * VEO_FAST_COST_PER_SEC
        else:
            cost = 0

        self.spent += cost
        self.operations.append({
            "type": f"veo_{variant}",
            "cost": cost,
            "timestamp": datetime.utcnow().isoformat()
        })
        self._save_to_file()

        remaining = self.initial_credits - self.spent
        percentage = (self.spent / self.initial_credits) * 100

        logger.info(
            f"Veo {variant}: ${cost:.2f} | "
            f"Spent: ${self.spent:.2f}/{self.initial_credits:.2f} ({percentage:.1f}%) | "
            f"Remaining: ${remaining:.2f}"
        )

        if remaining < 50:
            logger.warning(
                f"GCP credits low: ${remaining:.2f} remaining. "
                f"At current rate, credits exhaust in ~"
                f"{int(remaining / (self.spent / max(1, len(self.operations))))} more videos"
            )

    def estimate_remaining_videos(self) -> int:
        """Estimate how many more videos can be generated"""
        if not self.operations:
            return int(self.initial_credits / 0.80)

        avg_cost_per_op = self.spent / len(self.operations)
        remaining = self.initial_credits - self.spent

        return int(remaining / avg_cost_per_op)

    def summary(self) -> Dict:
        """Get usage summary"""
        return {
            "total_budget": self.initial_credits,
            "spent": self.spent,
            "remaining": self.initial_credits - self.spent,
            "percentage_spent": (self.spent / self.initial_credits) * 100,
            "num_operations": len(self.operations),
            "avg_cost_per_op": self.spent / max(1, len(self.operations)),
            "estimated_remaining_videos": self.estimate_remaining_videos()
        }

    def print_summary(self):
        """Print formatted cost summary to console"""
        s = self.summary()
        print("\n" + "="*60)
        print("💰 GCP CREDIT USAGE SUMMARY")
        print("="*60)
        print(f"Total Budget:        ${s['total_budget']:.2f}")
        print(f"Spent:               ${s['spent']:.2f} ({s['percentage_spent']:.1f}%)")
        print(f"Remaining:           ${s['remaining']:.2f}")
        print(f"Videos Generated:    {s['num_operations']}")
        print(f"Avg Cost/Video:      ${s['avg_cost_per_op']:.2f}")
        print(f"Estimated Videos Left: {s['estimated_remaining_videos']} more videos")
        print("="*60 + "\n")
