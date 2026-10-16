# Contributing to gitbare

This guide covers local setup, tests, helper scripts, and the release
workflow. User-facing usage lives in `README.md`.

## Requirements

- Python 3.10 or newer
- `git` on `PATH`
- [`uv`](https://github.com/astral-sh/uv) for environments and commands

## Development Setup

```bash
# Create a virtual environment and install dependencies plus test tooling
uv venv
uv sync --extra test
```

## Run Tests

```bash
uv run python -m unittest discover -s tests -v
```

The suite builds throwaway git repositories at run time. It does not commit git
metadata.

## Lint

```bash
uv run ruff check .
```

Ruff lives in the `test` optional dependency group, not in runtime
dependencies.

## Run The CLI Locally

```bash
uv run python -m gitbare --help
uv run gitbare --help
```

## Scripts

All scripts live in `scripts/` and are executable.

### `scripts/bump-version.sh [patch|minor|major]`

Bumps the version in `pyproject.toml` and `src/gitbare/__init__.py` and prints
the new version. Run it once per finalized change.

```bash
scripts/bump-version.sh patch   # 0.3.7 -> 0.3.8
```

### `scripts/validate-changelog.sh [path]`

Checks that `CHANGELOG.md` follows the wrap-up format: a `# Changelog` heading,
`## [X.Y.Z] - YYYY-MM-DD` version headers, `why`/`model`/`tags` bullets, valid
category headings, and descending version order. Defaults to `CHANGELOG.md`.

```bash
scripts/validate-changelog.sh
```

### `scripts/verify_codebase_sync.sh [path]`

Checks that every file path named in `CODEBASE.md` exists on disk. Run it
before wrap-up so the map never references deleted or renamed files. Defaults
to `CODEBASE.md`.

```bash
scripts/verify_codebase_sync.sh
```

## Workflow

Follow the timeline in `AGENTS.md`: architecture, implementation, testing,
synchronization, then wrap-up.

- `BLUEPRINT.md` holds the language-agnostic architecture.
- `CODEBASE.md` maps architecture to physical files. Update it when files are
  added, renamed, or removed, then run `scripts/verify_codebase_sync.sh`.
- `CHANGELOG.md` records each release. Add an entry at the top when you bump a
  version.

## Release Workflow

1. Bump the version once with `scripts/bump-version.sh`.
2. Add a `CHANGELOG.md` entry for the new version.
3. If `uv.lock` changed, stage it in the same commit.
4. Validate before commit:

   ```bash
   scripts/validate-changelog.sh
   scripts/verify_codebase_sync.sh
   ```

5. Tag the finalized commit with gitsem so the tag lands on the right commit:

   ```bash
   uvx --from git+https://github.com/aheimsbakk/gitsem gitsem vX.Y.Z
   ```

## Commit Conventions

- Use Conventional Commits: `<type>(<scope>): <summary>`.
- Stage files explicitly (`git add <path>`). Do not use `git add .` or
  wildcard staging.
- Keep `uv.lock` changes in the same commit as the related change.
