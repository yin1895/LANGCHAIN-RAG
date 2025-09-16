import os
import sys

sys.path.insert(0, os.path.abspath("."))
# Use temp docs root
import tempfile  # noqa: E402

from src.config import get_settings as get_src_settings  # noqa: E402
from src.ingestion.chunking import adaptive_chunk  # noqa: E402
from src.ingestion.docx_parser import ingest_to_raw  # noqa: E402
from src.rag.embeddings import OllamaEmbeddings  # noqa: E402
from src.rag.vector_store import FaissStore, build_or_update  # noqa: E402

tmpd = tempfile.mkdtemp()
print("tmp docs root", tmpd)
# set up minimal settings if needed: get_settings in project might read env vars; ensure default
os.environ["DOCS_ROOT"] = tmpd
s = get_src_settings()
# create dummy files? ingest_to_raw scans docs_root; empty dir should return empty list
raw = ingest_to_raw(s.docs_root)
print("raw count", len(raw))
# adaptive chunk of empty raw
chunks = adaptive_chunk(raw, s.chunk_size, s.chunk_overlap)
print("chunks", len(chunks))
# build a temporary FaissStore
idx = "tests/tmp_index.faiss"
meta = "tests/tmp_meta.jsonl"
store = FaissStore(idx, meta)
# Use OllamaEmbeddings if available; otherwise skip embed (we'll simulate by short-circuit)
try:
    embed = OllamaEmbeddings(s.embed_model)
except Exception as e:
    print("ollama not available, using dummy embed", e)

    class DummyEmbed:
        def embed_documents(self, texts):
            return [[float(len(t)), float(len(t))] for t in texts]

        def embed_query(self, q):
            return [float(len(q)), float(len(q))]

    embed = DummyEmbed()
added = build_or_update(chunks, store, embed)
print("added", added)
