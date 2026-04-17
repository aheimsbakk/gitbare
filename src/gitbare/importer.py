from __future__ import annotations

from pathlib import Path

import yaml

from gitbare.git_ops import GitCommandError, is_git_repository, run_command, run_git
from gitbare.logging_utils import OperationLogger


PROTECTED_CONFIG_KEYS = {
    "core.repositoryformatversion",
    "core.bare",
    "core.worktree",
}


def parse_yaml_import(text: str) -> dict[str, object]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("repositories"), list):
        raise ValueError("Input must be gitbare schema_version 1 YAML")
    return data


def ensure_relative_repo_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        raise ValueError(f"Repository path must be relative: {path_value}")
    return path


def validate_git_config(entries: list[dict[str, str]]) -> None:
    seen: set[str] = set()
    for entry in entries:
        key = entry["key"]
        if key in seen:
            raise ValueError(f"Duplicate git config key in backup data: {key}")
        seen.add(key)


def validate_import_data(data: dict[str, object]) -> None:
    repositories = data.get("repositories", [])
    for repo_data in repositories:
        ensure_relative_repo_path(str(repo_data["path"]))
        validate_git_config(list(repo_data.get("git_config", [])))


def is_compatible_repository(target_path: Path, repo_data: dict[str, object]) -> bool:
    if not is_git_repository(target_path):
        return False
    primary_remote = str(repo_data["primary_remote"])
    checkout_url = str(repo_data["checkout_url"])
    result = run_git(target_path, "remote", "get-url", primary_remote, check=False)
    return result.returncode == 0 and result.stdout.strip() == checkout_url


def restore_remotes(target_path: Path, repo_data: dict[str, object]) -> None:
    existing = set(run_git(target_path, "remote", check=False).stdout.splitlines())
    for remote in repo_data.get("remotes", []):
        name = remote["name"]
        fetch_url = remote["fetch_url"]
        push_url = remote["push_url"]
        if name in existing:
            run_git(target_path, "remote", "set-url", name, fetch_url)
        else:
            run_git(target_path, "remote", "add", name, fetch_url)
        run_git(target_path, "remote", "set-url", "--push", name, push_url)


def restore_head(target_path: Path, repo_data: dict[str, object], pull_mode: bool) -> None:
    head = repo_data["head"]
    head_type = head["type"]
    commit = head["commit"]
    primary_remote = str(repo_data["primary_remote"])
    if head_type == "branch":
        branch = head["name"]
        remote_branch = f"refs/remotes/{primary_remote}/{branch}"
        remote_exists = run_git(target_path, "rev-parse", "--verify", remote_branch, check=False).returncode == 0
        local_exists = run_git(target_path, "rev-parse", "--verify", f"refs/heads/{branch}", check=False).returncode == 0
        if pull_mode and local_exists and remote_exists:
            run_git(target_path, "checkout", branch)
            run_git(target_path, "merge", "--ff-only", remote_branch)
            return
        if remote_exists and not local_exists:
            run_git(target_path, "checkout", "-B", branch, "--track", f"{primary_remote}/{branch}")
            return
        if local_exists:
            run_git(target_path, "checkout", branch)
            return
        run_git(target_path, "checkout", "-B", branch, commit)
        return
    run_git(target_path, "checkout", "--detach", commit)


def restore_git_config(target_path: Path, repo_data: dict[str, object], logger: OperationLogger) -> None:
    entries = list(repo_data.get("git_config", []))
    validate_git_config(entries)
    for entry in entries:
        key = entry["key"]
        value = entry["value"]
        if key in PROTECTED_CONFIG_KEYS:
            logger.info(f"Skipping protected config key {key} in {repo_data['path']}")
            continue
        run_git(target_path, "config", "--local", "--unset-all", key, check=False)
        run_git(target_path, "config", "--local", "--add", key, value)


def restore_submodules(target_path: Path, repo_data: dict[str, object]) -> None:
    for submodule in repo_data.get("submodules", []):
        submodule_path = Path(submodule["path"])
        if submodule_path.is_absolute():
            raise ValueError(f"Submodule path must be relative: {submodule['path']}")
        run_git(
            target_path,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--init",
            "--",
            submodule["path"],
        )
        run_git(target_path / submodule_path, "fetch", "--all", "--prune", check=False)
        if submodule.get("commit"):
            run_git(target_path / submodule_path, "checkout", submodule["commit"])


def restore_worktrees(target_path: Path, repo_data: dict[str, object], destination_root: Path) -> None:
    for worktree in repo_data.get("worktrees", []):
        worktree_path = Path(worktree["path"])
        if worktree_path.is_absolute():
            raise ValueError(f"Worktree path must be relative: {worktree['path']}")
        absolute_path = destination_root / worktree_path
        if absolute_path.exists() and any(absolute_path.iterdir()):
            raise ValueError(f"Worktree target already exists and is non-empty: {worktree['path']}")
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        branch = worktree.get("branch")
        commit = worktree.get("commit", "HEAD")
        if branch:
            run_git(target_path, "worktree", "add", "-B", branch, str(absolute_path), commit)
        else:
            run_git(target_path, "worktree", "add", "--detach", str(absolute_path), commit)


