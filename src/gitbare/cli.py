from __future__ import annotations

import argparse
import io
import select
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from gitbare import __version__
from gitbare.exporter import dump_yaml, export_repositories
from gitbare.importer import import_repositories, parse_yaml_import


def get_version() -> str:
    try:
        return version("gitbare")
    except PackageNotFoundError:
        return __version__


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitbare",
        description="Export and restore local Git working copies as YAML.",
        epilog="Examples:\n  gitbare > git.yml\n  cat git.yml | gitbare\n  gitbare --import repo.yml\n  gitbare --export repo.yml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--import", dest="import_path", metavar="PATH|-", help="Read YAML from file or stdin")
    parser.add_argument("-e", "--export", dest="export_path", metavar="PATH|-", help="Write YAML to file or stdout")
    parser.add_argument("-r", "--recursive", action="store_true", help="Scan repositories recursively")
    parser.add_argument("--pull", action="store_true", help="Update compatible existing repositories during import")
    parser.add_argument("--dry-run", action="store_true", help="Plan actions without changing repositories")
    parser.add_argument("--restore-worktrees", action="store_true", help="Restore recorded linked worktrees during import")
    parser.add_argument("--restore-submodules", action="store_true", help="Restore recorded submodules during import")
    parser.add_argument("-v", "--verbose", action="store_true", help="Emit verbose logs to stderr")
    parser.add_argument("-V", "--version", action="version", version=get_version())
    return parser


def stdin_has_data(stream: io.TextIOBase) -> bool:
    if hasattr(stream, "isatty") and stream.isatty():
        return False
    buffer = getattr(stream, "buffer", None)
    if buffer is not None and hasattr(buffer, "peek"):
        try:
            return bool(buffer.peek(1))
        except Exception:
            pass
    try:
        ready, _, _ = select.select([stream], [], [], 0)
        return bool(ready)
    except Exception:
        return False


def detect_mode(args: argparse.Namespace, stdin: io.TextIOBase) -> str:
    if args.import_path:
        return "import"
    if args.export_path:
        return "export"
    if stdin_has_data(stdin):
        return "import"
    return "export"


def read_import_text(args: argparse.Namespace, stdin: io.TextIOBase) -> str:
    if args.import_path and args.import_path != "-":
        return Path(args.import_path).read_text(encoding="utf-8")
    return stdin.read()


def write_export_text(args: argparse.Namespace, stdout: io.TextIOBase, content: str) -> None:
    if args.export_path and args.export_path != "-":
        Path(args.export_path).write_text(content, encoding="utf-8")
        return
    stdout.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    mode = detect_mode(args, sys.stdin)
    if mode == "export" and (args.pull or args.restore_worktrees or args.restore_submodules):
        parser.error("--pull, --restore-worktrees, and --restore-submodules are import-only options")
    if mode == "import":
        try:
            input_text = read_import_text(args, sys.stdin)
            parse_yaml_import(input_text)
            messages, failed = import_repositories(
                Path.cwd(),
                input_text,
                pull=args.pull,
                dry_run=args.dry_run,
                restore_submodules_flag=args.restore_submodules,
                restore_worktrees_flag=args.restore_worktrees,
                verbose=args.verbose,
            )
        except (OSError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
        for message in messages:
            print(message, file=sys.stderr)
        return 3 if failed else 0
    data, warnings = export_repositories(Path.cwd(), args.recursive, args.verbose, args.dry_run)
    for warning in warnings:
        print(warning, file=sys.stderr)
    write_export_text(args, sys.stdout, dump_yaml(data))
    return 0
