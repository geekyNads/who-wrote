# whowrote — AI Agent Attribution for Code Repositories

## What this project is
`whowrote` analyzes a git repository (local path or GitHub URL) and estimates which AI coding
agent most likely wrote its code, as a probability distribution, e.g.:

```
Claude Code   62%  ██████████████
Cursor        21%  █████
Copilot        9%  ██
Human/Unknown  8%  ██
```

It is a **probabilistic fingerprinting tool, not a proof engine**. Agents share training data and
humans edit agent output. Every output must show *why* (the evidence list), not just percentages.

## Agents we classify (labels)
`claude_code`, `cursor`, `copilot`, `codex`, `devin`, `aider`, `windsurf`, `cline`, `gemini_cli`,
`human_unknown`. Always keep `human_unknown` as an explicit bucket — never force a guess.

## Architecture
```
whowrote/
  cli.py                # entry: `whowrote <path|github-url> [--json] [--verbose]`
  ingest/
    repo.py             # clone (shallow, --filter=blob:none) or open local repo
    git_history.py      # commits, trailers, authors, branches, timing
    files.py            # walk tracked files, skip vendored/generated/lockfiles
  signals/
    base.py             # Signal dataclass + Detector protocol
    tier1_provenance.py # commit trailers, bot authors, agent branch names
    tier2_config.py     # CLAUDE.md, .cursorrules, AGENTS.md, etc.
    tier3_style.py      # comment phrasing, emoji, docstring density, README shape
    tier4_git.py        # commit size, burstiness, message formatting
  scoring/
    combine.py          # evidence -> per-agent log-scores -> softmax
    weights.yaml        # all weights live here, never hard-coded
  report/
    terminal.py         # rich bar chart + evidence table
    json_out.py
  ml/                   # v2: learned classifier on style features
data/                   # labeled repos manifest (not committed if large)
tests/
  fixtures/             # tiny synthetic repos per agent
```

## Core contract
Every detector returns `list[Signal]`:
```python
@dataclass(frozen=True)
class Signal:
    id: str               # e.g. "tier1.claude_coauthor_trailer"
    tier: int             # 1..4
    agent: str            # label it supports
    strength: float       # log-likelihood ratio contribution (weights.yaml)
    count: int            # occurrences found
    evidence: list[str]   # human-readable snippets: file:line or commit sha
```
Scoring sums `strength * f(count)` per agent (f = log1p saturation so one noisy file can't dominate),
adds a prior, then softmax. Tier 1 signals are near-decisive; tier 3 signals are individually weak.

## Rules
- Python 3.11+, `uv` for env, `ruff` + `mypy --strict` must pass, `pytest` for tests.
- Weights only in `scoring/weights.yaml`. Every weight has a comment saying where it came from.
- Never claim certainty in output. Top line always says "estimated".
- Skip: `node_modules`, `vendor`, `dist`, `build`, lockfiles, minified files, files > 1 MB.
- Respect GitHub rate limits; prefer `git clone` over API calls. Read `GITHUB_TOKEN` from env if set.
- Never execute code from analyzed repos. Read-only analysis.
- Agent fingerprints change frequently — when adding one, record the date verified.

## Skills in this repo
- `agent-fingerprints` — reference of known fingerprints per agent; read before writing any detector.
- `add-signal` — procedure for adding a new detector end to end.
- `repo-ingestion` — cloning, history walking, file filtering.
- `scoring-calibration` — how weights and softmax are tuned.
- `build-labeled-dataset` — harvesting ground-truth labeled repos from tier-1 provenance.
- `evaluate-detector` — accuracy/calibration metrics and the eval report.

## Build order
1. Ingestion + CLI skeleton with JSON output.
2. Tier 1 + Tier 2 detectors (these alone give a useful v0).
3. Scoring + terminal report.
4. Labeled dataset + eval harness.
5. Tier 3/4 style detectors, tuned against the eval set.
6. v2: train a classifier on style features using tier-1-labeled repos with tier-1 signals *masked*.
7. Optional: web UI (paste GitHub URL → chart).