def clone_repository(destination_root: Path, repo_data: dict[str, object]) -> Path:
    target_path = destination_root / ensure_relative_repo_path(str(repo_data["path"]))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(["git", "clone", str(repo_data["checkout_url"]), str(target_path)])
    return target_path


def update_existing_repository(target_path: Path) -> None:
    run_git(target_path, "fetch", "--all", "--prune")


def restore_repository(
    destination_root: Path,
    repo_data: dict[str, object],
    *,
    pull: bool,
    dry_run: bool,
    restore_submodules_flag: bool,
    restore_worktrees_flag: bool,
    logger: OperationLogger,
) -> bool:
    relative_path = ensure_relative_repo_path(str(repo_data["path"]))
    target_path = destination_root / relative_path
    if dry_run:
        if target_path.exists() and is_compatible_repository(target_path, repo_data):
            if pull:
                logger.info(f"Would pull {repo_data['path']}")
                return False
            logger.info(f"Would fail {repo_data['path']}: compatible repository exists without --pull")
            return False
        if target_path.exists() and any(target_path.iterdir()):
            logger.info(f"Would fail {repo_data['path']}: target exists and is incompatible")
            return False
        logger.info(f"Would clone {repo_data['path']}")
        return False
    if target_path.exists():
        if is_compatible_repository(target_path, repo_data):
            if not pull:
                logger.info(f"Failed {repo_data['path']}: compatible repository exists without --pull")
                return True
            logger.detail(f"Updating existing compatible repository {repo_data['path']}")
            update_existing_repository(target_path)
            try:
                restore_remotes(target_path, repo_data)
                restore_head(target_path, repo_data, True)
            except GitCommandError as error:
                logger.info(f"Failed {repo_data['path']}: {error}")
                return True
        elif target_path.is_dir() and not any(target_path.iterdir()):
            try:
                logger.detail(f"Cloning into empty directory for {repo_data['path']}")
                target_path = clone_repository(destination_root, repo_data)
            except GitCommandError as error:
                logger.info(f"Failed {repo_data['path']}: {error}")
                return True
        else:
            logger.info(f"Failed {repo_data['path']}: target exists and is incompatible")
            return True
    else:
        try:
            logger.detail(f"Cloning repository {repo_data['path']}")
            target_path = clone_repository(destination_root, repo_data)
        except GitCommandError as error:
            logger.info(f"Failed {repo_data['path']}: {error}")
            return True
    try:
        logger.detail(f"Restoring remotes for {repo_data['path']}")
        restore_remotes(target_path, repo_data)
        logger.detail(f"Restoring HEAD state for {repo_data['path']}")
        restore_head(target_path, repo_data, pull)
        logger.detail(f"Reapplying local Git config for {repo_data['path']}")
        restore_git_config(target_path, repo_data, logger)
        if restore_submodules_flag:
            logger.detail(f"Restoring submodules for {repo_data['path']}")
            restore_submodules(target_path, repo_data)
        if restore_worktrees_flag:
            logger.detail(f"Restoring linked worktrees for {repo_data['path']}")
            restore_worktrees(target_path, repo_data, destination_root)
    except (GitCommandError, ValueError) as error:
        logger.info(f"Failed {repo_data['path']}: {error}")
        return True
    logger.detail(f"Completed restore for {repo_data['path']}")
    return False


def import_repositories(
    destination_root: Path,
    yaml_text: str,
    *,
    pull: bool,
    dry_run: bool,
    restore_submodules_flag: bool,
    restore_worktrees_flag: bool,
    verbose: bool = False,
) -> bool:
    data = parse_yaml_import(yaml_text)
    validate_import_data(data)
    logger = OperationLogger(verbose=verbose)
    failed = False
    if verbose:
        logger.detail(f"Starting import into {destination_root}")
        logger.detail(f"Loaded {len(data['repositories'])} repositories from YAML")
        if dry_run:
            logger.detail("Dry-run enabled: import will only report planned actions")
    total_repositories = len(data["repositories"])
    for index, repo_data in enumerate(data["repositories"], start=1):
        action = "Planning restore for" if dry_run else "Restoring"
        logger.progress(index, total_repositories, f"{action} {repo_data['path']}")
        failure = restore_repository(
            destination_root,
            repo_data,
            pull=pull,
            dry_run=dry_run,
            restore_submodules_flag=restore_submodules_flag,
            restore_worktrees_flag=restore_worktrees_flag,
            logger=logger,
        )
        if failure:
            failed = True
    if verbose:
        logger.detail(f"Import finished with {'failures' if failed else 'no failures'}")
    return failed
