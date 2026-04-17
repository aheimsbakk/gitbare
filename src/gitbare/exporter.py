from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from gitbare.git_ops import GitCommandError, classify_transport, is_clonable_source, is_git_repository, parse_null_config, relative_posix, run_git


def discover_repositories(scan_root: Path, recursive: bool) -> list[Path]:
    repositories: list[Path] = []
    candidates = sorted([child for child in scan_root.iterdir() if child.is_dir()])
    if recursive:
        seen: set[Path] = set()
        for current_root, dirnames, _filenames in os.walk(scan_root):
            current_path = Path(current_root)
            dirnames[:] = [name for name in dirnames if name != ".git"]
            if current_path == scan_root:
                continue
            if current_path in seen:
                continue
            if is_git_repository(current_path):
                repositories.append(current_path)
                seen.add(current_path)
    else:
        for candidate in candidates:
            if is_git_repository(candidate):
                repositories.append(candidate)
    return sorted(repositories, key=lambda item: (len(item.parts), relative_posix(item, scan_root)))


def capture_head_state(repo_path: Path) -> dict[str, str]:
    commit = run_git(repo_path, "rev-parse", "HEAD").stdout.strip()
    branch_result = run_git(repo_path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch_result.returncode == 0:
        return {"type": "branch", "name": branch_result.stdout.strip(), "commit": commit}
    return {"type": "detached", "commit": commit}


def capture_dirty_state(repo_path: Path) -> tuple[bool, list[str], list[str]]:
    status = run_git(repo_path, "status", "--porcelain").stdout.splitlines()
    dirty_files: list[str] = []
    untracked_files: list[str] = []
    for line in status:
        if not line:
            continue
        code = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = Path(path).as_posix()
        if code == "??":
            untracked_files.append(path)
        else:
            dirty_files.append(path)
    return bool(dirty_files or untracked_files), sorted(dirty_files), sorted(untracked_files)


def capture_remotes(repo_path: Path) -> list[dict[str, str]]:
    remote_names = run_git(repo_path, "remote").stdout.splitlines()
    remotes: list[dict[str, str]] = []
    for name in sorted(filter(None, remote_names)):
        fetch_url = run_git(repo_path, "remote", "get-url", name).stdout.strip()
        push_result = run_git(repo_path, "remote", "get-url", "--push", name, check=False)
        push_url = push_result.stdout.strip() if push_result.returncode == 0 else fetch_url
        remotes.append(
            {
                "name": name,
                "fetch_url": fetch_url,
                "push_url": push_url,
                "transport": classify_transport(fetch_url),
            }
        )
    return remotes


def select_primary_remote(remotes: list[dict[str, str]]) -> dict[str, str] | None:
    if not remotes:
        return None
    for remote in remotes:
        if remote["name"] == "origin":
            return remote
    return remotes[0]


def capture_git_config(repo_path: Path) -> list[dict[str, str]]:
    result = run_git(repo_path, "config", "--local", "--null", "--list", check=False)
    if result.returncode != 0:
        return []
    return parse_null_config(result.stdout)


def filter_custom_config(git_config: list[dict[str, str]]) -> list[dict[str, str]]:
    excluded_prefixes = (
        "remote.",
        "branch.",
    )
    excluded_exact = {
        "core.repositoryformatversion",
        "core.bare",
        "core.worktree",
    }
    custom_entries: list[dict[str, str]] = []
    for entry in git_config:
        key = entry["key"]
        if key in excluded_exact:
            continue
        if any(key.startswith(prefix) for prefix in excluded_prefixes):
            continue
        custom_entries.append({"key": entry["key"], "value": entry["value"]})
    return custom_entries


def capture_local_only_branches(repo_path: Path) -> list[str]:
    result = run_git(
        repo_path,
        "for-each-ref",
        "refs/heads",
        "--format=%(refname:short)\t%(upstream:short)",
        check=False,
    )
    if result.returncode != 0:
        return []
    local_only: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        name, _, upstream = line.partition("\t")
        if name and not upstream:
            local_only.append(name)
    return sorted(local_only)


def capture_local_only_tags(repo_path: Path) -> list[str]:
    local_tags = set(filter(None, run_git(repo_path, "tag", "--list").stdout.splitlines()))
    if not local_tags:
        return []
    remote_tags: set[str] = set()
    for remote in capture_remotes(repo_path):
        result = run_git(repo_path, "ls-remote", "--tags", remote["name"], check=False)
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            ref_name = parts[1]
            if not ref_name.startswith("refs/tags/"):
                continue
            tag_name = ref_name.removeprefix("refs/tags/")
            tag_name = tag_name.removesuffix("^{}")
            remote_tags.add(tag_name)
    return sorted(local_tags - remote_tags)


def capture_stashes(repo_path: Path) -> list[str]:
    result = run_git(repo_path, "stash", "list", check=False)
    if result.returncode != 0:
        return []
    stashes: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        name, _, _rest = line.partition(":")
        stashes.append(name)
    return stashes


def capture_submodules(repo_path: Path) -> list[dict[str, str]]:
    gitmodules_path = repo_path / ".gitmodules"
    if not gitmodules_path.exists():
        return []
    path_result = run_git(
        repo_path,
        "config",
        "--file",
        ".gitmodules",
        "--get-regexp",
        r"^submodule\..*\.path$",
        check=False,
    )
    if path_result.returncode != 0:
        return []
    submodules: list[dict[str, str]] = []
    for line in path_result.stdout.splitlines():
        key, _, submodule_path = line.partition(" ")
        name = key.split(".")[1]
        url = run_git(
            repo_path,
            "config",
            "--file",
            ".gitmodules",
            "--get",
            f"submodule.{name}.url",
        ).stdout.strip()
        branch_result = run_git(
            repo_path,
            "config",
            "--file",
            ".gitmodules",
            "--get",
            f"submodule.{name}.branch",
            check=False,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        commit_result = run_git(repo_path, "ls-files", "--stage", "--", submodule_path, check=False)
        commit = ""
        if commit_result.returncode == 0 and commit_result.stdout.strip():
            commit = commit_result.stdout.split()[1]
        entry = {"path": Path(submodule_path).as_posix(), "url": url, "commit": commit}
        if branch:
            entry["branch"] = branch
        submodules.append(entry)
    return sorted(submodules, key=lambda item: item["path"])


def capture_worktrees(repo_path: Path, scan_root: Path) -> list[dict[str, str]]:
    result = run_git(repo_path, "worktree", "list", "--porcelain", check=False)
    if result.returncode != 0:
        return []
    worktrees: list[dict[str, str]] = []
    block: dict[str, str] = {}
    for line in result.stdout.splitlines() + [""]:
        if not line:
            if block:
                worktree_path = Path(block["worktree"])
                if worktree_path.resolve() != repo_path.resolve():
                    entry = {
                        "path": relative_posix(worktree_path, scan_root),
                        "commit": block.get("HEAD", ""),
                    }
                    branch = block.get("branch", "")
                    if branch.startswith("refs/heads/"):
                        entry["branch"] = branch.removeprefix("refs/heads/")
                    worktrees.append(entry)
                block = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
            block[key] = value
        else:
            block[line] = "true"
    return sorted(worktrees, key=lambda item: item["path"])


def inspect_repository(repo_path: Path, scan_root: Path, verbose: bool) -> tuple[dict[str, object] | None, list[str], list[str]]:
    warnings: list[str] = []
    verbose_lines: list[str] = []
    remotes = capture_remotes(repo_path)
    primary_remote = select_primary_remote(remotes)
    if primary_remote is None or not is_clonable_source(primary_remote["fetch_url"]):
        warnings.append(f"Skipping {relative_posix(repo_path, scan_root)}: no clonable primary remote")
        return None, warnings, verbose_lines
    if primary_remote["transport"] == "other":
        warnings.append(
            f"Repository {relative_posix(repo_path, scan_root)} uses a local or non-standard remote and may not be portable"
        )
    dirty, dirty_files, untracked_files = capture_dirty_state(repo_path)
    if dirty:
        warnings.append(f"Repository {relative_posix(repo_path, scan_root)} is dirty")
        if verbose:
            for path in dirty_files:
                verbose_lines.append(f"dirty: {relative_posix(repo_path, scan_root)}:{path}")
            for path in untracked_files:
                verbose_lines.append(f"untracked: {relative_posix(repo_path, scan_root)}:{path}")
    local_only_branches = capture_local_only_branches(repo_path)
    if local_only_branches:
        warnings.append(f"Repository {relative_posix(repo_path, scan_root)} has local-only branches")
        if verbose:
            for branch in local_only_branches:
                verbose_lines.append(f"local-only-branch: {relative_posix(repo_path, scan_root)}:{branch}")
    local_only_tags = capture_local_only_tags(repo_path)
    if local_only_tags:
        warnings.append(f"Repository {relative_posix(repo_path, scan_root)} has local-only tags")
        if verbose:
            for tag in local_only_tags:
                verbose_lines.append(f"local-only-tag: {relative_posix(repo_path, scan_root)}:{tag}")
    stashes = capture_stashes(repo_path)
    if stashes:
        warnings.append(f"Repository {relative_posix(repo_path, scan_root)} has stashes that will not be backed up")
        if verbose:
            for stash in stashes:
                verbose_lines.append(f"stash: {relative_posix(repo_path, scan_root)}:{stash}")
    git_config = capture_git_config(repo_path)
    record: dict[str, object] = {
        "path": relative_posix(repo_path, scan_root),
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
    return record, warnings, verbose_lines


def export_repositories(scan_root: Path, recursive: bool, verbose: bool) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    verbose_lines: list[str] = []
    repositories: list[dict[str, object]] = []
    discovered = discover_repositories(scan_root, recursive)
    excluded_realpaths: set[Path] = set()
    for repo_path in discovered:
        try:
            real_path = repo_path.resolve()
            if real_path in excluded_realpaths:
                continue
            record, repo_warnings, repo_verbose = inspect_repository(repo_path, scan_root, verbose)
            warnings.extend(repo_warnings)
            verbose_lines.extend(repo_verbose)
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
            warnings.append(f"Skipping {relative_posix(repo_path, scan_root)}: {error}")
    repositories.sort(key=lambda item: item["path"])
    warnings.extend(verbose_lines)
    return {"schema_version": 1, "scan_root": ".", "recursive": recursive, "repositories": repositories}, warnings


def dump_yaml(data: dict[str, object]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
