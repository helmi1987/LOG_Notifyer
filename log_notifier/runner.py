"""Bottom-Up-Log-Auswertung und Webhook-Trigger."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore[assignment]

from .webhook import send_webhook

logger = logging.getLogger("log_notifier.run")

DEFAULT_ROTATION_SUFFIX = ".1"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Datei-Iteration
# ---------------------------------------------------------------------------

def _iter_lines_reversed(path: Path) -> Iterator[str]:
    with path.open("rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        buf = b""
        while pos > 0:
            read_size = min(4096, pos)
            pos -= read_size
            f.seek(pos)
            buf = f.read(read_size) + buf
            parts = buf.split(b"\n")
            buf = parts[0]
            for raw in reversed(parts[1:]):
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                if line:
                    yield line
        if buf:
            line = buf.decode("utf-8", errors="replace").rstrip("\r")
            if line:
                yield line


# ---------------------------------------------------------------------------
# Datumsfilter
# ---------------------------------------------------------------------------

def _today_string(fmt: str) -> str:
    tz_name = os.getenv("LOG_NOTIFIER_TZ", "Europe/Zurich")
    if ZoneInfo is not None:
        try:
            now = datetime.now(ZoneInfo(tz_name))
        except Exception:
            logger.warning("Unbekannte Zeitzone '%s', nutze Systemzeit.", tz_name)
            now = datetime.now()
    else:
        now = datetime.now()
    return now.strftime(fmt)


def _matches_date_filter(line: str, fmt: str, today_cache: dict) -> bool:
    if "today" not in today_cache:
        today_cache["today"] = _today_string(fmt)
    return today_cache["today"] in line


# ---------------------------------------------------------------------------
# Emoji-Mapping
# ---------------------------------------------------------------------------

def _resolve_emoji(priority: int, mapping: dict) -> str:
    """Wählt das Emoji der höchsten Stufe <= priority.

    mapping: {"0": "ℹ️", "5": "🔵", ...} – Schlüssel sind Zahlen als Strings.
    """
    if not mapping:
        return ""
    try:
        thresholds = sorted(int(k) for k in mapping.keys())
    except (ValueError, TypeError):
        logger.warning("priorityEmoji enthält ungültige Schlüssel: %r", mapping)
        return ""
    chosen = None
    for t in thresholds:
        if priority >= t:
            chosen = t
        else:
            break
    if chosen is None:
        return ""
    return mapping.get(str(chosen), "")


def _apply_emoji(title: str, priority: int, global_cfg: dict) -> str:
    mapping = global_cfg.get("priorityEmoji") or {}
    if not isinstance(mapping, dict) or not mapping:
        return title
    emoji = _resolve_emoji(priority, mapping)
    if not emoji:
        default = global_cfg.get("priorityEmojiDefault") or ""
        if default:
            return f"{default} {title}"
        return title
    return f"{emoji} {title}"


# ---------------------------------------------------------------------------
# Auswertung einer Log-Datei (inkl. Rotation)
# ---------------------------------------------------------------------------

def _scan_file(
    path: Path,
    start_pattern: str,
    patterns: list[dict],
    use_date_filter: bool,
    date_format: str,
) -> tuple[list[dict], bool]:
    hits: list[dict] = []
    found_start = False
    today_cache: dict = {}

    compiled = [(re.compile(p["regex"]), p) for p in patterns]

    for line in _iter_lines_reversed(path):
        if start_pattern and start_pattern in line:
            found_start = True
            break

        if use_date_filter and not _matches_date_filter(
            line, date_format, today_cache
        ):
            continue

        for rx, meta in compiled:
            m = rx.search(line)
            if m:
                hits.append({
                    "line": m.group(0),
                    "groups": list(m.groups()),
                    "priority": meta.get("priority", 0),
                    "regex": meta["regex"],
                })
                break  # pro Zeile nur ein Pattern (Reihenfolge = Config)

    hits.reverse()
    return hits, found_start


def evaluate_log(log_cfg: dict, global_cfg: dict) -> dict | None:
    log_id = log_cfg["logId"]
    path = Path(log_cfg["filePath"])
    start_pattern = log_cfg.get("startPattern", "")
    patterns = log_cfg.get("patterns", [])
    use_date_filter = log_cfg.get("useDateFilter", False)
    date_format = log_cfg.get("dateFormat", DEFAULT_DATE_FORMAT)
    check_rotated = log_cfg.get("checkRotatedLogs", False)
    rotation_suffix = log_cfg.get("rotationSuffix", DEFAULT_ROTATION_SUFFIX)

    if not path.is_file():
        logger.error("[%s] Logdatei fehlt: %s", log_id, path)
        return None

    hits, found_start = _scan_file(
        path, start_pattern, patterns, use_date_filter, date_format
    )

    if not found_start and check_rotated:
        rotated_path = Path(str(path) + rotation_suffix)
        if rotated_path.is_file():
            logger.info("[%s] startPattern nicht in %s, prüfe Rotation %s",
                        log_id, path.name, rotated_path.name)
            hits_rot, _ = _scan_file(
                rotated_path, start_pattern, patterns,
                use_date_filter, date_format,
            )
            hits = hits_rot + hits
        else:
            logger.warning("[%s] Rotierte Datei fehlt: %s", log_id, rotated_path)

    if not hits:
        logger.info("[%s] Keine Treffer.", log_id)
        return None

    max_priority = max(h["priority"] for h in hits)
    logger.info("[%s] %d Treffer, höchste Priorität %d",
                log_id, len(hits), max_priority)

    headers = dict(global_cfg.get("headers", {}))
    headers.update(log_cfg.get("headers", {}))

    url = log_cfg.get("webhookUrl") or global_cfg.get("webhookUrl", "")
    method = log_cfg.get("method", "POST")
    raw_title = log_cfg.get("title", f"Log Notifier: {log_id}")
    title = _apply_emoji(raw_title, max_priority, global_cfg)

    message_lines = [f"[{log_id}] {len(hits)} Treffer (Prio {max_priority})"]
    for h in hits:
        message_lines.append(f"  {h['line']}")

    payload = {
        "title": title,
        "message": message,
        "priority": max_priority,
        "logId": log_id,
    }

    ok = send_webhook(url, method, headers, payload)
    if not ok:
        logger.error("[%s] Webhook-Versand fehlgeschlagen.", log_id)

    return {
        "logId": log_id,
        "hits": len(hits),
        "priority": max_priority,
        "webhook_ok": ok,
        "payload": payload,
    }


def run_all(settings: dict) -> list[dict]:
    global_cfg = settings.get("global", {})
    results = []
    for log_cfg in settings.get("logs", []):
        res = evaluate_log(log_cfg, global_cfg)
        if res:
            results.append(res)
    return results


def run_by_id(settings: dict, log_id: str) -> dict | None:
    global_cfg = settings.get("global", {})
    for log_cfg in settings.get("logs", []):
        if log_cfg["logId"] == log_id:
            return evaluate_log(log_cfg, global_cfg)
    logger.error("Keine Log-Definition mit logId=%s", log_id)
    return None
