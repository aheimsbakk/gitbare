# BLUEPRINT.md

## Project
- **Name:** `gitbare`
- **Type:** Installable Python package with CLI entrypoint
- **Purpose:** Export and restore many local Git working copies, including checkout transport, repository-local configuration, and directory layout.

## Product Summary
`gitbare` is a backup-and-restore utility for Git working copies stored under the current directory.

It has two operating modes:

1. **Export mode**: discover Git repositories under the current directory and print a machine-generated YAML document to `stdout`.
2. **Import mode**: read that YAML document from `stdin`, recreate the repositories, restore the checkout style (`git@...` / `https://...` / other), restore repository-local Git config, and recreate nested paths recorded by the export.

The tool is intended to reproduce the exact practical layout of many repositories without depending on a database, third-party library, or external service beyond the local `git` executable.

---

## Goals
- Discover Git repositories inside subfolders of the current working directory.
- Support shallow discovery by default and recursive discovery with `-r` / `--recursive`.
- Emit YAML that is stable, readable, and safe for round-trip import by the same script.
- Preserve the original checkout URL and explicitly classify its transport as `ssh`, `https`, or `other`.
- Preserve repository-local Git configuration.
- Warn when exporting dirty repositories.
- Show dirty tracked and untracked file paths in verbose mode.
- Warn when repositories contain local tags or stashes that will not be backed up.
- Highlight custom repository-local configuration separately from standard clone/check-out metadata.
- Record submodules as part of their parent repository backup.
- Record linked worktrees in the backup.
- Recreate the original relative folder structure during import.
- Support import into an environment where some repositories already exist.
- Support opt-in recreation of submodules and linked worktrees during import.
- Skip repositories that do not have a clonable source, while always warning about the skip.
- Keep `stdout` clean in export mode so output can be redirected or piped directly.

## Non-Goals
- Managing bare repositories as first-class inputs.
- Discovering the current directory itself as a repository unless it appears as a discovered child path.
- Supporting arbitrary hand-written YAML from third-party tools.
- Performing destructive overwrite of existing non-empty directories.
- Managing credentials, SSH agents, or host key prompts.
- Replacing Git plumbing with pure Python repository manipulation.
- Automatically restoring uncommitted file contents from dirty working trees.
- Auto-merging or auto-rebasing divergent branches during `--pull`.

---

## Runtime and Dependency Policy
- Language: Python 3
- Minimum supported Python version: 3.10
- Implementation must use Python 3 plus the existing `git` command-line tool.
- YAML handling must use `PyYAML`.
- Use safe `PyYAML` loader and dumper APIs only.
- Other third-party dependencies should remain minimal and must be justified by clear implementation value.
- Minimum Python version is not fixed yet and should be decided during implementation.
- The project must be packaged as an installable Python package that exposes a `gitbare` console command.
- Local development should use `uv` for environment creation and command execution.
- The CLI must remain runnable through the installed entrypoint rather than relying on a top-level `gitbare.py` script file.

---

## CLI Contract

### Primary Invocation Examples
```bash
gitbare > git.yml
gitbare -r > git.yml
cat git.yml | gitbare
cat git.yml | gitbare --import -
gitbare --import repo.yml
gitbare -i repo.yml
gitbare --export repo.yml
gitbare -e repo.yml
gitbare --export - > repo.yml
cat git.yml | gitbare --dry-run
cat git.yml | gitbare --pull
cat git.yml | gitbare --restore-worktrees --restore-submodules
```

### Help and Version
```bash
gitbare --help
gitbare -h
gitbare --version
gitbare -V
```

### Packaging and `uvx` Usage
```bash
uvx --from git+https://github.com/OWNER/REPO.git gitbare --help
uvx --from git+https://github.com/OWNER/REPO.git gitbare > git.yml
cat git.yml | uvx --from git+https://github.com/OWNER/REPO.git gitbare --pull
uv tool install git+https://github.com/OWNER/REPO.git
gitbare --help
```

### Options
- `--import`, `-i` `<path|->`
  - Force import mode.
  - `-` means read YAML from `stdin`.
  - A file path means read YAML directly from that file.
- `--export`, `-e` `<path|->`
  - Force export mode.
  - `-` means write YAML to `stdout`.
  - A file path means write YAML directly to that file.
- `-r`, `--recursive`
  - **Export:** scan repositories recursively below the current directory.
  - **Import:** accepted for CLI symmetry, but restore layout is driven by stored `path` values in the YAML.
