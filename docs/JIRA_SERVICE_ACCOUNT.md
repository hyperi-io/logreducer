# JIRA Service Account Configuration

## Account Details

| Field | Value |
|-------|-------|
| Account Type | Service Account |
| Email | `automation@company.com` |
| Display Name | CI/CD Automation Bot |
| JIRA Groups | `service-accounts` |
| Created By | [Your Name] |
| Created Date | [Date] |
| Purpose | Automated release management via GitHub Actions |

## Permissions

### Project-Level Permissions
- ✅ Browse Projects
- ✅ Create Issues
- ✅ Edit Issues
- ✅ Add Comments
- ✅ Transition Issues
- ✅ Manage Versions
- ❌ Delete Issues
- ❌ Administer Project

### What This Account Can Do
1. Read all issues in configured projects
2. Update Fix Version field on issues
3. Add comments with release notes
4. Create new versions for releases
5. Transition issues through workflow

### What This Account CANNOT Do
1. Delete any data
2. Modify project settings
3. Add/remove users
4. Access administrative functions

## API Token Management

### Current Tokens
| Token Name | Created | Last Used | Purpose |
|------------|---------|-----------|---------|
| GitHub-Integration-Prod | [Date] | Active | Production releases |
| GitHub-Integration-Test | [Date] | Active | Test environment |

### Rotation Schedule
- Tokens rotated every 90 days
- Next rotation: [Date]
- Rotation performed by: JIRA Admin team

## GitHub Integration

### GitHub Secrets Required
```bash
JIRA_AUTH    = [base64 encoded email:token]
JIRA_DOMAIN  = https://company.atlassian.net
JIRA_PROJECT = PROJ
JIRA_EMAIL   = automation@company.com
```

### How to Generate JIRA_AUTH
```bash
echo -n "automation@company.com:API_TOKEN_HERE" | base64
```

## Monitoring

### Audit Log
- All actions logged in JIRA Audit Log
- Filter by: User = "CI/CD Automation Bot"
- Review weekly for unusual activity

### Usage Metrics
- Average updates per release: ~10-20 issues
- Versions created per month: ~5-10
- API calls per day: <1000 (well within limits)

## Access Management

### Who Has Access
- GitHub Actions (via secrets)
- DevOps team (emergency access)
- JIRA Admins (management)

### Password/Token Storage
- API Token: GitHub Secrets (encrypted)
- Account Password: Team password manager
- Recovery: JIRA Admin team

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Check group membership
   - Verify project permissions
   - Ensure token not expired

2. **Cannot Create Versions**
   - Need "Administer Project" or custom permission
   - Check project role

3. **API Rate Limits**
   - Current limit: 5000 requests/hour
   - If hit, implement caching

### Emergency Procedures

If compromised:
1. Immediately revoke all API tokens
2. Reset account password  
3. Audit recent activities
4. Generate new tokens
5. Update GitHub secrets

## Contact

- **Account Owner**: JIRA Admin Team
- **Technical Contact**: [Your Name]
- **Escalation**: [Manager Name]

## Appendix: Setup Commands

### Test Connection
```bash
curl -X GET \
  "https://company.atlassian.net/rest/api/3/myself" \
  -H "Authorization: Basic [BASE64_AUTH]" \
  -H "Accept: application/json"
```

### Create Version
```bash
curl -X POST \
  "https://company.atlassian.net/rest/api/3/version" \
  -H "Authorization: Basic [BASE64_AUTH]" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "3.2.2",
    "project": "PROJ",
    "released": true
  }'
```