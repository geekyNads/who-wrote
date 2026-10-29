"""Fixture helper: builds tiny synthetic git repos programmatically (no nested .git committed)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

HUMAN = ("Pat Dev", "pat@example.com")

# (message, {path: content}, (author name, email))
CommitSpec = tuple[str, dict[str, str], tuple[str, str]]
MakeRepo = Callable[..., Path]


@pytest.fixture
def make_repo(tmp_path: Path) -> MakeRepo:
    def build(commits: list[CommitSpec], branches: tuple[str, ...] = (), day_step: int = 1) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        g = ["git", "-C", str(repo)]
        subprocess.run([*g, "init", "-q", "-b", "main"], check=True)
        for i, (msg, files, (name, email)) in enumerate(commits):
            for rel, text in files.items():
                (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                (repo / rel).write_text(text)
            date = f"{1_700_000_000 + i * day_step * 86400} +0000"
            env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
                   "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
                   "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
            subprocess.run([*g, "add", "-A"], check=True)
            subprocess.run([*g, "commit", "-q", "--allow-empty", "-m", msg], check=True, env=env)
        for b in branches:
            subprocess.run([*g, "branch", b], check=True)
        return repo

    return build
