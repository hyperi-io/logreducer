# GitHub Actions Workflows

## [WARN] IMPORTANT: This Project Uses LOCAL CI/CD

**99% of CI/CD runs locally on your machine, NOT in GitHub Actions!**

The ONLY exception is JFrog Artifactory deployment which uses GitHub Actions for secure credential handling.

## Active Workflow (Only One!)

### `deploy-jfrog.yml` - JFrog Artifactory Deployment
- **Purpose**: Deploy packages to JFrog Artifactory using secure credentials
- **Trigger**: Manual only (workflow_dispatch)
- **When to use**: After running `make ci` locally and confirming all tests pass
- **Environments**: production, staging, test
- **Repository**: https://hyperi.jfrog.io/artifactory/api/pypi/hyperi-pypi-local/

## How to Deploy to JFrog

1. **Run CI locally first**:
   ```bash
   make ci
   # or
   make ci-fast  # skip slow tests
   ```

2. **Deploy via GitHub Actions**:
   ```bash
   gh workflow run deploy-jfrog.yml \
     -f deploy_environment=production
   ```

   Or use GitHub UI:
   - Go to Actions tab
   - Select "Deploy to JFrog Artifactory (Manual Only)"
   - Click "Run workflow"
   - Select environment
   - Click "Run workflow" button

## Required Secrets

Set these in Settings -> Secrets and variables -> Actions -> Secrets:

| Secret | Description |
|--------|-------------|
| `ARTIFACTORY_USERNAME` | JFrog username |
| `ARTIFACTORY_PASSWORD` | JFrog API token/password |

## Disabled Workflows

All other workflows are DISABLED and stored in `.github/workflows-disabled/`:
- `ci.yml` - Old full CI (replaced by local CI)
- `ci-minimal.yml` - Minimal CI wrapper (not needed)
- `pr-validation.yml` - PR checks (run locally)
- `release-python.yml` - Semantic release (run locally)
- `security.yml` - Security scanning (run locally)
- etc.

These files are kept for reference but DO NOT execute.

## Why Local CI?

| Aspect | GitHub Actions | Local CI |
|--------|---------------|----------|
| **Speed** | 5-10 min wait | Instant |
| **Cost** | Uses minutes/money | Free |
| **Privacy** | Code in cloud | Stays local |
| **Debugging** | Via artifacts | Direct access |
| **Control** | Limited | Complete |

## Local CI Commands

```bash
# Full CI pipeline
make ci

# Fast CI (no slow tests)
make ci-fast

# Individual stages
scripts/local-ci --stage test
scripts/local-ci --stage lint
scripts/local-ci --stage security
scripts/local-ci --stage build

# With custom settings
MIN_SECURITY_LEVEL=LOW make ci
```

## FAQ

### Q: Why is nothing happening when I push?
A: That's correct! CI runs locally, not on push. Run `make ci` before pushing.

### Q: How do I run CI?
A: Locally with `make ci` or `scripts/local-ci`

### Q: Where are the CI logs?
A: In your terminal and `.tmp/logs/local-ci.log`

### Q: How do I deploy to JFrog?
A: Run CI locally first, then trigger the GitHub Action manually

### Q: Can I enable GitHub Actions CI?
A: No, this project is configured for local CI only. The disabled workflows are for reference.

### Q: What about pull requests?
A: Run `make ci` locally before creating a PR

## Troubleshooting

### JFrog Deployment Fails

1. Check secrets are set:
   ```bash
   gh secret list
   ```

2. Check workflow logs:
   ```bash
   gh run list --workflow=deploy-jfrog.yml
   gh run view <run-id>
   ```

3. Test repository access:
   ```bash
   # This won't work locally (credentials are in GitHub Secrets)
   # Use the GitHub Action instead
   ```

### Need to Re-enable a Workflow?

If you absolutely need to re-enable a workflow:
```bash
mv .github/workflows-disabled/workflow-name.yml .github/workflows/
```

But consider: Can this be done locally instead?

## Summary

- **Local CI**: Everything except JFrog deployment
- **GitHub Actions**: ONLY for JFrog deployment with secure credentials
- **Disabled workflows**: Stored in `.github/workflows-disabled/` for reference
- **Speed**: Local CI is 5-10x faster than GitHub Actions
- **Cost**: $0 (no GitHub Actions minutes used)