- `--pull`
  - **Import only:** if a target repository already exists and is compatible with the YAML entry, update it from the remote instead of treating it as a conflict that requires clone-only restore behavior.
  - **Export:** invalid usage.
- `--dry-run`
  - **Export:** validate discovery and report warnings without writing clone or restore changes.
  - **Import:** parse YAML and report the actions, conflicts, and expected failures without modifying the filesystem or Git state.
- `--restore-worktrees`
  - **Import only:** recreate recorded linked worktrees after the main repositories are restored.
  - **Export:** invalid usage.
- `--restore-submodules`
  - **Import only:** initialize and update recorded submodules after the parent repository is restored.
  - **Export:** invalid usage.
- `-v`, `--verbose`
  - Emit progress and decision logs to `stderr`.
  - Must never pollute `stdout` during export.
- `-h`, `--help`
  - Print usage and exit `0`.
- `-V`, `--version`
  - Print program version and exit `0`.

### Mode Detection
- `--import` / `-i` explicitly selects import mode.
- `--export` / `-e` explicitly selects export mode.
- Without explicit mode flags:
  - **Export mode**: used when no YAML is provided on `stdin`.
  - **Import mode**: used when YAML is provided on `stdin`.
- `--help` and `--version` short-circuit before mode detection.
- Import-only flags must fail fast if used in export mode.
- `--dry-run` is valid in both modes.

### Exit Codes
- `0`: success.
- `1`: usage or argument error.
- `2`: discovery or export failure.
- `3`: import, restore, or apply failure.

---

## Repository Discovery Rules
- The scan root is the current working directory.
- If the current working directory itself contains a `.git` directory or `.git` file, it must be ignored.
- Default scope: direct child directories only.
- Recursive scope: all descendant directories.
- A repository is considered discovered when a candidate directory contains:
  - a `.git/` directory, or
  - a `.git` file that points to an external Git dir.
- The exported `path` must always be stored relative to the current working directory.
- Broken repositories must not crash the full export; they should produce a warning on `stderr` and be skipped.
- Repositories without a clonable primary remote must be skipped and must always emit a warning to `stderr`.

### Dirty Repository Policy
- Export must include repositories even when they have tracked or untracked changes.
- Export must emit a warning to `stderr` for every dirty repository.
- In verbose mode, export must print the dirty file list to `stderr`.
- Dirty state is informational only; uncommitted file contents are not backed up by this tool.

### Local-Only Branch Policy
- Local-only branches must not be backed up.
- Export must warn when a repository contains local branches that do not map to a restorable remote-tracking source.
- In verbose mode, export may list those skipped local-only branch names on `stderr`.

### Local Tag and Stash Policy
- Tags not present on any remote must not be backed up.
- Stashes must not be backed up.
- Export must warn when a repository contains tags not present on any remote or contains stash entries.
- In verbose mode, export may list the skipped tag names and stash references on `stderr`.

### Tag Comparison Method
- A tag should be considered local-only when its tag name is not present in any fetched remote tag namespace reachable from the repository remotes.
- v1 comparison should be name-based, not object-identity-based.
- v1 method: compare local tag names from `git tag --list` against the union of remote tag names gathered from `git ls-remote --tags <remote>` across all remotes.

### Local Filesystem Remote Policy
- Local filesystem remotes are considered clonable.
- Export must warn when a repository uses a local filesystem remote because such backups may not be portable to another machine.
- Dry-run export must include the same warning.

### Submodule and Worktree Discovery Policy
- Parent repositories that contain submodules must be exported normally, with submodule metadata recorded.
- Linked worktrees associated with a repository must be recorded as metadata attached to the owning repository.
- Standalone traversal must avoid double-counting linked worktrees as ordinary independent repositories when they are already represented through owning repository metadata.

### Out-of-Scope Discovery Cases
- Bare repositories whose Git metadata lives directly in the folder root are not part of v1 discovery.

---

## Export Data Model

The export format is YAML designed for machine round-tripping by this tool.

