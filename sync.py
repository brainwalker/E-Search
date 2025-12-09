#!/usr/bin/env python3
"""
Sync Script for E-Search Project

This script:
1. Compacts and organizes files
2. Updates documentation
3. Commits changes to git
4. Pushes to remote

Usage: python3 sync.py [commit-message]
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime


def run_command(cmd, cwd=None):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_git_status():
    """Check if there are changes to commit"""
    success, stdout, _ = run_command("git status --porcelain")
    if success:
        return bool(stdout.strip())
    return False


def get_changed_files():
    """Get list of changed files"""
    success, stdout, _ = run_command("git status --short")
    if success:
        return stdout.strip().split('\n') if stdout.strip() else []
    return []


def generate_commit_message(user_message=None):
    """Generate a descriptive commit message based on changes"""

    if user_message:
        # User provided message
        return f"""chore: {user_message}

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"""

    # Auto-generate based on changes
    changed_files = get_changed_files()

    # Analyze changes
    has_docs = any('docs/' in f for f in changed_files)
    has_backend = any('backend/' in f for f in changed_files)
    has_frontend = any('frontend/' in f for f in changed_files)
    has_config = any('.env' in f or 'config' in f.lower() for f in changed_files)

    # Determine commit type
    if has_docs and not (has_backend or has_frontend):
        commit_type = "docs"
        description = "update documentation"
    elif has_backend and has_docs:
        commit_type = "feat"
        description = "update backend and documentation"
    elif has_backend:
        commit_type = "feat"
        description = "update backend code"
    elif has_config:
        commit_type = "chore"
        description = "update configuration"
    else:
        commit_type = "chore"
        description = "sync project changes"

    # Build detailed message
    details = []
    if has_docs:
        details.append("- Updated documentation")
    if has_backend:
        details.append("- Modified backend code")
    if has_frontend:
        details.append("- Modified frontend code")
    if has_config:
        details.append("- Updated configuration")

    details_str = '\n'.join(details) if details else "- General project updates"

    return f"""{commit_type}: {description}

{details_str}

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"""


def sync_project(commit_message=None):
    """Main sync function"""

    print("=" * 60)
    print("E-Search Project Sync")
    print("=" * 60)
    print()

    # Step 1: Check for changes
    print("Step 1: Checking for changes...")
    if not check_git_status():
        print("✅ No changes to sync")
        return True

    changed_files = get_changed_files()
    print(f"✅ Found {len(changed_files)} changed files")
    for f in changed_files[:10]:  # Show first 10
        print(f"   {f}")
    if len(changed_files) > 10:
        print(f"   ... and {len(changed_files) - 10} more")
    print()

    # Step 2: Add all changes
    print("Step 2: Adding changes to git...")
    success, stdout, stderr = run_command("git add .")
    if not success:
        print(f"❌ Failed to add changes: {stderr}")
        return False
    print("✅ All changes staged")
    print()

    # Step 3: Generate commit message
    print("Step 3: Creating commit...")
    message = generate_commit_message(commit_message)
    print("Commit message:")
    print("-" * 60)
    print(message)
    print("-" * 60)
    print()

    # Create commit
    # Escape special characters and use heredoc for commit message
    success, stdout, stderr = run_command(
        f'git commit -m "$(cat <<\'EOF\'\n{message}\nEOF\n)"'
    )
    if not success:
        if "nothing to commit" in stderr:
            print("✅ Nothing to commit (already up to date)")
        else:
            print(f"❌ Failed to commit: {stderr}")
            return False
    else:
        print("✅ Changes committed")
    print()

    # Step 4: Push to remote
    print("Step 4: Pushing to remote...")
    success, stdout, stderr = run_command("git push")
    if not success:
        print(f"❌ Failed to push: {stderr}")
        print("Note: You may need to push manually")
        return False
    print("✅ Changes pushed to remote")
    print()

    # Step 5: Show final status
    print("=" * 60)
    print("✅ Sync Complete!")
    print("=" * 60)
    print()

    # Show current status
    success, stdout, _ = run_command("git status")
    if success:
        print("Git Status:")
        print(stdout)

    return True


def main():
    """Main entry point"""

    # Get commit message from command line if provided
    commit_msg = None
    if len(sys.argv) > 1:
        commit_msg = ' '.join(sys.argv[1:])

    # Run sync
    success = sync_project(commit_msg)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
