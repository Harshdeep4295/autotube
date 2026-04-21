"""
GCP credit usage monitoring and alerting
"""

import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

# Pricing (as of April 2026)
VEO_FAST_COST_PER_SEC = 0.10  # $0.80/8-sec video


class GCPCostTracker:
    """Track credit usage against $300 budget"""

    def __init__(self, initial_credits: float = 300.0):
        self.initial_credits = initial_credits
        self.spent = 0.0
        self.operations = []

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
            "timestamp": datetime.utcnow()
        })

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
