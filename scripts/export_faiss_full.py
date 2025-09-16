"""Export FAISS index vectors and metadata into a JSONL file for migration.

This script tries to read vectors from metas (if present). If vectors are not
stored in metas, it will attempt to reconstruct them from the Faiss index.

Usage:
  python scripts/export_faiss_full.py --index vector_store/index.faiss --meta vector_store/meta.jsonl --out out.jsonl
"""
import json
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.rag.vector_store import FaissStore


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--index', required=True)
    p.add_argument('--meta', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()

    store = FaissStore(args.index, args.meta)
    metas = store.get_metas_snapshot()
    out_count = 0
    with open(args.out, 'w', encoding='utf-8') as fo:
        for idx, m in enumerate(metas):
            vec = m.get('vector')
            if vec is None:
                # try to reconstruct from faiss index if available
                try:
                    if store._index is not None:
                        v = store._index.reconstruct(idx)
                        # faiss may return array-like
                        vec = list(map(float, v))
                except Exception:
                    vec = None
            item = {'hash': m.get('hash'), 'meta': m, 'vector': vec}
            fo.write(json.dumps(item, ensure_ascii=False) + '\n')
            out_count += 1
    print('exported', out_count, 'items to', args.out)


if __name__ == '__main__':
    main()
