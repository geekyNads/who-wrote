---
name: add-signal
description: End-to-end procedure for adding a new detector/signal to whowrote — detector code, weight, fixture, test, eval check. Use whenever adding or changing a fingerprint.
---

# Adding a signal

1. **Pick the fingerprint** from the `agent-fingerprints` skill. Confirm it on at least one real repo.
2. **Choose the module** by tier: `signals/tier1_provenance.py`, `tier2_config.py`, `tier3_style.py`,
   or `tier4_git.py`.
3. **Write the detector** as a pure function over ingested data:
   ```python
   def detect_claude_coauthor(history: GitHistory) -> list[Signal]:
       hits = [c for c in history.commits if CLAUDE_TRAILER.search(c.message)]
       if not hits:
           return []
       return [Signal(
           id="tier1.claude_coauthor_trailer", tier=1, agent="claude_code",
           strength=W["tier1.claude_coauthor_trailer"], count=len(hits),
           evidence=[f"commit {c.sha[:8]}: {c.subject}" for c in hits[:5]],
       )]
   ```
   - No network, no subprocess, no file writes inside detectors.
   - Cap evidence at 5 items.
   - Register it in the tier module's `DETECTORS` list.
4. **Add the weight** to `scoring/weights.yaml` with a comment:
   ```yaml
   tier1.claude_coauthor_trailer: 6.0   # near-decisive; verified 2026-10 on 20 repos
   ```
   Starting points: tier1 4–8, tier2 1.5–3, tier3 0.2–0.8, tier4 0.2–0.6.
5. **Add a fixture** in `tests/fixtures/<agent>_<signal>/` (tiny synthetic repo built by a fixture
   helper — create commits programmatically, don't commit nested `.git` dirs).
6. **Write tests**: positive (fires), negative (doesn't fire on a clean human fixture), and count saturation.
7. **Run** `uv run ruff check . && uv run mypy --strict whowrote && uv run pytest`.
8. **Run the eval** (`evaluate-detector` skill). If accuracy or calibration drops, lower the weight.
