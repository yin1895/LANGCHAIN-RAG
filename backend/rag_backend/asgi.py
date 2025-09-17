import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

# Ensure project root is on sys.path so 'backend' package can be imported regardless of CWD
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Use fully-qualified settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.rag_backend.settings")
application = get_asgi_application()
