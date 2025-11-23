import importlib
import os
import traceback

# If running inside a Django project where DJANGO_SETTINGS_MODULE is set,
# call django.setup() so imports that rely on apps won't raise AppRegistryNotReady.
if os.environ.get("DJANGO_SETTINGS_MODULE"):
    try:
        import django

        django.setup()
        print("django.setup() called")
    except Exception as e:
        print("django.setup() failed:", e)

modules = [
    "backend.rag_api.views",
    "backend.rag_api.auth",
    "backend.rag_api.urls",
    "backend.rag_backend.settings",
    "backend.rag_backend.urls",
]
for m in modules:
    try:
        importlib.import_module(m)
        print("OK", m)
    except Exception:
        print("ERROR", m)
        traceback.print_exc()
