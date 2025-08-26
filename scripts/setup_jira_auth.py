#!/usr/bin/env python3
"""
Helper script to set up JIRA API authentication for GitHub Secrets
"""

import base64
import sys
import getpass
import json
import urllib.request
import urllib.error


def create_auth_string(email, token):
    """Create base64 encoded auth string"""
    auth_str = f"{email}:{token}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    return encoded


def test_jira_connection(domain, auth_string):
    """Test JIRA API connection"""
    url = f"{domain}/rest/api/3/myself"
    
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Basic {auth_string}")
    request.add_header("Accept", "application/json")
    
    try:
        response = urllib.request.urlopen(request)
        data = json.loads(response.read())
        return True, data.get('displayName', 'Unknown')
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Authentication failed - check email and token"
        elif e.code == 404:
            return False, "API endpoint not found - check domain"
        else:
            return False, f"HTTP Error {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("JIRA API Token Setup for GitHub Secrets")
    print("=" * 60)
    print()
    
    # Collect information
    print("Step 1: Enter your JIRA information")
    print("-" * 40)
    
    domain = input("JIRA Domain (e.g., https://company.atlassian.net): ").strip()
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    
    email = input("JIRA Email: ").strip()
    
    print("\nPaste your API token from https://id.atlassian.com/manage-profile/security/api-tokens")
    token = getpass.getpass("API Token (hidden): ").strip()
    
    project = input("JIRA Project Key (e.g., PROJ): ").strip().upper()
    
    # Create auth string
    print("\n" + "=" * 60)
    print("Step 2: Generating Authentication String")
    print("-" * 40)
    
    auth_string = create_auth_string(email, token)
    
    # Test connection
    print("\nTesting JIRA connection...")
    success, message = test_jira_connection(domain, auth_string)
    
    if success:
        print(f"✅ Successfully connected as: {message}")
    else:
        print(f"❌ Connection failed: {message}")
        print("\nPlease check your credentials and try again.")
        sys.exit(1)
    
    # Display results
    print("\n" + "=" * 60)
    print("Step 3: GitHub Secrets Configuration")
    print("-" * 40)
    print("\nAdd these secrets to your GitHub repository:")
    print("(Settings → Secrets and variables → Actions → New repository secret)")
    print()
    
    print("SECRET NAME: JIRA_AUTH")
    print(f"SECRET VALUE: {auth_string}")
    print()
    
    print("SECRET NAME: JIRA_DOMAIN")
    print(f"SECRET VALUE: {domain}")
    print()
    
    print("SECRET NAME: JIRA_PROJECT")
    print(f"SECRET VALUE: {project}")
    print()
    
    print("SECRET NAME: JIRA_EMAIL")
    print(f"SECRET VALUE: {email}")
    print()
    
    # Generate test command
    print("=" * 60)
    print("Step 4: Test Command (run this to verify)")
    print("-" * 40)
    print(f"""
curl -X GET \\
  "{domain}/rest/api/3/project/{project}" \\
  -H "Authorization: Basic {auth_string}" \\
  -H "Accept: application/json" | python3 -m json.tool
""")
    
    print("\n✅ Setup complete! Now add the secrets to GitHub.")


if __name__ == "__main__":
    main()