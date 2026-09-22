"""Konfigurations-Laden, -Validierung und -Speicherung."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAME = "notifier_settings.json"
SCHEMA_VERSION = 1

ALLOWED_METHODS = {"GET", "POST", "PUT"}


class ConfigError(ValueError):
    """Fehler in der Konfiguration."""


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------

def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ConfigError(msg)


def _validate_pattern(p: Any, ctx: str) -> None:
    _require(isinstance(p, dict), f"{ctx}: Pattern muss ein Objekt sein")
    _require("regex" in p and isinstance(p["regex"], str) and p["regex"],
             f"{ctx}: 'regex' fehlt oder ist leer")
    prio = p.get("priority", 0)
    _require(isinstance(prio, int) and 0 <= prio <= 100,
             f"{ctx}: 'priority' muss int zwischen 0 und 100 sein")


def _validate_log(log: Any, idx: int) -> None:
    ctx = f"logs[{idx}]"
    _require(isinstance(log, dict), f"{ctx}: Eintrag muss ein Objekt sein")

    for key in ("logId", "filePath", "startPattern"):
        _require(isinstance(log.get(key), str) and log[key],
                 f"{ctx}: '{key}' fehlt oder ist leer")

    method = log.get("method", "POST")
    _require(method in ALLOWED_METHODS,
             f"{ctx}: 'method' muss eine von {sorted(ALLOWED_METHODS)} sein")

    for bool_key in ("useDateFilter", "checkRotatedLogs"):
        if bool_key in log:
            _require(isinstance(log[bool_key], bool),
                     f"{ctx}: '{bool_key}' muss boolean sein")

    for str_key in ("dateFormat", "rotationSuffix", "title", "webhookUrl"):
        if str_key in log:
            _require(isinstance(log[str_key], str),
                     f"{ctx}: '{str_key}' muss ein String sein")

    headers = log.get("headers", {})
    _require(isinstance(headers, dict),
             f"{ctx}: 'headers' muss ein Objekt sein")

    patterns = log.get("patterns")
    _require(isinstance(patterns, list) and patterns,
             f"{ctx}: 'patterns' muss eine nicht-leere Liste sein")
    for j, p in enumerate(patterns):
        _validate_pattern(p, f"{ctx}.patterns[{j}]")


def validate_settings(data: Any) -> None:
    """Wirft ConfigError, wenn data nicht dem Schema entspricht."""
    _require(isinstance(data, dict), "Root muss ein Objekt sein")

    # 'global' MUSS existieren und ein Objekt sein
    _require("global" in data and isinstance(data["global"], dict),
             "'global' fehlt oder ist kein Objekt")
    glob = data["global"]
    if "headers" in glob:
        _require(isinstance(glob["headers"], dict),
                 "'global.headers' muss ein Objekt sein")
    if "webhookUrl" in glob:
        _require(isinstance(glob["webhookUrl"], str),
                 "'global.webhookUrl' muss ein String sein")

    logs = data.get("logs")
    _require(isinstance(logs, list), "'logs' muss eine Liste sein")

    seen_ids: set[str] = set()
    for i, log in enumerate(logs):
        _validate_log(log, i)
        lid = log["logId"]
        _require(lid not in seen_ids, f"logs[{i}]: 'logId' doppelt: {lid}")
        seen_ids.add(lid)


# ---------------------------------------------------------------------------
# Laden / Speichern
# ---------------------------------------------------------------------------

def load_settings(path: str | os.PathLike[str]) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON-Fehler in {p}: {exc}") from exc
    validate_settings(data)
    return data


def save_settings(path: str | os.PathLike[str], data: dict) -> None:
    """Atomares Schreiben: erst tmp, dann replace."""
    validate_settings(data)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(p.parent), prefix=p.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, p)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def empty_settings() -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "global": {
            "webhookUrl": "",
            "headers": {"Content-Type": "application/json"},
        },
        "logs": [],
    }
