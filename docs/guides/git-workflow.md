# Git Workflow Quick Reference

## ✅ Setup Complete!

Your repository now uses a simplified branching strategy.

## Current Branch Structure

```
main (production) ──┬── dev (AI development)
                    │
                    ├── trusting-kilby (unmerged: scraper improvements)
                    └── wizardly-meitner (unmerged: data normalization)
```

## Daily Workflow

### Starting a New AI Session
```bash
cd /Users/shah/E-Search
git checkout dev
git pull origin dev
# Now work with Claude Code - it will use the dev branch
```

### Merging Your Work to Main
```bash
# When you're happy with changes on dev
git checkout main
git merge dev
git push origin main

# Then update dev
git checkout dev
git merge main
git push origin dev
```

## Branches to Review

You have 2 branches with unmerged work:

### 1. `trusting-kilby`
- **Commit**: `fix: improve scraper regex patterns to capture more profile fields`
- **Location**: `/Users/shah/.claude-worktrees/E-Search/trusting-kilby`
- **Action Needed**: Review and decide if you want to merge this

### 2. `wizardly-meitner`
- **Commit**: `feat: add comprehensive data normalization to minimize null fields`
- **Location**: `/Users/shah/.claude-worktrees/E-Search/wizardly-meitner`
- **Action Needed**: Review and decide if you want to merge this

### To Review These Branches
```bash
# View changes in trusting-kilby
git diff main...trusting-kilby

# View changes in wizardly-meitner
git diff main...wizardly-meitner

# To merge one (example with trusting-kilby)
git checkout main
git merge trusting-kilby
git push origin main

# Then delete the branch and worktree
git worktree remove /Users/shah/.claude-worktrees/E-Search/trusting-kilby
git branch -d trusting-kilby
```

## Cleaned Up Branches

Removed the following auto-generated branches (they were merged):
- ✅ `bold-colden`
- ✅ `dreamy-feistel`
- ✅ `epic-mahavira`
- ✅ `fix/scraper-comment`
- ✅ `flamboyant-tesla`
- ✅ `heuristic-wu`
- ✅ `inspiring-curran`
- ✅ `jovial-rubin`
- ✅ `lucid-yonath`

## Key Commands

```bash
# See all branches
git branch -vv

# See all worktrees
git worktree list

# Clean up merged branches
git branch --merged main | grep -v "main" | grep -v "dev" | xargs git branch -d

# Delete a worktree
git worktree remove /path/to/worktree

# Prune deleted remote branches
git fetch --prune
```

## Going Forward

1. **Always use `dev` branch** for AI sessions
2. **Only create feature branches** for major features you want to review separately
3. **Merge `dev` to `main`** when you have stable changes
4. **Clean up old branches** regularly

---

For more details, see `BRANCHING_STRATEGY.md`
