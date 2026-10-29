---
name: repo-ingestion
description: How whowrote opens local repos or clones GitHub URLs, walks git history (commits, trailers, authors, branches), and filters files. Use when working on whowrote/ingest/.
---

# Repo ingestion

## Inputs
- Local path → open with `pygit2` or by shelling to `git` (read-only commands only).
- GitHub URL (`https://github.com/owner/repo`, optionally `/tree/branch`) → clone into a temp dir:
  ```
  git clone --filter=blob:none --no-checkout <url> <tmp>
  git -C <tmp> checkout HEAD   # or the requested branch
  ```
  Use `--depth 500` as a default history cap; expose `--history N` on the CLI.
- Clean up temp dirs in a `finally` / context manager.

## History (git_history.py)
Extract per commit: sha, author name/email, committer, timestamp, subject, full body,
parsed trailers (`git interpret-trailers --parse` or regex on `^[\w-]+: .+$` in the last paragraph),
files changed + lines added/removed (`git log --numstat`).
Also collect: remote branch names (`git branch -r`), tags. For GitHub URLs, optionally fetch PR
bodies/authors via `gh api` when `GITHUB_TOKEN` is set — skip gracefully otherwise.

Parse in one `git log` call with a custom `--format` using `%x1e`/`%x1f` separators. Don't spawn one
process per commit.

## Files (files.py)
- Use `git ls-files` (tracked only).
- Skip dirs: node_modules, vendor, dist, build, .next, target, __pycache__, venv, .venv.
- Skip lockfiles (package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, Cargo.lock, uv.lock),
  minified (`*.min.*`), binaries, files > 1 MB.
- Detect language by extension; keep a `files_by_lang` map for style baselines.
- Record config files separately (dotfiles at root and `.github/`) for tier 2 — do NOT skip dotfiles.

## Safety
Never run install scripts, hooks, or code from the repo. Set `core.hooksPath=/dev/null` on clones.
