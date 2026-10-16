# Changelog

## [0.4.0] - 2026-10-16

- **why:** Harden import against hostile or malformed snapshots and close the findings from the code review
- **model:** kompis/qwen3.8-flash-next-iq3_s
- **tags:** import, validation, security, dependencies

### Added

- `src/gitbare/import_validation.py` checks required fields, head shape, and list types before any restore step runs
- Timeouts on every Git call in `src/gitbare/git_ops.py`: 120 seconds local, 600 seconds for clone, fetch, `ls-remote`, and submodule update
- 14 new tests, including the export-import-reexport round trip and the installed `gitbare` console entrypoint

### Changed

- Usage and argument errors now exit `1` instead of argparse's default `2` (`CliArgumentParser` in `src/gitbare/cli.py`)
- `--dry-run` import exits `3` when a planned action would fail, so scripts can detect blockers from the exit code
- `requires-python` raised to `>=3.11`; ruff pinned to `0.17.1`; `wheel` bounded in the build system
- `CONTRIBUTING.md` lint command is now `uv run --extra test ruff check .`, which makes `uv run` install and use the pinned ruff

### Fixed

- Malformed YAML and repository entries missing required fields now fail with a clear message instead of a traceback
- Submodules whose configured name contains dots (for example `vendor.lib`) are captured correctly in `capture_nesting.py`
- Dirty paths with spaces or non-ASCII characters export byte-exact through `git status --porcelain -z`
- `restore_remotes` no longer writes a push URL identical to the fetch URL, which broke round-trip comparison

### Security

- Import rejects stored paths that are absolute or contain `..`, so a hand-edited snapshot cannot write outside the restore root
- Timeout messages name only the Git subcommand, keeping credentialed remote URLs out of logs

## [0.3.11] - 2026-10-16

- **why:** Remove stale worklog references left over from the changelog switch
- **model:** kompis/qwen3.8-flash-next-iq3_s
- **tags:** agent-framework, docs, cleanup

### Changed

- `.opencode/RULES.md` rule 25 no longer names worklogs as a front-matter example
- `.opencode/skills/wrap-up/SKILL.md` gitignore rule no longer names `docs/worklogs/`

## [0.3.10] - 2026-10-16

- **why:** Split the oversized exporter module into focused discovery and capture modules
- **model:** kompis/qwen3.8-flash-next-iq3_s
- **tags:** refactor, modules, export

### Added

- `src/gitbare/discovery.py` for repository traversal
- `src/gitbare/capture.py` for per-aspect metadata capture
- `src/gitbare/capture_nesting.py` for submodule and worktree capture

### Changed

- `src/gitbare/exporter.py` now holds only orchestration and YAML emission (348 to 147 lines)

## [0.3.9] - 2026-10-16

- **why:** Replace the worklog workflow with changelog and codebase docs, and add sync and validation scripts
- **model:** kompis/qwen3.8-flash-next-iq3_s
- **tags:** docs, changelog, codebase, scripts

### Added

- `CODEBASE.md` mapping Blueprint components to physical files
- `CONTRIBUTING.md` with setup, tests, scripts, and release workflow
- `scripts/validate-changelog.sh` and `scripts/verify_codebase_sync.sh`
- Reconstructed `CHANGELOG.md` history for every release from the old worklogs

### Changed

- `BLUEPRINT.md` now requires changelog validation and codebase sync instead of worklog validation
- `README.md` moved development setup to `CONTRIBUTING.md`

### Removed

- `docs/PROJECT_RULES.md`, `docs/worklogs/`, and `CONTEXT.md`
- `scripts/validate-worklog.sh` (dead worklog tooling)

## [0.3.8] - 2026-10-16

- **why:** Replace the multi-agent workflow with one Vibe agent plus skills, and add a Blueprint/Codebase sync protocol
- **model:** kompis/qwen3.8-flash-next-iq3_s
- **tags:** agent-framework, workflow, docs

### Added

