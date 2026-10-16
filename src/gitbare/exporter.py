"""Export orchestration: inspect discovered repositories and emit YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from gitbare.capture import (
    capture_dirty_state,
    capture_git_config,
    capture_head_state,
    capture_local_only_branches,
    capture_local_only_tags,
    capture_remotes,
    capture_stashes,
    filter_custom_config,
    select_primary_remote,
)
from gitbare.capture_nesting import capture_submodules, capture_worktrees
from gitbare.discovery import discover_repositories
from gitbare.git_ops import GitCommandError, is_clonable_source, relative_posix
from gitbare.logging_utils import OperationLogger


def inspect_repository(
    repo_path: Path,
    scan_root: Path,
    logger: OperationLogger,
) -> dict[str, object] | None:
    relative_repo_path = relative_posix(repo_path, scan_root)
    remotes = capture_remotes(repo_path)
    primary_remote = select_primary_remote(remotes)
    if primary_remote is None or not is_clonable_source(primary_remote["fetch_url"]):
        logger.info(f"Skipping {relative_repo_path}: no clonable primary remote")
        return None
    logger.detail(
        f"Selected primary remote {primary_remote['name']} for {relative_repo_path}"
    )
    if primary_remote["transport"] == "other":
        logger.info(
            f"Repository {relative_repo_path} uses a local or non-standard remote and may not be portable"
        )
    dirty, dirty_files, untracked_files = capture_dirty_state(repo_path)
    if dirty:
        logger.info(f"Repository {relative_repo_path} is dirty")
        for path in dirty_files:
            logger.detail(f"Dirty tracked path in {relative_repo_path}: {path}")
        for path in untracked_files:
            logger.detail(f"Dirty untracked path in {relative_repo_path}: {path}")
    local_only_branches = capture_local_only_branches(repo_path)
    if local_only_branches:
        logger.info(f"Repository {relative_repo_path} has local-only branches")
        for branch in local_only_branches:
            logger.detail(f"Local-only branch in {relative_repo_path}: {branch}")
    local_only_tags = capture_local_only_tags(repo_path)
    if local_only_tags:
        logger.info(f"Repository {relative_repo_path} has local-only tags")
        for tag in local_only_tags:
            logger.detail(f"Local-only tag in {relative_repo_path}: {tag}")
    stashes = capture_stashes(repo_path)
    if stashes:
        logger.info(
            f"Repository {relative_repo_path} has stashes that will not be backed up"
        )
        for stash in stashes:
            logger.detail(f"Stash in {relative_repo_path}: {stash}")
    git_config = capture_git_config(repo_path)
    record: dict[str, object] = {
        "path": relative_repo_path,
        "primary_remote": primary_remote["name"],
        "checkout_url": primary_remote["fetch_url"],
        "checkout_transport": primary_remote["transport"],
        "dirty": dirty,
        "dirty_files": dirty_files,
        "untracked_files": untracked_files,
        "head": capture_head_state(repo_path),
        "remotes": remotes,
        "git_config": git_config,
        "custom_config": filter_custom_config(git_config),
        "submodules": capture_submodules(repo_path),
        "worktrees": capture_worktrees(repo_path, scan_root),
    }
    logger.detail(f"Captured {len(remotes)} remotes for {relative_repo_path}")
    logger.detail(
        f"Captured {len(record['git_config'])} local config entries for {relative_repo_path}"
    )
    if record["submodules"]:
        logger.detail(
            f"Captured {len(record['submodules'])} submodules for {relative_repo_path}"
        )
    if record["worktrees"]:
        logger.detail(
            f"Captured {len(record['worktrees'])} linked worktrees for {relative_repo_path}"
        )
    return record


def export_repositories(
    scan_root: Path, recursive: bool, verbose: bool, dry_run: bool = False
) -> dict[str, object]:
    logger = OperationLogger(verbose=verbose)
    repositories: list[dict[str, object]] = []
    if verbose:
        logger.detail(f"Starting export from {scan_root}")
        logger.detail(
            f"Discovery mode: {'recursive' if recursive else 'direct-children'}"
        )
        if dry_run:
            logger.detail("Dry-run enabled: export will only plan and emit YAML")
    discovered = discover_repositories(scan_root, recursive)
    logger.detail(f"Discovered {len(discovered)} candidate repositories")
    excluded_realpaths: set[Path] = set()
    for index, repo_path in enumerate(discovered, start=1):
        try:
            relative_repo_path = relative_posix(repo_path, scan_root)
            logger.progress(index, len(discovered), f"Inspecting {relative_repo_path}")
            real_path = repo_path.resolve()
            if real_path in excluded_realpaths:
                logger.detail(
                    f"Skipping nested path already represented elsewhere: {relative_repo_path}"
                )
                continue
            record = inspect_repository(repo_path, scan_root, logger)
            if record is None:
                continue
            repositories.append(record)
            for submodule in record.get("submodules", []):
                submodule_path = (repo_path / Path(submodule["path"])).resolve()
                excluded_realpaths.add(submodule_path)
            for worktree in record.get("worktrees", []):
                worktree_path = (scan_root / Path(worktree["path"])).resolve()
                excluded_realpaths.add(worktree_path)
        except GitCommandError as error:
            logger.info(f"Skipping {relative_posix(repo_path, scan_root)}: {error}")
    repositories.sort(key=lambda item: item["path"])
    logger.detail(f"Prepared export for {len(repositories)} repositories")
    return {
        "schema_version": 1,
        "scan_root": ".",
        "recursive": recursive,
        "repositories": repositories,
    }


def dump_yaml(data: dict[str, object]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
