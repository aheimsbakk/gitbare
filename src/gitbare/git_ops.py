from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable


class GitCommandError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stderr: str):
        self.args_list = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(stderr or f"git command failed: {' '.join(args)}")


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise GitCommandError(args, completed.returncode, completed.stderr.strip())
    return completed


def run_git(
    repo_path: Path,
    *git_args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *git_args], cwd=repo_path, check=check, input_text=input_text)


def is_git_repository(path: Path) -> bool:
    return (path / ".git").is_dir() or (path / ".git").is_file()


def classify_transport(url: str) -> str:
    if url.startswith("git@") or url.startswith("ssh://"):
        return "ssh"
    if url.startswith("https://"):
        return "https"
    return "other"


def is_clonable_source(url: str) -> bool:
    if not url:
        return False
    if url.startswith(("git@", "ssh://", "https://", "file://")):
        return True
    return True if os.path.sep in url or url.startswith(".") else False


def relative_posix(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path, base)).as_posix()


def parse_null_config(output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for item in output.split("\0"):
        if not item:
            continue
        key, _, value = item.partition("\n")
        entries.append({"key": key, "value": value})
    return entries


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})
