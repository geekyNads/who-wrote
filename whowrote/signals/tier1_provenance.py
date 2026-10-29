"""Tier 1: commit trailers, bot authors, agent branch names. Near-decisive.

Fingerprints from agent-fingerprints/fingerprints.md, unverified starting points as of 2026-10-29.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from whowrote.ingest.git_history import Commit
from whowrote.signals.base import Detector, RepoData, Signal, signals

_I, _IM = re.I, re.I | re.M


def _msg(c: Commit) -> str:
    return c.message


def _ids(c: Commit) -> str:
    return c.identities


# (signal id, agent, pattern, commit field it's matched against)
COMMIT_RULES: list[tuple[str, str, re.Pattern[str], Callable[[Commit], str]]] = [
    ("tier1.claude_coauthor_trailer", "claude_code",
     re.compile(r"^co-authored-by:\s*claude\b.*<noreply@anthropic\.com>", _IM), _msg),
    ("tier1.claude_generated_with", "claude_code",
     re.compile(r"generated with \[claude code\]", _I), _msg),
    ("tier1.cursor_coauthor_trailer", "cursor",
     re.compile(r"^co-authored-by:.*<cursoragent@cursor\.com>", _IM), _msg),
    ("tier1.copilot_coauthor_trailer", "copilot",
     re.compile(r"^co-authored-by:\s*copilot\b", _IM), _msg),
    ("tier1.aider_message_prefix", "aider", re.compile(r"^aider: ", _I), _msg),
    ("tier1.cursor_bot_author", "cursor", re.compile(r"cursor ?agent|@cursor\.com>", _I), _ids),
    ("tier1.copilot_bot_author", "copilot",
     re.compile(r"copilot-swe-agent|^copilot <|\+copilot@users\.noreply", _IM), _ids),
    ("tier1.codex_bot_author", "codex", re.compile(r"codex[\w-]*\[bot\]|chatgpt-codex", _I), _ids),
    ("tier1.devin_bot_author", "devin", re.compile(r"devin-ai-integration", _I), _ids),
    ("tier1.aider_author_suffix", "aider", re.compile(r"\(aider\) <", _I), _ids),
    ("tier1.jules_bot_author", "gemini_cli", re.compile(r"google-labs-jules", _I), _ids),
]

BRANCH_PREFIXES = {"claude": "claude_code", "cursor": "cursor", "copilot": "copilot",
                   "codex": "codex", "devin": "devin"}
# Merged agent branches survive in merge subjects even after the branch is deleted.
_MERGE_FROM = re.compile(r"^Merge (?:pull request #\d+ from [\w.-]+/|branch ')([\w.-]+)/")


def detect_commit_rules(data: RepoData) -> list[Signal]:
    out: list[Signal] = []
    attributed: set[str] = set()
    for sid, agent, rx, field in COMMIT_RULES:
        hits = [c for c in data.history.commits if rx.search(field(c))]
        if hits:
            attributed |= {c.sha for c in hits}
            ev = (f"commit {c.sha[:8]}: {c.subject}" for c in hits)
            out += signals(sid, (agent,), len(hits), ev)
    # Share correction: 1 trailer in 300 commits shouldn't mean "agent wrote it". Only fires when
    # some commits have provenance — absence alone is weak evidence (trailers get stripped).
    rest = [c for c in data.history.commits if c.sha not in attributed]
    if attributed and rest:
        out += signals("tier1.unattributed_commits", ("human_unknown",), len(rest),
                       [f"{len(rest)}/{len(data.history.commits)} commits lack agent provenance"])
    return out


def detect_branches(data: RepoData) -> list[Signal]:
    found: dict[str, list[str]] = {}
    for b in data.history.branches:
        prefix = b.split("/", 1)[0].lower()
        if "/" in b and prefix in BRANCH_PREFIXES:
            found.setdefault(prefix, []).append(f"branch {b}")
    for c in data.history.commits:
        if (m := _MERGE_FROM.match(c.subject)) and m[1].lower() in BRANCH_PREFIXES:
            found.setdefault(m[1].lower(), []).append(f"commit {c.sha[:8]}: {c.subject}")
    out: list[Signal] = []
    for prefix, ev in found.items():
        agent = BRANCH_PREFIXES[prefix]
        out += signals(f"tier1.{agent}_branch_prefix", (agent,), len(ev), ev)
    return out


DETECTORS: list[Detector] = [detect_commit_rules, detect_branches]
