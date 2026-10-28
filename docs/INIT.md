# API lokal einrichten

## Einmalig einrichten

```powershell | sh
# 1. Projektumgebung anlegen
py -3.13 -m venv api/.venv

# 2. Abhängigkeiten installieren
api/.venv/Scripts/python.exe -m pip install -r api/requirements.txt
```

Konfiguration (Dev-Defaults, siehe `api/src/modeling_api/core/config.py`) ist bereits fest hinterlegt,
für lokale Entwicklung ist keine `.env`-Datei mehr nötig.

VS Code interpreter auswählen über **Strg+Shift+P** → **Python: Select Interpreter** → **api/.venv**

## Starten

```powershell | sh
# 1. Datenbank und Collab-Kit starten (Container, laufen im Hintergrund)
docker compose up -d mongo collab-kit

# 2. venv für dieses Terminal aktivieren
# Windows
api/.venv/Scripts/Activate.ps1
# Linux / macOS
source api/.venv/bin/activate

# 3. API mit Auto-Reload starten
cd api
uvicorn modeling_api.main:app --app-dir src --reload
```

Danach im Browser öffnen: <http://localhost:8000/docs> (Swagger UI, interaktive Doku).

## Häufige Kommandos

```sh
docker compose up -d mongo collab-kit   # Datenbank und Collab-Kit starten
docker compose logs -f mongo    # Datenbank-Logs
docker compose down             # alles stoppen
uvicorn modeling_api.main:app --app-dir src --reload   # API mit Auto-Reload
docker compose up -d --build    # alle Container neu bauen und starten
```
