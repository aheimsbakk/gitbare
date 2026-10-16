"""Per-aspect Git metadata capture and config classification for export."""

from __future__ import annotations

from pathlib import Path

from gitbare.git_ops import (
    NETWORK_GIT_TIMEOUT_SECONDS,
    classify_transport,
    parse_null_config,
    run_git,
)

PROTECTED_CONFIG_KEYS = {
    "core.repositoryformatversion",
    "core.bare",
    "core.worktree",
}


def capture_head_state(repo_path: Path) -> dict[str, str]:
    commit = run_git(repo_path, "rev-parse", "HEAD").stdout.strip()
    branch_result = run_git(
        repo_path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False
    )
    if branch_result.returncode == 0:
        return {
            "type": "branch",
            "name": branch_result.stdout.strip(),
            "commit": commit,
        }
    return {"type": "detached", "commit": commit}


def capture_dirty_state(repo_path: Path) -> tuple[bool, list[str], list[str]]:
    # -z keeps paths byte-exact. Default porcelain output C-quotes paths with
    # spaces or non-ASCII characters, which corrupts the exported file lists.
    status = run_git(repo_path, "status", "--porcelain", "-z").stdout.split("\0")
    dirty_files: list[str] = []
    untracked_files: list[str] = []
    index = 0
    while index < len(status):
        entry = status[index]
        index += 1
        if not entry:
            continue
        code = entry[:2]
        path = entry[3:]
        if code[0] in {"R", "C"} and index < len(status) and status[index]:
            # Rename and copy entries carry the origin path in the next field.
            index += 1
        path = Path(path).as_posix()
        if code == "??":
            untracked_files.append(path)
        else:
            dirty_files.append(path)
    return (
        bool(dirty_files or untracked_files),
        sorted(dirty_files),
        sorted(untracked_files),
    )


def capture_remotes(repo_path: Path) -> list[dict[str, str]]:
    remote_names = run_git(repo_path, "remote").stdout.splitlines()
    remotes: list[dict[str, str]] = []
    for name in sorted(filter(None, remote_names)):
        fetch_url = run_git(repo_path, "remote", "get-url", name).stdout.strip()
        push_result = run_git(
            repo_path, "remote", "get-url", "--push", name, check=False
        )
        push_url = (
            push_result.stdout.strip() if push_result.returncode == 0 else fetch_url
        )
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
    return [
        entry
        for entry in parse_null_config(result.stdout)
        if entry["key"] not in PROTECTED_CONFIG_KEYS
    ]


def filter_custom_config(git_config: list[dict[str, str]]) -> list[dict[str, str]]:
    excluded_prefixes = (
        "remote.",
        "branch.",
    )
    custom_entries: list[dict[str, str]] = []
    for entry in git_config:
        key = entry["key"]
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
    local_tags = set(
        filter(None, run_git(repo_path, "tag", "--list").stdout.splitlines())
    )
    if not local_tags:
        return []
    remote_tags: set[str] = set()
    for remote in capture_remotes(repo_path):
        result = run_git(
            repo_path,
            "ls-remote",
            "--tags",
            remote["name"],
            check=False,
            timeout=NETWORK_GIT_TIMEOUT_SECONDS,
        )
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
