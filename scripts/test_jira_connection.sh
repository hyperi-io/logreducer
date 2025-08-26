#!/bin/bash
# Test JIRA API connection
# Usage: ./test_jira_connection.sh

echo "Testing JIRA API Connection"
echo "============================"
echo ""

# Check if environment variables are set
if [ -z "$JIRA_AUTH" ] || [ -z "$JIRA_DOMAIN" ] || [ -z "$JIRA_PROJECT" ]; then
    echo "❌ Missing environment variables!"
    echo ""
    echo "Please set:"
    echo "  export JIRA_AUTH='your-base64-auth-string'"
    echo "  export JIRA_DOMAIN='https://company.atlassian.net'"
    echo "  export JIRA_PROJECT='PROJ'"
    echo ""
    echo "Or run: python scripts/setup_jira_auth.py"
    exit 1
fi

echo "1. Testing authentication..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X GET \
    "${JIRA_DOMAIN}/rest/api/3/myself" \
    -H "Authorization: Basic ${JIRA_AUTH}" \
    -H "Accept: application/json")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "200" ]; then
    USER=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('displayName', 'Unknown'))")
    echo "✅ Authenticated as: $USER"
else
    echo "❌ Authentication failed (HTTP $HTTP_CODE)"
    echo "$BODY"
    exit 1
fi

echo ""
echo "2. Testing project access..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X GET \
    "${JIRA_DOMAIN}/rest/api/3/project/${JIRA_PROJECT}" \
    -H "Authorization: Basic ${JIRA_AUTH}" \
    -H "Accept: application/json")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "200" ]; then
    PROJECT_NAME=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('name', 'Unknown'))")
    echo "✅ Project found: $PROJECT_NAME"
else
    echo "❌ Project access failed (HTTP $HTTP_CODE)"
    echo "$BODY"
    exit 1
fi

echo ""
echo "3. Checking existing versions..."
VERSIONS=$(curl -s -X GET \
    "${JIRA_DOMAIN}/rest/api/3/project/${JIRA_PROJECT}/versions" \
    -H "Authorization: Basic ${JIRA_AUTH}" \
    -H "Accept: application/json" | \
    python3 -c "import sys, json; versions = json.load(sys.stdin); [print(f'  - {v[\"name\"]}') for v in versions[:5]]" 2>/dev/null)

if [ -n "$VERSIONS" ]; then
    echo "✅ Recent versions:"
    echo "$VERSIONS"
else
    echo "ℹ️  No versions found (this is OK for new projects)"
fi

echo ""
echo "4. Sample issue search..."
ISSUES=$(curl -s -X GET \
    "${JIRA_DOMAIN}/rest/api/3/search?jql=project=${JIRA_PROJECT}&maxResults=3" \
    -H "Authorization: Basic ${JIRA_AUTH}" \
    -H "Accept: application/json" | \
    python3 -c "import sys, json; data = json.load(sys.stdin); [print(f'  - {issue[\"key\"]}: {issue[\"fields\"][\"summary\"]}') for issue in data.get('issues', [])]" 2>/dev/null)

if [ -n "$ISSUES" ]; then
    echo "✅ Sample issues:"
    echo "$ISSUES"
else
    echo "ℹ️  No issues found (this is OK for new projects)"
fi

echo ""
echo "============================"
echo "✅ JIRA connection test complete!"
echo ""
echo "Your GitHub Secrets should be:"
echo "  JIRA_AUTH=${JIRA_AUTH:0:20}..."
echo "  JIRA_DOMAIN=${JIRA_DOMAIN}"
echo "  JIRA_PROJECT=${JIRA_PROJECT}"