### Top-Level Shape
```yaml
schema_version: 1
scan_root: .
recursive: true
repositories:
  - path: team/api
    primary_remote: origin
    checkout_url: git@github.com:example/team-api.git
    checkout_transport: ssh
    dirty: true
    dirty_files:
      - src/example.py
    untracked_files:
      - tmp/debug.txt
    head:
      type: branch
      name: main
      commit: 0123456789abcdef0123456789abcdef01234567
    remotes:
      - name: origin
        fetch_url: git@github.com:example/team-api.git
        push_url: git@github.com:example/team-api.git
        transport: ssh
    git_config:
      - key: core.filemode
        value: "true"
      - key: branch.main.remote
        value: origin
    custom_config:
      - key: user.name
        value: Jane Example
      - key: core.sshCommand
        value: ssh -i ~/.ssh/team-key
    submodules:
      - path: vendor/lib-a
        url: git@github.com:example/lib-a.git
        commit: fedcba9876543210fedcba9876543210fedcba98
        branch: main
    worktrees:
      - path: worktrees/team-api-hotfix
        branch: hotfix/urgent
        commit: abcdef0123456789abcdef0123456789abcdef01
```

### Field Definitions
- `schema_version`
  - Integer format version for future compatibility.
- `scan_root`
  - Always `.` for v1.
- `recursive`
  - Whether export discovery used recursive traversal.
- `repositories`
  - Ordered list of discovered repositories sorted by relative path.

### Per-Repository Fields
- `path`
  - Relative path from export root.
- `primary_remote`
  - The remote used for initial clone during import.
  - Default selection rule: `origin` if present, otherwise the first remote in lexical order.
- `checkout_url`
  - Fetch URL for the primary remote.
- `checkout_transport`
  - One of `ssh`, `https`, or `other`.
- `dirty`
  - Boolean indicating whether the working tree had tracked or untracked changes at export time.
- `dirty_files`
  - Relative file paths with tracked modifications, deletions, renames, or staged changes.
- `untracked_files`
  - Relative file paths not tracked by Git at export time.
- `head`
  - Current checkout state.
  - `type` is `branch` or `detached`.
  - `name` is required for `branch` and omitted for detached state.
  - `commit` is always included for reproducibility.
- `remotes`
  - All remotes configured in the repo.
  - Each remote stores `name`, `fetch_url`, `push_url`, and transport classification.
- `git_config`
  - Full repository-local config entries from `.git/config`, represented as an ordered list of key/value pairs.
  - This is the authoritative restore source.
- `custom_config`
  - Filtered subset of `git_config` intended for visibility.
  - This is informational and restorable.
- `submodules`
  - Recorded submodule definitions from the parent repository.
  - Each entry stores at least `path`, `url`, and the recorded commit SHA to restore.
  - Optional configured branch metadata may also be recorded for reference.
- `worktrees`
  - Recorded linked worktree definitions associated with the repository.
  - Each entry stores a worktree path that must be relative, plus checkout state needed for optional recreation.

### Transport Classification Rules
- `ssh`
  - URLs beginning with `git@`
  - URLs beginning with `ssh://`
- `https`
  - URLs beginning with `https://`
- `other`
  - Any other Git remote syntax, including local filesystem paths, `file://`, or unsupported schemes

### Clonable Source Rules
The following sources are considered clonable in v1:
- `git@...`
- `ssh://...`
- `https://...`
- local filesystem remotes, including absolute paths, relative paths, and `file://...`

Repositories without any such usable source must be skipped with a warning.

Local filesystem remotes must also produce a portability warning during export and export dry-run.

---

## Custom Config Definition
`custom_config` exists because the user explicitly wants repository-specific custom settings called out in the export.

### v1 Rule
`custom_config` must include repository-local config entries that are **not required merely to describe clone origin, remotes, or current branch wiring**.

Examples that usually belong in `custom_config`:
- `user.name`
- `user.email`
- `core.sshCommand`
- `commit.gpgsign`
- `http.*`
- `url.*`
- repository-only tooling keys

Examples that usually do **not** belong in `custom_config` because they are core clone/check-out metadata:
- `remote.*.url`
- `remote.*.fetch`
- `branch.*.remote`
- `branch.*.merge`

### Important Design Note
Because exact classification can vary by repository state, `git_config` is the authoritative restoration source. `custom_config` is a convenience subset for visibility and auditing.

---

## Import / Restore Behavior

### Input Assumption
- Import accepts only YAML previously generated by `gitbare` schema version `1`.
- If the YAML is malformed or does not match schema version `1`, fail fast.

### Non-Clonable Repository Policy
- Repositories without a clonable source must not appear in the exported `repositories` list.
- Export must always warn when such repositories are skipped.
- v1 will not attempt to recreate repositories that have no usable remote clone URL.

