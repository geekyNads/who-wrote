"""Tier 3: style habits in file contents. Individually weak; generic ones split across agents.

Untuned seeds from agent-fingerprints/fingerprints.md (2026-10-29). Tune against the eval set.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from whowrote.signals.base import AI_AGENTS, Detector, RepoData, Signal, signals

_IM = re.I | re.M

# (signal id, agents, pattern, languages it applies to; None = all)
RULES: list[tuple[str, tuple[str, ...], re.Pattern[str], set[str] | None]] = [
    ("tier3.existing_code_placeholder", ("cursor",),
     re.compile(r"^\s*(//|#|/\*|<!--|\{/\*)\s*\.\.\.\s*existing code\b", _IM), None),
    ("tier3.emoji_logs", AI_AGENTS,
     re.compile(r"\b(console\.\w+|print|println|logger?\.\w+|log\.\w+)\(.*[✅❌🚀🎉✨🔥📦🔧]",
                re.M), None),
    ("tier3.narrating_comments", AI_AGENTS,
     re.compile(r"^\s*(#|//)\s*(initialize the|helper function to|create a new|check if the"
                r"|loop through the|import necessary|define the)\b", _IM),
     None),
    ("tier3.broad_except_print", AI_AGENTS,
     re.compile(r"except Exception(\s+as\s+\w+)?:\s*\n\s*print\(", re.M), {"python"}),
    ("tier3.doc_status_emoji", ("claude_code",), re.compile(r"[✅❌]"), {"markdown"}),
]

_README_SECTIONS = re.compile(r"^#{1,3}\s*\W*\s*(features|installation|usage|project structure)\b",
                              _IM)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def detect_style_rules(data: RepoData) -> list[Signal]:
    out: list[Signal] = []
    for sid, agents, rx, langs in RULES:
        ev = []
        for path, text in data.files.texts.items():
            if langs is not None and data.files.lang(path) not in langs:
                continue
            if m := rx.search(text):
                snippet = text[m.start():].split("\n", 1)[0].strip()[:80]
                ev.append(f"{path}:{_line(text, m.start())}: {snippet}")
        if ev:
            out += signals(sid, agents, len(ev), ev)  # count = files, not occurrences
    return out


def detect_readme_template(data: RepoData) -> list[Signal]:
    for path, text in data.files.texts.items():
        if PurePosixPath(path).name.lower() == "readme.md":
            found = {m[1].lower() for m in _README_SECTIONS.finditer(text)}
            if len(found) >= 3:
                return signals("tier3.readme_template", ("claude_code",), 1,
                               [f"{path}: sections {', '.join(sorted(found))}"])
    return []


DETECTORS: list[Detector] = [detect_style_rules, detect_readme_template]
