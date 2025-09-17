import re
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

        # Math modeling domain keywords for query expansion
        self.domain_keywords = {
            "优化": ["线性规划", "整数规划", "非线性规划", "多目标优化", "约束优化"],
            "模型": ["数学模型", "建模", "模型建立", "模型求解", "模型验证"],
            "算法": ["遗传算法", "模拟退火", "粒子群优化", "动态规划", "贪心算法"],
            "统计": ["回归分析", "时间序列", "概率模型", "假设检验", "方差分析"],
            "预测": ["预测模型", "趋势分析", "时间序列预测", "机器学习预测"],
            "评价": ["评价体系", "层次分析法", "模糊评价", "综合评价"],
        }

    def _expand_query(self, query: str) -> str:
        """Expand query with domain-specific keywords for better retrieval"""
        expanded_terms = []
        query_lower = query.lower()

        for key, expansions in self.domain_keywords.items():
            if key in query_lower:
                expanded_terms.extend(expansions[:2])  # Add top 2 related terms

        if expanded_terms:
            expanded_query = query + " " + " ".join(expanded_terms)
            logger.debug(f"Query expanded: '{query}' -> '{expanded_query}'")
            return expanded_query

        return query

    def _preprocess_query(self, query: str) -> str:
        """Clean and normalize query for better matching"""
        # Remove special characters except Chinese, English, and numbers
        query = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", " ", query)
        # Normalize whitespace
        query = " ".join(query.split())
        return query.strip()

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
        processed_query = self._preprocess_query(query)
        expanded_query = self._expand_query(processed_query)
        qv = self.embed.embed_query(expanded_query)
        return self.store.search(qv, k)

    def bm25_search(self, query: str, k: int) -> List[Dict]:
        if not self._bm25:
            return []
        processed_query = self._preprocess_query(query)
        toks = list(jieba.cut_for_search(processed_query))
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
        """Enhanced retrieval with query preprocessing and adaptive ranking"""
        if not query.strip():
            return []

        # Use adaptive k based on query complexity
        query_complexity = len(query.split()) + len(list(jieba.cut(query)))
        adaptive_k = min(self.k + (query_complexity // 5), self.k * 2)

        if self.bm25_weight <= 0:
            results = self.vector_search(query, adaptive_k)
            # Apply relevance filtering
            results = self._filter_relevant(results, query)
            results = results[: self.k]  # Return to original k

            for i, r in enumerate(results):
                logger.debug(
                    f"hit[{i}] vec_only score={r['score']:.4f} src={r.get('source','')} hash={r['hash']}"
                )
            emit_metric("retrieve", mode="vector", hits=len(results), bm25_weight=0)
            return results

        vec_k = min(max(adaptive_k * 2, adaptive_k + 2), adaptive_k * 4)
        bm_k = vec_k
        vres = self.vector_search(query, vec_k)
        bres = self.bm25_search(query, bm_k)

        # Enhanced merging with adaptive weights
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

        ranked = sorted(merged.values(), key=lambda x: x["combined"], reverse=True)
        # Apply relevance filtering and return top k
        ranked = self._filter_relevant(ranked, query)[: self.k]

        for i, r in enumerate(ranked[:15]):
            logger.debug(
                f"hit[{i}] combined={r['combined']:.4f} vec={r.get('vec_score',0):.4f} bm25={r.get('bm25_score',0):.4f} src={r.get('source','')} hash={r['hash']}"
            )
        emit_metric(
            "retrieve",
            mode="hybrid",
            hits=len(ranked),
            bm25_weight=self.bm25_weight,
            vec_hits=len(vres),
            bm25_hits=len(bres),
        )
        return ranked

    def _filter_relevant(self, results: List[Dict], query: str) -> List[Dict]:
        """Filter results based on relevance threshold and content quality"""
        if not results:
            return results

        # Remove results with very low scores (below threshold)
        score_threshold = 0.1
        filtered = [r for r in results if r.get("score", 0) >= score_threshold]

        # Remove duplicate or very similar content based on content hash overlap
        unique_results = []
        # store immutable signatures to allow hashing and fast membership checks
        seen_content = set()

        for result in filtered:
            content = result.get("content", "")
            if content:
                # Create a simple content signature for deduplication
                # use frozenset so it can be stored in a set for seen-content tracking
                content_words = frozenset(jieba.cut(content))
                is_duplicate = False

                for seen_words in seen_content:
                    # seen_words is a frozenset as well; set operations work with frozenset
                    overlap = len(content_words & seen_words) / max(
                        len(content_words | seen_words), 1
                    )
                    if overlap > 0.8:  # 80% similarity threshold
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_content.add(content_words)
                    unique_results.append(result)
            else:
                unique_results.append(result)

        return unique_results
