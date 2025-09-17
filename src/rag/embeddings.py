import os
import time
from typing import List

import httpx

from ..logging_utils import emit_metric, get_logger

logger = get_logger("embeddings")

MODEL_ENV_NAME = "EMBED_MODEL"
DEFAULT_MODEL = "nomic-embed-text:v1.5"
OLLAMA_HOST_ENV = "OLLAMA_HOST"  # e.g. http://localhost:11434
OLLAMA_BASE_ENV = "OLLAMA_BASE_URL"  # alternate env name used elsewhere in repo
OLLAMA_PROBE_ENV = "OLLAMA_PROBE"  # set to '0' to disable probe
OLLAMA_FORCE_PROMPT_ENV = "OLLAMA_FORCE_PROMPT"  # set to '1' to prefer prompt-only payloads


class LocalOllamaEmbedding:
    def __init__(self, model: str | None = None, host: str | None = None, batch_size: int = 8):
        self.model = model or os.getenv(MODEL_ENV_NAME, DEFAULT_MODEL)
        # Accept either OLLAMA_HOST or OLLAMA_BASE_URL for compatibility
        raw_host = (
            host or os.getenv(OLLAMA_HOST_ENV) or os.getenv(OLLAMA_BASE_ENV) or "127.0.0.1:11434"
        )
        # auto-add scheme if missing
        if not raw_host.startswith("http://") and not raw_host.startswith("https://"):
            raw_host = "http://" + raw_host
        self.host = raw_host.rstrip("/")
        self.batch_size = batch_size
        self.max_chars = int(
            os.getenv("EMBED_MAX_CHARS", "3500")
        )  # truncate overly long chunk to avoid 5xx
        self.client = httpx.Client(timeout=120)
        # Probe optionally (can be disabled via env OLLAMA_PROBE=0)
        probe_enabled = os.getenv(OLLAMA_PROBE_ENV, "1") not in ("0", "false", "False")
        if probe_enabled:
            try:
                self._probe_host()
            except Exception as e:
                logger.debug("Ollama probe failed: %s", e)

    def _embed_batch(self, batch: List[str]) -> List[List[float]]:
        # Ollama embeddings API is single prompt per call currently; loop inside
        vectors: List[List[float]] = []
        for text in batch:
            original_len = len(text)
            if original_len > self.max_chars:
                text = text[: self.max_chars]
            payload = {"model": self.model, "prompt": text}
            retries = 4
            backoff = 1.5
            for attempt in range(1, retries + 1):
                try:
                    # Try two common payload formats to be tolerant to different Ollama versions
                    last_exc = None
                    # Decide payload variants: prefer prompt; if OLLAMA_FORCE_PROMPT=1 then do not fall back to input variants
                    force_prompt = os.getenv(OLLAMA_FORCE_PROMPT_ENV, "0") in ("1", "true", "True")
                    variants = (
                        (payload,)
                        if force_prompt
                        else (payload, {"model": self.model, "input": [text]})
                    )
                    for p in variants:
                        try:
                            logger.debug(
                                "Ollama request payload=%s",
                                p if len(str(p)) < 1000 else "payload(len>1000)",
                            )
                            r = self.client.post(f"{self.host}/api/embeddings", json=p)
                            logger.debug(
                                "Ollama resp status=%s headers=%s body=%s",
                                r.status_code,
                                dict(r.headers),
                                (r.text or "")[:2000],
                            )
                            if r.status_code >= 500:
                                # include response body in log to help debug 502/5xx
                                logger.debug("Ollama 5xx body: %s", (r.text or "")[:4000])
                                last_exc = RuntimeError(f"Server {r.status_code}")
                                # try next payload variant
                                continue
                            r.raise_for_status()
                            data = r.json()
                            # If the server returns an empty dict ({}), log it distinctly to aid debugging
                            if isinstance(data, dict) and not data:
                                logger.warning(
                                    "Ollama returned empty JSON object for payload type; payload=%s",
                                    "prompt" if "prompt" in p else "input",
                                )
                                logger.debug("Empty body: %s", r.text)
                            # accomodate different response shapes across Ollama versions
                            vec = None
                            # common shapes: {"embedding": [...]}, {"embeddings": [...]}, {"data": [{"embedding": [...]}]}
                            if isinstance(data, dict):
                                if "embedding" in data and isinstance(data["embedding"], list):
                                    vec = data["embedding"]
                                elif (
                                    "embeddings" in data
                                    and isinstance(data["embeddings"], list)
                                    and data["embeddings"]
                                ):
                                    # embeddings may be list of lists
                                    vec = data["embeddings"][0]
                                elif (
                                    "data" in data
                                    and isinstance(data["data"], list)
                                    and data["data"]
                                ):
                                    first = data["data"][0]
                                    if isinstance(first, dict) and "embedding" in first:
                                        vec = first["embedding"]
                            # sometimes API returns a list at top level
                            if vec is None and isinstance(data, list) and data:
                                first = data[0]
                                if isinstance(first, dict) and "embedding" in first:
                                    vec = first["embedding"]
                            # normalize dict-shaped embeddings (some versions may return dict keyed by index)
                            if isinstance(vec, dict):
                                # try convert {'0': val0, '1': val1} or {0: val0, ...} -> [val0, val1, ...]
                                try:
                                    # sort keys numerically when possible
                                    items = sorted(
                                        vec.items(),
                                        key=lambda kv: (
                                            int(kv[0])
                                            if isinstance(kv[0], str) and kv[0].isdigit()
                                            else (kv[0] if isinstance(kv[0], int) else 0)
                                        ),
                                    )
                                    vec = [v for _, v in items]
                                except Exception:
                                    # fallback: try common nested field
                                    if "values" in vec and isinstance(vec["values"], list):
                                        vec = vec["values"]
                                    else:
                                        if not vec:
                                            last_exc = RuntimeError(
                                                "empty embedding dict returned by server"
                                            )
                                            logger.debug(
                                                "Empty embedding dict in response: %s", data
                                            )
                                            continue
                            if vec is None:
                                last_exc = RuntimeError("no embedding field in response")
                                logger.debug("Unexpected embedding response shape: %s", data)
                                continue
                            vectors.append(vec)
                            emit_metric(
                                "embed_ok", length=len(text), truncated=(original_len != len(text))
                            )
                            raise StopIteration  # success: break outer retry loop
                        except StopIteration:
                            break
                        except Exception as inner_e:
                            last_exc = inner_e
                            logger.debug("Ollama inner attempt failed: %s", inner_e)
                    else:
                        # both payload attempts failed for this retry
                        raise last_exc or RuntimeError("unknown embedding error")
                except Exception as e:
                    if attempt == retries:
                        emit_metric("embed_error", length=len(text), attempt=attempt, error=str(e))
                        logger.error(f"embed_error length={len(text)} attempts={attempt} err={e}")
                        raise RuntimeError(
                            f"Ollama embeddings request failed after {retries} attempts: {e}"
                        )
                    # Adaptive fallback: if server error, progressively truncate further
                    if "Server 502" in str(e) and len(text) > 800:
                        text = text[: max(800, int(len(text) * 0.6))]
                        payload["prompt"] = text
                    emit_metric("embed_retry", length=len(text), attempt=attempt, error=str(e))
                    logger.warning(f"embed_retry attempt={attempt} len={len(text)} err={e}")
                    time.sleep(backoff)
                    backoff *= 2
        return vectors

    def _probe_host(self) -> None:
        """Lightweight probe to list models — logs model list or errors to help diagnose 5xx."""
        try:
            url = f"{self.host}/api/models"
            r = self.client.get(url)
            logger.debug("Ollama probe status=%s body=%s", r.status_code, (r.text or "")[:2000])
            if r.status_code == 200:
                try:
                    data = r.json()
                    # try to find model in returned list (shape may vary)
                    names = []
                    if isinstance(data, dict) and "models" in data:
                        for m in data.get("models", []):
                            if isinstance(m, dict) and "name" in m:
                                names.append(m.get("name"))
                            elif isinstance(m, str):
                                names.append(m)
                    elif isinstance(data, list):
                        for m in data:
                            if isinstance(m, dict) and "name" in m:
                                names.append(m.get("name"))
                            elif isinstance(m, str):
                                names.append(m)
                    logger.info("Ollama models discovered: %s", names[:20])
                    if self.model and names and self.model not in names:
                        logger.warning(
                            "Requested embed model '%s' not in discovered models", self.model
                        )
                except Exception:
                    logger.debug("Could not parse Ollama probe response JSON")
            else:
                logger.warning("Ollama probe returned status %s", r.status_code)
        except Exception as e:
            logger.debug("Error probing Ollama host %s: %s", getattr(self, "host", "<unknown>"), e)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        all_vecs: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            all_vecs.extend(self._embed_batch(batch))
        return all_vecs

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


# LangChain adapter
try:
    from langchain.embeddings.base import Embeddings

    class OllamaEmbeddings(Embeddings):
        def __init__(self, model: str | None = None, host: str | None = None, batch_size: int = 8):
            self.client = LocalOllamaEmbedding(model, host, batch_size)

        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return self.client.embed_documents(texts)

        def embed_query(self, text: str) -> List[float]:
            return self.client.embed_query(text)

except ImportError:
    pass
