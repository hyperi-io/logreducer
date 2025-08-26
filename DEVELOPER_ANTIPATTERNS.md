# Developer Experience: Old Way vs Framework Way

## When Developers Try Manual Approaches

### 1. Creating a Branch (Old Way)

**What they try (from Google/StackOverflow):**
```bash
git checkout -b my-new-feature
```

**What happens:**
```
✓ Branch created locally
✗ Pre-push hook FAILS with:
  Branch name lint fail! Branch "my-new-feature" must contain a separator "/"
```

**Framework guides them:**
```bash
./scripts/dev-helper.sh
# Menu appears → Select "Create a new feature branch"
# Prompts for JIRA ticket (optional)
# Creates: feature/PROJ-123-my-feature
```

### 2. Making a Commit (Old Way)

**What they try:**
```bash
git commit -m "fixed bug"
```

**What happens:**
```
✗ Pre-commit hook FAILS with:
  ✖ subject may not be empty [subject-empty]
  ✖ type may not be empty [type-empty]
```

**Framework guides them:**
```bash
./scripts/dev-helper.sh
# Menu → "Create a commit (interactive)"
# Shows examples of valid commits
# Preview shows: "This will trigger a PATCH version bump"
```

### 3. Manually Bumping Version (Old Way)

**What they try:**
```bash
# Edit pyproject.toml
version = "3.3.0"  # Manual bump
```

**What happens:**
```
✗ Pre-commit hook WARNING:
  ⚠️ Manual version change detected!
  Versions are automatically managed by semantic-release
✗ CI/CD will override with correct version
✗ Creates version conflicts
```

**Framework guides them:**
```bash
feat: add new feature  # Commit message determines version
# CI automatically bumps to 3.3.0
```

### 4. Pushing Without PR (Old Way)

**What they try:**
```bash
git push origin main
```

**What happens:**
```
✗ Branch protection prevents direct push
✗ Error: protected branch hook declined
```

**Framework guides them:**
```bash
git push origin feature/PROJ-123-my-feature
gh pr create  # Creates PR with template
```

### 5. Merging Without Squash (Old Way)

**What they try:**
```bash
git merge feature-branch
```

**What happens:**
```
✗ Creates messy history
✗ Multiple commits pollute changelog
✗ Semantic-release gets confused
```

**Framework guides them:**
```
# GitHub PR UI enforces squash-merge
# PR title becomes the commit message
# Single clean commit for semantic-release
```

## Manual Actions That Break Automation

### Critical Antipatterns:
• **Manually editing VERSION or version fields**
• **Bypassing hooks with --no-verify**  
• **Direct pushes to main/develop branches**
• **Cherry-picking between branches**
• **Manually creating tags**
• **Editing CHANGELOG.md directly**
• **Force pushing to shared branches**
• **Merging without squash on PR**
• **Creating releases on GitHub manually**
• **Modifying .releaserc.json or semantic config**

### How We Prevent Them:

• **Version edits** → Pre-commit hook detects and warns
• **--no-verify** → CI/CD validation catches it  
• **Direct main push** → Branch protection rules
• **Manual tags** → CI overwrites with correct tags
• **Changelog edits** → File is marked as managed by semantic-release
• **Force push** → Branch protection prevents it
• **Manual releases** → Only CI has release permissions
• **Config changes** → Require PR review

## Developer Onboarding Checklist

```bash
# First time setup (one command)
./scripts/dev-helper.sh
# Select: "15) Setup git aliases"

# Now developers can use:
git feature my-feature     # Creates feature/my-feature
git fix my-bugfix          # Creates fix/my-bugfix  
git commit-feat            # Interactive feat commit
git commit-fix             # Interactive fix commit
git pr                     # Create PR with validation
```

## Common Scenarios & Solutions

### "I need to fix a typo"
```bash
# Old way: git commit -m "fixed typo"
# New way:
git commit -m "docs: fix typo in README"
# Result: No version bump, clean history
```

### "I need to add a feature"
```bash
# Old way: git commit -m "added login"  
# New way:
git commit -m "feat: add user login functionality"
# Result: Minor version bump (3.2.0 → 3.3.0)
```

### "I broke production!"
```bash
# Old way: Panic edit on main
# New way:
./scripts/dev-helper.sh
# Select: "Create a hotfix branch"
git commit -m "fix!: resolve critical auth bypass"
# Result: Immediate patch + tracked in changelog
```

### "Tests are failing"
```bash
# Old way: git commit -m "fixed tests"
# New way:  
git commit -m "test: fix flaky integration tests"
# Result: No version bump, but tracked
```

## Visual Workflow

```
Developer Action → Git Hook → Helper Script → CI/CD
       ↓              ↓            ↓            ↓
   git commit   → Validates  → Suggests   → Releases
   git push     → Enforces   → Guides     → Deploys
   Manual edit  → Warns      → Corrects   → Overwrites
```

## Quick Reference Card

```bash
# NEVER DO:                    # ALWAYS DO:
vim pyproject.toml            feat: your message
git push --force              fix: your message  
git commit -m "stuff"         docs: your message
git tag v3.3.0                chore: your message
edit CHANGELOG.md             test: your message

# SHORTCUTS (after setup):
git feature NAME              # Create feature/NAME
git fix NAME                  # Create fix/NAME
git commit-feat               # Interactive commit
git pr                        # Create PR properly
```