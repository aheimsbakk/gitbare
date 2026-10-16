from __future__ import annotations

import argparse
import select
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NoReturn, TextIO

from gitbare import __version__
from gitbare.exporter import dump_yaml, export_repositories
from gitbare.importer import import_repositories


def print_stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def get_version() -> str:
    try:
        return version("gitbare")
    except PackageNotFoundError:
        return __version__


class CliArgumentParser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors; the CLI contract requires exit 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"gitbare: error: {message}\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(
        prog="gitbare",
        description="Export and restore local Git working copies as YAML.",
        epilog="Examples:\n  gitbare > git.yml\n  cat git.yml | gitbare\n  gitbare --import repo.yml\n  gitbare --export repo.yml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--import",
        dest="import_path",
        metavar="PATH|-",
        help="Read YAML from file or stdin",
    )
    parser.add_argument(
        "-e",
        "--export",
        dest="export_path",
        metavar="PATH|-",
        help="Write YAML to file or stdout",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Scan repositories recursively"
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Update compatible existing repositories during import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan actions without changing repositories",
    )
    parser.add_argument(
        "--restore-worktrees",
        action="store_true",
        help="Restore recorded linked worktrees during import",
    )
    parser.add_argument(
        "--restore-submodules",
        action="store_true",
        help="Restore recorded submodules during import",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Emit verbose logs to stderr"
    )
    parser.add_argument("-V", "--version", action="version", version=get_version())
    return parser


def _peek_has_data(buffer: object) -> bool | None:
    peek = getattr(buffer, "peek", None)
    if peek is None:
        return None
    try:
        return bool(peek(1))
    except (OSError, ValueError):
        # peek is unsupported on some stream types; caller falls back to select.
        return None


def stdin_has_data(stream: TextIO) -> bool:
    if hasattr(stream, "isatty") and stream.isatty():
        return False
    peeked = _peek_has_data(getattr(stream, "buffer", None))
    if peeked is not None:
        return peeked
    try:
        ready, _, _ = select.select([stream], [], [], 0)
        return bool(ready)
    except OSError:
        # select needs a real file descriptor; assume no piped YAML.
        return False


def detect_mode(args: argparse.Namespace, stdin: TextIO) -> str:
    if args.import_path:
        return "import"
    if args.export_path:
        return "export"
    if stdin_has_data(stdin):
        return "import"
    return "export"


def read_import_text(args: argparse.Namespace, stdin: TextIO) -> str:
    if args.import_path and args.import_path != "-":
        return Path(args.import_path).read_text(encoding="utf-8")
    return stdin.read()


def write_export_text(args: argparse.Namespace, stdout: TextIO, content: str) -> None:
    if args.export_path and args.export_path != "-":
        Path(args.export_path).write_text(content, encoding="utf-8")
        return
    stdout.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    mode = detect_mode(args, sys.stdin)
    if mode == "export" and (
        args.pull or args.restore_worktrees or args.restore_submodules
    ):
        parser.error(
            "--pull, --restore-worktrees, and --restore-submodules are import-only options"
        )
    if mode == "import":
        try:
            input_text = read_import_text(args, sys.stdin)
            failed = import_repositories(
                Path.cwd(),
                input_text,
                pull=args.pull,
                dry_run=args.dry_run,
                restore_submodules_flag=args.restore_submodules,
                restore_worktrees_flag=args.restore_worktrees,
                verbose=args.verbose,
            )
        except (OSError, ValueError, TypeError) as error:
            print_stderr(str(error))
            return 1
        return 3 if failed else 0
    data = export_repositories(Path.cwd(), args.recursive, args.verbose, args.dry_run)
    write_export_text(args, sys.stdout, dump_yaml(data))
    return 0
