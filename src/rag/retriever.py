from typing import Dict, List, Optional

import jieba
from rank_bm25 import BM25Okapi

from ..logging_utils import emit_metric, get_logger
from .embeddings import OllamaEmbeddings
from .vector_store import FaissStore

logger = get_logger("retriever")


class Retriever:
    def __init__(
        self, store: FaissStore, embed: OllamaEmbeddings, k: int = 6, bm25_weight: float = 0.35
    ):
        self.store = store
        self.embed = embed
        self.k = k
        self.bm25_weight = bm25_weight
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_docs: List[Dict] = []
        self._build_bm25()

    def _build_bm25(self):
        # Build BM25 corpus from metas contents
        tokens_corpus = []
        for m in self.store._metas:
            text = m.get("content", "")
            toks = list(jieba.cut_for_search(text))
            tokens_corpus.append(toks)
            self._bm25_docs.append(m)
        if tokens_corpus:
            self._bm25 = BM25Okapi(tokens_corpus)

    def vector_search(self, query: str, k: int) -> List[Dict]:
        qv = self.embed.embed_query(query)
        return self.store.search(qv, k)

    def bm25_search(self, query: str, k: int) -> List[Dict]:
        if not self._bm25:
            return []
        toks = list(jieba.cut_for_search(query))
        scores_arr = self._bm25.get_scores(toks)
        scores = [float(s) for s in scores_arr]
        if not scores:
            return []
        max_score = max(scores) if scores else 1.0
        idx_sorted = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        out: List[Dict] = []
        for i in idx_sorted:
            meta = self._bm25_docs[i]
            norm = scores[i] / max_score if max_score else 0.0
            out.append({"score": norm, **meta, "bm25_raw": scores[i]})
        return out

    def get_relevant(self, query: str) -> List[Dict]:
        if self.bm25_weight <= 0:
            results = self.vector_search(query, self.k)
            # log simple results
            for i, r in enumerate(results):
                logger.debug(
                    f"hit[{i}] vec_only score={r['score']:.4f} src={r.get('source','')} hash={r['hash']}"
                )
            emit_metric("retrieve", mode="vector", hits=len(results), bm25_weight=0)
            return results
        vec_k = min(max(self.k * 2, self.k + 2), self.k * 4)  # adaptive over-fetch
        bm_k = vec_k
        vres = self.vector_search(query, vec_k)
        bres = self.bm25_search(query, bm_k)
        merged: Dict[str, Dict] = {}
        for r in vres:
            merged[r["hash"]] = {
                "combined": r["score"] * (1 - self.bm25_weight),
                "vec_score": r["score"],
                "bm25_score": 0.0,
                **r,
            }
        for r in bres:
            if r["hash"] in merged:
                merged[r["hash"]]["combined"] += r["score"] * self.bm25_weight
                merged[r["hash"]]["bm25_score"] = r["score"]
            else:
                merged[r["hash"]] = {
                    "combined": r["score"] * self.bm25_weight,
                    "vec_score": 0.0,
                    "bm25_score": r["score"],
                    **r,
                }
        ranked = sorted(merged.values(), key=lambda x: x["combined"], reverse=True)[: self.k]
        # detailed logging (limit 15 lines)
        for i, r in enumerate(ranked[:15]):
            logger.debug(
                f"hit[{i}] combined={r['combined']:.4f} vec={r.get('vec_score',0):.4f} bm25={r.get('bm25_score',0):.4f} src={r.get('source','')} hash={r['hash']}"
            )
        emit_metric(
            "retrieve",
            mode="hybrid",
            hits=len(ranked),
            bm25_weight=self.bm25_weight,
            cand_vec=len(vres),
            cand_bm=len(bres),
        )
        return ranked
