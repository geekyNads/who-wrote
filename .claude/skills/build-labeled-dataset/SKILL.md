---
name: build-labeled-dataset
description: Harvest ground-truth labeled repos for whowrote using tier-1 provenance (agent trailers, bot authors) from public GitHub, plus a human baseline. Use when building or extending data/ for evaluation or training.
---

# Building the labeled dataset

## Idea
Tier-1 signals (agent co-author trailers, agent bot authors) are near-certain labels. Use them to
label repos/commits for free, then evaluate and train on everything *else* about those commits.

## Sources
- GitHub commit search via `gh api search/commits -f q='"Co-Authored-By: Claude"'` (and the other
  tier-1 strings from `agent-fingerprints`). Respect rate limits: sleep between pages, cache results.
- PRs authored by agent bot accounts: `gh api search/issues -f q='author:app/copilot-swe-agent is:pr'`.
- Human baseline: commits from before 2021 (pre-assistant era) in active repos.

## Manifest
`data/manifest.jsonl`, one line per repo:
```json
{"repo":"owner/name","label":"claude_code","label_source":"tier1.claude_coauthor_trailer",
 "labeled_shas":["abc123..."],"collected":"2026-10-29","split":"train"}
```
- Assign split by repo hash (70/15/15), never by commit.
- Cap repos per owner (≤3) so one prolific user doesn't dominate.
- Store the manifest, not the clones. Clone on demand into a gitignored cache.

## Label hygiene
- Commit-level labels are cleaner than repo-level. Prefer evaluating on labeled commits' diffs.
- A repo with trailers from 2+ agents → label `mixed`, exclude from single-label eval.
- When training style models, **mask tier 1 and tier 2 signals** so the model learns style, not the label source.
- Only public repos. Don't store author emails in the dataset.
