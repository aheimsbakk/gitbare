"""Input validation for imported YAML snapshots.

Schema checks live here, apart from restore logic, so `importer.py` stays
focused on applying changes. Every failure raises `ValueError` with a
plain-language message naming the offending field or path.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REQUIRED_REPO_KEYS = ("path", "primary_remote", "checkout_url", "head")


def parse_yaml_import(text: str) -> dict[str, object]:
    """Load snapshot text and enforce the schema-version-1 envelope."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError(f"Input is not valid YAML: {error}") from error
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or not isinstance(data.get("repositories"), list)
    ):
        raise ValueError("Input must be gitbare schema_version 1 YAML")
    return data


def ensure_relative_path(path_value: str, kind: str) -> Path:
    """Reject stored paths that could escape the restore root.

    Absolute paths and `..` segments are refused so a hand-edited snapshot
    cannot clone or write outside the destination directory.
    """
    path = Path(path_value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{kind} path must stay inside the restore root: {path_value}")
    return path


def validate_git_config(entries: list[dict[str, str]]) -> None:
    seen: set[str] = set()
    for entry in entries:
        key = entry["key"]
        if key in seen:
            raise ValueError(f"Duplicate git config key in backup data: {key}")
        seen.add(key)


def validate_import_data(data: dict[str, object]) -> None:
    """Check every repository entry before any restore step runs."""
    repositories = data.get("repositories", [])
    if not isinstance(repositories, list):
        raise TypeError("repositories must be a list")
    for repo_data in repositories:
        if not isinstance(repo_data, dict):
            raise TypeError("Each repository entry must be a mapping")
        missing = [key for key in REQUIRED_REPO_KEYS if key not in repo_data]
        if missing:
            raise ValueError(
                f"Repository entry is missing required fields: {', '.join(missing)}"
            )
        ensure_relative_path(str(repo_data["path"]), "Repository")
        _validate_head(repo_data)
        _validate_remotes(repo_data)
        _validate_nested_entries(repo_data)
        _validate_git_config_entries(repo_data)


def _validate_head(repo_data: dict[str, object]) -> None:
    head = repo_data["head"]
    if not isinstance(head, dict) or head.get("type") not in {"branch", "detached"}:
        raise ValueError(f"Repository {repo_data['path']} has an invalid head entry")
    if "commit" not in head:
        raise ValueError(f"Repository {repo_data['path']} head entry requires a commit")
    if head.get("type") == "branch" and not head.get("name"):
        raise ValueError(
            f"Repository {repo_data['path']} head of type branch requires a name"
        )


def _validate_remotes(repo_data: dict[str, object]) -> None:
    remotes = repo_data.get("remotes", [])
    if not isinstance(remotes, list):
        raise TypeError(f"Repository {repo_data['path']} remotes must be a list")
    for remote in remotes:
        if not isinstance(remote, dict) or not {"name", "fetch_url", "push_url"} <= set(
            remote
        ):
            raise ValueError(
                f"Repository {repo_data['path']} has a remote entry without "
                "name, fetch_url, and push_url"
            )


def _validate_nested_entries(repo_data: dict[str, object]) -> None:
    for field_name, kind in (("submodules", "Submodule"), ("worktrees", "Worktree")):
        entries = repo_data.get(field_name, [])
        if not isinstance(entries, list):
            raise TypeError(
                f"Repository {repo_data['path']} {field_name} must be a list"
            )
        for entry in entries:
            if not isinstance(entry, dict) or "path" not in entry:
                raise ValueError(
                    f"Repository {repo_data['path']} has a {field_name[:-1]} "
                    "entry without a path"
                )
            ensure_relative_path(str(entry["path"]), kind)


def _validate_git_config_entries(repo_data: dict[str, object]) -> None:
    entries = repo_data.get("git_config", [])
    if not isinstance(entries, list):
        raise TypeError(f"Repository {repo_data['path']} git_config must be a list")
    for entry in entries:
        if not isinstance(entry, dict) or "key" not in entry or "value" not in entry:
            raise ValueError(
                f"Repository {repo_data['path']} has a git_config entry "
                "without key and value"
            )
    validate_git_config(entries)
