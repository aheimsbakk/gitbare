from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from io import StringIO
from pathlib import Path

import yaml

from gitbare.cli import print_stderr
from gitbare.git_ops import GitCommandError, run_command
from gitbare.logging_utils import OperationLogger

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def normalize_export(document: dict) -> list[dict]:
    """Reduce an export document to the fields a round trip must preserve."""
    entries = []
    for repo in document["repositories"]:
        entries.append(
            {
                "path": repo["path"],
                "primary_remote": repo["primary_remote"],
                "checkout_url": repo["checkout_url"],
                "checkout_transport": repo["checkout_transport"],
                "head": repo["head"],
                "remotes": repo["remotes"],
                "git_config": sorted(
                    (entry["key"], entry["value"]) for entry in repo["git_config"]
                ),
            }
        )
    return entries


def run(
    args: list[str], *, cwd: Path, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    env.setdefault("GIT_AUTHOR_NAME", "Test User")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Test User")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    return subprocess.run(
        [sys.executable, "-m", "gitbare", *args],
        cwd=str(cwd),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "Test User")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Test User")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )


class GitbareCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gitbare-tests-"))
        self.fixture_dir = Path(tempfile.mkdtemp(prefix="gitbare-fixtures-"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(self.fixture_dir, ignore_errors=True))

    def create_remote_repo(self, name: str) -> Path:
        remote_parent = self.fixture_dir / "remotes"
        remote_parent.mkdir(exist_ok=True)
        source = self.fixture_dir / f"{name}-source"
        source.mkdir()
        run_git(["init", "-b", "main"], cwd=source)
        (source / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        run_git(["add", "README.md"], cwd=source)
        run_git(["commit", "-m", "initial"], cwd=source)
        bare_remote = remote_parent / f"{name}.git"
        run_git(
            ["clone", "--bare", str(source), str(bare_remote)], cwd=self.fixture_dir
        )
        run_git(["remote", "add", "origin", str(bare_remote)], cwd=source)
        run_git(["push", "-u", "origin", "main"], cwd=source)
        return bare_remote

    def create_working_repo(self, path: Path, remote: Path) -> Path:
        run_git(["clone", str(remote), str(path)], cwd=self.temp_dir)
        run_git(["config", "--local", "user.name", "Local User"], cwd=path)
        run_git(
            ["config", "--local", "core.sshCommand", "ssh -i ~/.ssh/test-key"], cwd=path
        )
        return path

    def test_help_and_version(self) -> None:
        help_result = run(["--help"], cwd=self.temp_dir)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("gitbare > git.yml", help_result.stdout)
        version_result = run(["--version"], cwd=self.temp_dir)
        self.assertEqual(version_result.returncode, 0)
        self.assertRegex(version_result.stdout.strip(), r"\d+\.\d+\.\d+")

    def test_installed_console_entrypoint_launches(self) -> None:
        # Exercises the packaged console script, not `python -m gitbare`, so
        # the pyproject entrypoint declaration stays covered.
        command = shutil.which("gitbare")
        if command is None:
            self.skipTest("gitbare console script is not installed in this environment")
        help_result = subprocess.run(
            [command, "--help"],
            cwd=str(self.temp_dir),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("gitbare > git.yml", help_result.stdout)
        version_result = subprocess.run(
            [command, "--version"],
            cwd=str(self.temp_dir),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(version_result.returncode, 0)
        self.assertRegex(version_result.stdout.strip(), r"\d+\.\d+\.\d+")

    def test_operation_logger_streams_and_flushes_messages_immediately(self) -> None:
        class FlushTrackingStream(StringIO):
            def __init__(self) -> None:
                super().__init__()
                self.flush_count = 0

            def flush(self) -> None:
                self.flush_count += 1
                super().flush()

        stream = FlushTrackingStream()
        logger = OperationLogger(verbose=True, stream=stream)
        logger.info("warning")
        logger.progress(1, 2, "Inspecting repo")
        logger.detail("detail")
        self.assertEqual(
            stream.getvalue().splitlines(),
            ["warning", "[1/2] Inspecting repo", "detail"],
        )
        self.assertEqual(stream.flush_count, 3)

    def test_cli_print_stderr_flushes_immediately(self) -> None:
        class FlushTrackingStream(StringIO):
            def __init__(self) -> None:
                super().__init__()
                self.flush_count = 0

            def flush(self) -> None:
                self.flush_count += 1
                super().flush()

        stream = FlushTrackingStream()
        original_stderr = sys.stderr
        sys.stderr = stream
        try:
            print_stderr("error")
        finally:
            sys.stderr = original_stderr
        self.assertEqual(stream.getvalue(), "error\n")
        self.assertEqual(stream.flush_count, 1)

    def test_export_direct_child_repository_to_stdout(self) -> None:
        remote = self.create_remote_repo("alpha")
        working = self.create_working_repo(self.temp_dir / "alpha", remote)
        (working / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result = run([], cwd=self.temp_dir)
        self.assertEqual(result.returncode, 0)
        exported = yaml.safe_load(result.stdout)
        self.assertEqual(exported["schema_version"], 1)
        self.assertEqual([repo["path"] for repo in exported["repositories"]], ["alpha"])
        self.assertIn("Repository alpha is dirty", result.stderr)
        self.assertEqual(exported["repositories"][0]["checkout_transport"], "other")

    def test_recursive_export_detects_nested_repository(self) -> None:
        remote = self.create_remote_repo("nested")
        nested_parent = self.temp_dir / "team"
        nested_parent.mkdir()
        self.create_working_repo(nested_parent / "api", remote)
        shallow = run([], cwd=self.temp_dir)
        recursive = run(["--recursive"], cwd=self.temp_dir)
        self.assertEqual(yaml.safe_load(shallow.stdout)["repositories"], [])
        self.assertEqual(
            yaml.safe_load(recursive.stdout)["repositories"][0]["path"], "team/api"
        )

    def test_export_skips_current_directory_repository(self) -> None:
        run_git(["init", "-b", "main"], cwd=self.temp_dir)
        result = run([], cwd=self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(yaml.safe_load(result.stdout)["repositories"], [])

    def test_export_to_file(self) -> None:
        remote = self.create_remote_repo("file-export")
        self.create_working_repo(self.temp_dir / "repo", remote)
        output_path = self.temp_dir / "repos.yml"
        result = run(["--export", str(output_path)], cwd=self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(output_path.exists())
        exported = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        self.assertEqual(exported["repositories"][0]["path"], "repo")

    def test_export_excludes_protected_git_config_keys_from_backup(self) -> None:
        remote = self.create_remote_repo("protected-config")
        repo = self.create_working_repo(self.temp_dir / "repo", remote)
        run_git(["config", "--local", "core.repositoryformatversion", "0"], cwd=repo)
        run_git(["config", "--local", "core.bare", "false"], cwd=repo)
        run_git(["config", "--local", "core.worktree", str(repo)], cwd=repo)
        result = run([], cwd=self.temp_dir)
        self.assertEqual(result.returncode, 0)
        exported = yaml.safe_load(result.stdout)
        keys = [entry["key"] for entry in exported["repositories"][0]["git_config"]]
        self.assertNotIn("core.repositoryformatversion", keys)
        self.assertNotIn("core.bare", keys)
        self.assertNotIn("core.worktree", keys)

    def test_verbose_export_reports_decisions_to_stderr(self) -> None:
        remote = self.create_remote_repo("verbose-export")
        working = self.create_working_repo(self.temp_dir / "repo", remote)
        (working / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result = run(["--verbose", "--dry-run"], cwd=self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Starting export", result.stderr)
        self.assertIn(
            "Dry-run enabled: export will only plan and emit YAML", result.stderr
        )
        self.assertIn("[1/1] Inspecting repo", result.stderr)
        self.assertIn("Dirty untracked path in repo: dirty.txt", result.stderr)

    def test_verbose_export_reports_incrementing_progress(self) -> None:
        first_remote = self.create_remote_repo("first")
        second_remote = self.create_remote_repo("second")
        self.create_working_repo(self.temp_dir / "first", first_remote)
        self.create_working_repo(self.temp_dir / "second", second_remote)
        result = run(["--verbose"], cwd=self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("[1/2] Inspecting first", result.stderr)
        self.assertIn("[2/2] Inspecting second", result.stderr)

    def test_import_from_stdin_restores_repository(self) -> None:
        remote = self.create_remote_repo("importable")
        self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore"
        restore_root.mkdir()
        result = run([], cwd=restore_root, input_text=exported_text)
        self.assertEqual(result.returncode, 0)
        restored = restore_root / "source"
        self.assertTrue((restored / ".git").exists())
        remote_url = run_git(
            ["remote", "get-url", "origin"], cwd=restored
        ).stdout.strip()
        self.assertEqual(remote_url, str(remote))

    def test_import_from_file(self) -> None:
        remote = self.create_remote_repo("file-import")
        self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-file"
        restore_root.mkdir()
        import_file = self.temp_dir / "import.yml"
        import_file.write_text(exported_text, encoding="utf-8")
        result = run(["--import", str(import_file)], cwd=restore_root)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((restore_root / "source" / ".git").exists())

    def test_import_only_flags_are_rejected_in_export_mode(self) -> None:
        result = run(["--pull"], cwd=self.temp_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("import-only", result.stderr)

    def test_pull_updates_existing_compatible_repository(self) -> None:
        remote = self.create_remote_repo("pullable")
        source = self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-pull"
        restore_root.mkdir()
        first_import = run([], cwd=restore_root, input_text=exported_text)
        self.assertEqual(first_import.returncode, 0)
        (source / "README.md").write_text("# updated\n", encoding="utf-8")
        run_git(["add", "README.md"], cwd=source)
        run_git(["commit", "-m", "update"], cwd=source)
        run_git(["push", "origin", "main"], cwd=source)
        second_import = run(["--pull"], cwd=restore_root, input_text=exported_text)
        self.assertEqual(second_import.returncode, 0)
        restored_readme = (restore_root / "source" / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("updated", restored_readme)

    def test_duplicate_git_config_keys_fail_import(self) -> None:
        payload = textwrap.dedent(
            """
            schema_version: 1
            scan_root: .
            recursive: false
            repositories:
              - path: demo
                primary_remote: origin
                checkout_url: /tmp/missing.git
                checkout_transport: other
                head:
                  type: branch
                  name: main
                  commit: 0123456789abcdef0123456789abcdef01234567
                remotes: []
                git_config:
                  - key: user.name
                    value: one
                  - key: user.name
                    value: two
                custom_config: []
                submodules: []
                worktrees: []
            """
        ).strip()
        result = run([], cwd=self.temp_dir, input_text=payload)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Duplicate git config key", result.stderr)

    def test_submodule_and_worktree_round_trip_metadata(self) -> None:
        lib_remote = self.create_remote_repo("lib")
        app_remote = self.create_remote_repo("app")
        self.create_working_repo(self.temp_dir / "lib", lib_remote)
        app_working = self.create_working_repo(self.temp_dir / "app", app_remote)
        run_git(
            [
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(lib_remote),
                "vendor/lib",
            ],
            cwd=app_working,
        )
        run_git(["commit", "-am", "add submodule"], cwd=app_working)
        run_git(["push", "origin", "main"], cwd=app_working)
        worktree_path = self.temp_dir / "worktrees" / "app-hotfix"
        worktree_path.parent.mkdir()
        run_git(
            ["worktree", "add", "-b", "hotfix/urgent", str(worktree_path)],
            cwd=app_working,
        )
        exported = yaml.safe_load(run(["--recursive"], cwd=self.temp_dir).stdout)
        app_repo = next(
            repo for repo in exported["repositories"] if repo["path"] == "app"
        )
        self.assertEqual(app_repo["submodules"][0]["path"], "vendor/lib")
        self.assertEqual(app_repo["worktrees"][0]["path"], "worktrees/app-hotfix")
        self.assertTrue(
            all(
                repo["path"] != "worktrees/app-hotfix"
                for repo in exported["repositories"]
            )
        )

    def test_restore_worktrees_and_submodules(self) -> None:
        lib_remote = self.create_remote_repo("restore-lib")
        app_remote = self.create_remote_repo("restore-app")
        self.create_working_repo(self.temp_dir / "restore-lib", lib_remote)
        app_working = self.create_working_repo(
            self.temp_dir / "restore-app", app_remote
        )
        run_git(
            [
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(lib_remote),
                "vendor/lib",
            ],
            cwd=app_working,
        )
        run_git(["commit", "-am", "add submodule"], cwd=app_working)
        run_git(["push", "origin", "main"], cwd=app_working)
        worktree_path = self.temp_dir / "worktrees" / "restore-app-hotfix"
        worktree_path.parent.mkdir()
        run_git(
            ["worktree", "add", "-b", "hotfix/urgent", str(worktree_path)],
            cwd=app_working,
        )
        exported_text = run(["--recursive"], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-target"
        restore_root.mkdir()
        result = run(
            ["--restore-submodules", "--restore-worktrees"],
            cwd=restore_root,
            input_text=exported_text,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(
            (restore_root / "restore-app" / "vendor" / "lib" / ".git").exists()
        )
        self.assertTrue(
            (restore_root / "worktrees" / "restore-app-hotfix" / ".git").exists()
        )

    def test_verbose_import_reports_planned_and_restore_steps(self) -> None:
        remote = self.create_remote_repo("verbose-import")
        self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-verbose"
        restore_root.mkdir()
        dry_run_result = run(
            ["--verbose", "--dry-run"], cwd=restore_root, input_text=exported_text
        )
        self.assertEqual(dry_run_result.returncode, 0)
        self.assertIn("Starting import", dry_run_result.stderr)
        self.assertIn(
            "Dry-run enabled: import will only report planned actions",
            dry_run_result.stderr,
        )
        self.assertIn("[1/1] Planning restore for source", dry_run_result.stderr)
        self.assertIn("Would clone source", dry_run_result.stderr)
        result = run(["--verbose"], cwd=restore_root, input_text=exported_text)
        self.assertEqual(result.returncode, 0)
        self.assertIn("[1/1] Restoring source", result.stderr)
        self.assertIn("Cloning repository source", result.stderr)
        self.assertIn("Restoring HEAD state for source", result.stderr)
        self.assertIn("Completed restore for source", result.stderr)

    def test_verbose_import_reports_incrementing_progress(self) -> None:
        first_remote = self.create_remote_repo("import-first")
        second_remote = self.create_remote_repo("import-second")
        self.create_working_repo(self.temp_dir / "first", first_remote)
        self.create_working_repo(self.temp_dir / "second", second_remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-progress"
        restore_root.mkdir()
        result = run(
            ["--verbose", "--dry-run"], cwd=restore_root, input_text=exported_text
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("[1/2] Planning restore for first", result.stderr)
        self.assertIn("[2/2] Planning restore for second", result.stderr)

    def test_usage_errors_exit_with_code_1(self) -> None:
        pull_result = run(["--pull"], cwd=self.temp_dir)
        self.assertEqual(pull_result.returncode, 1)
        unknown_result = run(["--bogus-flag"], cwd=self.temp_dir)
        self.assertEqual(unknown_result.returncode, 1)

    def test_malformed_yaml_fails_with_clear_message(self) -> None:
        result = run([], cwd=self.temp_dir, input_text="not: [valid\n  yaml: {{{")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not valid YAML", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_required_fields_fail_import(self) -> None:
        payload = textwrap.dedent(
            """
            schema_version: 1
            scan_root: .
            recursive: false
            repositories:
              - checkout_url: /tmp/missing.git
            """
        ).strip()
        result = run([], cwd=self.temp_dir, input_text=payload)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required fields", result.stderr)

    def test_import_rejects_repository_path_that_escapes_restore_root(self) -> None:
        payload = textwrap.dedent(
            """
            schema_version: 1
            scan_root: .
            recursive: false
            repositories:
              - path: ../escaped
                primary_remote: origin
                checkout_url: /tmp/missing.git
                checkout_transport: other
                head:
                  type: branch
                  name: main
                  commit: 0123456789abcdef0123456789abcdef01234567
                remotes: []
                git_config: []
                custom_config: []
                submodules: []
                worktrees: []
            """
        ).strip()
        result = run([], cwd=self.temp_dir, input_text=payload)
        self.assertEqual(result.returncode, 1)
        self.assertIn("must stay inside the restore root", result.stderr)
        self.assertFalse((self.temp_dir.parent / "escaped").exists())

    def test_import_rejects_worktree_path_that_escapes_restore_root(self) -> None:
        payload = textwrap.dedent(
            """
            schema_version: 1
            scan_root: .
            recursive: false
            repositories:
              - path: demo
                primary_remote: origin
                checkout_url: /tmp/missing.git
                checkout_transport: other
                head:
                  type: branch
                  name: main
                  commit: 0123456789abcdef0123456789abcdef01234567
                remotes: []
                git_config: []
                custom_config: []
                submodules: []
                worktrees:
                  - path: ../escaped-worktree
                    commit: 0123456789abcdef0123456789abcdef01234567
            """
        ).strip()
        result = run([], cwd=self.temp_dir, input_text=payload)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Worktree path must stay inside the restore root", result.stderr)

    def test_dry_run_import_exits_3_when_action_would_fail(self) -> None:
        remote = self.create_remote_repo("dryrun-fail")
        self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-dryrun-fail"
        blocker = restore_root / "source"
        blocker.mkdir(parents=True)
        (blocker / "occupied.txt").write_text("x\n", encoding="utf-8")
        result = run(["--dry-run"], cwd=restore_root, input_text=exported_text)
        self.assertEqual(result.returncode, 3)
        self.assertIn("Would fail source", result.stderr)
        self.assertFalse((blocker / ".git").exists())

    def test_import_refuses_existing_compatible_repository_without_pull(self) -> None:
        remote = self.create_remote_repo("refuse-pull")
        self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-refuse"
        restore_root.mkdir()
        first_import = run([], cwd=restore_root, input_text=exported_text)
        self.assertEqual(first_import.returncode, 0)
        second_import = run([], cwd=restore_root, input_text=exported_text)
        self.assertEqual(second_import.returncode, 3)
        self.assertIn("without --pull", second_import.stderr)

    def test_import_fails_on_conflicting_existing_directory(self) -> None:
        remote = self.create_remote_repo("conflict-dir")
        self.create_working_repo(self.temp_dir / "source", remote)
        exported_text = run([], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-conflict"
        blocker = restore_root / "source"
        blocker.mkdir(parents=True)
        (blocker / "occupied.txt").write_text("x\n", encoding="utf-8")
        result = run([], cwd=restore_root, input_text=exported_text)
        self.assertEqual(result.returncode, 3)
        self.assertIn("incompatible", result.stderr)

    def test_import_does_not_restore_submodules_or_worktrees_by_default(self) -> None:
        lib_remote = self.create_remote_repo("default-lib")
        app_remote = self.create_remote_repo("default-app")
        self.create_working_repo(self.temp_dir / "default-lib", lib_remote)
        app_working = self.create_working_repo(
            self.temp_dir / "default-app", app_remote
        )
        run_git(
            [
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(lib_remote),
                "vendor/lib",
            ],
            cwd=app_working,
        )
        run_git(["commit", "-am", "add submodule"], cwd=app_working)
        run_git(["push", "origin", "main"], cwd=app_working)
        worktree_path = self.temp_dir / "worktrees" / "default-app-hotfix"
        worktree_path.parent.mkdir()
        run_git(
            ["worktree", "add", "-b", "hotfix/urgent", str(worktree_path)],
            cwd=app_working,
        )
        exported_text = run(["--recursive"], cwd=self.temp_dir).stdout
        restore_root = self.temp_dir / "restore-defaults"
        restore_root.mkdir()
        result = run([], cwd=restore_root, input_text=exported_text)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((restore_root / "default-app" / ".git").exists())
        self.assertFalse(
            (restore_root / "default-app" / "vendor" / "lib" / ".git").exists()
        )
        self.assertFalse((restore_root / "worktrees" / "default-app-hotfix").exists())

    def test_round_trip_export_import_reexport_matches(self) -> None:
        remote = self.create_remote_repo("roundtrip")
        working = self.create_working_repo(self.temp_dir / "source", remote)
        run_git(["config", "--local", "user.email", "local@example.com"], cwd=working)
        first_document = yaml.safe_load(run([], cwd=self.temp_dir).stdout)
        restore_root = self.temp_dir / "restore-roundtrip"
        restore_root.mkdir()
        import_result = run(
            [], cwd=restore_root, input_text=run([], cwd=self.temp_dir).stdout
        )
        self.assertEqual(import_result.returncode, 0)
        second_document = yaml.safe_load(run([], cwd=restore_root).stdout)
        self.assertEqual(
            normalize_export(first_document), normalize_export(second_document)
        )

    def test_export_captures_submodule_with_dotted_name(self) -> None:
        lib_remote = self.create_remote_repo("dotted-lib")
        app_remote = self.create_remote_repo("dotted-app")
        self.create_working_repo(self.temp_dir / "dotted-lib", lib_remote)
        app_working = self.create_working_repo(self.temp_dir / "dotted-app", app_remote)
        run_git(
            [
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "--name",
                "vendor.lib",
                str(lib_remote),
                "vendor/lib",
            ],
            cwd=app_working,
        )
        run_git(["commit", "-am", "add submodule"], cwd=app_working)
        run_git(["push", "origin", "main"], cwd=app_working)
        exported = yaml.safe_load(run(["--recursive"], cwd=self.temp_dir).stdout)
        app_repo = next(
            repo for repo in exported["repositories"] if repo["path"] == "dotted-app"
        )
        submodule = app_repo["submodules"][0]
        self.assertEqual(submodule["path"], "vendor/lib")
        self.assertEqual(submodule["url"], str(lib_remote))

    def test_export_captures_dirty_paths_with_spaces_and_unicode(self) -> None:
        remote = self.create_remote_repo("weirdpaths")
        working = self.create_working_repo(self.temp_dir / "weirdpaths", remote)
        (working / "weird name æøå.txt").write_text("x\n", encoding="utf-8")
        exported = yaml.safe_load(run([], cwd=self.temp_dir).stdout)
        self.assertEqual(
            exported["repositories"][0]["untracked_files"], ["weird name æøå.txt"]
        )

    def test_git_command_timeout_raises_error(self) -> None:
        with self.assertRaises(GitCommandError) as caught:
            run_command(["sleep", "5"], timeout=0.1)
        self.assertIn("timed out", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
