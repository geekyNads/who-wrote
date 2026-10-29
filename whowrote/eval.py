"""Evaluate against the labeled manifest (evaluate-detector skill).

    uv run python -m whowrote.eval --split val [--mask-tier 1,2] [--out reports/eval-<date>.md]

Signals are gathered once per repo; the three ablations (full / mask 1 / mask 1,2) are re-scored
from them, so every run reports all three. --mask-tier picks which one gets the detailed sections.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from whowrote.cli import gather
from whowrote.dataset import CACHE, MANIFEST, load_manifest
from whowrote.scoring.combine import combine, contribution
from whowrote.scoring.weights import WEIGHTS
from whowrote.signals.base import AGENTS, Signal

ABLATIONS: dict[str, tuple[int, ...]] = {"full": (), "mask 1": (1,), "mask 1,2": (1, 2)}
HIGHER_IS_BETTER = {"top1": True, "top2": True, "coverage": True,
                    "nll": False, "brier": False, "ece": False}
REGRESSION_EPS = 0.005
Prediction = tuple[dict[str, Any], list[Signal]]


def mask(signals: list[Signal], tiers: tuple[int, ...]) -> list[Signal]:
    return [s for s in signals if s.tier not in tiers]


def metrics(y: list[str], probs: list[dict[str, float]],
            threshold: float = WEIGHTS["inconclusive_below"]) -> dict[str, Any]:
    n = len(y)
    if not n:
        return {"n": 0}
    ranked = [sorted(p, key=p.__getitem__, reverse=True) for p in probs]
    preds = [r[0] for r in ranked]
    conf = [p[r[0]] for p, r in zip(probs, ranked, strict=True)]
    correct = [pr == t for pr, t in zip(preds, y, strict=True)]

    bins: list[dict[str, Any]] = []
    for b in range(10):
        idx = [i for i, c in enumerate(conf) if min(int(c * 10), 9) == b]
        if idx:
            bins.append({"bin": f"{b / 10:.1f}-{(b + 1) / 10:.1f}", "n": len(idx),
                         "conf": sum(conf[i] for i in idx) / len(idx),
                         "acc": sum(correct[i] for i in idx) / len(idx)})

    labels = [a for a in AGENTS if a in y or a in preds]
    per_agent = {}
    for a in labels:
        tp = sum(p == t == a for p, t in zip(preds, y, strict=True))
        fp = sum(p == a != t for p, t in zip(preds, y, strict=True))
        fn = sum(t == a != p for p, t in zip(preds, y, strict=True))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_agent[a] = {"precision": prec, "recall": rec, "f1": f1, "support": y.count(a)}

    return {
        "n": n,
        "top1": sum(correct) / n,
        "top2": sum(t in r[:2] for t, r in zip(y, ranked, strict=True)) / n,
        "nll": sum(-math.log(max(p.get(t, 0.0), 1e-12)) for p, t in zip(probs, y, strict=True)) / n,
        "brier": sum(sum((p[a] - (a == t)) ** 2 for a in AGENTS)
                     for p, t in zip(probs, y, strict=True)) / n,
        "ece": sum(b["n"] / n * abs(b["acc"] - b["conf"]) for b in bins),
        "coverage": sum(c >= threshold for c in conf) / n,
        "reliability": bins,
        "per_agent": per_agent,
        "confusion": {t: dict(Counter(p for p, tt in zip(preds, y, strict=True) if tt == t))
                      for t in labels},
    }


def evaluate(preds: list[Prediction], tiers: tuple[int, ...]) -> tuple[dict[str, Any], list[Any]]:
    results = [combine(mask(sigs, tiers)) for _, sigs in preds]
    y = [row["label"] for row, _ in preds]
    return metrics(y, [r.probabilities for r in results]), results


def predict_all(rows: list[dict[str, Any]], history: int, workers: int) -> list[Prediction]:
    def one(row: dict[str, Any]) -> Prediction | None:
        target = row.get("path") or f"https://github.com/{row['repo']}"
        try:
            sigs, _ = gather(target, history, row.get("rev"), CACHE / "repos")
        except (subprocess.CalledProcessError, OSError) as e:
            err = getattr(e, "stderr", None) or e
            print(f"  skip {row['repo']}: {str(err).strip()[:100]}", file=sys.stderr)
            return None
        return row, sigs

    with ThreadPoolExecutor(workers) as pool:
        return [p for p in pool.map(one, rows) if p]


def _f(x: float) -> str:
    return f"{x:.3f}"


def previous_report(out: Path, split: str) -> tuple[Path, dict[str, Any]] | None:
    found = []
    for p in out.parent.glob("eval-*.json"):
        if p != out.with_suffix(".json"):
            data = json.loads(p.read_text())
            if data.get("split") == split:
                found.append((p.stat().st_mtime, p, data))
    if not found:
        return None
    _, path, data = max(found, key=lambda f: f[0])
    return path, data


def render(split: str, mode: str, summary: dict[str, dict[str, Any]], detail: dict[str, Any],
           preds: list[Prediction], results: list[Any], skipped: int,
           prev: tuple[Path, dict[str, Any]] | None) -> str:
    out = [f"# whowrote eval — {date.today().isoformat()}", "",
           f"Split **{split}** · {detail['n']} repos evaluated ({skipped} skipped) · "
           f"detail mode **{mode}**", "",
           "> Human baseline = pre-2021 snapshots, agent repos = recent: era differences "
           "(history length, tooling) can leak into tier 3/4. Masked rows are the honest number.",
           "", "## Ablations", "",
           "| mode | n | top-1 | top-2 | NLL | Brier | ECE | coverage |",
           "|---|---|---|---|---|---|---|---|"]
    for m, s in summary.items():
        out.append(f"| {m} | {s['n']} | " + " | ".join(_f(s[k]) for k in HIGHER_IS_BETTER) + " |"
                   if s["n"] else f"| {m} | 0 | – | – | – | – | – | – |")

    if prev:
        path, data = prev
        out += ["", f"## vs previous ({path.name})", "", "| mode | metric | prev | now | Δ | |",
                "|---|---|---|---|---|---|"]
        for m, s in summary.items():
            old = data.get("summary", {}).get(m)
            if not old or not s["n"] or not old.get("n"):
                continue
            for k, higher in HIGHER_IS_BETTER.items():
                d = s[k] - old[k]
                bad = (d < -REGRESSION_EPS) if higher else (d > REGRESSION_EPS)
                out.append(f"| {m} | {k} | {_f(old[k])} | {_f(s[k])} | {d:+.3f} | "
                           f"{'⚠️ regressed' if bad else ''} |")

    if not detail["n"]:
        return "\n".join(out) + "\n"
    labels = list(detail["per_agent"])
    out += ["", f"## Per-agent ({mode})", "", "| agent | precision | recall | F1 | support |",
            "|---|---|---|---|---|"]
    for a, s in detail["per_agent"].items():
        out.append(f"| {a} | {_f(s['precision'])} | {_f(s['recall'])} | {_f(s['f1'])} | "
                   f"{s['support']} |")
    out += ["", "## Confusion matrix (rows = true, cols = predicted)", "",
            "| true \\ pred | " + " | ".join(labels) + " |", "|---" * (len(labels) + 1) + "|"]
    for t, row in detail["confusion"].items():
        out.append(f"| {t} | " + " | ".join(str(row.get(p, 0)) for p in labels) + " |")
    out += ["", "## Reliability (10 bins, top-1 confidence)", "",
            "| bin | n | mean conf | accuracy |", "|---|---|---|---|"]
    for b in detail["reliability"]:
        out.append(f"| {b['bin']} | {b['n']} | {_f(b['conf'])} | {_f(b['acc'])} |")

    misses = sorted(((row, sigs, r) for (row, sigs), r in zip(preds, results, strict=True)
                     if r.top != row["label"]),
                    key=lambda x: x[2].probabilities[x[0]["label"]])[:10]
    out += ["", f"## Worst {len(misses)} misses ({mode})", "",
            "| repo | true | predicted | top signals |", "|---|---|---|---|"]
    for row, _, r in misses:
        top = sorted(r.signals, key=lambda s: -contribution(s))[:3]
        sig_txt = ", ".join(f"{s.id}→{s.agent}" for s in top) or "none"
        out.append(f"| {row['repo']} | {row['label']} "
                   f"({r.percents[row['label']]}%) | {r.top} ({r.percents[r.top]}%) | {sig_txt} |")
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(prog="whowrote.eval", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--split", default="val", choices=["train", "val", "test", "all"])
    p.add_argument("--mask-tier", default="", help="tiers masked in detail sections, e.g. 1,2")
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--out", type=Path, default=Path(f"reports/eval-{date.today().isoformat()}.md"))
    p.add_argument("--history", type=int, default=300)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--limit", type=int, default=0, help="evaluate at most N repos (0 = all)")
    args = p.parse_args()

    rows = [r for r in load_manifest(args.manifest) if r["label"] in AGENTS
            and (args.split == "all" or r["split"] == args.split)]  # drops "mixed"
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        sys.exit(f"no repos for split {args.split!r} in {args.manifest} — run whowrote.dataset")
    tiers = tuple(sorted(int(t) for t in args.mask_tier.split(",") if t))
    mode = next((m for m, t in ABLATIONS.items() if t == tiers), f"mask {args.mask_tier}")

    preds = predict_all(rows, args.history, args.workers)
    summary = {m: {k: v for k, v in evaluate(preds, t)[0].items()
                   if k == "n" or k in HIGHER_IS_BETTER} for m, t in ABLATIONS.items()}
    detail, results = evaluate(preds, tiers)
    summary.setdefault(mode, {k: v for k, v in detail.items()
                              if k == "n" or k in HIGHER_IS_BETTER})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    prev = previous_report(args.out, args.split)
    args.out.write_text(render(args.split, mode, summary, detail, preds, results,
                               len(rows) - len(preds), prev))
    args.out.with_suffix(".json").write_text(json.dumps(
        {"split": args.split, "mode": mode, "summary": summary, "detail": detail}, indent=2))
    print(f"wrote {args.out}", file=sys.stderr)
    print(args.out.read_text().split("## vs previous")[0].split("## Per-agent")[0])


if __name__ == "__main__":
    main()
