"""Check repository for files larger than a threshold (in MB).

This script is intended for CI: it exits with non-zero status when a large file
is present. It checks the working tree (all files) and reports any files above
the provided size.
"""

import argparse
import os
import sys


def human_size(bytes_size):
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f}TB"


def find_large_files(root: str, max_mb: int):
    max_bytes = max_mb * 1024 * 1024
    large = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip .git
        if ".git" in dirpath.split(os.sep):
            continue
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size > max_bytes:
                large.append((path, size))
    return large


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-mb", type=int, default=50, help="Max allowed file size in MB")
    args = parser.parse_args()

    root = os.getcwd()
    large = find_large_files(root, args.max_mb)
    if large:
        print("Found files larger than {} MB:".format(args.max_mb))
        for p, s in sorted(large, key=lambda x: x[1], reverse=True):
            print(f" - {p} ({human_size(s)})")
        sys.exit(2)
    print("No files larger than {} MB found.".format(args.max_mb))


if __name__ == "__main__":
    main()