### Restore Flow Per Repository
1. Create parent directories for the stored relative `path`.
2. Evaluate whether the target path already exists.
3. If the target path does not contain a compatible Git working copy, clone using `checkout_url` from `primary_remote`.
4. If the target path already contains a compatible Git working copy and `--pull` is enabled, update that working copy from the remote instead of recloning.
5. Recreate all additional remotes and remote push URLs.
6. Restore the recorded `head` state.
7. Reapply repository-local config from `git_config`.
8. If `--restore-submodules` is enabled, initialize and update recorded submodules.
9. If `--restore-worktrees` is enabled, recreate recorded linked worktrees.
10. Preserve the directory structure exactly as represented by `path`.

### `--dry-run` Behavior
`--dry-run` must perform planning and validation without mutating repositories, directories, config, submodules, or worktrees.

In export mode:
- discovery still runs,
- all normal warnings still appear,
- YAML may still be emitted to `stdout` because export itself is read-only,
- verbose output should clearly mark the run as dry-run planning.

In import mode:
- YAML parsing and validation still run,
- compatibility checks still run,
- the tool must report what it would clone, pull, skip, fail, restore, or warn about,
- no filesystem changes or Git mutations are allowed.

`--dry-run` is intended to let users discover path conflicts, non-clonable repositories, remote mismatches, missing commits, submodule/worktree restore risks, and other blockers before executing a real import.

### `--pull` Behavior
`--pull` only changes import behavior for already-existing compatible repositories.

Compatibility means:
- the target path is a Git working copy, and
- the repository can be matched to the YAML entry using the primary remote name and URL.

When `--pull` is active and the repository is compatible:
1. run a fetch/update step against the configured remotes,
2. ensure the recorded remotes and URLs match the YAML after reconciliation,
3. restore the recorded branch or detached commit state,
4. reapply local config.

Implementation target for v1:
- use `git fetch --all --prune` as the mandatory refresh step,
- if `head.type == branch`, perform a safe fast-forward style update for the tracked branch when possible,
- if `head.type == detached`, fetch required refs and then check out the recorded commit.
- if pull/update fails because histories diverge or fast-forward is not possible, emit a warning to `stderr`, mark that repository as failed, and continue with later repositories.

If `--pull` is not provided and a compatible repository already exists, import should fail for that repository rather than silently mutating it.

### Submodule Restore Behavior
- Submodule metadata must be recorded during export.
- Default import behavior must **not** automatically initialize submodules.
- When `--restore-submodules` is provided:
  - ensure the parent repository is restored first,
  - restore `.gitmodules`-defined URLs and branch settings from the recorded parent state,
  - restore each submodule to its recorded commit SHA,
  - run submodule initialization/update commands only as needed to reach the recorded commit.
- If submodule restoration fails, report failure for that parent repository and continue with the next repository.

### Worktree Restore Behavior
- Linked worktree metadata must be recorded during export.
- Default import behavior must **not** recreate linked worktrees.
- When `--restore-worktrees` is provided:
  - restore the main repository first,
  - recreate each linked worktree using Git worktree commands,
  - restore the recorded branch or detached commit state for each worktree,
  - reject any worktree entry whose stored path is absolute,
  - fail safely if a target worktree path already exists and is incompatible.

### Feasibility Note: Worktrees
Yes, linked worktrees are possible to recreate in v1 because Git exposes them via `git worktree list --porcelain` and they can be re-added with `git worktree add`.

The practical limitation is that worktree recreation depends on the referenced commit or branch being available after clone/fetch. Therefore worktree restore is feasible as an **opt-in** feature, not a guaranteed default action.

### Feasibility Note: Submodules
Yes, submodules can be recorded and optionally restored in v1 because Git exposes them through `.gitmodules`, local config, and submodule commands.

The practical limitation is that successful restore depends on submodule URLs being reachable and the recorded commits being available upstream. Therefore submodule restore should remain opt-in.

### Config Reapplication Rules
- Reapply repository-local config only, never global config.
- If duplicate config keys are encountered in the exported repository-local config data, abort processing with exit code `1` because this backup format does not support ambiguous duplicate-key restoration.
- For keys being restored, remove existing local values for that key before writing restored values so the final `.git/config` is deterministic.
- Protected keys that should not be blindly forced in v1:
  - `core.repositoryformatversion`
  - `core.bare`
  - `core.worktree`
