"""`whowrote <path|github-url> [--json] [--verbose] [--history N]`"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from whowrote.ingest.files import load_files
from whowrote.ingest.git_history import load_history
from whowrote.ingest.repo import open_repo
from whowrote.report.json_out import to_json
from whowrote.report.terminal import render
from whowrote.scoring.combine import Result, combine
from whowrote.signals import collect
from whowrote.signals.base import RepoData, Signal


def gather(target: str, history: int = 500, rev: str | None = None,
           cache: Path | None = None) -> tuple[list[Signal], dict[str, Any]]:
    """Ingest + run all detectors. Separate from scoring so eval can mask tiers afterwards."""
    with open_repo(target, history, rev, cache) as repo:
        data = RepoData(load_history(repo, history, rev), load_files(repo))
    meta = {"target": target, "commits": len(data.history.commits),
            "files": len(data.files.texts)}
    return collect(data), meta


def analyze(target: str, history: int = 500) -> tuple[Result, dict[str, Any]]:
    sigs, meta = gather(target, history)
    return combine(sigs), meta


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="whowrote", description=__doc__)
    p.add_argument("target", help="local repo path or https://github.com/owner/repo[/tree/branch]")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--verbose", "-v", action="store_true", help="show all evidence")
    p.add_argument("--history", type=int, default=500, help="max commits to read (default 500)")
    args = p.parse_args(argv)
    try:
        result, meta = analyze(args.target, args.history)
    except subprocess.CalledProcessError as e:
        print(f"whowrote: git failed: {(e.stderr or '').strip() or e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"whowrote: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(to_json(result, meta))
    else:
        render(result, meta, args.verbose)
    return 0


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))
