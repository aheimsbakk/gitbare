# CODEBASE.md

Concrete file-to-component map for `gitbare`. This file lists physical paths.
`BLUEPRINT.md` holds the language-agnostic architecture; this file maps it to
the real tree.

## Technology Stack

- Language: Python 3, minimum 3.11
- Runtime dependency: `PyYAML` (safe load/dump only)
- External tool: `git` on `PATH`
- Package manager and env tooling: `uv`
- Build backend: `setuptools` (`pyproject.toml`)
- Test framework: `unittest` (standard library)
- Lint: Ruff, in the `test` optional dependency group

## Naming Conventions

- Python modules: `snake_case` (for example `src/gitbare/git_ops.py`,
  `src/gitbare/logging_utils.py`). Python's import system requires module names
  to be valid identifiers, so the project-wide `kebab-case` rule does not apply
  to `.py` files.
- Shell scripts: `kebab-case` (for example `scripts/bump-version.sh`).
- Public functions: `snake_case`. Internal records use plain `dict`.

## Entry Points

- Console command `gitbare`: declared in `pyproject.toml` under
  `[project.scripts]` as `gitbare = "gitbare.cli:main"`.
- Module run `python -m gitbare`: `src/gitbare/__main__.py` calls
  `gitbare.cli:main`.
- Application version string: `src/gitbare/__init__.py` (`__version__`).

## Repository Layout

```
pyproject.toml            packaging metadata, console script, test extra
uv.lock                   locked dependency graph
CHANGELOG.md              release history (Keep a Changelog format)
README.md                 user documentation
CONTRIBUTING.md           developer setup, scripts, release workflow
BLUEPRINT.md              language-agnostic architecture
CODEBASE.md               this file

src/
  gitbare/
    __init__.py           package marker and __version__
    __main__.py           `python -m gitbare` shim
    cli.py                argument parsing, mode detection, stdin/stdout I/O
    discovery.py          scan-root traversal to find git working copies
    capture.py            per-aspect git metadata capture and config filter
    capture_nesting.py    submodule and linked-worktree capture
    exporter.py           export orchestration and YAML emission
    importer.py           YAML parse and restore/apply
    import_validation.py  snapshot schema and path-safety validation
    git_ops.py            subprocess git wrapper and URL/config helpers
    logging_utils.py      OperationLogger for verbose stderr output
  gitbare.egg-info/       build artifact (git-ignored)

tests/
  test_gitbare.py         end-to-end unittest suite over fixture repos

scripts/
  bump-version.sh         bump version in pyproject.toml and __init__.py
  validate-changelog.sh   validate CHANGELOG.md structure
  verify_codebase_sync.sh check that paths named in CODEBASE.md exist
```

## Blueprint Component → Physical File

| Blueprint responsibility | Physical location |
|---|---|
| `main`, `build_arg_parser`, `detect_mode` | `src/gitbare/cli.py` |
| `discover_repositories` | `src/gitbare/discovery.py` |
| `inspect_repository` | `src/gitbare/exporter.py` |
| `select_primary_remote` | `src/gitbare/capture.py` |
| `capture_head_state` | `src/gitbare/capture.py` |
| `capture_dirty_state` | `src/gitbare/capture.py` |
| `capture_git_config` | `src/gitbare/capture.py` |
| `capture_submodules` | `src/gitbare/capture_nesting.py` |
| `capture_worktrees` | `src/gitbare/capture_nesting.py` |
| `filter_custom_config` | `src/gitbare/capture.py` |
| `emit_yaml` | `dump_yaml` in `src/gitbare/exporter.py` |
| `parse_yaml_import` | `src/gitbare/import_validation.py` |
| Import schema and path validation | `src/gitbare/import_validation.py` |
| `plan_operations` | dry-run branch in `restore_repository`, `src/gitbare/importer.py` |
| `restore_repository` | `src/gitbare/importer.py` |
| `clone_repository` | `src/gitbare/importer.py` |
| `update_existing_repository` | `src/gitbare/importer.py` |
| `restore_remotes` | `src/gitbare/importer.py` |
| `restore_head` | `src/gitbare/importer.py` |
| `restore_git_config` | `src/gitbare/importer.py` |
| `restore_submodules` | `src/gitbare/importer.py` |
| `restore_worktrees` | `src/gitbare/importer.py` |
| `run_git` | `src/gitbare/git_ops.py` |
| `classify_transport` | `src/gitbare/git_ops.py` |
| `log_verbose` | `OperationLogger` in `src/gitbare/logging_utils.py` |

## Module Responsibilities

- `src/gitbare/cli.py` — input/output layer. Parses flags, detects import or
  export mode, reads stdin or a file, writes stdout or a file, maps failures to
  exit codes. No restore rules live here.
- `src/gitbare/discovery.py` — filesystem traversal. Walks the scan root
  (direct children or recursively) and returns Git working-copy paths in a
  deterministic order.
- `src/gitbare/capture.py` — export capture. Reads HEAD, dirty state, remotes,
  local config, local-only branches/tags, and stashes, and classifies custom
  config. Pure per-aspect git queries with no logging.
- `src/gitbare/capture_nesting.py` — nested structure capture. Reads submodule
  and linked-worktree definitions for a repository.
- `src/gitbare/exporter.py` — export orchestration and emission. Inspects each
  discovered repository, assembles the schema-version-1 dict, and writes YAML.
- `src/gitbare/importer.py` — import business logic. Applies clone, pull,
  remote, HEAD, config, submodule, and worktree restore steps.
- `src/gitbare/import_validation.py` — import input validation. Parses the
  snapshot with the safe loader, enforces the schema-version-1 envelope and
  required per-repository fields, and rejects stored paths that could escape
  the restore root. Raises `ValueError` with plain-language messages.
- `src/gitbare/git_ops.py` — shared git access. Runs git with argument lists,
  classifies transport, checks clonable sources, and parses null-delimited
  config.
- `src/gitbare/logging_utils.py` — presentation helper. `OperationLogger` writes
  info, verbose detail, and progress lines to `stderr` with flushing.

## Test Layout

- `tests/test_gitbare.py` — full `unittest` suite. Builds fixture git repos at
  run time instead of committing git metadata. Covers CLI, export, import, and
  round-trip cases listed in `BLUEPRINT.md`.

## Language Rationale

- Export and import live in separate modules to keep the two flows independent,
  as `BLUEPRINT.md` requires.
- Git access is isolated in `src/gitbare/git_ops.py` so both flows reuse one
  subprocess wrapper and never build shell strings.
- Verbose output is centralized in `src/gitbare/logging_utils.py` so `stdout`
  stays clean during export.
- `setuptools` with `src/` layout is used so the installed `gitbare` command
  works without a top-level script file.
