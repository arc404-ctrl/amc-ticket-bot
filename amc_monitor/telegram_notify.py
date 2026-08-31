import logging

import requests

from . import config

log = logging.getLogger("amc-monitor.telegram")


def send_message(text):
    """
    Sends `text` to every configured chat (see config.TELEGRAM_CHAT_IDS).
    Raises only if every recipient failed -- a single bad chat id
    shouldn't block the others or trigger main.py's "retry next run"
    handling when the rest of the sends went through fine. Any
    per-recipient failure alongside at least one success is still logged
    as a warning, so it isn't silently lost.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not configured")
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    responses = []
    last_exc = None
    for chat_id in config.TELEGRAM_CHAT_IDS:
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            responses.append(resp.json())
        except Exception as exc:
            last_exc = exc
            log.warning("Failed to notify chat %s: %s", chat_id, exc)

    if not responses and last_exc:
        raise last_exc
    return responses