- If a protected key appears in exported `git_config`, skip it and emit a warning to `stderr`.

### Existing Directory Policy
- If the target directory does not exist: create it.
- If the target directory exists but is empty: proceed with clone/setup.
- If the target directory exists and is a compatible Git repo:
  - with `--pull`: update and reconcile it.
  - without `--pull`: fail for that repository and continue.
- If the target directory exists and is non-empty but not a compatible repo: fail for that repository and continue with the next one.

### Recursive Layout Restoration
- Import must not invent paths.
- Nested folder structure is recreated entirely from each repository `path` value.
- Therefore a config exported with `-r` automatically recreates nested layout during import.

---

## Parsing and Safety Constraints

### YAML Strategy
A dedicated YAML library should be used for parsing and emission instead of a hand-rolled parser.

Preferred v1 choice:
- `PyYAML`

Acceptable alternative if round-trip formatting preservation becomes important:
- `ruamel.yaml`

Implications:
- Use safe loader and dumper APIs only.
- Never deserialize arbitrary Python objects.
- The tool may accept hand-edited YAML as long as it matches the documented schema.
- Emitted YAML should remain deterministic enough for stable diffs and repeatable backups.

### Input Safety
- Never execute data from YAML.
- Never use `eval()`.
- Treat all parsed strings as untrusted input.
- Always invoke Git with argument lists via `subprocess`, never shell-expanded command strings.
- Send diagnostics to `stderr`, never mix them into exported YAML.

---

## Proposed Script Structure
Primary CLI entrypoint is `gitbare`.

Implementation should stay function-oriented. A package layout such as `src/gitbare/` with `__main__.py` and a console-script entrypoint is preferred. If internals grow, split them into focused modules while preserving `gitbare` as the installed executable command.

### Responsibilities
- `main`
- `build_arg_parser`
- `detect_mode`
- `plan_operations`
- `discover_repositories`
- `inspect_repository`
- `select_primary_remote`
- `classify_transport`
- `capture_head_state`
- `capture_dirty_state`
- `capture_git_config`
- `capture_submodules`
- `capture_worktrees`
- `filter_custom_config`
- `emit_yaml`
- `parse_yaml_import`
- `restore_repository`
- `clone_repository`
- `update_existing_repository`
- `restore_remotes`
- `restore_head`
- `restore_git_config`
- `restore_submodules`
- `restore_worktrees`
- `run_git`
- `log_verbose`

### Expected Standard Library Usage
- `argparse` for CLI parsing
- `subprocess` for Git execution
- `pathlib` and `os` for filesystem traversal
- `sys` for stdin/stdout/stderr and exit control
- `dataclasses` or plain dictionaries for internal records
- `importlib.metadata` or package metadata helpers for version reporting
- `unittest` for the test suite

### Expected Third-Party Usage
- `PyYAML` for safe YAML loading and dumping

### Packaging Requirements
- Use modern Python packaging metadata in `pyproject.toml`.
- Define a console-script entrypoint named `gitbare`.
- Console entrypoint means package installation exposes a shell command named `gitbare` that runs the Python application without requiring users to type `python -m ...`.
- Keep dependencies minimal.
- Declare `PyYAML` explicitly with a stable version range.
- Include installation and execution docs for:
  - local editable/development use with `uv`,
  - installed CLI use,
  - `uv tool install` from a GitHub repository,
  - remote execution with `uvx` from a GitHub repository.
- Source code must live under `src/`.
- Automated tests must live under `tests/`.
- Users should run the installed `gitbare` command; the package directory itself is not a user-facing execution target.

### Internal Principles
- Keep export and import logic clearly separated.
- Use helper functions for repeated Git queries.
- Avoid hidden global mutation where possible.
- Keep all path handling relative to the invocation directory.
- Preserve deterministic ordering for repeatable exports.

---

## Operational Requirements
- Installed command name: `gitbare`
- Interpreter: Python 3
- Minimum supported version target: Python 3.10
- External executable required: `git`
- Required Python dependency: `PyYAML`.
- The package must be installable with standard Python packaging metadata.
- The project must support local development via `uv venv` and command execution via `uv run`.
- The package must expose a console entrypoint so users do not need to invoke a raw `.py` file.
- Application source files must be stored under `src/`.
- Automated tests must be stored under `tests/`.
- `--help` output must document stdin/stdout usage examples.
- `--version` output should expose the application version in a simple machine-readable string.
- User-facing documentation must include `uvx --from git+https://github.com/... gitbare ...` examples.
- User-facing documentation must also include `uv tool install git+https://github.com/...` examples.

