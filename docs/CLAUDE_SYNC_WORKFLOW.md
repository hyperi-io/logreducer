# Claude Documentation Sync Workflow

## Overview

The `scripts/sync-claude-docs` script maintains Claude-specific documentation, settings, and development context in a separate repository from the main codebase. This separation keeps the CI/CD pipeline clean while preserving valuable development documentation.

## Why Separate Repositories?

1. **Clean CI/CD**: Claude-specific files don't trigger unnecessary CI/CD runs
2. **Development Context**: Preserves detailed development decisions and AI pair-programming context
3. **Template Extraction**: Makes it easier to extract a clean template without Claude-specific content
4. **Security**: Keeps potentially sensitive development discussions separate from public code

## Files Synced

The following files are automatically synced to the Claude docs repository:

- `CLAUDE.md` - Main Claude development documentation and decisions
- `.claude/` - Claude Code settings and configurations
- `scripts/sync-claude-docs` - This sync script itself
- `scripts/README.md` - Scripts documentation
- `.vscode/settings.json` - VS Code Claude integration settings
- `docs/DEVELOPER_ANTIPATTERNS.md` - Development best practices
- `docs/DEVELOPER_CHANGES.md` - Development changelog
- `docs/SCRIPT_ARCHITECTURE.md` - Script system documentation

## Setup

### 1. Initialize a New Claude Docs Repository

```bash
# Create a local Claude docs repo
scripts/sync-claude-docs --init-repo --target-dir ~/claude-docs/logreducer

# Or specify a custom location
scripts/sync-claude-docs --init-repo --target-dir /path/to/claude-docs
```

### 2. Connect to Remote Repository (Optional)

```bash
# Create a GitHub repo (e.g., logreducer-claude-docs)
# Then sync with remote URL
scripts/sync-claude-docs \
  --repo-url git@github.com:username/logreducer-claude-docs.git \
  --target-dir ~/claude-docs/logreducer
```

### 3. Regular Syncing

```bash
# Sync and push to remote
scripts/sync-claude-docs

# Sync without pushing (commit only)
scripts/sync-claude-docs --no-push

# Custom commit message
scripts/sync-claude-docs --message "docs: Update template recommendations"
```

## Workflow Examples

### After Claude Session

When you've had a productive Claude Code session with important decisions:

```bash
# Sync all Claude-related files to the docs repo
scripts/sync-claude-docs --message "docs: Add CI/CD template recommendations from session"
```

### Before Template Extraction

When preparing to extract a clean template:

```bash
# Ensure all Claude docs are safely stored
scripts/sync-claude-docs --message "docs: Final sync before template extraction"

# Then in main repo, Claude files can be excluded from template
```

### Setting Up on New Machine

```bash
# Clone the Claude docs repo
git clone git@github.com:username/logreducer-claude-docs.git ~/claude-docs/logreducer

# Future syncs will update this repo
scripts/sync-claude-docs --target-dir ~/claude-docs/logreducer
```

## Command Options

```bash
scripts/sync-claude-docs [OPTIONS]

Options:
  --repo-url URL        URL of Claude docs repository
  --target-dir PATH     Local directory for Claude docs (default: ~/claude-docs/logreducer)
  --no-push            Don't push to remote after committing
  --message MSG        Custom commit message
  --init-repo          Initialize a new Claude docs repository
```

## Repository Structure

The Claude docs repository will have this structure:

```
logreducer-claude-docs/
├── README.md                 # Auto-generated readme
├── CLAUDE.md                # Main Claude documentation
├── .claude/                 # Claude Code settings
│   └── settings.local.json
├── scripts/                 # Synced scripts
│   ├── sync-claude-docs
│   └── README.md
├── docs/                    # Development documentation
│   ├── DEVELOPER_ANTIPATTERNS.md
│   ├── DEVELOPER_CHANGES.md
│   └── SCRIPT_ARCHITECTURE.md
├── .vscode/                 # VS Code settings
│   └── settings.json
└── .claude-sync.json        # Sync metadata
```

## Metadata

The `.claude-sync.json` file tracks:
- Last sync timestamp
- Source repository URL
- List of synced files
- Sync tool version

## Best Practices

1. **Regular Syncing**: Sync after significant Claude sessions
2. **Meaningful Messages**: Use descriptive commit messages
3. **Review Before Sync**: Check `git status` in main repo first
4. **Separate Concerns**: Keep CI/CD files in main repo only
5. **Documentation Focus**: Use Claude repo for detailed explanations

## Troubleshooting

### Authentication Issues

If you can't push to remote:
```bash
# Set up SSH keys for GitHub
ssh-keygen -t ed25519 -C "your_email@example.com"
# Add the public key to GitHub settings

# Or use HTTPS with token
git remote set-url origin https://github.com/username/repo.git
```

### Merge Conflicts

If the Claude docs repo has conflicts:
```bash
cd ~/claude-docs/logreducer
git pull --rebase
# Resolve any conflicts
git add .
git rebase --continue
```

### Missing Files

If expected files aren't synced:
1. Check they exist in the main repository
2. Verify they're listed in `CLAUDE_FILES` in the script
3. Ensure they're not matching `EXCLUDE_PATTERNS`

## Integration with CI/CD

The Claude docs repository is intentionally **excluded from CI/CD**. This means:
- No automated testing on Claude doc changes
- No version bumps from documentation updates
- No deployment triggers from Claude-specific content

This separation ensures development documentation doesn't interfere with production workflows.

## Future Enhancements

Potential improvements for the sync workflow:

1. **Bidirectional Sync**: Pull Claude docs changes back to main repo
2. **Selective Sync**: Choose specific files to sync per session
3. **Diff Viewer**: Show changes before syncing
4. **Multiple Projects**: Support syncing multiple projects to one Claude repo
5. **Automatic Sync**: Git hooks to sync on specific events

## See Also

- [Script Architecture](SCRIPT_ARCHITECTURE.md) - Overall script system design
- [Developer Changes](DEVELOPER_CHANGES.md) - Development history
- [CLAUDE.md](/CLAUDE.md) - Main Claude documentation