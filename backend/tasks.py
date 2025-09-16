"""Celery tasks for backend. These are optional and will be used only if Celery is installed
and configured via backend.celery_app.
"""

import time
import traceback

try:
    from backend.rag_api.views import _INGEST_JOBS
except Exception:
    _INGEST_JOBS = None


def run_ingest_task(job_id: str):
    """Run ingest logic. This function is a plain callable so Celery or other runners
    can call it. If _INGEST_JOBS is available, update job status there for visibility.
    """
    jid = job_id
    if _INGEST_JOBS is not None:
        _INGEST_JOBS[jid] = {
            "status": "running",
            "started_at": int(time.time()),
            "finished_at": None,
            "error": None,
            "added": 0,
        }
    try:
        from src.config import get_settings as get_src_settings
        from src.ingestion.chunking import adaptive_chunk
        from src.ingestion.docx_parser import ingest_to_raw
        from src.rag.vector_store import build_or_update

        s = get_src_settings()
        raw = ingest_to_raw(s.docs_root)
        chunks = adaptive_chunk(raw, s.chunk_size, s.chunk_overlap)
        added = build_or_update(chunks, None, None)
        if _INGEST_JOBS is not None:
            _INGEST_JOBS[jid]["added"] = int(added)
            _INGEST_JOBS[jid]["status"] = "finished"
            _INGEST_JOBS[jid]["finished_at"] = int(time.time())
        return {"added": int(added)}
    except Exception as e:
        tb = traceback.format_exc()
        if _INGEST_JOBS is not None:
            _INGEST_JOBS[jid]["status"] = "error"
            _INGEST_JOBS[jid]["error"] = str(e)
            _INGEST_JOBS[jid]["finished_at"] = int(time.time())
        # include traceback in the raised exception to surface it to callers
        raise RuntimeError(f"ingest failed: {e}\n{tb}")


def run_ingest_sync():
    """Synchronous ingest entrypoint for edge mode.

    This runs the same logic as run_ingest_task but returns the result directly
    (no job tracking). Useful for tightly-coupled edge deployments where
    background workers add complexity.
    """
    try:
        from src.config import get_settings as get_src_settings
        from src.ingestion.chunking import adaptive_chunk
        from src.ingestion.docx_parser import ingest_to_raw
        from src.rag.vector_store import build_or_update

        s = get_src_settings()
        raw = ingest_to_raw(s.docs_root)
        chunks = adaptive_chunk(raw, s.chunk_size, s.chunk_overlap)
        added = build_or_update(chunks, None, None)
        return {"added": int(added), "raw_items": len(raw), "chunks": len(chunks)}
    except Exception:
        raise


# If Celery is present, expose a task wrapper
try:
    from backend.celery_app import celery as celery_app  # type: ignore

    @celery_app.task(name="backend.tasks.run_ingest")
    def run_ingest(job_id: str):
        return run_ingest_task(job_id)

except Exception:
    # Celery not available; no-op
    pass
