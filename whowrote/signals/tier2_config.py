"""Tier 2: agent config files. Proves the tool was configured, not that it wrote the code.

Paths from agent-fingerprints/fingerprints.md, unverified starting points as of 2026-10-29.
"""

from __future__ import annotations

import re

from whowrote.signals.base import Detector, RepoData, Signal, signals

# (signal id, agents that read it, path pattern). Shared files split credit across agents.
RULES: list[tuple[str, tuple[str, ...], re.Pattern[str]]] = [
    (sid, agents, re.compile(rx, re.I)) for sid, agents, rx in [
        ("tier2.claude_config", ("claude_code",), r"(^|/)CLAUDE(\.local)?\.md$|^\.claude/"),
        ("tier2.cursor_config", ("cursor",), r"^\.cursorrules$|^\.cursorignore$|^\.cursor/"),
        ("tier2.copilot_config", ("copilot",),
         r"^\.github/(copilot-instructions\.md$|instructions/.+\.instructions\.md$|prompts/)"),
        ("tier2.agents_md", ("codex", "cursor", "gemini_cli"), r"(^|/)AGENTS\.md$"),
        ("tier2.codex_config", ("codex",), r"^\.codex/"),
        ("tier2.devin_config", ("devin",), r"^\.devin/"),
        ("tier2.aider_config", ("aider",), r"^\.aider"),
        ("tier2.windsurf_config", ("windsurf",),
         r"^\.windsurfrules$|^\.windsurf/|^\.codeiumignore$"),
        ("tier2.cline_config", ("cline",),
         r"^\.clinerules(/|$)|(^|/)memory-bank/(activeContext|progress)\.md$|^\.roo/|^\.roomodes$"),
        ("tier2.gemini_config", ("gemini_cli",), r"(^|/)GEMINI\.md$|^\.gemini/"),
    ]
]


def detect_config_files(data: RepoData) -> list[Signal]:
    out: list[Signal] = []
    for sid, agents, rx in RULES:
        matches = [(p, m[0]) for p in data.files.tracked if (m := rx.search(p))]
        if matches:
            # Count distinct config kinds, not files: 30 files under .claude/ is still one config.
            kinds = {k.lstrip("/").lower() for _, k in matches}
            out += signals(sid, agents, len(kinds), (p for p, _ in matches))
    return out


DETECTORS: list[Detector] = [detect_config_files]
