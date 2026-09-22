# LOG_Notifyer

Ein generisches, zustandsloses (stateless) Tool zur Log-Auswertung und
Webhook-Benachrichtigung. Es liest Logdateien **von unten nach oben**, um
den aktuellen Ausführungsblock zu finden, unterstützt Logrotation nativ
und verschickt bei definierten Mustern maßgeschneiderte Webhooks.

Getestet gegen **Gotify** (inkl. Bark-Plugin) und **ntfy**.

---

## Hauptfunktionen

- **Zustandsloses Lesen (Bottom-Up):** Sucht immer rückwärts vom Ende der
  Datei. Keine State-Dateien nötig.
- **Logrotation-Unterstützung:** Liest nahtlos über Dateigrenzen hinweg
  (z. B. `app.log` -> `app.log.1`), falls das Start-Muster nicht in der
  aktuellen Datei gefunden wird.
- **Regex-basierte Muster:** Mit individuellen Prioritäten.
- **Flexible Webhooks:** POST, GET, PUT. Header und URLs global und pro Log.
- **Datumsfilter:** Optional nur Einträge des aktuellen Tages.
- **Zeitzonenbewusst:** Datumsfilter über `LOG_NOTIFIER_TZ` konfigurierbar.
- **Emoji-Mapping:** Prioritätsabhängige Emojis vor dem Titel.
- **Interaktives Setup:** `configure`-Subcommand inkl. Tab-Completion.
- **Atomares Speichern:** Keine kaputten Configs bei Abbruch.
- **Webhook-Retry:** 3 Versuche mit Backoff.

---

## Voraussetzungen

- Python >= 3.9
- Python-Paket: `requests`
- Optional für saubere Tab-Completion: `gnureadline`

Installation:

    python3 -m pip install --user requests
    # optional:
    python3 -m pip install --user gnureadline

---

## Verzeichnisstruktur

    LOG-Notifier/
    |-- notifier.py                    # CLI-Einstiegspunkt
    |-- requirements.txt
    |-- notifier_settings.json         # wird vom Wizard erzeugt (nicht committen!)
    |-- README.md
    |-- LICENSE
    |-- .gitignore
    +-- log_notifier/
        |-- __init__.py
        |-- config.py                  # Laden / Validieren / atomar Speichern
        |-- logging_setup.py           # plattformunabhängige Logrotation
        |-- runner.py                  # Bottom-Up-Parsing + Emoji
        |-- webhook.py                 # HTTP-Layer mit Retry
        +-- setup_wizard.py            # interaktiver Wizard

---

## Nutzung

    # Konfiguration erstellen / bearbeiten
    python3 notifier.py configure

    # Konfiguration prüfen
    python3 notifier.py validate

    # Alle Logs prüfen
    python3 notifier.py run --all

    # Ein spezifisches Log prüfen
    python3 notifier.py run --id embyCacheJob

    # Alternative Konfigurationsdatei
    python3 notifier.py run --config /pfad/zu/config.json --all

---

## Konfiguration

Die Struktur der JSON-Konfiguration hat zwei Bereiche: **Global** und **Logs**.

### Global

| Feld | Beschreibung |
|---|---|
| `webhookUrl` | Standard-Webhook-URL |
| `headers` | Standard-Header (werden pro Log gemerged) |
| `priorityEmoji` | Optionales Mapping `{"<prio>": "<emoji>"}` |
| `priorityEmojiDefault` | Fallback-Emoji, wenn keine Stufe passt |

### Logs (pro Eintrag)

| Parameter | Beschreibung |
|---|---|
| `logId` | Eindeutige ID für `--id` |
| `filePath` | Absoluter Pfad zur Logdatei |
| `startPattern` | String, der den Beginn eines Ausführungsblocks markiert |
| `useDateFilter` | `true`/`false` - nur Zeilen mit heutigem Datum |
| `dateFormat` | Python-`strftime`-Format (Default: `%Y-%m-%d`) |
| `checkRotatedLogs` | `true`/`false` - rotierte Datei bei Bedarf prüfen |
| `rotationSuffix` | Endung der rotierten Datei (Default: `.1`) |
| `patterns` | Liste von `{ "regex": ..., "priority": ... }` |
| `method` | `POST` (Default), `GET`, `PUT` |
| `title` | Titel der Benachrichtigung |
| `webhookUrl` | Überschreibt die globale URL |
| `headers` | Ergänzt / überschreibt globale Header |

**Prioritäten:** Frei wählbar (0-100+). Der höchste Treffer bestimmt
die Priorität der Nachricht. Bei Gotify mit Bark-Plugin bewusst hoch
ansetzen (z. B. 20 für Fehler).

**Emoji-Auswahl:** Es gewinnt die **höchste definierte Stufe <= Treffer-Prio**.
Beispiel-Mapping:

    "priorityEmoji": {
      "0":  "ℹ️",
      "5":  "🔵",
      "8": "🟡",
      "9": "🔴",
      "10": "🚨"
    }

Bei Prio 20 wird das Emoji der Stufe 20 vor den Titel gesetzt.

---

## Beispiel: Gotify mit Bark-Plugin

    {
      "schemaVersion": 1,
      "global": {
        "webhookUrl": "http://GOTIFY-IP/message",
        "headers": {
          "Content-Type": "application/json",
          "X-Gotify-Key": "DEIN-APP-TOKEN"
        },
        "priorityEmoji": {
          "0":  "i",
          "5":  "b",
          "10": "y",
          "20": "r",
          "50": "!"
        }
      },
      "logs": [
        {
          "logId": "embyCacheJob",
          "filePath": "/mnt/user/appdata/embycache/embycache.log",
          "title": "EmbyCache Sync Abschluss",
          "useDateFilter": true,
          "startPattern": "Process started",
          "checkRotatedLogs": true,
          "patterns": [
            { "regex": "Moved to cache:\\s*([\\d.]+)\\s*GB", "priority": 5 },
            { "regex": "(?i)error|critical|failed",          "priority": 20 }
          ]
        }
      ]
    }

---

## Umgebungsvariablen

| Variable | Default | Zweck |
|---|---|---|
| `LOG_NOTIFIER_LOG_DIR` | `/var/log`, dann `~/.local/state/log-notifier`, dann `./logs` | Zielordner für Skript-Logs |
| `LOG_NOTIFIER_LOGLEVEL` | `INFO` | Log-Level (`DEBUG`, `INFO`, ...) |
| `LOG_NOTIFIER_MAX_BYTES` | `10485760` | Rotationsgröße der Skript-Logs |
| `LOG_NOTIFIER_BACKUPS` | `20` | Anzahl behaltener Logdateien |
| `LOG_NOTIFIER_TZ` | `Europe/Zurich` | Zeitzone für Datumsfilter |

---

## Wie das Bottom-Up-Parsing funktioniert

1. Datei wird von der letzten zur ersten Zeile gelesen.
2. Jede Zeile wird gegen die Patterns geprüft - Treffer werden gesammelt.
3. Bei Fund des `startPattern` stoppt die Suche.
4. Wurde das `startPattern` nicht gefunden und ist `checkRotatedLogs`
   aktiv, wird `datei.log.1` (bzw. `rotationSuffix`) weiter durchsucht.
5. Treffer werden chronologisch sortiert und als Webhook versendet.
   Die höchste Priorität bestimmt die Priorität der Benachrichtigung
   und die Auswahl des Emojis.

---

## Lizenz

MIT - siehe `LICENSE`.
