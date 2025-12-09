# Sync Guide

## Overview

The "sync" command is a convenience feature that compacts, organizes, and commits all changes to the project in one go.

## What "Sync" Does

When you say **"sync"** to Claude, it will:

### 1. **Compact & Organize** 📁
- Move any loose files to appropriate folders
- Ensure all documentation is in `docs/`
- Ensure all scripts are in `backend/scripts/`
- Ensure database files are in `backend/data/`
- Clean up root directory

### 2. **Update Documentation** 📚
- Update any outdated documentation
- Update README.md if structure changed
- Update docs/README.md index
- Ensure all docs follow naming conventions

### 3. **Git Operations** 🔄
- Stage all changes (`git add .`)
- Create descriptive commit message
- Commit with proper formatting
- Push to remote repository

### 4. **Verify & Report** ✅
- List files moved/changed
- Show git status
- Confirm all changes applied
- Display new folder structure

### 5. **Compact Reminder** 💡
- After sync completes, Claude will remind you about compacting
- You can click the Compact button in Claude UI if desired
- Compacting is optional but helpful for long sessions
- All work is safely saved in git before compacting

## Usage

### Basic Sync

Just type:
```
sync
```

Claude will automatically:
- Detect what changed
- Generate appropriate commit message
- Push everything to git

### Sync with Custom Message

```
sync "add new feature for location filtering"
```

This will use your message in the commit.

### Using the Sync Script

You can also run the sync script manually:

```bash
# Basic sync (auto-generated commit message)
python3 sync.py

# Sync with custom message
python3 sync.py "add new feature"
```

## What Gets Synced

### Code Changes
- Backend code in `backend/api/`
- Scripts in `backend/scripts/`
- Frontend code in `frontend/`
- Configuration files

### Documentation Changes
- All files in `docs/`
- README.md updates
- New documentation files

### Configuration Changes
- `.env.example` updates
- `.gitignore` changes
- Project configuration

### Excluded from Sync
- Database files (`backend/data/*.db`)
- Environment files (`.env`)
- Python cache (`__pycache__/`)
- IDE files (`.vscode/`, `.idea/`)

## Compact Reminder

After every successful sync, Claude will remind you about the Compact feature.

### What is Compacting?

Compacting is Claude's built-in feature that:
- Summarizes the current conversation
- Reduces memory/context usage
- Keeps important information in project files
- Frees up tokens for new work

### How to Compact

After sync, you'll see a reminder:

```
✅ Sync complete! All changes pushed to git.

💡 Tip: Consider clicking the 'Compact' button to free up conversation memory.
   This will summarize our work and reduce context usage.
   All your work is safely saved in git!
```

Then you can:
1. Click the **Compact** button in Claude's UI (if you want)
2. Or just continue working (compacting is optional)

### Why Compact After Sync?

- **Natural checkpoint** - Sync marks end of a work session
- **Clean slate** - Start fresh after saving work
- **Better performance** - Reduced context = faster responses
- **Safe** - All work is saved in git before compacting

### What Gets Preserved?

Everything important is in files:
- ✅ All code changes (in git)
- ✅ Documentation (in `docs/`)
- ✅ Project structure (organized folders)
- ✅ Database (in `backend/data/`)
- ✅ Scripts (in `backend/scripts/`)

**Compact only clears the conversation context, not your files!**

## Commit Message Format

Synced commits follow this format:

```
type: brief description

Detailed explanation:
- Change 1
- Change 2
- Change 3

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Commit Types

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation only
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Tests
- `chore:` - Maintenance
- `style:` - Code style

## Examples

### Example 1: Documentation Update

**You say:** "sync"

**Claude does:**
```bash
# Detects documentation changes
# Creates commit:
docs: update documentation

- Updated database schema docs
- Updated quick start guide

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Example 2: Backend Changes

**You say:** "sync"

**Claude does:**
```bash
# Detects backend changes
# Creates commit:
feat: update backend code

- Modified scraper logic
- Updated database models
- Updated documentation

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Example 3: Custom Message

**You say:** "sync add location filtering feature"

**Claude does:**
```bash
# Uses your message
chore: add location filtering feature

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Before Syncing

