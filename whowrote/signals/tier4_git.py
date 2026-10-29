"""Tier 4: git behavior — message formatting, commit size, history shape. Weak signals.

Untuned seeds from agent-fingerprints/fingerprints.md (2026-10-29). Tune against the eval set.
"""

from __future__ import annotations

import re

from whowrote.signals.base import AI_AGENTS, Detector, RepoData, Signal, signals

_CONVENTIONAL = re.compile(r"^(feat|fix|chore|docs|refactor|test|style|perf|build|ci)(\(.+\))?!?: ")
_BULLET = re.compile(r"^\s*[-*] \S", re.M)
_LAZY = re.compile(r"^(wip|fix|fixes|fixed|asdf|update|updates|stuff|changes|tmp|minor|test|\.+)$",
                   re.I)
LARGE_COMMIT_FILES = 20
_DAY = 86400


def detect_git_behavior(data: RepoData) -> list[Signal]:
    commits = [c for c in data.history.commits if not c.subject.startswith("Merge ")]
    out: list[Signal] = []
    if len(commits) >= 10:
        conv = [c for c in commits if _CONVENTIONAL.match(c.subject)]
        bulleted = [c for c in conv if _BULLET.search(c.message)]
        if len(conv) >= 0.8 * len(commits) and len(bulleted) >= 0.5 * len(conv):
            out += signals("tier4.conventional_bulleted", AI_AGENTS, 1,
                           [f"{len(conv)}/{len(commits)} conventional, {len(bulleted)} bulleted"])

    big = [c for c in commits if len(c.files) >= LARGE_COMMIT_FILES]
    if big:
        out += signals("tier4.large_feature_commits", AI_AGENTS, len(big),
                       (f"commit {c.sha[:8]}: {len(c.files)} files, {c.subject}" for c in big))

    lazy = [c for c in commits if _LAZY.match(c.subject)]
    if lazy:
        out += signals("tier4.lazy_messages", ("human_unknown",), len(lazy),
                       (f"commit {c.sha[:8]}: {c.subject!r}" for c in lazy))

    if len(commits) >= 100:
        span = (max(c.timestamp for c in commits) - min(c.timestamp for c in commits)) // _DAY
        if span >= 365:
            out += signals("tier4.long_irregular_history", ("human_unknown",), 1,
                           [f"{len(commits)} commits over {span} days"])
    return out


DETECTORS: list[Detector] = [detect_git_behavior]
