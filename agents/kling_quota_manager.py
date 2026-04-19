"""
Kling daily quota management
- Track credit consumption
- Alert when quota low
- Queue jobs for next day if exhausted
"""

import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)

DAILY_CREDITS = 66
ALERT_THRESHOLD = 10  # Alert if <10 credits remaining
GENERATION_COST = 10  # 5-second 720p video = 10 credits


class KlingQuotaTracker:
    """Track daily credit usage and alert on low quota"""

    def __init__(self, state_file: str = "data/kling_state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def _load_state(self):
        """Load quota state from file"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                state = json.load(f)
                self.last_reset = datetime.fromisoformat(state["last_reset"])
                self.credits_used_today = state["credits_used_today"]
        else:
            self.last_reset = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            self.credits_used_today = 0

    def _save_state(self):
        """Save quota state to file"""
        with open(self.state_file, "w") as f:
            json.dump({
                "last_reset": self.last_reset.isoformat(),
                "credits_used_today": self.credits_used_today
            }, f)

    def _check_and_reset(self):
        """Check if day has changed, reset counter if needed"""
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if today > self.last_reset:
            # New day, reset counter
            logger.info("Daily quota reset")
            self.last_reset = today
            self.credits_used_today = 0
            self._save_state()

    def get_remaining_credits(self) -> int:
        """Get remaining credits for today"""
        self._check_and_reset()
        return max(0, DAILY_CREDITS - self.credits_used_today)

    def can_generate(self) -> bool:
        """Check if enough credits for one video"""
        remaining = self.get_remaining_credits()
        enough = remaining >= GENERATION_COST

        if not enough:
            logger.warning(f"Insufficient credits: need {GENERATION_COST}, have {remaining}")

        if remaining < ALERT_THRESHOLD:
            logger.warning(
                f"Kling quota running low: {remaining}/{DAILY_CREDITS} credits remaining"
            )

        return enough

    def consume_credits(self, amount: int = GENERATION_COST):
        """Record credit consumption"""
        self.credits_used_today += amount
        self._save_state()
        logger.info(
            f"Consumed {amount} credits. "
            f"Remaining: {self.get_remaining_credits()}/{DAILY_CREDITS}"
        )

    def refund_credits(self, amount: int = GENERATION_COST):
        """Refund credits (if generation fails)"""
        self.credits_used_today = max(0, self.credits_used_today - amount)
        self._save_state()
        logger.info(f"Refunded {amount} credits")
