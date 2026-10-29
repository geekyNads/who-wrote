"""Evidence -> per-agent log-scores -> softmax. See the scoring-calibration skill."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from whowrote.scoring.weights import WEIGHTS
from whowrote.signals.base import AGENTS, Signal

_LOG2 = math.log1p(1)


@dataclass(frozen=True)
class Result:
    probabilities: dict[str, float]  # full distribution, sums to 1
    percents: dict[str, int]  # whole percents, sum to 100, never 100 for one agent
    top: str
    inconclusive: bool
    signals: list[Signal]


def saturate(count: int) -> float:
    """1 hit = 1.0, 10 hits ~ 3.5, 100 hits ~ 6.7: volume can't run away."""
    return math.log1p(count) / _LOG2


def contribution(sig: Signal, weights: dict[str, Any] = WEIGHTS) -> float:
    return min(sig.strength * saturate(sig.count), float(weights["tier_cap"][sig.tier]))


def scores(signals: list[Signal], weights: dict[str, Any] = WEIGHTS) -> dict[str, float]:
    s = {a: float(weights["priors"].get(a, 0.0)) for a in AGENTS}
    s["human_unknown"] += weights["human_baseline"]
    for sig in signals:
        s[sig.agent] += contribution(sig, weights)
    return s


def softmax(s: dict[str, float], temperature: float) -> dict[str, float]:
    hi = max(s.values())
    e = {k: math.exp((v - hi) / temperature) for k, v in s.items()}
    total = sum(e.values())
    return {k: v / total for k, v in e.items()}


def largest_remainder(probs: dict[str, float]) -> dict[str, int]:
    raw = {k: v * 100 for k, v in probs.items()}
    out = {k: math.floor(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: 100 - sum(out.values())]:
        out[k] += 1
    top = max(out, key=lambda k: out[k])
    if out[top] == 100:  # never print certainty
        out[top] = 99
        out["human_unknown" if top != "human_unknown" else sorted(out)[0]] += 1
    return out


def combine(signals: list[Signal], weights: dict[str, Any] = WEIGHTS) -> Result:
    probs = softmax(scores(signals, weights), float(weights["temperature"]))
    top = max(probs, key=lambda k: probs[k])
    return Result(
        probabilities=probs,
        percents=largest_remainder(probs),
        top=top,
        inconclusive=probs[top] < weights["inconclusive_below"],
        signals=sorted(signals, key=lambda s: (s.tier, -contribution(s, weights))),
    )
