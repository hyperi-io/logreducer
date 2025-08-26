# JIRA OAuth 2.0 Setup for Auto-Renewing Tokens

## Why OAuth Instead of API Tokens?

- ✅ **Auto-renewable** - Refresh tokens last forever if used
- ✅ **More secure** - Short-lived access tokens (1 hour)
- ✅ **No manual rotation** - Fully automated
- ✅ **Audit trail** - OAuth apps have better logging

## Step 1: Create OAuth 2.0 App

1. Go to: https://developer.atlassian.com/console/myapps/
2. Click **"Create app"**
3. Name: `LogReducer CI/CD Integration`
4. Click **"OAuth 2.0 integration"**

## Step 2: Configure OAuth Settings

### App Details
```
App name: LogReducer CI/CD
App description: Automated JIRA updates from GitHub releases
App type: OAuth 2.0 (3LO)
```

### Permissions (Scopes)
```
Classic Scopes:
✅ read:jira-work
✅ write:jira-work  
✅ manage:jira-project

Granular Scopes:
✅ read:issue:jira
✅ write:issue:jira
✅ read:project:jira
✅ write:project.version:jira
✅ write:comment:jira
```

### Callback URL
```
https://github.com/hypersec-io/logreducer/settings/secrets/actions
```
(Or use `http://localhost:8080/callback` for initial setup)

## Step 3: Get Initial Tokens

### 3.1 Get Authorization Code
```bash
# Open in browser (replace CLIENT_ID)
https://auth.atlassian.com/authorize?
  audience=api.atlassian.com&
  client_id=YOUR_CLIENT_ID&
  scope=read:jira-work%20write:jira-work%20manage:jira-project&
  redirect_uri=http://localhost:8080/callback&
  state=YOUR_STATE&
  response_type=code&
  prompt=consent
```

### 3.2 Exchange for Tokens
```bash
curl -X POST https://auth.atlassian.com/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "code": "AUTH_CODE_FROM_CALLBACK",
    "redirect_uri": "http://localhost:8080/callback"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGc...",  // Use for 1 hour
  "refresh_token": "eyJhbGc...", // Save this! Lasts forever if used
  "expires_in": 3600,
  "scope": "read:jira-work write:jira-work"
}
```

## Step 4: Add to GitHub Secrets

| Secret Name | Value |
|------------|-------|
| `JIRA_CLIENT_ID` | Your OAuth app Client ID |
| `JIRA_CLIENT_SECRET` | Your OAuth app Client Secret |
| `JIRA_REFRESH_TOKEN` | The refresh_token from Step 3 |
| `JIRA_CLOUD_ID` | Your Atlassian Cloud ID |

Get Cloud ID:
```bash
curl https://api.atlassian.com/oauth/token/accessible-resources \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

## Step 5: Update Release Workflow

```yaml
name: Update JIRA with OAuth

on:
  release:
    types: [published]

jobs:
  update-jira:
    runs-on: ubuntu-latest
    steps:
    - name: Get Fresh Token
      id: token
      run: |
        # Refresh the token
        RESPONSE=$(curl -X POST \
          "https://auth.atlassian.com/oauth/token" \
          -H "Content-Type: application/json" \
          -d "{
            \"grant_type\": \"refresh_token\",
            \"client_id\": \"${{ secrets.JIRA_CLIENT_ID }}\",
            \"client_secret\": \"${{ secrets.JIRA_CLIENT_SECRET }}\",
            \"refresh_token\": \"${{ secrets.JIRA_REFRESH_TOKEN }}\"
          }")
        
        ACCESS_TOKEN=$(echo $RESPONSE | jq -r '.access_token')
        echo "::add-mask::$ACCESS_TOKEN"
        echo "token=$ACCESS_TOKEN" >> $GITHUB_OUTPUT
    
    - name: Update JIRA Issues
      run: |
        curl -X PUT \
          "https://api.atlassian.com/ex/jira/${{ secrets.JIRA_CLOUD_ID }}/rest/api/3/issue/PROJ-123" \
          -H "Authorization: Bearer ${{ steps.token.outputs.token }}" \
          -H "Content-Type: application/json" \
          -d '{"fields": {"fixVersions": [{"name": "3.2.2"}]}}'
```

## Step 6: Auto-Renewal Workflow

The refresh token workflow runs daily to keep tokens fresh:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

This ensures:
- Access tokens are always fresh (renewed daily)
- Refresh tokens never expire (used regularly)
- No manual intervention needed

## Security Best Practices

1. **Minimal Scopes**: Only request needed permissions
2. **Token Masking**: Use `::add-mask::` in workflows
3. **Secure Storage**: Only in GitHub Secrets
4. **Audit Logging**: Review OAuth app activity monthly
5. **Rotation Alert**: Create issues for any manual steps

## Testing

```bash
# Test with fresh token
curl -X GET \
  "https://api.atlassian.com/ex/jira/YOUR_CLOUD_ID/rest/api/3/myself" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Troubleshooting

### Token Expired
- The automation should prevent this
- If it happens, manually refresh once
- Check the daily workflow is running

### Permission Denied
- Verify OAuth scopes
- Check user has project access
- Ensure Cloud ID is correct

### Refresh Failed
- Refresh tokens can expire if unused for 90 days
- Re-authorize manually if needed

## Benefits Over API Tokens

| Feature | API Tokens | OAuth 2.0 |
|---------|-----------|-----------|
| Auto-renew | ❌ Manual | ✅ Automatic |
| Expiration | 1 year max | Never (with refresh) |
| Security | Long-lived | Short-lived tokens |
| Audit | Basic | Detailed app logs |
| Management | Per user | Per app |
| Revocation | Manual | Centralized |