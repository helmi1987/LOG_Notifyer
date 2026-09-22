"""Interaktiver Konfigurations-Wizard."""
from __future__ import annotations

import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Readline-Setup: gnureadline (GNU) hat Vorrang vor macOS-libedit
# ---------------------------------------------------------------------------
_readline_module = None
_readline_backend = "none"

try:
    import gnureadline as _readline_module  # type: ignore
    _readline_backend = "gnu"
except ImportError:
    try:
        import readline as _readline_module  # type: ignore
        # Auf macOS ist das meist libedit
        if "libedit" in getattr(_readline_module, "__doc__", "") or "":
            _readline_backend = "libedit"
        else:
            _readline_backend = "gnu"
    except ImportError:
        _readline_module = None

from . import config as cfg

logger = logging.getLogger("log_notifier.setup")


# ---------------------------------------------------------------------------
# Tab-Completion für Dateipfade
# ---------------------------------------------------------------------------

def _path_completer(text: str, state: int):
    try:
        expanded = str(Path(text).expanduser()) if text else "."
        p = Path(expanded)
        if text.endswith("/") or p.is_dir():
            base = p
            prefix = ""
        else:
            base = p.parent
            prefix = p.name
        if not base.is_dir():
            return None
        matches = [
            str(base / name)
            for name in sorted(x.name for x in base.iterdir())
            if name.startswith(prefix)
        ]
        for i, m in enumerate(matches):
            if Path(m).is_dir():
                matches[i] = m + "/"
        return matches[state] if state < len(matches) else None
    except Exception:
        return None


def _enable_path_completion() -> None:
    """Aktiviert Completion je nach Backend."""
    if _readline_module is None:
        return
    try:
        _readline_module.set_completer(_path_completer)
        if _readline_backend == "gnu":
            _readline_module.parse_and_bind("tab: complete")
        else:
            # libedit braucht andere Bindings
            _readline_module.parse_and_bind("bind ^I rl_complete")
        _readline_module.set_completer_delims(" \t\n")
    except Exception:
        pass


def _disable_path_completion() -> None:
    if _readline_module is None:
        return
    try:
        _readline_module.set_completer(None)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Eingabe-Helfer
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: str | None = None, required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if default:
            return default
        if not required:
            return ""
        print("  ⚠ Eingabe erforderlich.")


def _ask_path(prompt: str, default: str | None = None, required: bool = True) -> str:
    """Wie _ask, aber mit Tab-Completion für Pfade."""
    _enable_path_completion()
    try:
        return _ask(prompt, default, required)
    finally:
        _disable_path_completion()


def _ask_bool(prompt: str, default: bool = False) -> bool:
    d = "J/n" if default else "j/N"
    raw = input(f"{prompt} [{d}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("j", "ja", "y", "yes", "1", "true")


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  ⚠ Bitte eine Zahl eingeben.")


def _ask_choice(prompt: str, choices: list[str], default: str) -> str:
    print(f"{prompt} ({'/'.join(choices)})")
    while True:
        raw = input(f"  Auswahl [{default}]: ").strip().upper()
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"  ⚠ Erlaubt: {choices}")


# ---------------------------------------------------------------------------
# Log-Bearbeitung
# ---------------------------------------------------------------------------

def _edit_patterns(existing: list[dict] | None = None) -> list[dict]:
    patterns = list(existing or [])
    print("\n  Aktuelle Patterns:")
    for i, p in enumerate(patterns):
        print(f"    [{i}] Prio {p.get('priority', 0):>3}  {p['regex']}")
    if not patterns:
        print("    (keine)")

    while _ask_bool("  Pattern hinzufügen?", default=not patterns):
        regex = _ask("    Regex", required=True)
        prio = _ask_int("    Priorität", 10)
        patterns.append({"regex": regex, "priority": prio})

    while patterns and _ask_bool("  Pattern löschen?", default=False):
        idx = _ask_int("    Index", 0)
        if 0 <= idx < len(patterns):
            patterns.pop(idx)
            print("    entfernt.")
        else:
            print("    ⚠ ungültiger Index.")

    return patterns


