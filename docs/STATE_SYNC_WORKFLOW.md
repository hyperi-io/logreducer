# Development State Sync Workflow

## Overview

The `scripts/state-sync` script maintains development state documentation, AI assistant settings, and development context in a separate repository from the main codebase. This separation keeps the CI/CD pipeline clean while preserving valuable development documentation.

## Why Separate Repositories?

1. **Clean CI/CD**: AI assistant-specific files don't trigger unnecessary CI/CD runs
2. **Development Context**: Preserves detailed development decisions and AI pair-programming context
3. **Template Extraction**: Makes it easier to extract a clean template without AI-specific content
4. **Security**: Keeps potentially sensitive development discussions separate from public code
5. **AI Portability**: Supports multiple AI assistants (Claude, Cursor, ChatGPT, etc.)

## Files Synced

The following files are automatically synced to the development state repository:

- `STATE.md` - Main development state documentation
- `.claude/` - Claude Code settings (if present)
- `.cursorrules` - Cursor AI configuration (if present)
- `scripts/state-sync` - This sync script itself
- `scripts/README.md` - Scripts documentation
- `.vscode/settings.json` - VS Code AI integration settings
- `docs/DEVELOPER_ANTIPATTERNS.md` - Development best practices
- `docs/DEVELOPER_CHANGES.md` - Development changelog
- `docs/SCRIPT_ARCHITECTURE.md` - Script system documentation
- `END_OF_DAY.md` - End of day workflow documentation

## Setup

### 1. Initialize a New State Repository

```bash
# Create a local state docs repo
scripts/state-sync --init-repo --target-dir ~/development-state/logreducer

# Or specify a custom location
scripts/state-sync --init-repo --target-dir /path/to/dev-state
```

### 2. Connect to Remote Repository (Optional)

```bash
# Create a GitHub repo (e.g., logreducer-state)
# Then sync with remote URL
scripts/state-sync \
  --repo-url git@github.com:username/logreducer-state.git \
  --target-dir ~/development-state/logreducer
```

### 3. Regular Syncing

```bash
# Sync and push to remote
scripts/state-sync

# Sync without pushing (commit only)
scripts/state-sync --no-push

# Custom commit message
scripts/state-sync --message "docs: Update development state after refactoring"
```

## Workflow Examples

### After Development Session

When you've had a productive development session with important decisions:

```bash
# Sync all state-related files to the docs repo
scripts/state-sync --message "docs: Add architecture decisions from session"
```

### Before Template Extraction

When preparing to extract a clean template:

```bash
# Ensure all development state is safely stored
scripts/state-sync --message "docs: Final sync before template extraction"

# Then in main repo, AI-specific files can be excluded from template
```

### Setting Up on New Machine

```bash
# Clone the state docs repo
git clone git@github.com:username/logreducer-state.git ~/development-state/logreducer

# Future syncs will update this repo
scripts/state-sync --target-dir ~/development-state/logreducer
```

## Command Options

```bash
scripts/state-sync [OPTIONS]

Options:
  --repo-url URL        URL of development state repository
  --target-dir PATH     Local directory for state docs (default: ~/development-state/logreducer)
  --no-push            Don't push to remote after committing
  --message MSG        Custom commit message
  --init-repo          Initialize a new state repository
  --check-legacy       Check for legacy Claude-specific files
  --dry-run            Show what would be synced without making changes
```

## Repository Structure

The development state repository will have this structure:

```
logreducer-state/
├── README.md                 # Auto-generated readme
├── STATE.md                  # Main development state documentation
├── .claude/                  # Claude Code settings (if using Claude)
│   └── settings.local.json
├── .cursorrules              # Cursor AI configuration (if using Cursor)
├── scripts/                  # Synced scripts
│   ├── state-sync
│   └── README.md
├── docs/                     # Development documentation
│   ├── DEVELOPER_ANTIPATTERNS.md
│   ├── DEVELOPER_CHANGES.md
│   └── SCRIPT_ARCHITECTURE.md
├── .vscode/                  # VS Code settings
│   └── settings.json
├── END_OF_DAY.md            # End of day workflow
└── .state-sync.json         # Sync metadata
```

## Metadata

The `.state-sync.json` file tracks:
- Last sync timestamp
- Source repository URL
- List of synced files
- Sync tool version
- Compatible AI assistants

## AI Assistant Compatibility

The state sync workflow supports multiple AI coding assistants:

### Claude Code
- Settings stored in `.claude/settings.local.json`
- Full permissions configuration
- Standalone operation

### Cursor AI
- Configuration in `.cursorrules`
- Auto-approval rules for common operations
- Workspace-specific settings

### ChatGPT/GPT-4
- STATE.md provides full context
- Can work with pasted content
- Code interpreter support

### Generic LLMs
- Universal documentation format
- Clear file structure
- Step-by-step instructions

## Best Practices

1. **Regular Syncing**: Sync after significant development sessions
2. **Meaningful Messages**: Use descriptive commit messages
3. **Review Before Sync**: Check `git status` in main repo first
4. **Separate Concerns**: Keep CI/CD files in main repo only
5. **Documentation Focus**: Use state repo for detailed explanations
6. **AI Agnostic**: Keep documentation generic when possible

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

If the state repo has conflicts:
```bash
cd ~/development-state/logreducer
git pull --rebase
# Resolve any conflicts
git add .
git rebase --continue
```

### Missing Files

If expected files aren't synced:
1. Check they exist in the main repository
2. Verify they're listed in `STATE_FILES` in the script
3. Ensure they're not matching `EXCLUDE_PATTERNS`
4. Optional files (like .cursorrules) won't cause warnings if missing

### Legacy File Migration

If you have old Claude-specific files:
```bash
# Check for legacy files
scripts/state-sync --check-legacy

# They will be automatically migrated during sync:
# CLAUDE.md → STATE.md
# CLAUDE_END_OF_DAY.md → END_OF_DAY.md
# scripts/claude-sync → scripts/state-sync
```

## Integration with CI/CD

The development state repository is intentionally **excluded from CI/CD**. This means:
- No automated testing on state doc changes
- No version bumps from documentation updates
- No deployment triggers from AI-specific content

This separation ensures development documentation doesn't interfere with production workflows.

## Environment Variables

Configure the sync via environment variables:

```bash
# New generic variables (preferred)
export DEV_STATE_REPO="git@github.com:username/dev-state.git"
export DEV_STATE_SUBDIR="logreducer"
export DEV_STATE_LOCAL_PATH="~/development-state"

# Legacy variables (still supported for compatibility)
export CLAUDE_STATE_REPO="..."  # Mapped to DEV_STATE_REPO
export CLAUDE_STATE_SUBDIR="..." # Mapped to DEV_STATE_SUBDIR
```

## Future Enhancements

Potential improvements for the sync workflow:

1. **Bidirectional Sync**: Pull state changes back to main repo
2. **Selective Sync**: Choose specific files to sync per session
3. **Diff Viewer**: Show changes before syncing
4. **Multiple Projects**: Support syncing multiple projects to one state repo
5. **Automatic Sync**: Git hooks to sync on specific events
6. **AI Detection**: Auto-detect which AI assistant is being used

## See Also

- [Script Architecture](SCRIPT_ARCHITECTURE.md) - Overall script system design
- [Developer Changes](DEVELOPER_CHANGES.md) - Development history
- [STATE.md](/STATE.md) - Main development state documentation
- [END_OF_DAY.md](/END_OF_DAY.md) - End of day workflow
