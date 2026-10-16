"""Capture nested Git structures: submodules and linked worktrees."""

from __future__ import annotations

from pathlib import Path

from gitbare.git_ops import relative_posix, run_git


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
        commit_result = run_git(
            repo_path, "ls-files", "--stage", "--", submodule_path, check=False
        )
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
