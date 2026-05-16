---
name: sync-github
description: Pull latest changes from GitHub and merge with local changes. Use when user says "pull", "sync", "merge latest", or "get latest from github".
disable-model-invocation: true
---

Sync local repo with GitHub origin/main.

## Current State
- Branch: !`git branch --show-current`
- Status: !`git status --short`
- Remote: !`git remote -v`

## Steps

1. **Check for uncommitted changes:**
   ```bash
   git status --short
   ```

2. **If there are local changes (modified/untracked files):**
   ```bash
   git stash --include-untracked -m "local changes before sync"
   ```

3. **Pull latest from GitHub:**
   ```bash
   git pull origin main
   ```

4. **If we stashed changes, attempt to restore:**
   ```bash
   git stash pop
   ```
   - If `stash pop` fails with conflicts:
     - Run `git status` to see conflicting files
     - The stash likely contains the same changes already pulled (uploaded from another machine)
     - Compare stash vs pulled changes: `git stash show -p stash@{0} | head -50`
     - If they're the same, drop the stash: `git stash drop`
     - If they're different, resolve conflicts manually

5. **If stash pop succeeds or no stash was needed, show final status:**
   ```bash
   git status
   git log --oneline -5
   ```

6. **Report result:** Show current branch, HEAD commit, and whether working tree is clean.
