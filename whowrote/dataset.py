"""Harvest tier-1-labeled repos from GitHub into data/manifest.jsonl (build-labeled-dataset skill).

    uv run python -m whowrote.dataset [--per-agent 20] [--human 40] [--agents claude_code,cursor]

Agent repos: GitHub commit search on tier-1 strings, then each candidate is cloned and verified —
the agent's trailer/bot commits must be >= MIN_SHARE of history and no other agent may show up.
Human baseline: established repos snapshotted at their last commit before 2021 (pre-assistant).
Stores the manifest only; clones live in the gitignored .cache/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from whowrote.ingest.git_history import load_history
from whowrote.ingest.repo import open_repo
from whowrote.signals.tier1_provenance import COMMIT_RULES

CACHE = Path(".cache")
MANIFEST = Path("data/manifest.jsonl")
HISTORY = 300
MIN_SHARE = 0.2  # agent commits / all commits needed to call it that agent's repo
NOISE_SHARE = 0.05  # another agent above this -> "mixed", excluded from single-label eval
MAX_PER_OWNER = 3
# ponytail: fixed pacing; GitHub's secondary limit tripped at ~2s gaps (2026-10-29).
PACE_S = 8.0

# Tier-1 search strings per agent. Unverified as queries except claude_code + cursor (2026-10-29).
QUERIES: dict[str, list[str]] = {
    "claude_code": ['"Co-Authored-By: Claude" noreply@anthropic.com'],
    "cursor": ["author-email:cursoragent@cursor.com"],
    "copilot": ["author-name:Copilot", '"Co-authored-by: Copilot"'],
    "codex": ["author-name:chatgpt-codex-connector[bot]"],
    "devin": ["author-name:devin-ai-integration[bot]"],
    "aider": ['author-name:"(aider)"'],
    "gemini_cli": ["author-name:google-labs-jules[bot]"],
}
HUMAN_LANGS = ["python", "javascript", "typescript", "go", "rust", "java", "ruby", "php"]
HUMAN_CUTOFF = "2021-01-01T00:00:00Z"

_last_call = 0.0


def gh(endpoint: str, **params: str | int) -> Any:
    """`gh api` GET with on-disk cache, fixed pacing and backoff on rate limits."""
    global _last_call
    key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
    cached = CACHE / "gh" / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    args = ["gh", "api", "-X", "GET", endpoint]
    for k, v in params.items():
        args += ["-f", f"{k}={v}"]
    for attempt in range(4):
        time.sleep(max(0.0, _last_call + PACE_S - time.monotonic()))
        _last_call = time.monotonic()
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode == 0:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(p.stdout)
            return json.loads(p.stdout)
        if "rate limit" not in (p.stdout + p.stderr).lower():
            raise RuntimeError(f"gh api {endpoint}: {p.stderr.strip() or p.stdout[:200]}")
        wait = 60 * 2**attempt
        print(f"  rate limited, sleeping {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"gh api {endpoint}: still rate limited")


def split_for(repo: str) -> str:
    """70/15/15 by repo hash — stable, never by commit."""
    h = int(hashlib.sha256(repo.encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def label_from_counts(counts: Counter[str], n_commits: int) -> str | None:
    """Agent label if one agent clearly dominates provenance, "mixed" if several, else None."""
    if not n_commits or not counts:
        return None
    present = [a for a, c in counts.items() if c / n_commits >= NOISE_SHARE]
    if len(present) > 1:
        return "mixed"
    agent, c = counts.most_common(1)[0]
    return agent if c / n_commits >= MIN_SHARE else None


def verify(repo: str) -> dict[str, Any] | None:
    """Clone (cached) and label from tier-1 commit provenance across the repo's history."""
    try:
        with open_repo(f"https://github.com/{repo}", HISTORY, cache=CACHE / "repos") as path:
            history = load_history(path, HISTORY)
    except subprocess.CalledProcessError as e:
        print(f"  skip {repo}: clone failed ({(e.stderr or '').strip()[:80]})", file=sys.stderr)
        return None
    counts: Counter[str] = Counter()
    hits: dict[str, tuple[str, list[str]]] = {}
    for c in history.commits:
        for agent, sid in {(a, sid) for sid, a, rx, field in COMMIT_RULES if rx.search(field(c))}:
            counts[agent] += 1
            hits.setdefault(agent, (sid, []))[1].append(c.sha)
    label = label_from_counts(counts, len(history.commits))
    if label is None:
        return None
    src, shas = hits.get(label, ("tier1.multiple", []))
    share = round(counts[label] / len(history.commits), 3) if label in counts else None
    return {"repo": repo, "label": label, "label_source": src, "labeled_shas": shas[:5],
            "agent_share": share, "rev": None}


