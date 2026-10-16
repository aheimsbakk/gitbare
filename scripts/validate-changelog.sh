#!/usr/bin/env bash
# validate-changelog.sh - Check that CHANGELOG.md follows the wrap-up format.
#
# Usage: scripts/validate-changelog.sh [path-to-changelog]
#
# Rules checked:
#   - File starts with a "# Changelog" heading.
#   - Each version header is "## [X.Y.Z] - YYYY-MM-DD".
#   - Each version section lists why, model, and tags bullets.
#   - Each version section has at least one category heading.
#   - Category headings are one of Added, Changed, Fixed, Removed, Security.
#   - Version sections appear in descending version order.

set -euo pipefail

CHANGELOG="${1:-CHANGELOG.md}"

python3 - "$CHANGELOG" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


path = Path(sys.argv[1])
if not path.is_file():
    fail(f"Changelog file not found: {path}")

text = path.read_text(encoding="utf-8")
lines = text.splitlines()

if not lines or lines[0].strip() != "# Changelog":
    fail("Changelog must start with a '# Changelog' heading")

version_re = re.compile(r"^## \[(\d+)\.(\d+)\.(\d+)\] - (\d{4}-\d{2}-\d{2})$")
allowed_categories = {"Added", "Changed", "Fixed", "Removed", "Security"}

# Collect version sections: (major, minor, patch, header_line, body_lines)
sections: list[tuple[int, int, int, str, list[str]]] = []
current: tuple[int, int, int, str] | None = None
body: list[str] = []

for line in lines:
    match = version_re.match(line)
    if match:
        if current is not None:
            sections.append((*current, body))
        current = (int(match.group(1)), int(match.group(2)), int(match.group(3)), line)
        body = []
        continue
    if line.startswith("## ") and current is not None:
        # Unknown level-2 heading inside the version list.
        fail(f"Unexpected section heading (not a version header): {line}")
    if current is not None:
        body.append(line)

if current is not None:
    sections.append((*current, body))

if not sections:
    fail("Changelog has no version sections")

for major, minor, patch, header, section_body in sections:
    joined = "\n".join(section_body)
    for label in ("**why:**", "**model:**", "**tags:**"):
        if label not in joined:
            fail(f"{header} is missing a '{label}' bullet")

    categories = [
        line[4:].strip()
        for line in section_body
        if line.startswith("### ")
    ]
    if not categories:
        fail(f"{header} has no category heading (### Added/Changed/Fixed/...)")
    for category in categories:
        if category not in allowed_categories:
            fail(f"{header} has an invalid category heading: {category}")

# Versions must descend.
for previous, current_pair in zip(sections, sections[1:]):
    left = previous[:3]
    right = current_pair[:3]
    if right >= left:
        fail(
            f"Versions must descend: {current_pair[3]} is not older than {previous[3]}"
        )

print(f"Validated changelog: {path} ({len(sections)} versions)")
PY
