import json
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np

from ..logging_utils import emit_metric, get_logger, span
from .embeddings import OllamaEmbeddings

logger = get_logger("vector_store")


class FaissStore:
    def __init__(self, index_path: str, meta_path: str, dim: int | None = None):
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.dim = dim
        self._index = None
        self._metas: List[Dict[str, Any]] = []
        if self.index_path.exists() and self.meta_path.exists():
            self._load()

    def _create_index(self, dim: int):
        self._index = faiss.IndexFlatIP(dim)
        self.dim = dim

    def add(self, vectors: List[List[float]], metas: List[Dict[str, Any]]):
        arr = np.array(vectors, dtype="float32")
        if self._index is None:
            self._create_index(arr.shape[1])
        elif arr.shape[1] != self.dim:
            raise ValueError("Dimension mismatch")
        # Normalize for cosine similarity approximate
        faiss.normalize_L2(arr)
        self._index.add(arr)
        self._metas.extend(metas)

    def search(self, query: List[float], k: int = 5):
        if self._index is None:
            return []
        q = np.array([query], dtype="float32")
        faiss.normalize_L2(q)
        scores, idxs = self._index.search(q, k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:
                continue
            meta = self._metas[idx]
            results.append({"score": float(score), **meta})
        return results

    def persist(self):
        # Ensure target directories exist before attempting to write files
        try:
            if self.index_path.parent:
                self.index_path.parent.mkdir(parents=True, exist_ok=True)
            if self.meta_path.parent:
                self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.exception("failed to create vector_store directories: %s", e)
            raise

        if self._index is not None:
            try:
                faiss.write_index(self._index, str(self.index_path))
            except Exception as e:
                logger.exception("faiss.write_index failed: %s", e)
                raise
        try:
            with self.meta_path.open("w", encoding="utf-8") as f:
                for m in self._metas:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.exception("failed to write meta file %s: %s", self.meta_path, e)
            raise

    def _load(self):
        self._index = faiss.read_index(str(self.index_path))
        with self.meta_path.open("r", encoding="utf-8") as f:
            self._metas = [json.loads(line) for line in f]
        if self._metas:
            sample_vec = self._metas[0].get("vector")
            if sample_vec:
                self.dim = len(sample_vec)


def build_or_update(chunks: List[Dict], store: FaissStore, embed_model: OllamaEmbeddings):
    """Embed new chunks with per-item resilience.

    Strategy:
    - Deduplicate by hash.
    - For each new chunk, attempt embedding with progressive truncation lengths.
    - On total failure, skip that chunk (log in returned stats via negative count placeholder if needed).
    """
    existing_hashes = {m["hash"] for m in store._metas if "hash" in m}
    new_chunks = [c for c in chunks if c["hash"] not in existing_hashes]
    if not new_chunks:
        return 0
    vectors = []
    metas = []
    skipped = 0
    for c in new_chunks:
        content = c["content"]
        attempts = [None, 2000, 1200, 800, 600, 400]
        vec = None
        last_err = None
        for lim in attempts:
            text_try = content if lim is None else content[:lim]
            try:
                with span("embed_one", logger, limit=lim if lim else -1, orig_len=len(content)):
                    vec = embed_model.embed_documents([text_try])[0]
                # mark truncated
                if lim is not None and lim < len(content):
                    c["truncated_to"] = lim
                break
            except Exception as e:
                last_err = e
                logger.warning(f"embed_fail hash={c['hash']} limit={lim} err={e}")
                emit_metric("embed_fail", hash=c["hash"], limit=lim if lim else -1, error=str(e))
                continue
        if vec is None:
            skipped += 1
            logger.error(
                f"embed_skip hash={c['hash']} reason=all_attempts_failed last_err={last_err}"
            )
            emit_metric("embed_skip", hash=c["hash"], error=str(last_err) if last_err else "")
            continue
        m = {k: c[k] for k in ("hash", "source", "content") if k in c}
        if "truncated_to" in c:
            m["truncated_to"] = c["truncated_to"]
        m["vector"] = vec
        metas.append(m)
        vectors.append(vec)
    if vectors:
        store.add(vectors, metas)
        store.persist()
    logger.info(
        f"build_or_update added={len(vectors)} skipped={skipped} new_total={len(store._metas)}"
    )
    emit_metric("build_or_update", added=len(vectors), skipped=skipped, total=len(store._metas))
    # Optionally could return (added, skipped)
    return len(vectors)
