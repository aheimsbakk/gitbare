---
when: 2026-04-19T13:15:59Z
why: keep lint tooling out of runtime dependencies while documenting the required release tagging workflow
what: add Ruff as a test extra, add worklog validation, and record gitsem tagging rules
model: github-copilot/gpt-5.4
tags: [packaging, lint, docs, release]
---

Moved Ruff into a dedicated `test` optional dependency in `pyproject.toml` and refreshed `uv.lock` for version 0.3.7. Updated `README.md`, `BLUEPRINT.md`, `CONTEXT.md`, and `docs/PROJECT_RULES.md` to document test setup, worklog validation, and `gitsem`-based release tagging. Added `scripts/validate-worklog.sh` and kept the earlier Ruff cleanup in `src/gitbare/exporter.py` and `tests/test_gitbare.py`.
