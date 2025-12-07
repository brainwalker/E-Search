# Git Branching Strategy for E-Search

## Overview
Simple, maintainable branching strategy for AI-assisted development.

## Branch Structure

### Main Branches
- **`main`** - Production-ready code, always stable
- **`dev`** - Active development branch for AI sessions

### Feature Branches (only when needed)
- **`feature/description`** - For significant new features
- **`fix/description`** - For bug fixes that need review

## Workflow

### For Regular AI Development Sessions
```bash
# Start work - switch to dev branch
git checkout dev

# Let Claude Code work on this branch
# All AI sessions use 'dev' branch

# When satisfied with changes
git checkout main
git merge dev
git push origin main
```

### For Specific Features
```bash
# Only create feature branches for major changes
git checkout -b feature/new-scraper
# Work on feature
git checkout main
git merge feature/new-scraper
git branch -d feature/new-scraper
```

## Configuration for Claude Code

To make Claude Code use the `dev` branch instead of creating new branches:
1. Always start Claude Code sessions from the `dev` branch
2. The worktree will use whatever branch you're on

## Branch Cleanup Rules

### Delete branches when:
- ✅ Changes are merged into main
- ✅ Branch is more than 1 week old with no unique commits
- ✅ Auto-generated names (like `dreamy-feistel`, `bold-colden`)

### Keep branches when:
- ❌ Contains unmerged work you want to review
- ❌ Active feature in progress
- ❌ Pushed to remote and being reviewed

## Quick Commands

```bash
# See all branches
git branch -vv

# Delete merged local branch
git branch -d branch-name

# Delete unmerged branch (careful!)
git branch -D branch-name

# Clean up remote tracking branches
git fetch --prune

# See branches merged into main
git branch --merged main

# See branches NOT merged into main
git branch --no-merged main
```

## Current Setup

### Active Branches
- `main` - Main branch (production)
- `dev` - Development branch (for AI sessions)

### Archived Branches
Old auto-generated branches have been cleaned up.

---

**Last Updated**: 2025-12-07
**Strategy**: Keep it simple, use `dev` for AI work, merge to `main` when ready