def search_agent_repos(agent: str, want: int) -> list[str]:
    owners: Counter[str] = Counter()
    repos: list[str] = []
    for q in QUERIES[agent]:
        for page in range(1, 11):  # search caps at 1000 results
            items = gh("search/commits", q=q, per_page=100, page=page).get("items", [])
            for it in items:
                r = it["repository"]
                name, owner = r["full_name"], r["owner"]["login"]
                if r.get("fork") or name in repos or owners[owner] >= MAX_PER_OWNER:
                    continue
                owners[owner] += 1
                repos.append(name)
            if len(repos) >= want or len(items) < 100:
                break
    return repos[:want]


def harvest_human(want: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    per_lang = max(1, -(-want // len(HUMAN_LANGS)))
    for lang in HUMAN_LANGS:
        q = f"language:{lang} created:2013-01-01..2018-12-31 pushed:>2025-01-01 stars:100..5000"
        taken = 0
        for r in gh("search/repositories", q=q, per_page=per_lang * 2).get("items", []):
            if r.get("fork") or taken >= per_lang:
                continue
            commits = gh(f"repos/{r['full_name']}/commits", until=HUMAN_CUTOFF, per_page=1)
            if commits:
                taken += 1
                rows.append({"repo": r["full_name"], "label": "human_unknown",
                             "label_source": "pre-2021 snapshot", "labeled_shas": [],
                             "agent_share": None, "rev": commits[0]["sha"]})
    return rows[:want]


def load_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    p = argparse.ArgumentParser(prog="whowrote.dataset", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--per-agent", type=int, default=20, help="verified repos wanted per agent")
    p.add_argument("--human", type=int, default=40, help="pre-2021 human baseline repos")
    p.add_argument("--agents", default=",".join(QUERIES), help="comma-separated agent labels")
    p.add_argument("--out", type=Path, default=MANIFEST)
    p.add_argument("--workers", type=int, default=6, help="parallel clones for verification")
    args = p.parse_args()

    rows = {r["repo"]: r for r in load_manifest(args.out)}
    today = date.today().isoformat()
    for agent in [a for a in args.agents.split(",") if a]:
        candidates = [r for r in search_agent_repos(agent, args.per_agent * 3) if r not in rows]
        print(f"{agent}: verifying {len(candidates)} candidates", file=sys.stderr)
        kept = 0
        with ThreadPoolExecutor(args.workers) as pool:
            for row in pool.map(verify, candidates):
                if row and kept < args.per_agent and row["repo"] not in rows:
                    rows[row["repo"]] = row | {"collected": today, "split": split_for(row["repo"])}
                    kept += row["label"] != "mixed"
        print(f"{agent}: kept {kept}", file=sys.stderr)
    if args.human:
        for row in harvest_human(args.human):
            rows.setdefault(row["repo"], row | {"collected": today,
                                                "split": split_for(row["repo"])})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows.values()))
    print(f"wrote {len(rows)} repos to {args.out}: "
          f"{dict(Counter(r['label'] for r in rows.values()))}", file=sys.stderr)


if __name__ == "__main__":
    main()
