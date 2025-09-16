# Celery integration (local smoke & notes)

This document explains how to run a local Redis + Celery worker to process ingestion tasks.

Quick start (with Docker Compose):

1. Start services:

   docker compose up -d redis

2. Start a Celery worker (from repo root):

   # Make sure your Python env has requirements installed (celery, redis)
   # Option A: Use PowerShell helper (Windows)
   .\scripts\start_celery.ps1

   # Option B: direct command
   python -m celery -A backend.celery_app.celery worker --loglevel=info

3. Submit an ingest via the Django endpoint or via the smoke script in `scripts/`.

Notes:
- The small `docker-compose.yml` in repo provides a Redis service and a worker command example.
- In CI or production you should run both web and worker services in containers and configure persistent storage for job state rather than the in-memory `_INGEST_JOBS`.

Installing dependencies locally (optional):

```powershell
# activate your venv (example)
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If you prefer Docker, you can run Redis with `docker compose up -d redis` and run the worker locally after installing requirements.
