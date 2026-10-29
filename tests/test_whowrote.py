from __future__ import annotations

import json

import pytest
from conftest import HUMAN, MakeRepo

from whowrote.cli import analyze, run
from whowrote.ingest.repo import GITHUB_URL
from whowrote.scoring.combine import combine, largest_remainder, saturate
from whowrote.scoring.weights import WEIGHTS
from whowrote.signals import DETECTORS
from whowrote.signals.base import signals

CLAUDE_MSG = "feat: add parser\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def human_repo(make_repo: MakeRepo) -> list[tuple[str, dict[str, str], tuple[str, str]]]:
    return [("init", {"main.py": "x = 1\n"}, HUMAN), ("wip", {"main.py": "x = 2\n"}, HUMAN)]


def ids(result_signals: list[object]) -> set[str]:
    return {s.id for s in result_signals}  # type: ignore[attr-defined]


def test_human_repo_has_no_agent_provenance(make_repo: MakeRepo) -> None:
    result, meta = analyze(str(make_repo(human_repo(make_repo))))
    assert not any(s.tier in (1, 2) for s in result.signals)
    assert "tier4.lazy_messages" in ids(result.signals)
    assert result.top == "human_unknown"
    assert meta["commits"] == 2


def test_claude_trailer_and_config(make_repo: MakeRepo) -> None:
    repo = make_repo([("init", {"CLAUDE.md": "# rules\n", ".claude/settings.json": "{}"}, HUMAN),
                      (CLAUDE_MSG, {"a.py": "pass\n"}, HUMAN)])
    result, _ = analyze(str(repo))
    assert {"tier1.claude_coauthor_trailer", "tier2.claude_config"} <= ids(result.signals)
    assert result.top == "claude_code" and not result.inconclusive
    assert result.percents["claude_code"] <= 99  # never print certainty


def test_one_trailer_in_many_human_commits_is_not_claude(make_repo: MakeRepo) -> None:
    commits = [(f"change {i}", {"a.py": f"x = {i}\n"}, HUMAN) for i in range(200)]
    result, _ = analyze(str(make_repo([*commits, (CLAUDE_MSG, {"b.py": "pass\n"}, HUMAN)])))
    assert "tier1.unattributed_commits" in ids(result.signals)
    assert result.top == "human_unknown"


def test_cursor_bot_branch_and_placeholder(make_repo: MakeRepo) -> None:
    repo = make_repo([("init", {".cursorrules": "be nice\n"}, HUMAN),
                      ("edit", {"a.ts": "// ... existing code ...\n"},
                       ("Cursor Agent", "cursoragent@cursor.com"))],
                     branches=("cursor/fix-bug",))
    result, _ = analyze(str(repo))
    assert {"tier1.cursor_bot_author", "tier1.cursor_branch_prefix", "tier2.cursor_config",
            "tier3.existing_code_placeholder"} <= ids(result.signals)
    assert result.top == "cursor"


def test_agents_md_splits_credit(make_repo: MakeRepo) -> None:
    result, _ = analyze(str(make_repo([("init", {"AGENTS.md": "x\n"}, HUMAN)])))
    shared = [s for s in result.signals if s.id == "tier2.agents_md"]
    assert {s.agent for s in shared} == {"codex", "cursor", "gemini_cli"}
    assert shared[0].strength == pytest.approx(WEIGHTS["signals"]["tier2.agents_md"] / 3)


def test_config_counts_kinds_not_files(make_repo: MakeRepo) -> None:
    files = {f".claude/skills/s{i}/SKILL.md": "x\n" for i in range(30)}
    result, _ = analyze(str(make_repo([("init", files, HUMAN)])))
    [sig] = [s for s in result.signals if s.id == "tier2.claude_config"]
    assert sig.count == 1 and len(sig.evidence) == 5


def test_saturation() -> None:
    assert saturate(1) == pytest.approx(1.0)
    assert 3 < saturate(10) < 4 and 6 < saturate(100) < 7
    one = combine(signals("tier3.emoji_logs", ("cursor",), 1, []))
    many = combine(signals("tier3.emoji_logs", ("cursor",), 1000, []))
    assert many.probabilities["cursor"] > one.probabilities["cursor"]
    assert many.probabilities["cursor"] < 0.9  # one weak signal can't run away


def test_no_evidence_is_inconclusive() -> None:
    assert combine([]).inconclusive


def test_largest_remainder_sums_to_100() -> None:
    p = largest_remainder({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3})
    assert sum(p.values()) == 100
    sure = largest_remainder({"claude_code": 0.9999, "human_unknown": 0.0001})
    assert sure == {"claude_code": 99, "human_unknown": 1}


def test_every_signal_id_has_a_weight() -> None:
    from whowrote.signals import tier1_provenance as t1
    from whowrote.signals import tier2_config as t2

    used = {r[0] for r in t1.COMMIT_RULES} | {r[0] for r in t2.RULES}
    used |= {f"tier1.{a}_branch_prefix" for a in t1.BRANCH_PREFIXES.values()}
    assert used <= set(WEIGHTS["signals"])
    assert DETECTORS


def test_github_url_parsing() -> None:
    m = GITHUB_URL.match("https://github.com/owner/repo.git")
    assert m and m.groups() == ("owner", "repo", None)
    m = GITHUB_URL.match("github.com/o/r/tree/feature/x")
    assert m and m.groups() == ("o", "r", "feature/x")
    assert not GITHUB_URL.match("/tmp/some/path")


def test_cli_json(make_repo: MakeRepo, capsys: pytest.CaptureFixture[str]) -> None:
    repo = make_repo([(CLAUDE_MSG, {"a.py": "pass\n"}, HUMAN)])
    assert run([str(repo), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["estimated"] == "claude_code" and sum(out["percents"].values()) == 100


def test_cli_not_a_repo(tmp_path: object, capsys: pytest.CaptureFixture[str]) -> None:
    assert run([str(tmp_path)]) == 2
