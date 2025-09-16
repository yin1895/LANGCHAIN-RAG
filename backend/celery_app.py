import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# For quick local smoke tests, allow memory transport but use an RPC result backend
# because some transports don't provide a result backend implementation named 'memory'.
_broker = REDIS_URL
_backend = REDIS_URL
if REDIS_URL and REDIS_URL.startswith("memory://"):
	_broker = REDIS_URL
	_backend = "rpc://"

# Create Celery app and export both `app` and `celery` names for compatibility
app = Celery("backend", broker=_broker, backend=_backend)
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.worker_prefetch_multiplier = 1

# export canonical name used elsewhere
celery = app

# Optionally autodiscover tasks in the backend package
try:
	app.autodiscover_tasks(['backend'])
except Exception:
	# best-effort: if autodiscover fails during static analysis, ignore
	pass
