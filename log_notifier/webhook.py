"""Webhook-Versand mit einfachem Retry."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("log_notifier.run")

DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


def send_webhook(
    url: str,
    method: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> bool:
    if not url:
        logger.error("Webhook-URL ist leer, Versand übersprungen.")
        return False

    method = method.upper()
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method == "GET":
                flat = {
                    "title": payload.get("title", ""),
                    "priority": payload.get("priority", 0),
                    "message": payload.get("message", "")[:500],
                    "logId": payload.get("logId", ""),
                }
                resp = requests.get(url, headers=headers, params=flat,
                                    timeout=DEFAULT_TIMEOUT)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=payload,
                                    timeout=DEFAULT_TIMEOUT)
            else:
                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=DEFAULT_TIMEOUT)

            if 200 <= resp.status_code < 300:
                logger.info("Webhook OK (%s %s -> %s)",
                            method, url, resp.status_code)
                return True

            logger.warning("Webhook HTTP %s bei Versuch %d: %s",
                           resp.status_code, attempt, resp.text[:200])
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Webhook Fehler bei Versuch %d: %s", attempt, exc)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    if last_exc:
        logger.error("Webhook endgültig fehlgeschlagen: %s", last_exc)
    return False
