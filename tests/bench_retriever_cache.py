import os
import sys

sys.path.insert(0, os.path.abspath("."))
import numpy as np  # noqa: E402

from src.rag.retriever import Retriever  # noqa: E402
from src.rag.vector_store import FaissStore  # noqa: E402


# Simple dummy embed that returns a vector based on provided numpy vector (we'll bypass it)
class DummyEmbed:
    def __init__(self, dim):
        self.dim = dim

    def embed_query(self, q):
        # q is a string; map to deterministic vector by hashing
        h = abs(hash(q))
        rng = np.random.RandomState(h % (2**32))
        v = rng.randn(self.dim).astype("float32")
        v = v / np.linalg.norm(v)
        return v.tolist()


# Simple cache fallback if cachetools not installed
class SimpleCache(dict):
    def get(self, k, default=None):
        return super().get(k, default)


# Build a FaissStore with random vectors
def build_store(num=2000, dim=128):
    idx = "tests/bench_index.faiss"
    meta = "tests/bench_meta.jsonl"
    try:
        os.remove(idx)
    except Exception:
        pass
    try:
        os.remove(meta)
    except Exception:
        pass
    store = FaissStore(idx, meta)
    vectors = []
    metas = []
    rng = np.random.RandomState(1234)
    for i in range(num):
        v = rng.randn(dim).astype("float32")
        v = v / np.linalg.norm(v)
        vectors.append(v.tolist())
        metas.append({"hash": f"h{i}", "source": f"s{i}", "content": f"doc {i}"})
    store.add(vectors, metas)
    store.persist()
    return store


def bench(retriever, query, runs=50):
    import time

    ts = []
    # warmup
    for _ in range(5):
        _ = retriever.get_relevant(query)
    for _ in range(runs):
        t0 = time.perf_counter()
        _ = retriever.get_relevant(query)
        t1 = time.perf_counter()
        ts.append((t1 - t0) * 1000)
    ts = sorted(ts)
    return {
        "min_ms": ts[0],
        "p50_ms": ts[len(ts) // 2],
        "p95_ms": ts[int(len(ts) * 0.95) - 1],
        "mean_ms": sum(ts) / len(ts),
    }


def main():
    num = 2000
    dim = 128
    print("building store...", num, "vectors")
    store = build_store(num=num, dim=dim)
    embed = DummyEmbed(dim)

    # Vector-only retriever (bm25_weight=0)
    r_vec = Retriever(store, embed, k=6, bm25_weight=0)
    # Ensure cache disabled
    r_vec._local_cache = None
    r_vec._use_redis = False

    q = "sample query for bench"
    print("Benchmark vector-only WITHOUT cache...")
    res0 = bench(r_vec, q, runs=40)
    print(res0)

    # Enable simple local cache
    r_vec._local_cache = SimpleCache()
    print("First call to populate cache...")
    _ = r_vec.get_relevant(q)
    print("Benchmark vector-only WITH cache (repeated calls)...")
    res1 = bench(r_vec, q, runs=40)
    print(res1)

    # Hybrid retriever (bm25_weight=0.35)
    r_h = Retriever(store, embed, k=6, bm25_weight=0.35)
    r_h._local_cache = None
    r_h._use_redis = False
    print("Benchmark hybrid WITHOUT cache...")
    res2 = bench(r_h, q, runs=30)
    print(res2)

    r_h._local_cache = SimpleCache()
    _ = r_h.get_relevant(q)
    print("Benchmark hybrid WITH cache...")
    res3 = bench(r_h, q, runs=30)
    print(res3)

    print("\nSummary:")
    print(
        "vector-only no-cache mean(ms):", res0["mean_ms"], "with-cache mean(ms):", res1["mean_ms"]
    )
    print("hybrid no-cache mean(ms):", res2["mean_ms"], "with-cache mean(ms):", res3["mean_ms"])


if __name__ == "__main__":
    main()
