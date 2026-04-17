---
when: 2026-04-17T20:36:39Z
why: enforce consistent commits whenever uv.lock changes during development or release work
what: add the uv.lock commit rule, sync project docs, and bump release metadata to v0.3.2
model: github-copilot/gpt-5.4
tags: [workflow, documentation, uv, git, release]
---

Added `docs/PROJECT_RULES.md` to require staging `uv.lock` whenever it changes and synchronized the same rule into `BLUEPRINT.md` and `CONTEXT.md`. Bumped the package metadata to `0.3.2` and recorded the workflow rule change for future wrap-ups.
