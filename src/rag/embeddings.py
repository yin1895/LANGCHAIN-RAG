import os
import httpx
import time
from ..logging_utils import get_logger, emit_metric
from typing import List

logger = get_logger('embeddings')

MODEL_ENV_NAME = 'EMBED_MODEL'
DEFAULT_MODEL = 'nomic-embed-text:v1.5'
OLLAMA_HOST_ENV = 'OLLAMA_HOST'  # e.g. http://localhost:11434


class LocalOllamaEmbedding:
    def __init__(self, model: str | None = None, host: str | None = None, batch_size: int = 8):
        self.model = model or os.getenv(MODEL_ENV_NAME, DEFAULT_MODEL)
        self.host = (host or os.getenv(OLLAMA_HOST_ENV) or 'http://localhost:11434').rstrip('/')
        self.batch_size = batch_size
        self.max_chars = int(os.getenv('EMBED_MAX_CHARS', '3500'))  # truncate overly long chunk to avoid 5xx
        self.client = httpx.Client(timeout=120)

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
                    r = self.client.post(f"{self.host}/api/embeddings", json=payload)
                    if r.status_code >= 500:
                        raise RuntimeError(f"Server {r.status_code}")
                    r.raise_for_status()
                    data = r.json()
                    vec = data['embedding']
                    # If we truncated, note in vector metadata upstream (handled by caller if needed)
                    vectors.append(vec)
                    emit_metric('embed_ok', length=len(text), truncated=(original_len!=len(text)))
                    break
                except Exception as e:
                    if attempt == retries:
                        emit_metric('embed_error', length=len(text), attempt=attempt, error=str(e))
                        logger.error(f"embed_error length={len(text)} attempts={attempt} err={e}")
                        raise RuntimeError(f"Ollama embeddings request failed after {retries} attempts: {e}")
                    # Adaptive fallback: if server error, progressively truncate further
                    if 'Server 502' in str(e) and len(text) > 800:
                        text = text[: max(800, int(len(text) * 0.6))]
                        payload['prompt'] = text
                    emit_metric('embed_retry', length=len(text), attempt=attempt, error=str(e))
                    logger.warning(f"embed_retry attempt={attempt} len={len(text)} err={e}")
                    time.sleep(backoff)
                    backoff *= 2
        return vectors

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        all_vecs: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
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
