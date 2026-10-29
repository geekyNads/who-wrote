"""Open a local repo or shallow-clone a GitHub URL. Read-only: never runs repo hooks or code."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

GITHUB_URL = re.compile(
    r"^(?:https?://)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/(.+?))?/?$"
)

# No hooks, no credential prompts, no LFS downloads.
_SAFE = ("-c", "core.hooksPath=/dev/null")


def _env() -> dict[str, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    if token := os.environ.get("GITHUB_TOKEN"):
        # Passed via env config so the token never shows up in argv / ps.
        auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env |= {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {auth}",
        }
    return env


def _run(*args: str) -> str:
    return subprocess.run(
        ["git", *_SAFE, *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    ).stdout


def git(repo: Path, *args: str) -> str:
    return _run("-C", str(repo), *args)


def _clone(url: str, dest: Path, history: int, branch: str | None, rev: str | None) -> None:
    if rev:  # snapshot at a past commit: fetch just that commit's history, not today's branches
        _run("clone", "-q", "--filter=blob:none", "--depth=1", "--no-checkout", url, str(dest))
        git(dest, "fetch", "-q", "--filter=blob:none", f"--depth={history}", "origin", rev)
        git(dest, "-c", "advice.detachedHead=false", "checkout", "-q", rev)
        return
    args = ["clone", "-q", "--filter=blob:none", "--no-single-branch", f"--depth={history}"]
    if branch:
        args += ["--branch", branch]
    _run(*args, url, str(dest))


@contextmanager
def open_repo(target: str, history: int = 500, rev: str | None = None,
              cache: Path | None = None) -> Iterator[Path]:
    """Yield the repo's top-level dir.

    GitHub URLs are cloned to a temp dir (removed after), or into `cache` (kept and reused).
    `rev` checks out a past commit; local repos must already be at the revision you want.
    """
    m = GITHUB_URL.match(target)
    if not m:
        path = Path(target).expanduser().resolve()
        yield Path(git(path, "rev-parse", "--show-toplevel").strip())
        return
    owner, name, branch = m.groups()
    url = f"https://github.com/{owner}/{name}.git"
    if cache is not None:
        dest = cache / (f"{owner}__{name}" + (f"@{rev[:12]}" if rev else ""))
        if not (dest / ".git").is_dir():
            shutil.rmtree(dest, ignore_errors=True)  # leftover from an interrupted clone
            cache.mkdir(parents=True, exist_ok=True)
            try:
                _clone(url, dest, history, branch, rev)
            except BaseException:
                shutil.rmtree(dest, ignore_errors=True)
                raise
        yield dest
        return
    tmp = Path(tempfile.mkdtemp(prefix="whowrote-"))
    try:
        _clone(url, tmp / "repo", history, branch, rev)
        yield tmp / "repo"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
