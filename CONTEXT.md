# CONTEXT.md

## Current State
- Greenfield project.
- No implementation files exist yet.
- `BLUEPRINT.md` defines the first agreed product contract.

## Agreed Runtime
- Main executable: `gitbare`
- Language: Python 3
- Minimum version target: Python 3.10
- Dependency policy: minimal dependencies, with a YAML package allowed in addition to the external `git` executable already available on the system
- Packaging: installable Python package with a console entrypoint
- Local environment tooling: `uv`
- YAML package: `PyYAML`

## Agreed Product Behavior
- Export discovered repositories under the current directory to YAML on `stdout`.
- Import repository state from YAML on `stdin`.
- Support explicit `--import` / `-i` from stdin or file.
- Support explicit `--export` / `-e` to stdout or file.
- Support shallow discovery by default and recursive discovery with `-r` / `--recursive`.
- Ignore the current working directory itself even if it contains `.git` metadata.
- Preserve relative folder structure, checkout URL, checkout transport classification, remotes, current HEAD state, and repository-local Git config.
- Warn when dirty repositories are exported and show dirty file paths in verbose mode.
- Do not back up local-only branches; warn about them instead.
- Do not back up local tags not present on any remote, or stashes; warn about them instead.
- Surface repository-specific custom config separately from general local Git config.
- Support `--pull` during import to update already-existing compatible repositories instead of failing clone-only behavior.
- If `--pull` fails due to divergence or non-fast-forward constraints, warn and continue with later repositories.
- Support `--dry-run` so users can preview warnings, conflicts, and planned actions before making changes.
- Treat `git@`, `https://`, `ssh://`, and local filesystem remotes as clonable sources.
- Warn when local filesystem remotes are exported because they may not be portable.
- Skip repositories without clonable remotes, always with a warning.
- Record submodule metadata and support opt-in restore by recorded commit SHA with `--restore-submodules`.
- Record linked worktree metadata with relative paths only and support opt-in restore with `--restore-worktrees`.
- Do not store extra remote metadata beyond what is required for backup and restore.

## Agreed CLI Surface
- `gitbare > git.yml`
- `cat git.yml | gitbare`
- `cat git.yml | gitbare --dry-run`
- `cat repo.yml | gitbare --import -`
- `gitbare --import repo.yml`
- `gitbare -i repo.yml`
- `-r` / `--recursive`
- `--export` / `-e`
- `--import` / `-i`
- `--dry-run`
- `--pull`
- `--restore-submodules`
- `--restore-worktrees`
- `-v` / `--verbose`
- `-h` / `--help`
- `-V` / `--version`
- `uvx --from git+https://github.com/OWNER/REPO.git gitbare --help`

## Implementation Constraints
- Use Git through `subprocess` with explicit argument lists.
- Use `PyYAML` for parsing and emission.
- Keep export `stdout` clean and send logs to `stderr`.
- Use safe YAML loading only.
- Compare local tag names from `git tag --list` against the union of remote tag names gathered with `git ls-remote --tags <remote>` when deciding which tags should trigger warnings.
- Treat duplicate git config keys in backup data as a fatal validation error with exit code `1`.
- Back up secrets present in repository-local Git config and related recorded URLs; users will handle the export securely.
- Package the project so the installed command is `gitbare`.
- Place application code under `src/`.
- Place the full automated test suite under `tests/`.
- Use Python `unittest` for the test suite.
- Document local development with `uv`, installation with `uv tool install`, and remote execution with `uvx` from GitHub.
- Document that local filesystem remote backups may fail to restore on different machines.
- Users should run the installed `gitbare` command, not the package directory.
- Write warnings and errors to `stderr`, and return non-zero on critical failures.
