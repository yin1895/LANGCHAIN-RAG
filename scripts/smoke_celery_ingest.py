"""Smoke script to submit an ingest job.

Usage: python scripts/smoke_celery_ingest.py

It will try to call the Django endpoint POST /api/ingest if the backend is running,
otherwise it will try to import backend.tasks and call run_ingest_task directly.
"""

import os
import sys
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def try_http_submit():
    try:
        import requests

        resp = requests.post("http://localhost:8000/api/ingest")
        print("HTTP submit status", resp.status_code, resp.text)
        return True
    except Exception as e:
        print("HTTP submit failed:", e)
        return False


def try_direct_call():
    try:
        from backend.tasks import run_ingest_task

        # Ensure we don't parse large documents during smoke: use a tiny docs_root
        os.environ["DOCS_ROOT"] = os.environ.get(
            "DOCS_ROOT", os.path.join(ROOT, "tests", "fixtures", "docs_empty")
        )
        job_id = str(uuid.uuid4())
        print(
            "Calling run_ingest_task directly with job_id",
            job_id,
            "DOCS_ROOT=",
            os.environ["DOCS_ROOT"],
        )
        res = run_ingest_task(job_id)
        print("Direct result:", res)
        return True
    except Exception as e:
        print("Direct call failed:", e)
        return False


if __name__ == "__main__":
    if not try_http_submit():
        try_direct_call()
