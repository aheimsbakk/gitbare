# PROJECT_RULES.md

## Git Workflow Rules
- If `uv.lock` is modified during a task, it MUST be explicitly staged and included in the final commit together with the related dependency, version, or packaging changes.
- Do not leave `uv.lock` modified in the working tree after wrap-up.
