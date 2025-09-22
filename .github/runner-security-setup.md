# Self-Hosted Runner Security Guide

## [SECURE] Critical Security Measures

### 1. **NEVER Use on Public Repositories**
[WARN] **CRITICAL**: Self-hosted runners on public repos can be used by ANYONE who forks and opens a PR!

### 2. **Repository-Specific Runner (Recommended)**
Instead of organization-wide, tie the runner to ONLY this specific repository:
```bash
# When configuring, use repository URL, not organization
./config.sh --url https://github.com/hypersec-io/logreducer
```

### 3. **Restrict Who Can Trigger Workflows**

#### Option A: Require Approval for External Contributors
Go to: **Settings -> Actions -> General**
- Set "Fork pull request workflows from outside collaborators" to:
  **"Require approval for all outside collaborators"**

#### Option B: Disable PR Runs Completely
Modify workflows to only run on push to protected branches:
```yaml
on:
  push:
    branches: [main]  # Remove pull_request trigger
```

### 4. **Use Labels to Control Runner Selection**
Configure your runner with a unique label:
```bash
./config.sh --labels "self-hosted,linux,trusted-runner-derek"
```

Then in workflows, explicitly require that label:
```yaml
runs-on: [self-hosted, linux, trusted-runner-derek]
```

### 5. **Run Runner in Isolated Environment**

#### Docker Container Isolation
```bash
# Create isolated runner container
docker run -d \
  --name github-runner \
  --restart unless-stopped \
  -e RUNNER_NAME="isolated-runner" \
  -e GITHUB_TOKEN="YOUR_TOKEN" \
  -e RUNNER_WORKDIR="_work" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  myoung34/github-runner:latest
```

#### Or Use Virtual Machine
Run the runner in a VM that can be easily reset/destroyed if compromised.

### 6. **Implement Branch Protection Rules**
Go to: **Settings -> Branches -> Add rule**
- Require pull request reviews before merging
- Dismiss stale PR approvals when new commits are pushed
- Require review from CODEOWNERS
- Include administrators

### 7. **Create CODEOWNERS File**
```bash
# .github/CODEOWNERS
# Protect workflow files - only you can approve changes
.github/workflows/ @YOUR_GITHUB_USERNAME
.github/runner-* @YOUR_GITHUB_USERNAME
scripts/setup_github_runner.sh @YOUR_GITHUB_USERNAME
```

### 8. **Monitor Runner Activity**

#### Create Monitoring Workflow
```yaml
name: Runner Activity Monitor
on:
  workflow_run:
    workflows: ["*"]
    types: [requested]

jobs:
  log-activity:
    runs-on: ubuntu-latest  # Use GitHub hosted for monitoring
    steps:
      - name: Log runner usage
        run: |
          echo "Workflow: ${{ github.event.workflow.name }}"
          echo "Actor: ${{ github.actor }}"
          echo "Trigger: ${{ github.event.workflow_run.event }}"
          
      - name: Alert on suspicious activity
        if: github.actor != 'YOUR_USERNAME' && github.actor != 'dependabot[bot]'
        run: |
          echo "[WARN] ALERT: Non-owner triggered self-hosted runner!"
          # Send alert to your email/Slack
```

### 9. **Restrict Secrets Access**
Create separate environments for self-hosted vs GitHub-hosted:
1. Go to: **Settings -> Environments**
2. Create "self-hosted" environment
3. Add protection rules:
   - Required reviewers: YOU
   - Restrict to specific branches: main only

### 10. **Regular Security Practices**
- Review workflow changes in PRs carefully
- Rotate runner token regularly
- Check runner logs: `journalctl -u github-runner -f`
- Update runner software regularly

## ?? Maximum Security Setup (Paranoid Mode)

### Create a Restricted Runner Script
```bash
#!/bin/bash
# /home/runner/secure-runner.sh

# Run in isolated namespace
unshare --mount --uts --ipc --pid --fork \
  --user --map-root-user \
  ./run.sh
```

### Use systemd Security Features
```ini
# /etc/systemd/system/github-runner.service
[Service]
# Security restrictions
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
NoNewPrivileges=yes
ReadWritePaths=/home/runner/github-runner/_work
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
```

## ? Emergency Kill Switch

### Create Quick Disable Script
```bash
#!/bin/bash
# ~/emergency-stop-runner.sh

# Stop runner immediately
sudo systemctl stop github-runner

# Remove from GitHub
cd ~/github-runner
./config.sh remove --token YOUR_REMOVAL_TOKEN

# Disable service
sudo systemctl disable github-runner

echo "Runner emergency stopped and removed!"
```

## ? Audit Script
```bash
#!/bin/bash
# Check who's been using your runner

gh api /repos/hypersec-io/logreducer/actions/runs \
  --jq '.workflow_runs[] | 
    select(.runner_name == "logreducer-local") | 
    {actor: .actor.login, workflow: .name, created: .created_at}'
```

## ?? Recommended Configuration

1. **Use separate GitHub account** for runner if possible
2. **Enable 2FA** on your GitHub account
3. **Use fine-grained PAT** with minimal permissions
4. **Run on dedicated user account** not your main user
5. **Set up log monitoring** to detect unusual activity

## ? Signs of Compromise
Watch for:
- Unexpected CPU/memory usage
- Unknown processes running
- Modified files outside _work directory
- Unusual network connections
- Workflow runs you didn't trigger

## Quick Security Check Command
```bash
# Run this periodically
ps aux | grep -v "runner\|github" | grep -E "curl|wget|nc|python|perl"
```