### Check What Will Be Synced

```bash
git status
```

This shows all changes that will be committed.

### Review Changes

```bash
git diff
```

This shows line-by-line changes.

### Test Your Code

Make sure everything works before syncing:
```bash
cd backend
python3 -m api.main
```

## After Syncing

### Verify Sync

```bash
# Check git status
git status

# View last commit
git log -1

# Check remote status
git log origin/main..HEAD
```

### If Something Went Wrong

#### Undo Last Commit (Keep Changes)
```bash
git reset --soft HEAD~1
```

#### Undo Last Commit (Discard Changes)
```bash
git reset --hard HEAD~1
```

#### Undo Push (Dangerous!)
```bash
git push --force
```

⚠️ Only use force push if you're sure no one else has pulled your changes.

## Best Practices

### 1. Sync Frequently
- Sync after completing a feature
- Sync after fixing bugs
- Sync at end of work session

### 2. Test Before Syncing
- Run the server
- Test key functionality
- Check for errors

### 3. Review Changes
- Use `git status` to see what's changed
- Review `git diff` for large changes
- Make sure no sensitive data is included

### 4. Write Good Messages
- Be descriptive when using custom messages
- Mention what changed and why
- Keep messages concise

### 5. Don't Sync Broken Code
- Fix errors before syncing
- Test functionality
- Update tests if needed

## Troubleshooting

### "Nothing to commit"

This means there are no changes to sync. All files are already committed.

**Solution:** Make changes, then sync.

### "Failed to push"

This usually means:
- No internet connection
- Remote repository not configured
- Merge conflicts

**Solution:**
```bash
# Pull latest changes first
git pull

# Resolve conflicts if any
# Then try syncing again
```

### "Database file in commit"

Database files should not be committed.

**Solution:**
```bash
# Remove from staging
git reset backend/data/*.db

# Add to .gitignore if not already there
echo "*.db" >> backend/data/.gitignore

# Commit without database
git commit -m "fix: remove database from commit"
```

### "Large file warning"

GitHub has file size limits (100MB).

**Solution:**
- Don't commit large files
- Use `.gitignore` to exclude them
- Use Git LFS for large files if needed

## Advanced Usage

### Sync Specific Files Only

```bash
# Add specific files
git add backend/api/main.py
git add docs/guides/new-guide.md

# Commit
git commit -m "feat: update specific files"

# Push
git push
```

### Sync with Branch

```bash
# Create branch
git checkout -b feature/new-feature

# Make changes
# ...

# Sync
git add .
git commit -m "feat: add new feature"
git push -u origin feature/new-feature
```

### Sync Multiple Commits

```bash
# Make multiple small commits
git add backend/api/main.py
git commit -m "fix: update endpoint"

git add docs/api/endpoints.md
git commit -m "docs: update API docs"

# Push all commits
git push
```

## Project Structure Enforcement

When syncing, Claude ensures files are in the correct locations:

### ✅ Correct Locations

```
docs/                   # All documentation
backend/api/           # Application code
backend/data/          # Database files
backend/scripts/       # Management scripts
frontend/              # Frontend files
.env.example           # Environment template
```

### ❌ Incorrect Locations

```
DATABASE_SCHEMA.md     # Should be in docs/database/
backend/migrate.py     # Should be in backend/scripts/
backend/db.db          # Should be in backend/data/
new_feature.md         # Should be in docs/
```

Claude will automatically move files to correct locations during sync.

## Integration with Claude

### Automatic Sync

Claude can automatically sync when you ask:
- "sync"
- "sync my changes"
- "commit and push"
- "save everything to git"

### Manual Control

You can also ask Claude to:
- "show me what will be synced"
- "sync but don't push yet"
- "create a commit but let me review first"

## Related Commands

- `git status` - See what changed
- `git diff` - See line-by-line changes
- `git log` - See commit history
- `git push` - Push commits to remote
- `git pull` - Pull changes from remote

## Questions?

See:
- [Git Workflow Guide](git-workflow.md)
- [Branching Strategy](branching.md)
- [Project Structure Plan](../project/structure-plan.md)
