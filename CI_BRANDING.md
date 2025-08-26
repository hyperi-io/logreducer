# CI/CD Entity Branding Configuration

## Overview

All CI/CD workflows, developer tools, and automation scripts support configurable entity branding to facilitate company rebranding or multi-organization deployments.

## Configuration

### Environment Variable

The entity name is controlled by the `CICD_ENTITY` environment variable:

```bash
# Default value
CICD_ENTITY=HyperSec
```

### Setting the Entity Name

#### Method 1: Local Development (.env file)

Create a `.env` file in your project root:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and set your entity name
CICD_ENTITY=YourCompany
```

#### Method 2: GitHub Repository Variables

1. Go to Settings → Secrets and variables → Actions
2. Click on "Variables" tab
3. Add a new repository variable:
   - Name: `CICD_ENTITY`
   - Value: `YourCompany`

#### Method 3: GitHub Organization Variables

For consistent branding across multiple repositories:

1. Go to Organization Settings → Secrets and variables → Actions
2. Click on "Variables" tab
3. Add a new organization variable:
   - Name: `CICD_ENTITY`
   - Value: `YourCompany`

## Where Entity Name Appears

The configured entity name appears in:

### 1. Developer Tools
- **dev-helper.sh**: Interactive menu header
- Branch creation prompts
- Git alias setup instructions
- Version bump rule descriptions

### 2. Git Hooks
- **pre-commit**: Validation messages
- **pre-push**: Check notifications
- **commit-msg**: Format validation

### 3. CI/CD Workflows
- **PR Validation**: Branch and commit validation messages
- **Security Scanning**: Report headers
- **Documentation**: Build notifications
- **Release**: Deployment messages

### 4. Output Messages
All automation messages will use the configured entity name:
- "Running {ENTITY} pre-commit checks..."
- "{ENTITY} branch name validation failed!"
- "{ENTITY} Security Scan Summary"
- "{ENTITY} Developer Helper"

## Examples

### Example 1: Rebranding to "TechCorp"

**.env file:**
```bash
CICD_ENTITY=TechCorp
```

**Result in dev-helper.sh:**
```
═══════════════════════════════════════════════
  TechCorp Developer Helper
═══════════════════════════════════════════════
```

### Example 2: Division-Specific Branding

**.env file:**
```bash
CICD_ENTITY=TechCorp-Security
```

**Result in git hooks:**
```
🔍 Running TechCorp-Security pre-commit checks...
📝 Validating commit message format for TechCorp-Security semantic release...
```

### Example 3: Project-Specific Override

**GitHub Repository Variable:**
```
CICD_ENTITY=ProjectAlpha
```

**Result in CI/CD:**
```
🔍 Validating ProjectAlpha branch name: feature/new-feature
## ProjectAlpha PR Validation Summary
# ProjectAlpha Security Scan Summary
```

## Priority Order

The entity name is resolved in this order (highest to lowest priority):

1. **GitHub Repository Variable** (`vars.CICD_ENTITY`)
2. **GitHub Organization Variable** (inherited)
3. **Local .env file** (`CICD_ENTITY`)
4. **Default value** (`HyperSec`)

## Best Practices

### 1. Consistency
Use the same entity name across all environments for consistency:
- Development (.env)
- CI/CD (GitHub variables)
- Production deployments

### 2. Short Names
Keep entity names concise for better formatting:
- ✅ Good: `TechCorp`, `AlphaSec`, `DevOps`
- ❌ Avoid: `Technology Corporation International Division`

### 3. No Special Characters
Use only alphanumeric characters and hyphens:
- ✅ Valid: `Tech-Corp`, `Alpha2`, `DevOps-Team`
- ❌ Invalid: `Tech@Corp`, `Alpha$ec`, `Dev/Ops`

### 4. Case Sensitivity
Entity names are case-sensitive and will appear exactly as configured:
- `TechCorp` → "TechCorp Developer Helper"
- `TECHCORP` → "TECHCORP Developer Helper"
- `techcorp` → "techcorp Developer Helper"

## Migration Guide

### Rebranding Steps

1. **Update GitHub Variables:**
   ```bash
   gh variable set CICD_ENTITY --body "NewCompany"
   ```

2. **Update Local Development:**
   ```bash
   echo "CICD_ENTITY=NewCompany" >> .env
   ```

3. **Verify Changes:**
   ```bash
   # Test local tools
   ./scripts/dev-helper.sh
   
   # Test git hooks
   git commit -m "test: verify rebranding"
   ```

4. **Deploy Changes:**
   - Push changes to trigger CI/CD
   - Verify new branding in workflow logs

## Troubleshooting

### Entity Name Not Updating

1. **Check .env file exists and is loaded:**
   ```bash
   cat .env | grep CICD_ENTITY
   ```

2. **Verify GitHub variable is set:**
   ```bash
   gh variable list | grep CICD_ENTITY
   ```

3. **Clear local git config cache:**
   ```bash
   git config --unset-all core.hooksPath
   git config core.hooksPath .husky
   ```

### Inconsistent Branding

If you see mixed entity names:

1. Ensure all environments use the same value
2. Check for hardcoded values in custom scripts
3. Restart terminals to reload environment variables

### CI/CD Not Using Custom Entity

1. Verify repository/organization variables in GitHub
2. Check workflow logs for entity resolution
3. Ensure workflows have latest changes

## Related Files

Files that support entity configuration:

- `.env.example` - Template with CICD_ENTITY variable
- `scripts/dev-helper.sh` - Interactive developer tool
- `.husky/pre-commit` - Pre-commit validation
- `.husky/pre-push` - Pre-push validation  
- `.husky/commit-msg` - Commit message validation
- `.github/workflows/pr-validation.yml` - PR validation
- `.github/workflows/security.yml` - Security scanning
- `.github/workflows/ci.yml` - Main CI/CD pipeline
- `.github/workflows/docs.yml` - Documentation builds
- `.github/workflows/release.yml` - Semantic release

## Support

For issues with entity configuration:

1. Check this documentation
2. Review `.env.example` for configuration options
3. Examine workflow logs for entity resolution
4. Open an issue with details about your configuration