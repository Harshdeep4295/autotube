"""
Reminder Cron — sends WhatsApp summary of pending unapproved scripts.
Run every 2 hours via cron:
  0 */2 * * * cd /path/to/autotube && .venv/bin/python3 remind_pending.py
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from config import config


def main():
    if not config.WHATSAPP_ENABLED:
        logger.info("WhatsApp not enabled — skipping reminder")
        return

    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        logger.info("Supabase not configured — skipping reminder")
        return

    from supabase import create_client
    client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    res = (
        client.table("pending_videos")
        .select("id, topic, created_at")
        .eq("status", "pending")
        .eq("approved", False)
        .order("created_at")
        .execute()
    )

    if not res.data:
        logger.info("No pending scripts — no reminder needed")
        return

    from datetime import datetime, timezone
    from agents.whatsapp_agent import WhatsAppAgent

    lines = []
    for r in res.data:
        created = r.get("created_at", "")[:16].replace("T", " ")
        lines.append(f"• #{r['id']}: {r['topic'][:45]} ({created})")

    hours_left = config.APPROVAL_TIMEOUT_HOURS
    message = (
        f"⏳ *AutoTube — {len(res.data)} script(s) awaiting approval*\n\n"
        + "\n".join(lines)
        + f"\n\n⏰ Auto-approves in {hours_left}h if no response.\n"
        f"Reply *1* to approve, *2* to reject, *status* for details."
    )

    wa = WhatsAppAgent()
    if wa.send_approval_request is not None:
        wa._send_message(message)
        logger.info(f"Reminder sent: {len(res.data)} pending scripts")
    else:
        logger.warning("WhatsApp not configured")


if __name__ == "__main__":
    main()
