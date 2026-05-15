"""
WhatsApp Approval Agent
Sends script approval requests via WhatsApp Cloud API and processes replies.
User replies "1" to approve, "2" to reject — updates Supabase pending_videos table.
"""

import logging
from typing import Dict, Optional

import requests

from config import config

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"


class WhatsAppAgent:
    """Sends approval notifications via WhatsApp Cloud API."""

    def __init__(self):
        self.phone_number_id = config.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = config.WHATSAPP_ACCESS_TOKEN
        self.recipient = config.WHATSAPP_RECIPIENT

    @property
    def is_configured(self) -> bool:
        return bool(self.phone_number_id and self.access_token and self.recipient)

    def send_approval_request(self, row_id: int, script: Dict) -> bool:
        """
        Send a WhatsApp message asking for approval.
        Returns True if message sent successfully.
        """
        if not self.is_configured:
            logger.warning("WhatsApp not configured — skipping notification")
            return False

        title = script.get("title", "Untitled")[:80]
        thumb_text = script.get("thumbnail_text", "")[:40]
        word_count = sum(len(s.get("text", "").split()) for s in script.get("sections", []))
        sections = len(script.get("sections", []))
        tags = ", ".join(script.get("tags", [])[:5])

        message = (
            f"🎬 *AutoTube — New Script Ready*\n\n"
            f"*Title:* {title}\n"
            f"*Thumbnail:* {thumb_text}\n"
            f"*Words:* {word_count} | *Sections:* {sections}\n"
            f"*Tags:* {tags}\n"
            f"*ID:* {row_id}\n\n"
            f"Reply:\n"
            f"*1* → Approve ✅\n"
            f"*2* → Reject ❌\n"
            f"*3* → Show full script"
        )

        return self._send_message(message)

    def send_status_update(self, title: str, status: str, video_url: str = "") -> bool:
        """Send a status update (published, failed, etc.)."""
        if not self.is_configured:
            return False

        emoji = "✅" if status == "published" else "❌" if status == "failed" else "ℹ️"
        message = f"{emoji} *AutoTube — {status.title()}*\n\n*{title}*"
        if video_url:
            message += f"\n🔗 {video_url}"

        return self._send_message(message)

    def _send_message(self, text: str) -> bool:
        """Send a WhatsApp text message via Cloud API."""
        url = f"{WHATSAPP_API_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": self.recipient,
            "type": "text",
            "text": {"body": text},
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            logger.info(f"WhatsApp message sent to {self.recipient}")
            return True
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False


def handle_whatsapp_reply(sender: str, message_text: str) -> Optional[str]:
    """
    Process an incoming WhatsApp reply. Called by the webhook endpoint.
    Returns response message to send back, or None.
    """
    text = message_text.strip().lower()

    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        return "⚠️ Supabase not configured"

    from supabase import create_client
    client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    if text == "1":
        row = _get_oldest_pending(client)
        if not row:
            return "No pending scripts to approve."
        client.table("pending_videos").update(
            {"approved": True}
        ).eq("id", row["id"]).execute()
        title = row.get("script_json", {}).get("title", row.get("topic", "Unknown"))
        return f"✅ Approved: *{title}*\nWill render on next pipeline run."

    elif text == "2":
        row = _get_oldest_pending(client)
        if not row:
            return "No pending scripts to reject."
        client.table("pending_videos").update(
            {"status": "rejected"}
        ).eq("id", row["id"]).execute()
        title = row.get("script_json", {}).get("title", row.get("topic", "Unknown"))
        return f"❌ Rejected: *{title}*"

    elif text == "3":
        row = _get_oldest_pending(client)
        if not row:
            return "No pending scripts."
        script = row.get("script_json", {})
        sections_text = "\n".join(
            f"  {i+1}. {s.get('title', '')}" for i, s in enumerate(script.get("sections", []))
        )
        return (
            f"📄 *{script.get('title', 'Untitled')}*\n\n"
            f"*Sections:*\n{sections_text}\n\n"
            f"Reply *1* to approve, *2* to reject."
        )

    elif text.startswith("approve "):
        try:
            row_id = int(text.split(" ")[1])
            client.table("pending_videos").update(
                {"approved": True}
            ).eq("id", row_id).execute()
            return f"✅ Approved row #{row_id}"
        except (ValueError, IndexError):
            return "Usage: approve <id>"

    elif text.startswith("reject "):
        try:
            row_id = int(text.split(" ")[1])
            client.table("pending_videos").update(
                {"status": "rejected"}
            ).eq("id", row_id).execute()
            return f"❌ Rejected row #{row_id}"
        except (ValueError, IndexError):
            return "Usage: reject <id>"

    elif text == "status":
        res = client.table("pending_videos").select(
            "id, topic, status, approved"
        ).eq("status", "pending").order("created_at").limit(5).execute()
        if not res.data:
            return "No pending scripts in queue."
        lines = []
        for r in res.data:
            emoji = "⏳" if not r["approved"] else "✅"
            lines.append(f"{emoji} #{r['id']}: {r['topic'][:40]}")
        return f"*Pending Scripts:*\n" + "\n".join(lines)

    else:
        return (
            "🤖 *AutoTube Commands:*\n"
            "*1* → Approve oldest pending\n"
            "*2* → Reject oldest pending\n"
            "*3* → Show script details\n"
            "*status* → List all pending\n"
            "*approve <id>* → Approve specific\n"
            "*reject <id>* → Reject specific"
        )


def _get_oldest_pending(client) -> Optional[Dict]:
    """Get the oldest unapproved pending script."""
    res = (
        client.table("pending_videos")
        .select("*")
        .eq("status", "pending")
        .eq("approved", False)
        .order("created_at")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None
