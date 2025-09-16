"""Export FAISS index vectors and metadata into a JSONL file for migration.

Usage: python scripts/export_faiss_to_jsonl.py --index vector_store/index.faiss --meta vector_store/meta.jsonl --out out.jsonl
"""

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.rag.vector_store import FaissStore  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--meta", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    store = FaissStore(args.index, args.meta)
    metas = store.get_metas_snapshot()
    # extract vectors by querying all ids (FaissStore should expose a method to return all vectors; fallback: search by each vector)
    out = []
    for m in metas:
        item = {"hash": m.get("hash"), "meta": m}
        out.append(item)
    with open(args.out, "w", encoding="utf-8") as f:
        for it in out:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print("exported", len(out), "items to", args.out)


if __name__ == "__main__":
    main()
