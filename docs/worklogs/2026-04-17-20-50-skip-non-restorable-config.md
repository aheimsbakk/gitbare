---
when: 2026-04-17T20:50:15Z
why: avoid backing up Git config entries that are always skipped during restore
what: filter non-restorable config from exports, document the rule, and bump release metadata to v0.3.4
model: github-copilot/gpt-5.4
tags: [python, cli, git, config, testing]
---

Updated export behavior to exclude non-restorable Git config keys from backups so import no longer emits guaranteed skip messages for them. Documented the new backup rule in `BLUEPRINT.md` and `CONTEXT.md`, added regression coverage in `tests/test_gitbare.py`, and bumped the package version to `0.3.4`.
