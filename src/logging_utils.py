import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

_metrics_lock = threading.Lock()
_metrics_file = LOG_DIR / "metrics.jsonl"


def get_logger(name: str = "rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))
        fmt = os.getenv("LOG_FORMAT", "plain")
        handler = logging.StreamHandler()
        if fmt == "json":
            formatter = JsonLogFormatter()
        else:
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": int(record.created * 1000),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def emit_metric(event: str, **fields):
    payload = {"ts": time.time(), "event": event}
    payload.update(fields)
    line = json.dumps(payload, ensure_ascii=False)
    with _metrics_lock:
        with _metrics_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


@contextmanager
def span(name: str, logger=None, **extra):
    t0 = time.time()
    try:
        yield
    except Exception as e:
        if logger:
            logger.exception(f"span_error name={name} err={e}")
        emit_metric("span_error", name=name, error=str(e), **extra)
        raise
    else:
        dur = time.time() - t0
        if logger:
            logger.debug(f"span_end name={name} dur_ms={dur*1000:.1f}")
        emit_metric("span_end", name=name, duration_ms=round(dur * 1000, 2), **extra)
