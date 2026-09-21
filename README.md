# Log Notifier

Ein generisches, zustandsloses (stateless) Tool zur Log-Auswertung und Webhook-Benachrichtigung. Es wurde entwickelt, um Logdateien effizient von unten nach oben auszulesen, Logrotationen nativ zu unterstüzen und bei definierten Mustern massgeschneiderte Webhooks auszulösen.

## Inhaltsverzeichnis

* [Hauptfunktionen](#features)
* [Installation & Setup](#installation)
* [Konfiguration](#konfiguration)
* [Vollständiges Konfigurationsbeispiel](#beispiel)
* [Nutzung (Skriptaufruf)](#nutzung)
* [Funktionsweise der Auswertung](#funktionsweise)

## Hauptfunktionen

* **Zustandsloses Lesen (Bottom-Up):** Sucht immer rückwärts vom Ende der Datei. Dadurch sind keine temporären State-Dateien nötig.
* **Logrotation-Unterstützung:** Liest nahtlos über Dateigrenzen hinweg (z. B. von `app.log` zu `app.log.1`), falls ein Start-Muster nicht in der aktuellen Datei gefunden wird.
* **Reguläre Ausdrücke (Regex):** Flexibles Definieren von Suchmustern mit individuellen Prioritäten.
* **Flexible Webhooks:** Unterstützt POST, GET und PUT. Header und URLs können global definiert und pro Log überschrieben oder ergänzt werden.
* **Datumsfilter:** Optionaler Filter, um ausschliesslich Log-Einträge des aktuellen Tages zu berücksichtigen. Format anpassbar.
* **Interaktives Setup:** Konfiguration via `setup.py` inklusive Tab-Autovervollständigung für Dateipfade.

## Installation & Setup

Das Projekt benötigt eine Standard-Python3-Umgebung sowie die Bibliothek `requests`. Es müssen keine weiteren externen Systempakete installiert werden.

1. Kopiere die Dateien `setup.py` und `notifier_run.py` in ein gewünschtes Verzeichnis (z. B. `/opt/log-notifier/`).
2. Führe das Setup-Skript aus, um die initiale Konfiguration zu erstellen:

   python3 setup.py

Das Skript führt dich durch ein interaktives Menü (Edit, Add, Remove), um die Einstellungen für deine Logdateien festzulegen. Die Konfiguration wird in der Datei `notifier_settings.json` gespeichert.

## Konfiguration

Die Struktur der generierten JSON-Konfiguration ist in zwei Hauptbereiche unterteilt: **Global** und **Logs**.

### Globale Einstellungen

Definiert die Standardwerte, die für alle Logs gelten, sofern sie nicht überschrieben werden.

* `webhookUrl`: Die Standard-URL (z. B. Gotify).
* `headers`: Standard-HTTP-Header (z. B. Content-Type).

### Log-spezifische Einstellungen

Für jedes zu überwachende Logfile können spezifische Parameter festgelegt werden:

Parameter

Beschreibung

`logId`

Eindeutige ID für den gezielten Aufruf per Kommandozeile.

`filePath`

Absoluter Pfad zur Logdatei (z. B. `/var/log/embycache.log`).

`startPattern`

Ein String, der den Beginn eines Ausführungsblocks markiert. Findet das Skript diesen Text (von unten nach oben lesend), stoppt es die Suche.

`useDateFilter`

`true/false`. Wenn aktiv, werden nur Zeilen verarbeitet, die das heutige Datum enthalten.

`dateFormat`

Das Datumsformat für den Filter (Standard: `%Y-%m-%d`). Akzeptiert gängige Python `strftime` Platzhalter.

`checkRotatedLogs`

`true/false`. Wenn aktiv, wird bei Fehlen des `startPattern` automatisch die rotierte Datei geprüft.

`rotationSuffix`

Die Dateiendung des rotierten Logs (Standard: `.1`).

`patterns`

Ein Array von Regex-Regeln. Jede Regel benötigt ein `regex` (das Suchmuster) und eine `priority`.

**Tipp zu Headern & URLs:** Wenn im Log-Block eine eigene `webhookUrl` oder eigene `headers` definiert werden, überschreiben/ergänzen diese die globalen Einstellungen.

## Vollständiges Konfigurationsbeispiel

Hier ist ein komplettes Beispiel der `notifier_settings.json`, das alle verfügbaren Parameter und Überschreibungen demonstriert.

```
{
  "global": {
    "webhookUrl": "http://GOTIFY-IP/message?token=GLOBAL-TOKEN",
    "headers": {
      "Content-Type": "application/json",
      "User-Agent": "LogNotifier/1.0"
    }
  },
  "logs": [
    {
      "logId": "embyCacheJob",
      "filePath": "/var/log/embycache.log",
      "webhookUrl": "http://GOTIFY-IP/message?token=SPECIFIC-TOKEN",
      "method": "POST",
      "headers": {
        "Authorization": "Bearer abc123def456"
      },
      "title": "EmbyCache Sync Abschluss",
      "useDateFilter": true,
      "dateFormat": "%Y-%m-%d",
      "startPattern": "Process started",
      "checkRotatedLogs": true,
      "rotationSuffix": ".1",
      "patterns": [
        {
          "regex": "Moved to cache:\\s*([\\d.]+)\\s*GB",
          "priority": 5
        },
        {
          "regex": "Moved to array:\\s*([\\d.]+)\\s*GB",
          "priority": 5
        },
        {
          "regex": "(?i)error|critical|failed",
          "priority": 20
        }
      ]
    }
  ]
}
```

### Beschreibung der Parameter im Beispiel

* **global.webhookUrl & headers:** Werden als Standard verwendet, falls im Log-Block nichts anderes definiert ist.
* **logs.webhookUrl:** Überschreibt in diesem Fall die globale URL mit einem spezifischen Token (z. B. für einen eigenen Gotify-Kanal).
* **logs.headers:** Der `Authorization`-Header wird zu den globalen Headern hinzugefügt. Der Request sendet somit `Content-Type`, `User-Agent` und `Authorization`.
* **method:** Setzt die HTTP-Methode für den Webhook (POST).
* **title:** Der Titel, der in der Push-Benachrichtigung angezeigt wird.
* **useDateFilter & dateFormat:** Es werden ausschliesslich Zeilen verarbeitet, die exakt das heutige Datum im Format `YYYY-MM-DD` enthalten.
* **startPattern:** Das Skript liest die Datei von unten nach oben, bis es exakt den String `Process started` findet. Alles darüber wird als veraltet ignoriert.
* **checkRotatedLogs & rotationSuffix:** Falls `Process started` in der aktuellen `embycache.log` nicht gefunden wird, öffnet das Skript nahtlos die `embycache.log.1` und sucht dort weiter.
* **patterns:** Die Regex-Muster suchen nach verschobenen Gigabytes (Priorität 5) und Fehlern (Priorität 20). Findet das Skript beides, wird die Webhook-Meldung mit der höchsten gefundenen Priorität (20) verschickt. Die extrahierten Werte (z. B. "45.2") werden durch die Regex-Gruppierung `(...)` sauber als Payload formatiert.

## Nutzung (Skriptaufruf)

Das Hauptskript `notifier_run.py` liest die JSON-Konfiguration ein und führt die Auswertung aus. Es bietet verschiedene Parameter für den gezielten Einsatz, z. B. als Cronjob oder am Ende eines anderen Skripts.

### Alle konfigurierten Logs prüfen

```
python3 notifier_run.py --all
```

### Ein spezifisches Log anhand der ID prüfen

```
python3 notifier_run.py --id myAppLog
```

### Eine alternative Konfigurationsdatei verwenden

```
python3 notifier_run.py --config /pfad/zur/anderen_config.json --all
```

## Funktionsweise der Auswertung (Bottom-Up Parsing)

1. Das Skript öffnet die Logdatei und liest sie **rückwärts (von der letzten zur ersten Zeile)**.
2. Jede Zeile wird gegen die definierten Regex-Muster (`patterns`) geprüft. Treffer werden im Speicher gesammelt.
3. Die Suche stoppt sofort, wenn das `startPattern` gefunden wird. Dies definiert den aktuellen, relevanten Ausführungsblock.
4. Wird der Dateianfang erreicht und das `startPattern` fehlt (weil das Log rotiert wurde), öffnet das Skript automatisch die rotierte Datei (z. B. `app.log.1`) und setzt die Rückwärts-Suche nahtlos fort.
5. Die gesammelten Treffer werden in chronologisch korrekte Reihenfolge (wieder von oben nach unten) gebracht und als Webhook versendet. Die höchste Priorität aller Treffer bestimmt die Priorität der Benachrichtigung.

**Eigene Skript-Logs:** Beide Skripte (`setup.py` und `notifier_run.py`) protokollieren ihre eigene Ausführung mit einer integrierten Logrotation (max. 20 Dateien à 10 MB) unter `/var/log/notifier_setup.log` und `/var/log/notifier_run.log`.