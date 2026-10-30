# who wrote

Estimate which AI coding agent wrote a GitHub repository, and show the evidence.

```
Estimated author: Claude Code 62%

Claude Code    62%  ██████████████
Cursor         21%  █████
Copilot         9%  ██
Human/Unknown   8%  ██
```

This is a probabilistic fingerprinting tool, not proof. Agents share training data, humans edit
agent output, and commit trailers can be stripped. Every result lists the signals behind it.

Labels: `claude_code`, `cursor`, `copilot`, `codex`, `devin`, `aider`, `windsurf`, `cline`,
`gemini_cli`, and `human_unknown`. If no agent reaches 40%, the result is "Inconclusive".

## How it works

1. **Ingest.** Shallow, blobless clone of the repo, or a local path. Git hooks are disabled, and no
   code from the repo is ever run.
2. **Detect.** Four tiers of signals:
   - **Tier 1, provenance:** co-author trailers, bot authors, agent branch names. Near-decisive.
   - **Tier 2, config:** `CLAUDE.md`, `.cursorrules`, `AGENTS.md`, `.github/copilot-instructions.md`, etc.
   - **Tier 3, style:** comment phrasing, emoji in logs, README shape. Individually weak.
   - **Tier 4, git habits:** commit size, message format, history length.
3. **Score.** Per-agent sum of `strength × log1p(count)`, capped per tier, plus a prior, then
   softmax. All weights live in [`whowrote/scoring/weights.yaml`](whowrote/scoring/weights.yaml).

## Quick start

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and git.

```bash
uv sync
```

```bash
uv run whowrote https://github.com/psf/requests
```

```bash
uv run whowrote . --json
```

CLI options: `--json`, `--verbose` (all evidence), `--history N` (commits to read, default 500).
A `/tree/<branch>` URL analyzes that branch. Set `GITHUB_TOKEN` to raise rate limits.

## Web UI

```bash
uv run whowrote-web
```

Open http://localhost:8000 and paste a GitHub URL. Results are shareable as `/?repo=<url>`.

| Endpoint | |
|---|---|
| `GET /` | the page |
| `GET /api/analyze?url=<github url>` | JSON result |
| `GET /healthz` | health check |

| Env var | Default | |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | bind address |
| `WHOWROTE_MAX_JOBS` | `2` | concurrent analyses; extra requests get 429 |
| `WHOWROTE_GIT_TIMEOUT` | `180` | seconds per git command |

The web server only accepts public `github.com` URLs and drops `GITHUB_TOKEN` at startup.

## Deploy

**Docker:**

```bash
docker build -t whowrote .
```

```bash
docker run -p 8000:8000 whowrote
```

**Render:** Dashboard → New → Blueprint → pick this repo. [`render.yaml`](render.yaml) creates a
free web service from the Dockerfile with a `/healthz` health check. The free plan has 512 MB and
sleeps when idle, so the first request after a while is slow.

## Dataset and evaluation

Harvest labeled repos (agents from tier-1 provenance, humans from pre-2021 snapshots). Needs the
`gh` CLI, signed in:

```bash
uv run python -m whowrote.dataset --per-agent 20 --human 40
```

Evaluate against the manifest, with tier-1 and tier-1+2 masked ablations:

```bash
uv run python -m whowrote.eval --split val
```

This writes `reports/eval-<date>.md` and `.json`: top-1/top-2 accuracy, per-agent P/R/F1, a
confusion matrix, calibration (NLL, Brier, ECE), and the worst misses.

## Development

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run mypy whowrote
```

To add a detector, follow [`.claude/skills/add-signal`](.claude/skills/add-signal/SKILL.md).
Project rules are in [`CLAUDE.md`](CLAUDE.md).
