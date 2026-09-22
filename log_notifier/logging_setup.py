"""Zentrale Logging-Konfiguration für alle Skripte."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
DEFAULT_BACKUPS = 20


def _resolve_log_dir() -> Path:
    """Ermittelt ein beschreibbares Log-Verzeichnis."""
    env = os.getenv("LOG_NOTIFIER_LOG_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path("/var/log"))
    candidates.append(Path.home() / ".local" / "state" / "log-notifier")
    candidates.append(Path.cwd() / "logs")

    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            test = c / ".write_test"
            test.touch()
            test.unlink()
            return c
        except (OSError, PermissionError):
            continue
    raise RuntimeError("Kein beschreibbares Log-Verzeichnis gefunden.")


def setup_logging(name: str) -> logging.Logger:
    """Konfiguriert einen Logger mit Rotation + Konsole.

    name z.B. 'setup' oder 'run' -> logdatei notifier_<name>.log
    """
    logger = logging.getLogger(f"log_notifier.{name}")
    if logger.handlers:
        return logger  # schon konfiguriert

    logger.setLevel(logging.INFO)

    log_dir = _resolve_log_dir()
    log_file = log_dir / f"notifier_{name}.log"

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=int(os.getenv("LOG_NOTIFIER_MAX_BYTES", DEFAULT_MAX_BYTES)),
            backupCount=int(os.getenv("LOG_NOTIFIER_BACKUPS", DEFAULT_BACKUPS)),
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        # Falls Datei nicht schreibbar -> nur Konsole
        print(f"[warn] Datei-Logging deaktiviert: {exc}")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    logger.debug("Logging initialisiert, Datei: %s", log_file)
    return logger
