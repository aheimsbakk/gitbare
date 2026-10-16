# CODEBASE.md

Concrete file-to-component map for `gitbare`. This file lists physical paths.
`BLUEPRINT.md` holds the language-agnostic architecture; this file maps it to
the real tree.

## Technology Stack

- Language: Python 3, minimum 3.10
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
    exporter.py           discovery and YAML export capture
    importer.py           YAML parse and restore/apply
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
| `discover_repositories` | `src/gitbare/exporter.py` |
| `inspect_repository` | `src/gitbare/exporter.py` |
| `select_primary_remote` | `src/gitbare/exporter.py` |
| `capture_head_state` | `src/gitbare/exporter.py` |
| `capture_dirty_state` | `src/gitbare/exporter.py` |
| `capture_git_config` | `src/gitbare/exporter.py` |
| `capture_submodules` | `src/gitbare/exporter.py` |
| `capture_worktrees` | `src/gitbare/exporter.py` |
| `filter_custom_config` | `src/gitbare/exporter.py` |
| `emit_yaml` | `dump_yaml` in `src/gitbare/exporter.py` |
| `parse_yaml_import` | `src/gitbare/importer.py` |
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
- `src/gitbare/exporter.py` — export business logic. Discovers repositories and
  captures HEAD, dirty state, remotes, config, submodules, and worktrees into a
  schema-version-1 dict.
- `src/gitbare/importer.py` — import business logic. Validates YAML and applies
  clone, pull, remote, HEAD, config, submodule, and worktree restore steps.
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
