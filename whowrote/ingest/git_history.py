"""Commits, trailers, authors, branches, tags — parsed from one `git log` call."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from whowrote.ingest.repo import git

_REC, _FLD = "\x1e", "\x1f"
_FORMAT = _REC + _FLD.join(["%H", "%an", "%ae", "%cn", "%ce", "%at", "%B"]) + _FLD
_TRAILER = re.compile(r"^([A-Za-z][\w-]*):\s*(.+)$")


@dataclass(frozen=True)
class Commit:
    sha: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    timestamp: int
    message: str
    files: tuple[str, ...] = ()  # paths changed

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0].strip()

    @property
    def identities(self) -> str:
        """Author and committer as `name <email>` lines, for bot-author matching."""
        return (
            f"{self.author_name} <{self.author_email}>\n"
            f"{self.committer_name} <{self.committer_email}>"
        )

    @property
    def trailers(self) -> list[tuple[str, str]]:
        paras = self.message.strip().split("\n\n")
        if len(paras) < 2:
            return []
        return [(m[1], m[2]) for line in paras[-1].splitlines() if (m := _TRAILER.match(line))]


@dataclass(frozen=True)
class GitHistory:
    commits: tuple[Commit, ...]
    branches: tuple[str, ...]  # local + remote, remote prefix stripped
    tags: tuple[str, ...]


def parse_log(raw: str) -> tuple[Commit, ...]:
    commits = []
    for rec in raw.split(_REC)[1:]:
        sha, an, ae, cn, ce, ts, msg, names = rec.split(_FLD, 7)
        commits.append(Commit(sha, an, ae, cn, ce, int(ts), msg.strip(),
                              tuple(n.strip() for n in names.split("\0") if n.strip())))
    return tuple(commits)


def load_history(repo: Path, limit: int = 500, rev: str | None = None) -> GitHistory:
    """All refs' history, or only `rev`'s ancestry (then branches/tags are skipped: they're from
    after the snapshot and would leak e.g. later claude/ branches into a pre-2021 baseline)."""
    refs_args = [rev] if rev else ["--branches", "--remotes", "--tags"]
    # --name-only needs trees only; --numstat would lazily fetch every blob in a blobless clone.
    raw = git(repo, "log", *refs_args, f"-n{limit}", "-z", "--name-only", f"--format={_FORMAT}")
    if rev:
        return GitHistory(parse_log(raw), (), ())
    branches = set()
    refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    for ref in refs.split():
        if ref.startswith("refs/heads/"):
            branches.add(ref.removeprefix("refs/heads/"))
        elif not ref.endswith("/HEAD"):
            branches.add(ref.split("/", 3)[3])  # refs/remotes/<remote>/<branch>
    tags = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/tags").split()
    return GitHistory(parse_log(raw), tuple(sorted(branches)), tuple(tags))
