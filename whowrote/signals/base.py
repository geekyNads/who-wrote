"""Signal contract shared by every detector."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import islice

from whowrote.ingest.files import RepoFiles
from whowrote.ingest.git_history import GitHistory
from whowrote.scoring.weights import strength

AGENTS = ("claude_code", "cursor", "copilot", "codex", "devin", "aider", "windsurf", "cline",
          "gemini_cli", "human_unknown")
AI_AGENTS = AGENTS[:-1]
MAX_EVIDENCE = 5


@dataclass(frozen=True)
class Signal:
    id: str
    tier: int
    agent: str
    strength: float
    count: int
    evidence: list[str]


@dataclass(frozen=True)
class RepoData:
    history: GitHistory
    files: RepoFiles


Detector = Callable[[RepoData], list[Signal]]


def signals(sid: str, agents: tuple[str, ...], count: int, evidence: Iterable[str]) -> list[Signal]:
    """One Signal per agent; a signal shared by n agents gives each strength / n."""
    ev = list(islice(evidence, MAX_EVIDENCE))
    w = strength(sid) / len(agents)
    return [Signal(sid, int(sid[4]), a, w, count, ev) for a in agents]
