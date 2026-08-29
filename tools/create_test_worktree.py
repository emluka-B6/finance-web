#!/usr/bin/env python3
"""Create an isolated Git worktree with a copy of the development database."""

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = Path("server/instance/sqlite_alchemy.db")


def run_git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True)


def copy_sqlite_database(source: Path, destination: Path) -> None:
    """Create a consistent SQLite copy, including changes not yet checkpointed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a sibling Git worktree at REVISION with an isolated copy of "
            "the current SQLite application database."
        )
    )
    parser.add_argument("revision", help="Git branch, tag, or commit to check out")
    parser.add_argument(
        "name",
        help="Worktree directory name, created next to the current repository",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="Database path relative to the project root (default: %(default)s)",
    )
    parser.add_argument(
        "--no-database-copy",
        action="store_true",
        help="Create only the worktree; do not copy the SQLite database",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    source_database = (PROJECT_ROOT / args.database).resolve()
    worktree_path = PROJECT_ROOT.parent / args.name

    if worktree_path.exists():
        print(f"Error: worktree path already exists: {worktree_path}", file=sys.stderr)
        return 1
    if not args.no_database_copy and not source_database.is_file():
        print(f"Error: database does not exist: {source_database}", file=sys.stderr)
        return 1

    try:
        run_git("worktree", "add", "--detach", str(worktree_path), args.revision)
        if not args.no_database_copy:
            relative_database = source_database.relative_to(PROJECT_ROOT)
            copy_sqlite_database(source_database, worktree_path / relative_database)
    except (subprocess.CalledProcessError, OSError, sqlite3.Error, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        if worktree_path.exists():
            run_git("worktree", "remove", "--force", str(worktree_path))
        return 1

    print(f"Created isolated worktree: {worktree_path}")
    if not args.no_database_copy:
        print(f"Copied database: {source_database} -> {worktree_path / relative_database}")
    print("Run migrations or destructive tests only inside this worktree.")
    print(f"Remove it when finished: git worktree remove {worktree_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())