"""Tracked files: the full path list (for tier 2 config) and filtered text contents (tier 3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from whowrote.ingest.repo import git

SKIP_DIRS = {"node_modules", "vendor", "dist", "build", ".next", "target", "__pycache__",
             "venv", ".venv", "third_party"}
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock",
             "uv.lock", "Gemfile.lock", "composer.lock", "go.sum"}
MAX_BYTES = 1_000_000
# ponytail: hard cap on files read; sample by language if big repos lose signal.
MAX_FILES = 3000

LANGS = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rs": "rust", ".java": "java",
    ".kt": "kotlin", ".swift": "swift", ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".sh": "shell", ".md": "markdown",
}


@dataclass(frozen=True)
class RepoFiles:
    tracked: tuple[str, ...]  # every tracked path, dotfiles included
    texts: Mapping[str, str]  # path -> contents, filtered for style analysis

    def lang(self, path: str) -> str | None:
        return LANGS.get(PurePosixPath(path).suffix.lower())


def wanted(path: str) -> bool:
    p = PurePosixPath(path)
    return (
        p.suffix.lower() in LANGS
        and p.name not in LOCKFILES
        and ".min." not in p.name
        and not SKIP_DIRS.intersection(p.parts[:-1])
    )


def load_files(repo: Path) -> RepoFiles:
    tracked = tuple(p for p in git(repo, "ls-files", "-z").split("\0") if p)
    texts: dict[str, str] = {}
    for rel in tracked:
        if len(texts) >= MAX_FILES:
            break
        f = repo / rel
        # Symlinks could point outside the repo; never follow them.
        if not wanted(rel) or f.is_symlink() or not f.is_file() or f.stat().st_size > MAX_BYTES:
            continue
        data = f.read_bytes()
        if b"\0" not in data[:8192]:
            texts[rel] = data.decode("utf-8", errors="replace")
    return RepoFiles(tracked, texts)
