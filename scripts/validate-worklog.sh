#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 1 ]; then
  printf 'Usage: %s <worklog-path>\n' "$0" >&2
  exit 1
fi

python3 - "$1" <<'PY'
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


path = Path(sys.argv[1])
if not path.is_file():
    fail(f"Worklog file not found: {path}")

text = path.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    fail("Worklog must start with YAML front matter")

parts = text.split("\n---\n", 1)
if len(parts) != 2:
    fail("Worklog must contain exactly one YAML front matter block")

front_matter = parts[0].splitlines()[1:]
body = parts[1].strip()

required_keys = {"when", "why", "what", "model", "tags"}
parsed: dict[str, str] = {}

for line in front_matter:
    if not line.strip():
        continue
    if ": " not in line:
        fail(f"Invalid front matter line: {line}")
    key, value = line.split(": ", 1)
    if key in parsed:
        fail(f"Duplicate front matter key: {key}")
    parsed[key] = value

if set(parsed) != required_keys:
    fail("Worklog front matter must contain only: when, why, what, model, tags")

if not parsed["why"].strip():
    fail("Worklog 'why' must not be empty")
if not parsed["what"].strip():
    fail("Worklog 'what' must not be empty")
if not parsed["model"].strip():
    fail("Worklog 'model' must not be empty")
if not (parsed["tags"].startswith("[") and parsed["tags"].endswith("]")):
    fail("Worklog 'tags' must use inline YAML list syntax")

try:
    datetime.strptime(parsed["when"], "%Y-%m-%dT%H:%M:%SZ")
except ValueError as error:
    fail(f"Worklog 'when' must be ISO 8601 UTC: {error}")

body_lines = [line for line in body.splitlines() if line.strip()]
if not 1 <= len(body_lines) <= 4:
    fail("Worklog body must contain 1 to 4 non-empty lines")

print(f"Validated worklog: {path}")
PY
