---
name: scoring-calibration
description: How whowrote turns signals into per-agent probabilities (log-score sum, saturation, priors, softmax, temperature) and how to tune weights so percentages are calibrated. Use when working on whowrote/scoring/.
---

# Scoring and calibration

## Formula
For each agent `a`:
```
score[a] = prior[a] + Σ_signals_for_a  strength * log1p(count) / log1p(1)
```
- `log1p` saturation: 1 hit = full strength, 10 hits ≈ 3.5x, 100 hits ≈ 6.7x — volume can't run away.
- `human_unknown` gets a fixed baseline score (start 1.0) plus human-leaning signals. This is what
  stops weak evidence from producing confident wrong answers.
- Shared signals (e.g. `AGENTS.md`) add `strength / n_agents` to each agent that reads it.
- Probabilities: `softmax(score / T)` with temperature `T` (start 1.0) in weights.yaml.

## Priors
Log of rough market share, kept modest so evidence dominates. Store in weights.yaml under `priors:`.

## Calibration
Goal: when we say 70%, we're right ~70% of the time.
1. Run the eval set (`evaluate-detector`) to get predictions + true labels.
2. Plot a reliability diagram (10 bins) and compute ECE.
3. Overconfident → raise `T` or lower tier 3/4 weights. Underconfident → lower `T`.
4. Optionally fit `T` by minimizing NLL on a held-out split (single scalar, scipy `minimize_scalar`).
5. Never tune on the test split. Use train/val/test by repo, never by commit.

## Output rules
- Round to whole percents; ensure they sum to 100 (largest-remainder method).
- Hide agents < 2% into "other" in terminal output; keep full distribution in JSON.
- If top probability < 40%, headline says "Inconclusive" rather than naming an agent.
