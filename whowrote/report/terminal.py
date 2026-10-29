"""Rich bar chart + evidence table."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from whowrote.scoring.combine import Result

LABELS = {
    "claude_code": "Claude Code", "cursor": "Cursor", "copilot": "Copilot", "codex": "Codex",
    "devin": "Devin", "aider": "Aider", "windsurf": "Windsurf", "cline": "Cline",
    "gemini_cli": "Gemini CLI", "human_unknown": "Human/Unknown",
}
HIDE_BELOW = 2  # percent; folded into "Other"
BAR_WIDTH = 30


def render(result: Result, meta: dict[str, Any], verbose: bool = False,
           console: Console | None = None) -> None:
    con = console or Console()
    pct = result.percents
    if result.inconclusive:
        con.print(f"[bold]Estimated: Inconclusive[/] — no agent above "
                  f"{max(pct.values())}% ({meta['commits']} commits, {meta['files']} files)")
    else:
        con.print(f"[bold]Estimated author: {LABELS[result.top]} ({pct[result.top]}%)[/] "
                  f"({meta['commits']} commits, {meta['files']} files)")
    con.print()

    rows = sorted(((LABELS[k], v) for k, v in pct.items() if v >= HIDE_BELOW), key=lambda r: -r[1])
    if other := sum(v for v in pct.values() if v < HIDE_BELOW):
        rows.append(("Other", other))
    for label, v in rows:
        con.print(f"  {label:<14}{v:>3}%  [cyan]{'█' * round(v * BAR_WIDTH / 100)}[/]")
    con.print()

    if not result.signals:
        con.print("[dim]No signals found.[/]")
        return
    table = Table(title="Evidence", show_lines=verbose)
    for col in ("Tier", "Signal", "Supports", "Count", "Evidence"):
        table.add_column(col)
    seen: set[str] = set()
    for s in result.signals:
        if s.id in seen:  # shared signals are split per agent; show once
            continue
        seen.add(s.id)
        agents = ", ".join(LABELS[x.agent] for x in result.signals if x.id == s.id)
        if len(agents) > 40:
            agents = "AI agents (generic)"
        ev = s.evidence if verbose else s.evidence[:2]
        table.add_row(str(s.tier), s.id.split(".", 1)[1], agents, str(s.count), "\n".join(ev))
    con.print(table)
    con.print("[dim]Probabilistic estimate from fingerprints, not proof. "
              "Humans edit agent output; trailers can be stripped.[/]")