- Skills under `.opencode/skills/`: `clear-language`, `clear-language-norwegian`, `memory`, `todo-txt`, `wrap-up`
- `AGENTS.md` Master Rules: Blueprint generation, Codebase mapping, and a Synchronization Protocol
- `RULES.md` rules for commit consent, layer boundaries, state ownership, verification gate, intent-based comments, and documentation separation

### Changed

- `AGENTS.md` rewritten from a two-mode agent protocol to Master Rules
- `.opencode/agents/vibe.md` wake-up contract now loads skills and `CODEBASE.md`
- `opencode.json` lists `AGENTS.md` in instructions and sets `autoupdate`, `formatter`, `lsp`, `share`, and `snapshot`
- `.opencode/update.sh` now pulls from `aheimsbakk/agentic-opencode`

### Removed

- Multi-agent workflow agents: `pm`, `architect`, `builder`, `qa`, `brainstorm`
- Worklog system: `.opencode/WORKLOG_TEMPLATE.md` and the worklog rules in `AGENTS.md`

## [0.3.7] - 2026-04-19

- **why:** Keep lint tooling out of runtime dependencies and document the release tagging workflow
- **model:** github-copilot/gpt-5.4
- **tags:** packaging, lint, docs, release

### Added

- `test` optional dependency group in `pyproject.toml` for Ruff
- `gitsem` release-tagging rule recorded in `BLUEPRINT.md`

### Changed

- Moved Ruff from runtime dependencies to the `test` group and refreshed `uv.lock`

## [0.3.6] - 2026-04-17

- **why:** Improve README readability by removing horizontal rule dividers between sections
- **model:** opencode/claude-sonnet-4-6
- **tags:** docs, readme, formatting

### Changed

- Removed all `---` dividers from `README.md`

## [0.3.5] - 2026-04-17

- **why:** Improve onboarding by replacing the minimal README with a structured, user-friendly document
- **model:** opencode/claude-sonnet-4-6
- **tags:** docs, readme, refactor

### Changed

- Rewrote `README.md` with features, requirements, install options, quick-start, CLI reference, exit codes, and security notes

## [0.3.4] - 2026-04-17

- **why:** Avoid backing up Git config entries that are always skipped during restore
- **model:** github-copilot/gpt-5.4
- **tags:** python, cli, git, config, testing

### Fixed

- Export now excludes non-restorable config keys (`core.repositoryformatversion`, `core.bare`, `core.worktree`), so import no longer emits guaranteed-skip messages

## [0.3.3] - 2026-04-17

- **why:** Emit verbose progress and diagnostics immediately while import and export run
- **model:** github-copilot/gpt-5.4
- **tags:** python, cli, logging, stderr, testing

### Fixed

- Verbose progress and diagnostics now flush to `stderr` during import and export instead of buffering

## [0.3.2] - 2026-04-17

- **why:** Show accurate repository progress in verbose output and enforce committing `uv.lock`
- **model:** github-copilot/gpt-5.4
- **tags:** python, cli, logging, progress, workflow

### Added

- Rule to stage `uv.lock` in the same commit whenever it changes

### Changed

- Verbose export and import now report ordered per-repository progress counters

## [0.3.0] - 2026-04-17

- **why:** Make the verbosity flag explain export and import planning without polluting YAML output
- **model:** github-copilot/gpt-5.4
- **tags:** python, cli, logging, git, testing

### Added

- Structured verbose logging (`-v`) for export and import planning and restore steps, streamed to `stderr`

## [0.2.0] - 2026-04-17

- **why:** Implement the first working gitbare CLI defined by the project blueprint
- **model:** github-copilot/gpt-5.4
- **tags:** python, cli, git, yaml, testing

### Added

- Installable `gitbare` package under `src/` with export, import, Git metadata capture, restore logic, and CLI
- Packaging and usage docs in `pyproject.toml` and `README.md`
- End-to-end `unittest` coverage in `tests/test_gitbare.py`
- `scripts/bump-version.sh`
