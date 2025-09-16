<#
Start a Celery worker using the current Python environment.
Usage (PowerShell):
  .\scripts\start_celery.ps1

This script does NOT install dependencies. Ensure you have installed requirements (pip install -r requirements.txt)
and have Redis running (e.g. via Docker). It will run: python -m celery -A backend.celery_app.celery worker --loglevel=info
#>
$ErrorActionPreference = 'Stop'
$python = "python"
Write-Host "Starting Celery worker with Python: $python"
& $python -m celery -A backend.celery_app.celery worker --loglevel=info