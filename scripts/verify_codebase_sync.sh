#!/usr/bin/env bash
# verify_codebase_sync.sh - Check that file paths named in CODEBASE.md exist.
#
# Usage: scripts/verify_codebase_sync.sh [path-to-codebase]
#
# Reads backticked tokens from CODEBASE.md, keeps the ones that look like
# repository paths, and fails if any named path is missing on disk. This keeps
# CODEBASE.md from referencing files that were renamed or deleted.

set -euo pipefail

CODEBASE="${1:-CODEBASE.md}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$ROOT" "$CODEBASE" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


root = Path(sys.argv[1])
codebase = Path(sys.argv[2])
if not codebase.is_absolute():
    codebase = root / codebase
if not codebase.is_file():
    fail(f"Codebase file not found: {codebase}")

text = codebase.read_text(encoding="utf-8")

# Drop fenced code blocks so triple backticks do not mis-pair inline spans.
kept: list[str] = []
in_fence = False
for line in text.splitlines():
    if line.strip().startswith("```"):
        in_fence = not in_fence
        continue
    if not in_fence:
        kept.append(line)

# Inline backticked spans only.
spans = re.findall(r"`([^`]+)`", "\n".join(kept))

dir_prefixes = ("src/", "tests/", "scripts/", "docs/", ".opencode/")
file_suffixes = (".py", ".sh", ".toml", ".md", ".lock", ".txt", ".json", ".yml", ".yaml")

candidates: set[str] = set()
for span in spans:
    token = span.strip().lstrip("./")
    if not token or " " in token:
        continue
    if token.startswith(dir_prefixes) or token.endswith(file_suffixes):
        candidates.add(token)

missing = sorted(name for name in candidates if not (root / name).exists())

if missing:
    print("CODEBASE.md references paths that do not exist:", file=sys.stderr)
    for name in missing:
        print(f"  - {name}", file=sys.stderr)
    raise SystemExit(1)

print(f"Verified CODEBASE.md: {len(candidates)} referenced paths exist")
PY
