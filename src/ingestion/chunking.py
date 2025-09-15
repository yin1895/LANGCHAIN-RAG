import hashlib
from typing import Dict, List


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def adaptive_chunk(elements: List[Dict], chunk_size: int = 1200, overlap: int = 120) -> List[Dict]:
    chunks = []
    buffer = []
    buffer_len = 0
    for el in elements:
        if el.get("type") == "table":
            # Represent table as markdown
            rows = el.get("rows", [])
            md_lines = []
            if rows:
                header = rows[0]
                md_lines.append("| " + " | ".join(header) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                for r in rows[1:]:
                    md_lines.append("| " + " | ".join(r) + " |")
            text = "\n".join(md_lines)
        else:
            text = el.get("text", "")
        if not text:
            continue
        tokens = len(text)
        if buffer_len + tokens > chunk_size and buffer:
            merged = "\n".join(buffer)
            chunks.append(
                {
                    "content": merged,
                    "hash": hash_text(merged),
                    "source": el.get("source"),
                    "meta": {},
                }
            )
            # overlap
            if overlap > 0:
                overlap_text = merged[-overlap:]
                buffer = [overlap_text, text]
                buffer_len = len(overlap_text) + tokens
            else:
                buffer = [text]
                buffer_len = tokens
        else:
            buffer.append(text)
            buffer_len += tokens
    if buffer:
        merged = "\n".join(buffer)
        chunks.append(
            {
                "content": merged,
                "hash": hash_text(merged),
                "source": elements[-1].get("source") if elements else "",
                "meta": {},
            }
        )
    return chunks
