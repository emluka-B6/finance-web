#!/usr/bin/env python3
"""Remove a sibling Git worktree created for isolated testing."""

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove a sibling Git worktree created for isolated testing."
    )
    parser.add_argument(
        "name",
        help="Worktree directory name, located next to the current repository",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove the worktree even when it contains uncommitted changes",
    )
    return parser.parse_args()


def get_registered_worktrees() -> set[Path]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    }


def main() -> int:
    args = parse_arguments()
    if Path(args.name).name != args.name or args.name in {".", ".."}:
        print("Error: name must be a single directory name.", file=sys.stderr)
        return 1

    worktree_path = (PROJECT_ROOT.parent / args.name).resolve()
    try:
        registered_worktrees = get_registered_worktrees()
    except subprocess.CalledProcessError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if worktree_path == PROJECT_ROOT:
        print("Error: refusing to remove the primary worktree.", file=sys.stderr)
        return 1
    if worktree_path not in registered_worktrees:
        print(f"Error: not a registered sibling worktree: {worktree_path}", file=sys.stderr)
        return 1

    command = ["git", "worktree", "remove"]
    if args.force:
        command.append("--force")
    command.append(str(worktree_path))

    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as error:
        print(
            "Error: worktree was not removed. Commit or discard its changes, or rerun "
            "with --force to discard them.",
            file=sys.stderr,
        )
        return error.returncode or 1

    print(f"Removed test worktree: {worktree_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())