def _edit_log(existing: dict | None = None) -> dict:
    log = dict(existing or {})
    print("\n--- Log-Eintrag bearbeiten ---")

    log["logId"] = _ask("logId", log.get("logId"), required=True)
    log["filePath"] = _ask_path("filePath", log.get("filePath"), required=True)
    log["startPattern"] = _ask("startPattern", log.get("startPattern"), required=True)

    if _ask_bool("Methode ändern?", default="method" not in log):
        log["method"] = _ask_choice(
            "HTTP-Methode", ["POST", "GET", "PUT"], log.get("method", "POST")
        )

    log["useDateFilter"] = _ask_bool(
        "Datumsfilter verwenden?", log.get("useDateFilter", False)
    )
    if log["useDateFilter"]:
        log["dateFormat"] = _ask(
            "  dateFormat", log.get("dateFormat", "%Y-%m-%d")
        )

    log["checkRotatedLogs"] = _ask_bool(
        "Rotierte Logs prüfen?", log.get("checkRotatedLogs", True)
    )
    if log["checkRotatedLogs"]:
        log["rotationSuffix"] = _ask(
            "  rotationSuffix", log.get("rotationSuffix", ".1")
        )

    if _ask_bool("Eigene Webhook-URL für dieses Log?",
                 default=bool(log.get("webhookUrl"))):
        log["webhookUrl"] = _ask(
            "  URL", log.get("webhookUrl"), required=True
        )
    else:
        log.pop("webhookUrl", None)

    if _ask_bool("Eigene Header für dieses Log?",
                 default=bool(log.get("headers"))):
        headers = dict(log.get("headers", {}))
        while _ask_bool("  Header hinzufügen/ändern?", default=not headers):
            k = _ask("    Name", required=True)
            v = _ask("    Wert", required=True)
            headers[k] = v
        log["headers"] = headers
    else:
        log.pop("headers", None)

    log["title"] = _ask(
        "Benachrichtigungstitel",
        log.get("title", f"Log Notifier: {log['logId']}"),
    )

    log["patterns"] = _edit_patterns(log.get("patterns"))
    return log


def _edit_global(settings: dict) -> None:
    print("\n--- Globale Einstellungen ---")
    glob = settings.setdefault("global", {})
    glob["webhookUrl"] = _ask("Globale Webhook-URL", glob.get("webhookUrl", ""))

    headers = dict(glob.get("headers", {"Content-Type": "application/json"}))
    while _ask_bool("Globalen Header hinzufügen/ändern?", default=not headers):
        k = _ask("  Name", required=True)
        v = _ask("  Wert", required=True)
        headers[k] = v
    glob["headers"] = headers


# ---------------------------------------------------------------------------
# Hauptmenü
# ---------------------------------------------------------------------------

def _print_menu(settings: dict) -> None:
    glob = settings.setdefault("global", {})
    print("\n" + "=" * 60)
    print(" LOG_Notifyer – Konfiguration")
    print("=" * 60)
    print(" Globale URL:", glob.get("webhookUrl") or "(leer)")
    print(" Logs:")
    for i, log in enumerate(settings.get("logs", [])):
        print(f"  [{i}] {log['logId']:<20} {log['filePath']}")
    if not settings.get("logs"):
        print("   (keine)")
    print("-" * 60)
    print(" [a] Log hinzufügen")
    print(" [e] Log bearbeiten")
    print(" [d] Log löschen")
    print(" [g] Globale Einstellungen")
    print(" [s] Speichern & beenden")
    print(" [q] Beenden ohne Speichern")


def run_wizard(config_path: str) -> None:
    path = Path(config_path)
    if path.is_file():
        try:
            settings = cfg.load_settings(path)
        except cfg.ConfigError as exc:
            print(f"⚠ Bestehende Config ungültig: {exc}")
            print("  Starte mit leerer Vorlage.")
            settings = cfg.empty_settings()
    else:
        settings = cfg.empty_settings()

    settings.setdefault("schemaVersion", cfg.SCHEMA_VERSION)
    settings.setdefault("global", {})
    settings.setdefault("logs", [])

    if _readline_module is None:
        print("ℹ Tab-Completion deaktiviert (kein readline verfügbar).")
    elif _readline_backend == "libedit":
        print("ℹ Tab-Completion via libedit aktiv "
              "(installiere 'gnureadline' für besseres Verhalten).")
    else:
        print("ℹ Tab-Completion via GNU readline aktiv.")

    while True:
        _print_menu(settings)
        choice = input(" Auswahl: ").strip().lower()

        if choice == "a":
            try:
                settings["logs"].append(_edit_log())
            except KeyboardInterrupt:
                print("\n  Abgebrochen.")
        elif choice == "e":
            idx = _ask_int(" Index", 0)
            if 0 <= idx < len(settings["logs"]):
                settings["logs"][idx] = _edit_log(settings["logs"][idx])
            else:
                print(" ⚠ ungültiger Index.")
        elif choice == "d":
            idx = _ask_int(" Index", 0)
            if 0 <= idx < len(settings["logs"]):
                removed = settings["logs"].pop(idx)
                print(f" gelöscht: {removed['logId']}")
            else:
                print(" ⚠ ungültiger Index.")
        elif choice == "g":
            _edit_global(settings)
        elif choice == "s":
            try:
                cfg.save_settings(path, settings)
            except cfg.ConfigError as exc:
                print(f" ⚠ Speichern fehlgeschlagen: {exc}")
                continue
            print(f" ✔ Gespeichert: {path}")
            logger.info("Konfiguration gespeichert: %s", path)
            return
        elif choice == "q":
            print(" Abgebrochen, nichts gespeichert.")
            return
        else:
            print(" ⚠ Unbekannte Auswahl.")
