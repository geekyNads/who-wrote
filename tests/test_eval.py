from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest
from conftest import HUMAN, MakeRepo

from whowrote import eval as ev
from whowrote.dataset import label_from_counts, split_for
from whowrote.signals.base import AGENTS, signals


def test_label_from_counts() -> None:
    assert label_from_counts(Counter({"claude_code": 50}), 100) == "claude_code"
    assert label_from_counts(Counter({"claude_code": 5}), 100) is None  # below MIN_SHARE
    assert label_from_counts(Counter({"claude_code": 50, "cursor": 10}), 100) == "mixed"
    assert label_from_counts(Counter(), 100) is None


def test_split_is_stable_and_roughly_70_15_15() -> None:
    assert split_for("a/b") == split_for("a/b")
    c = Counter(split_for(f"owner/repo{i}") for i in range(2000))
    assert 0.65 < c["train"] / 2000 < 0.75 and 0.12 < c["val"] / 2000 < 0.18


def one_hot(agent: str, p: float = 0.9) -> dict[str, float]:
    rest = (1 - p) / (len(AGENTS) - 1)
    return {a: p if a == agent else rest for a in AGENTS}


def test_metrics() -> None:
    y = ["claude_code", "cursor", "human_unknown", "cursor"]
    probs = [one_hot("claude_code"), one_hot("cursor"), one_hot("human_unknown"),
             one_hot("claude_code")]
    m = ev.metrics(y, probs)
    assert m["top1"] == 0.75 and m["coverage"] == 1.0
    assert m["per_agent"]["cursor"] == pytest.approx(
        {"precision": 1.0, "recall": 0.5, "f1": 2 / 3, "support": 2})
    assert m["confusion"]["cursor"] == {"cursor": 1, "claude_code": 1}
    assert m["ece"] == pytest.approx(abs(0.75 - 0.9))  # one bin: conf 0.9, acc 0.75
    perfect = ev.metrics(["cursor"], [one_hot("cursor", 1.0)])
    assert perfect["nll"] == pytest.approx(0.0) and perfect["brier"] == pytest.approx(0.0)


def test_mask() -> None:
    sigs = [*signals("tier1.claude_coauthor_trailer", ("claude_code",), 1, []),
            *signals("tier2.claude_config", ("claude_code",), 1, []),
            *signals("tier3.emoji_logs", ("cursor",), 1, [])]
    assert [s.tier for s in ev.mask(sigs, (1, 2))] == [3]


def test_eval_end_to_end(make_repo: MakeRepo, tmp_path: Path,
                         monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo([("feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
                       {"CLAUDE.md": "x\n"}, HUMAN)])
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"repo": "local/claude", "path": str(repo),
                                    "label": "claude_code", "split": "val"}) + "\n"
                        + json.dumps({"repo": "local/mixed", "path": str(repo),
                                      "label": "mixed", "split": "val"}) + "\n")
    out = tmp_path / "reports" / "eval-test.md"
    for _ in range(2):  # second run diffs against the first
        monkeypatch.setattr(sys, "argv", ["eval", "--manifest", str(manifest), "--out", str(out),
                                          "--mask-tier", "1,2"])
        ev.main()
        (out.parent / "eval-prev.json").write_text(out.with_suffix(".json").read_text())
    report = out.read_text()
    assert "| full | 1 | 1.000" in report  # mixed excluded, trailer found
    assert "detail mode **mask 1,2**" in report and "## vs previous" in report
    data = json.loads(out.with_suffix(".json").read_text())
    assert set(data["summary"]) == {"full", "mask 1", "mask 1,2"}
