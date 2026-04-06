"""
WhatsApp Cloud API sender.

Covers:
- Plain text
- Interactive button messages  (≤ 3 buttons)
- Interactive list messages    (> 3 options, used for Stage menu)
- Template messages            (for first outbound / 24-h window opener)
"""
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"{settings.META_API_BASE}/{settings.WHATSAPP_PHONE_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    "Content-Type": "application/json",
}


async def _post(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        if resp.status_code not in (200, 201):
            logger.error("WA API error %s: %s", resp.status_code, resp.text)
        return resp.json()


async def send_text(to: str, body: str) -> dict:
    """Send a plain text message."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    logger.info("→ TEXT to %s: %s", to, body[:80])
    return await _post(payload)


async def send_buttons(
    to: str,
    body: str,
    buttons: list[dict],          # [{"id": "...", "title": "..."}]  max 3
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> dict:
    """Send an interactive reply-button message (max 3 buttons)."""
    btn_list = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
        for b in buttons[:3]
    ]
    interactive: dict = {
        "type": "button",
        "body": {"text": body},
        "action": {"buttons": btn_list},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    logger.info("→ BUTTONS to %s | body=%s | btns=%s", to, body[:60], [b["id"] for b in buttons])
    return await _post(payload)


async def send_list(
    to: str,
    body: str,
    button_label: str,
    sections: list[dict],
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> dict:
    """
    Send an interactive list message.
    sections = [{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]
    """
    interactive: dict = {
        "type": "list",
        "body": {"text": body},
        "action": {"button": button_label, "sections": sections},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    logger.info("→ LIST to %s | %s", to, body[:60])
    return await _post(payload)


async def send_template(
    to: str,
    template_name: str,
    language_code: str = "en",
    components: Optional[list] = None,
) -> dict:
    """
    Send a template message (required to open a new 24-hour conversation window).
    You must pre-approve templates in Meta Business Manager.
    """
    payload: dict = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components

    logger.info("→ TEMPLATE '%s' to %s", template_name, to)
    return await _post(payload)


# ── Convenience: date-time picker workaround ──────────────────────────────────
# WhatsApp Cloud API does not natively support a date-time picker widget.
# Best practice: ask driver to type date & time in a specified format,
# then validate and re-prompt on bad input.

DATETIME_FORMAT_HINT = "Please reply in format: DD/MM/YYYY HH:MM AM/PM\nExample: 25/06/2024 02:30 PM"


async def ask_datetime(to: str, question: str) -> dict:
    """Ask for a date+time value using the 12-hour text format."""
    body = f"{question}\n\n{DATETIME_FORMAT_HINT}"
    return await send_text(to, body)
