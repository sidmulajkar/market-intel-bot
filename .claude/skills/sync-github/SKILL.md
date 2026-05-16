---
name: sync-github
description: Multi-VM aware GitHub sync. Backs up local changes to temp, pulls remote, re-applies only NEW changes. Use when user says "pull", "sync", "merge latest", "sync-github", or "get latest from github".
disable-model-invocation: true
---

# Sync-GitHub — Multi-VM Aware

Handles the case where another VM has already pushed code to GitHub, and local changes need to be preserved and re-applied on top.

## Current State
- Branch: !`git branch --show-current`
- Status: !`git status --short`
- Remote: !`git remote -v`

## Procedure

### Step 1: Fetch remote and check if behind
```bash
git fetch origin
git log --oneline HEAD..origin/main
```
If no new commits, skip to Step 5 (just need to commit local changes).

### Step 2: Snapshot local changes to temp
```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/sync-github-$TIMESTAMP"
mkdir -p "$BACKUP_DIR/untracked"

# Save file list
git status --short > "$BACKUP_DIR/files.txt"

# Save diffs
git diff > "$BACKUP_DIR/unstaged.diff"
git diff --cached > "$BACKUP_DIR/staged.diff"

# Save untracked files (preserve directory structure)
git ls-files --others --exclude-standard | while read f; do
  mkdir -p "$BACKUP_DIR/untracked/$(dirname "$f")"
  cp "$f" "$BACKUP_DIR/untracked/$f"
done

echo "Backup saved to: $BACKUP_DIR"
cat "$BACKUP_DIR/files.txt"
```

### Step 3: Stash everything
```bash
git stash --include-untracked -m "sync-github: stashed at $TIMESTAMP"
```

### Step 4: Pull remote
```bash
git pull origin main
```

### Step 5: Analyze what's new vs already-merged
For each file in the stash, check if the local version differs from the freshly pulled version:

```bash
# Get list of files that were in the stash
git stash show --name-only
```

For each file:
- If the stash version == remote version → **already merged**, skip
- If the stash version != remote version → **new change**, needs re-apply
- If file doesn't exist in remote → **new file**, needs re-apply

### Step 6: Re-apply new changes
```bash
# Try to pop stash first
git stash pop 2>&1

# If stash pop fails (conflicts):
#   - For each conflicting file, compare:
#     - The stash version (our changes)
#     - The remote version (what was pulled)
#   - If they're the same content → accept remote, discard stash version
#   - If they're different → keep our version (it's a new change)
#   - Resolve with: git checkout --theirs <file> OR git checkout --ours <file>

# If stash pop succeeds, verify no conflicts remain
git diff --name-only --diff-filter=U
```

### Step 7: Verify everything works
```bash
# Syntax check all Python files
python3 -c "
import ast, glob
for f in glob.glob('src/**/*.py', recursive=True) + glob.glob('jobs/**/*.py', recursive=True):
    try:
        ast.parse(open(f).read())
    except SyntaxError as e:
        print(f'FAIL {f}: {e}')
        exit(1)
print('All files OK')
"

# Run end-to-end test if available
# python3 -c "from src.data_fetcher import fetch_macro_anchors; ..."
```

### Step 8: Report and push
Show final state:
```bash
git status
git log --oneline -5
```

If clean, ready to push:
```bash
git add -A
git commit -m "sync: re-applied local changes on top of remote"
git push
```

## Conflict Resolution Rules

| Scenario | Action |
|----------|--------|
| Stash file == Remote file | Skip (already merged from another VM) |
| Stash file != Remote file, no conflict | Keep stash version (new change) |
| Stash file conflicts with remote | Compare contents, keep the one with more changes |
| Untracked file exists in remote | Skip (already added from another VM) |
| Untracked file not in remote | Re-apply (new file) |

## Example: Multi-VM Scenario

```
VM1: Makes changes to A, B, C → pushes to GitHub
VM2: Makes changes to B, D, E (based on old code) → needs to sync

Sync process:
1. Backup B, D, E changes to /tmp/
2. Stash B, D, E
3. Pull A, B, C from GitHub
4. Compare:
   - B: stash version == remote version → already merged, skip
   - D: not in remote → NEW change, re-apply
   - E: not in remote → NEW change, re-apply
5. Result: A, B, C from remote + D, E from local
6. Push: A, B, C, D, E all in GitHub
```
