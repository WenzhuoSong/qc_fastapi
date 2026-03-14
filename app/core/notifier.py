"""
Telegram Alert Module

Sends critical notifications (pipeline errors, timeouts) to a Telegram chat.
Fails silently — alerting should never crash the pipeline itself.
"""

import httpx
from app.config import settings

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_alert(message: str) -> bool:
    """Send a Telegram message. Returns True on success, False on failure."""
    token = settings.TG_BOT_TOKEN
    chat_id = settings.TG_CHAT_ID

    if not token or not chat_id:
        print(f"[ALERT] (Telegram not configured) {message}")
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TELEGRAM_API.format(token=token),
                json={"chat_id": chat_id, "text": f"🚨 QC Pipeline\n\n{message}"},
            )
            return resp.status_code == 200
    except Exception as e:
        print(f"[ALERT] Telegram send failed: {e}")
        return False
