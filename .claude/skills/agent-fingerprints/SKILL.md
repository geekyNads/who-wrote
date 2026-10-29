---
name: agent-fingerprints
description: Reference of known fingerprints (commit trailers, bot authors, branch names, config files, style habits) for each AI coding agent. Read before writing or changing any detector.
---

# Agent fingerprints

Fingerprints drift as tools update. Treat this as a starting point: **verify each one against a real
repo or official docs before encoding it**, and record the verification date in a code comment.

See `fingerprints.md` in this folder for the per-agent table.

## How to use
1. Find the agent in `fingerprints.md`.
2. Pick the tier: provenance (1), config (2), style (3), git behavior (4).
3. Encode it as a detector via the `add-signal` skill.
4. If a fingerprint is shared by several agents (e.g. `AGENTS.md` is read by Codex, Cursor, and
   others), emit a Signal for each with a lower strength rather than picking one.

## Pitfalls
- A config file proves the tool was *configured*, not that it wrote the code. Tier 2 < Tier 1.
- Humans copy `.cursorrules` / `CLAUDE.md` templates from other repos. Check file age vs code age.
- Style signals overlap heavily between agents using the same underlying model. Don't over-weight.
- Forked repos inherit history; attribute only commits after the fork point when possible.
- Commit trailers can be stripped or squashed away. Absence of tier 1 is weak evidence, not proof of human.
