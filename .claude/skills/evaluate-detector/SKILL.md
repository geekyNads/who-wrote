---
name: evaluate-detector
description: Run whowrote against the labeled dataset and report accuracy, per-agent precision/recall, confusion matrix, calibration (ECE, reliability), and ablations. Use after adding or reweighting signals.
---

# Evaluating

## Command
`uv run python -m whowrote.eval --split val [--mask-tier 1,2] [--out reports/eval-<date>.md]`

## Metrics to report
- Top-1 accuracy and top-2 accuracy
- Per-agent precision / recall / F1
- Confusion matrix (agents × agents, incl. human_unknown)
- Log loss (NLL) and Brier score
- ECE (10 bins) + reliability table
- Coverage: % of repos where top prob ≥ 40% (not "Inconclusive")

## Ablations (run every time)
1. Full model
2. `--mask-tier 1` — how well do we do without trailers/bot authors?
3. `--mask-tier 1,2` — style + git behavior only (the honest "fingerprinting" number)

The masked numbers are the ones worth bragging about; full-model accuracy is inflated by tier 1.

## Report
Write a markdown report to `reports/` with the metrics table, confusion matrix, worst 10 misses
(repo, true, predicted, top signals), and diff vs the previous report. Flag any metric that regressed.
