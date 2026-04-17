#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 1 ]; then
  printf 'Usage: %s [patch|minor|major]\n' "$0" >&2
  exit 1
fi

bump_type="$1"

case "$bump_type" in
  patch|minor|major) ;;
  *)
    printf 'Invalid bump type: %s\n' "$bump_type" >&2
    exit 1
    ;;
esac

python3 - "$bump_type" <<'PY'
from pathlib import Path
import re
import sys

bump_type = sys.argv[1]

files = [Path('/work/pyproject.toml'), Path('/work/src/gitbare/__init__.py')]

version_pattern = re.compile(r'(\d+)\.(\d+)\.(\d+)')
current_text = files[0].read_text(encoding='utf-8')
match = re.search(r'^version = "(\d+\.\d+\.\d+)"$', current_text, re.MULTILINE)
if not match:
    raise SystemExit('Unable to find version in pyproject.toml')

major, minor, patch = map(int, match.group(1).split('.'))
if bump_type == 'patch':
    patch += 1
elif bump_type == 'minor':
    minor += 1
    patch = 0
else:
    major += 1
    minor = 0
    patch = 0

new_version = f'{major}.{minor}.{patch}'

for path in files:
    text = path.read_text(encoding='utf-8')
    text = version_pattern.sub(new_version, text, count=1)
    path.write_text(text, encoding='utf-8')

print(new_version)
PY
