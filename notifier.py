#!/usr/bin/env python3
"""LOG_Notifyer – CLI-Einstiegspunkt.

Verwendung:
    python3 notifier.py configure [--config PATH]
    python3 notifier.py validate  [--config PATH]
    python3 notifier.py run --all  [--config PATH]
    python3 notifier.py run --id <logId> [--config PATH]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Erlaubt Aufruf aus beliebigem CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from log_notifier import __version__
from log_notifier import config as cfg
from log_notifier.logging_setup import setup_logging

DEFAULT_CONFIG = Path(__file__).resolve().parent / cfg.DEFAULT_CONFIG_NAME


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="notifier",
        description="LOG_Notifyer – stateless log watcher with webhooks",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("configure", help="Interaktive Konfiguration")
    pc.add_argument("--config", default=str(DEFAULT_CONFIG))

    pv = sub.add_parser("validate", help="Konfiguration prüfen")
    pv.add_argument("--config", default=str(DEFAULT_CONFIG))

    pr = sub.add_parser("run", help="Logs auswerten")
    pr.add_argument("--config", default=str(DEFAULT_CONFIG))
    grp = pr.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="Alle Logs prüfen")
    grp.add_argument("--id", help="Nur diesen logId prüfen")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "configure":
        # Lazy-Import: zieht kein requests/urllib3 → keine SSL-Warnung
        from log_notifier import setup_wizard
        logger = setup_logging("setup")
        logger.info("Konfigurations-Wizard gestartet")
        setup_wizard.run_wizard(args.config)
        return 0

    if args.command == "validate":
        logger = setup_logging("setup")
        try:
            cfg.load_settings(args.config)
        except cfg.ConfigError as exc:
            print(f"✘ Ungültig: {exc}")
            logger.error("Validierung fehlgeschlagen: %s", exc)
            return 2
        print(f"✔ Konfiguration OK: {args.config}")
        logger.info("Konfiguration OK: %s", args.config)
        return 0

    if args.command == "run":
        # Lazy-Import: erst hier brauchen wir requests
        from log_notifier import runner
        logger = setup_logging("run")
        try:
            settings = cfg.load_settings(args.config)
        except cfg.ConfigError as exc:
            logger.error("Konfiguration ungültig: %s", exc)
            print(f"✘ {exc}")
            return 2

        if args.all:
            results = runner.run_all(settings)
            logger.info("Lauf beendet, %d Benachrichtigung(en).", len(results))
            return 0

        if args.id:
            # Kein Treffer ist KEIN Fehler – Cron soll nicht alarmieren
            runner.run_by_id(settings, args.id)
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
