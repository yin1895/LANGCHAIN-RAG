"""Recursively compile all .py files to detect syntax errors.

Usage: python scripts/check_syntax.py
"""

import py_compile
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
targets = [root / "src", root / "backend"]
errors = []
for t in targets:
    if not t.exists():
        continue
    for p in sorted(t.rglob("*.py")):
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as e:
            errors.append((str(p), str(e)))

if errors:
    print("FOUND SYNTAX ERRORS:")
    for f, e in errors:
        print(f"{f}: {e}")
    sys.exit(2)

print("All .py files compiled OK")