---

## Error Handling
- A single broken repo must not destroy a full export.
- Import should continue processing later repositories after a per-repo failure and return non-zero if any repo failed.
- All user-facing errors must be actionable and concise.
- All warnings and errors must be written to `stderr`.
- Critical failures must return a non-zero exit code.
- Exported YAML must remain valid even when some repositories are skipped.
- Verbose logs belong on `stderr` only.

---

## Ordering Rules
- Export repositories sorted by relative `path` for deterministic output.
- Export `git_config` in stable key/value order as returned by Git or explicitly sorted during capture.
- Export `remotes` in lexical name order.

---

## Security Notes
- The script may export repository-local Git config verbatim.
- If a repository-local config contains secrets or tokens, they will appear in the YAML by design because round-trip restoration requires fidelity.
- The script must not duplicate those values into logs or extra diagnostic output.
- Users are responsible for storing exported YAML securely.
- This includes secrets embedded in `.git/config`, remote URLs, submodule URLs, and related repository-local settings.
- Documentation must warn that backups using local filesystem remotes may fail to restore correctly on different machines or directory layouts.

---

## Test Strategy

### CLI Tests
- `--help` returns `0` and prints usage.
- `--version` returns `0` and prints version.
- `--import -` reads from `stdin`.
- `--import repo.yml` reads from a file.
- `--export -` writes to `stdout`.
- `--export repo.yml` writes to a file.
- `cat repo.yml | gitbare --import -` imports from stdin explicitly.
- `-v` emits logs only to `stderr`.
- `--dry-run` is accepted in export and import modes.
- `--pull` is rejected in export mode.
- `--restore-worktrees` is rejected in export mode.
- `--restore-submodules` is rejected in export mode.
- Installed `gitbare` console entrypoint launches successfully.
- `uv run gitbare --help` works in local development.

### Export Tests
- Detect one repo in a direct child directory.
- Ignore a Git repository located at the current working directory itself.
- Detect nested repos only when `-r` is set.
- Correctly classify `git@...` as `ssh`.
- Correctly classify `https://...` as `https`.
- Correctly accept `ssh://...` as clonable.
- Correctly accept local filesystem remotes as clonable.
- Warn when a repository uses a local filesystem remote.
- Warn when a repository is dirty.
- Show dirty file paths in verbose mode.
- Warn when a repository contains local-only branches.
- Warn when a repository contains local tags.
- Warn when a repository contains stashes.
- Include repository-local custom config in `custom_config`.
- Record submodule metadata when present.
- Record linked worktree metadata when present.
- Skip repositories without clonable remotes and warn.
- Produce deterministic path ordering.

### Import Tests
- Recreate a flat set of repositories from YAML.
- Recreate nested directory layout from recursive export YAML.
- Restore remotes and push URLs.
- Clone from local filesystem remotes.
- Restore branch checkout state.
- Restore detached HEAD state.
- Restore repository-local config entries.
- Restore submodules by recorded commit SHA when enabled.
- Reject absolute worktree paths.
- Fail safely on malformed YAML.
- Fail safely on conflicting existing directories.
- `--dry-run` reports planned clone/pull/skip actions without mutating anything.
- Update an already-existing compatible repository when `--pull` is provided.
- Warn and continue when `--pull` encounters divergence or non-fast-forward failure.
- Refuse to mutate an already-existing compatible repository when `--pull` is not provided.
- Abort with exit code `1` when duplicate git config keys are encountered in backup data.
- Restore submodules when `--restore-submodules` is provided.
- Do not restore submodules by default.
- Restore linked worktrees when `--restore-worktrees` is provided.
- Do not restore linked worktrees by default.

### Round-Trip Test
- Export fixtures -> import into empty directory -> re-export -> compare normalized YAML-relevant fields.

### Test Suite Layout
- Keep the full automated test suite under `tests/`.
- Use fixture repositories created dynamically during tests rather than committed Git metadata where possible.
- Use Python `unittest` for the full test suite.

---

## Open Decisions For Implementation
- None currently.

For v1, the implementation should prefer deterministic and reversible behavior over broad YAML flexibility.
