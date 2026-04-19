# PROJECT_RULES.md

## Git Workflow Rules
- If `uv.lock` is modified during a task, it MUST be explicitly staged and included in the final commit together with the related dependency, version, or packaging changes.
- Do not leave `uv.lock` modified in the working tree after wrap-up.

## Release Tagging Rules
- When finalizing a versioned change, use `uvx --from git+https://github.com/aheimsbakk/gitsem gitsem` to add the version tag to the correct final commit.
- Do not create or move the version tag manually when this workflow applies.
