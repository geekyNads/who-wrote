# Fingerprint table (unverified starting points — verify before encoding)

Format: **Tier 1** provenance · **Tier 2** config files · **Tier 3/4** soft habits.
Regexes are case-insensitive unless noted.

## claude_code
- T1: commit trailer `Co-Authored-By: Claude.*<noreply@anthropic.com>`
- T1: commit/PR body line `Generated with \[Claude Code\]` (often with 🤖)
- T1: branch prefix `claude/`
- T2: `CLAUDE.md`, `CLAUDE.local.md`, `.claude/` (settings.json, commands/, skills/, agents/)
- T3: README sections in a "Features / Installation / Usage / Project Structure" shape; heavy markdown
  tables; emoji status markers (✅ ❌) in docs/logs

## cursor
- T1: branch prefix `cursor/` (background agents); bot author names containing `cursor`
- T2: `.cursorrules`, `.cursor/rules/*.mdc`, `.cursor/` dir, `.cursorignore`
- T3: placeholder comments like `// ... existing code ...` left in files

## copilot
- T1: bot author `copilot-swe-agent[bot]` or `Copilot` GitHub bot; branch prefix `copilot/`
- T1: `Co-authored-by: Copilot` trailers
- T2: `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `.github/prompts/`

## codex (OpenAI)
- T1: branch prefix `codex/`; PRs from Codex cloud tasks; bot authors containing `codex`
- T2: `AGENTS.md` (shared standard — also read by Cursor, Jules, others → split credit), `.codex/`

## devin
- T1: bot author `devin-ai-integration[bot]`; branch prefix `devin/`
- T2: `.devin/`

## aider
- T1: author name suffix ` (aider)`; older versions prefix commit messages with `aider: `
- T2: `.aider.conf.yml`, `.aiderignore`, `.aider.chat.history.md`, `.aider.input.history`, `.aider.tags.cache*`

## windsurf
- T2: `.windsurfrules`, `.windsurf/rules/`, `.codeiumignore`

## cline
- T2: `.clinerules` (file or dir), `memory-bank/` dir with `activeContext.md`, `progress.md`
- (Roo Code fork: `.roo/`, `.roomodes` — map to `cline` or add `roo` label)

## gemini_cli
- T1: Jules bot author `google-labs-jules[bot]` (consider a separate `jules` label)
- T2: `GEMINI.md`, `.gemini/`

## Generic "AI-ish" style signals (tier 3, low strength, split across agents)
- Comment-to-code ratio far above repo language baseline
- Docstrings on trivial one-line functions
- Comments narrating the obvious: `# Initialize the list`, `// Helper function to ...`
- Emoji in console logs (`🚀 Server running`, `✅ Done`)
- Broad `try/except Exception` with print-and-continue
- Every commit in Conventional Commits format with bulleted bodies (tier 4)
- Single commits touching 20+ files with complete features (tier 4)

## Human-leaning signals (support `human_unknown`)
- Typos in commit messages, messages like `wip`, `fix`, `asdf`
- Long history with small, irregular commits over months
- Inconsistent formatting across files
