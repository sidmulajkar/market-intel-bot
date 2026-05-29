---
name: sync-github
description: Safely sync code from GitHub main branch. Use when user says "pull", "sync", "merge latest", "sync-github", "get latest from github", or "make this directory up to date with the remote github repo".
---

# Sync from GitHub Main

## When to use
User asks to pull latest code from GitHub remote before working on the project, or to make the local directory up to date with the remote repo.

## Steps
1. **Check current state**: `git status --short` and `git remote -v`
2. **Fetch**: `git fetch origin main` — see what's different
3. **Stash if needed**: If there are local changes, `git stash --include-untracked -m "pre-github-sync-backup"`
4. **Pull**: `git pull origin main`
5. **Compare stash to pulled**: `git stash show --stat` — if the files match what was pulled, `git stash drop`
6. **Verify clean**: `git status --short` should show no modifications

## Safety rules
- NEVER use `git reset --hard` unless explicitly requested
- ALWAYS stash first — never pull over local changes
- Compare stash with pulled files before dropping
- Report exact state after: which files differ, if any
