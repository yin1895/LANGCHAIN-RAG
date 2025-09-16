import os

from src.rag.retriever import Retriever
from src.rag.vector_store import FaissStore, build_or_update

# Setup simple in-memory test
idx_path = "tests/test_index.faiss"
meta_path = "tests/test_meta.jsonl"

# Ensure tests dir
os.makedirs("tests", exist_ok=True)

# Create a small FaissStore
store = FaissStore(idx_path, meta_path)


# Dummy embedding model that returns simple vectors
class DummyEmbed:
    def embed_documents(self, texts):
        return [[float(len(t)), float(len(t))] for t in texts]

    def embed_query(self, q):
        return [float(len(q)), float(len(q))]


embed = DummyEmbed()

# Build some chunks
chunks = [
    {"hash": "h1", "source": "s1", "content": "hello world"},
    {"hash": "h2", "source": "s2", "content": "goodbye"},
]

added = build_or_update(chunks, store, embed)
print("added", added)

# Retriever
retriever = Retriever(store, embed, k=2)
res = retriever.get_relevant("hello")
print("results", res)

# Query again to test cache (should be cached)
res2 = retriever.get_relevant("hello")
print("results cached?", res2)
