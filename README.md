# gitbare

> Snapshot your local Git repositories to YAML — and restore them anywhere.

`gitbare` discovers all Git working copies under the current directory, exports their metadata (remotes, HEAD state, local config, submodules, linked worktrees) to a single YAML file, and can fully restore that layout on another machine.

## Features

- **Export** all Git repos under the current directory to a portable YAML snapshot.
- **Restore** the original directory layout, remotes, branch/HEAD state, and local Git config on any machine.
- **Shallow or recursive** discovery: scan direct children (default) or all descendants (`-r`).
- **Safe preview** with `--dry-run` before touching anything.
- **Update** already-existing repositories with `--pull` instead of failing.
- **Opt-in restore** of submodules (`--restore-submodules`) and linked worktrees (`--restore-worktrees`).
- **Clean stdout**: all warnings, errors, and verbose logs go to `stderr` so output is always pipeable.
- Warns about dirty repos, local-only branches, local tags, stashes, and non-portable filesystem remotes.

## Requirements

- Python ≥ 3.10
- `git` available on `PATH`
- [`uv`](https://github.com/astral-sh/uv) (recommended for installation and local development)

## Installation

### Install permanently (recommended)

```bash
uv tool install git+https://github.com/aheimsbakk/gitbare.git
gitbare --version
```

### Run once without installing

```bash
uvx --from git+https://github.com/aheimsbakk/gitbare.git gitbare --help
```

## Quick Start

### Export — snapshot all repos under the current directory

```bash
# Print YAML to stdout
gitbare > git.yml

# Save YAML to a file explicitly
gitbare --export git.yml

# Recursive scan (includes nested repos)
gitbare -r > git.yml
```

### Import — restore repos from a snapshot

```bash
# Pipe from stdin
cat git.yml | gitbare

# Read from a file
gitbare --import git.yml

# Preview what would happen without making any changes
cat git.yml | gitbare --dry-run

# Update repos that already exist instead of failing
cat git.yml | gitbare --pull

# Also restore submodules and linked worktrees
cat git.yml | gitbare --restore-submodules --restore-worktrees
```

### Run remotely without installing

```bash
# Export
uvx --from git+https://github.com/aheimsbakk/gitbare.git gitbare > git.yml

# Import
cat git.yml | uvx --from git+https://github.com/aheimsbakk/gitbare.git gitbare --pull
```

## CLI Reference

```
gitbare [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--export <path\|->`  | `-e` | Export to a file or `-` for stdout (default when no stdin YAML is detected). |
| `--import <path\|->` | `-i` | Import from a file or `-` for stdin. |
| `--recursive` | `-r` | Scan all descendant directories, not just direct children. |
| `--dry-run` | | Preview planned actions or warnings without changing anything. |
| `--pull` | | On import: update already-existing compatible repos instead of failing. |
| `--restore-submodules` | | On import: initialize and restore recorded submodules. |
| `--restore-worktrees` | | On import: recreate recorded linked worktrees. |
| `--verbose` | `-v` | Stream per-repository progress and decision logs to `stderr`. |
| `--version` | `-V` | Print version and exit. |
| `--help` | `-h` | Print usage and exit. |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Usage or argument error |
| `2` | Discovery or export failure |
| `3` | Import, restore, or apply failure |

## How It Works

**Export mode** (no stdin YAML detected, or `--export`):

1. Scans child directories (or all descendants with `-r`) for Git working copies.
2. Skips the current directory itself even if it contains `.git`.
3. Skips repos with no clonable remote (always warns).
4. Collects remotes, HEAD state, local Git config, submodule definitions, and linked worktree paths.
5. Emits a deterministic, human-readable YAML document to `stdout`.

**Import mode** (stdin YAML detected, or `--import`):

1. Reads and validates the YAML snapshot.
2. Recreates the original directory structure from stored `path` values.
3. Clones each repository using its primary remote URL.
4. Restores additional remotes, HEAD state, and repository-local Git config.
5. Optionally restores submodules and linked worktrees.

> **Note:** `gitbare` does not back up uncommitted file contents. Export warns about dirty repos, but only the committed history and configuration are restored.

## Security Notes

- Repository-local Git config (including remote URLs) is exported verbatim to support faithful round-trip restoration. If your `.git/config` contains secrets or tokens, they will appear in the YAML.
- **Store exported YAML files securely.**
- Backups that reference local filesystem remotes (e.g. `/mnt/repos/foo`) may not restore correctly on a different machine or directory layout — `gitbare` will warn you at export time.

## Development

```bash
# Create virtual environment and install dependencies
uv venv
uv sync

# Run the test suite
uv run python -m unittest discover -s tests -v

# Run the CLI locally
uv run python -m gitbare --help
```

Source code lives under `src/`, tests under `tests/`.
