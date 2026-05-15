"""
WhatsApp Webhook Server (FastAPI)
Receives WhatsApp Cloud API webhook callbacks, processes approval replies,
and updates Supabase pending_videos table.

Run locally:  uvicorn webhook_server:app --port 8765 --reload
Deploy:       uvicorn webhook_server:app --host 0.0.0.0 --port 8765
Behind proxy: use Cloudflare Tunnel or ngrok for HTTPS (required by Meta)
"""

import logging
import os
import sys

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import config
from agents.whatsapp_agent import WhatsAppAgent, handle_whatsapp_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoTube WhatsApp Webhook", version="1.0")
wa = WhatsAppAgent()


@app.get("/webhook")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification (required during Meta app setup)."""
    if hub_mode == "subscribe" and hub_token == config.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive(request: Request):
    """Process incoming WhatsApp messages and route to approval handler."""
    data = await request.json()
    if not data:
        return JSONResponse({"status": "no data"})

    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        for msg in messages:
            if msg.get("type") != "text":
                continue
            sender = msg.get("from", "")
            text = msg.get("text", {}).get("body", "")
            logger.info(f"Received from {sender}: {text}")

            reply = handle_whatsapp_reply(sender, text)
            if reply:
                wa._send_message(reply)

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "running",
        "whatsapp_configured": wa.is_configured,
        "supabase_configured": bool(config.SUPABASE_URL and config.SUPABASE_KEY),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEBHOOK_PORT", "8765"))
    logger.info(f"WhatsApp webhook server starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
