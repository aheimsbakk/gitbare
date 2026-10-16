"""Repository discovery: walk the scan root and find Git working copies."""

from __future__ import annotations

import os
from pathlib import Path

from gitbare.git_ops import is_git_repository, relative_posix


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
    return sorted(
        repositories,
        key=lambda item: (len(item.parts), relative_posix(item, scan_root)),
    )
