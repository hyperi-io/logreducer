#!/bin/bash

# Developer Helper Script
# Interactive tool to help developers work with the automated release system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -E '^CICD_ENTITY=' "$PROJECT_ROOT/.env" | xargs)
fi

# Set default entity name if not configured
CICD_ENTITY=${CICD_ENTITY:-"HyperSec"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Helper functions
print_header() {
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository!"
    exit 1
fi

# Main menu
show_menu() {
    clear
    print_header "${CICD_ENTITY} Developer Helper"
    echo ""
    echo "What would you like to do?"
    echo ""
    echo -e "${BOLD}Branch Management:${NC}"
    echo "  1) Create a new feature branch"
    echo "  2) Create a bug fix branch"
    echo "  3) Create a hotfix branch"
    echo "  4) Create a release branch"
    echo "  5) Validate current branch name"
    echo ""
    echo -e "${BOLD}Commit Management:${NC}"
    echo "  6) Create a commit (interactive)"
    echo "  7) Validate commit message"
    echo "  8) Amend last commit message"
    echo ""
    echo -e "${BOLD}Release Management:${NC}"
    echo "  9) Check what version will be released"
    echo "  10) Manually bump version (NOT recommended)"
    echo "  11) View recent releases"
    echo ""
    echo -e "${BOLD}Help & Info:${NC}"
    echo "  12) Show version bump rules"
    echo "  13) Show branch naming conventions"
    echo "  14) Show commit message examples"
    echo "  15) Setup git aliases"
    echo ""
    echo "  0) Exit"
    echo ""
}

# Create branch with validation
create_branch() {
    local branch_type=$1
    local prefix=$2
    
    echo -e "${BOLD}Creating $branch_type branch${NC}"
    echo ""
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        print_warning "You have uncommitted changes. Commit or stash them first."
        echo ""
        echo "Options:"
        echo "  1) Stash changes and continue"
        echo "  2) Cancel"
        read -p "Choice [1-2]: " choice
        
        if [ "$choice" = "1" ]; then
            git stash push -m "Auto-stash before creating $branch_type branch"
            print_success "Changes stashed"
        else
            return
        fi
    fi
    
    # Get JIRA ticket (optional)
    echo ""
    read -p "JIRA ticket number (optional, e.g., PROJ-123): " jira_ticket
    
    # Get description
    echo ""
    echo "Enter a brief description (lowercase, use-hyphens):"
    read -p "Description: " description
    
    # Clean and validate description
    description=$(echo "$description" | tr '[:upper:]' '[:lower:]' | tr ' _' '--')
    
    # Build branch name
    if [ -n "$jira_ticket" ]; then
        branch_name="${prefix}/${jira_ticket}-${description}"
    else
        branch_name="${prefix}/${description}"
    fi
    
    # Validate branch name
    echo ""
    echo "Branch name will be: ${BOLD}$branch_name${NC}"
    
    # Test with branch-name-lint
    if command -v npx > /dev/null; then
        # Create temp repo to test branch name
        temp_dir=$(mktemp -d)
        cd "$temp_dir"
        git init -q
        git checkout -q -b "$branch_name"
        
        if npx branch-name-lint "$PROJECT_ROOT/.branchlintrc.json" 2>/dev/null; then
            print_success "Branch name is valid"
        else
            print_error "Branch name validation failed!"
            cd "$PROJECT_ROOT"
            rm -rf "$temp_dir"
            return
        fi
        
        cd "$PROJECT_ROOT"
        rm -rf "$temp_dir"
    fi
    
    read -p "Create branch? [y/N]: " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        git checkout -b "$branch_name"
        print_success "Created and switched to branch: $branch_name"
        
        echo ""
        print_info "Next steps:"
        echo "  1. Make your changes"
        echo "  2. Use 'git add <files>' to stage changes"
        echo "  3. Run this script option 6 to create a proper commit"
        echo "  4. Push with 'git push -u origin $branch_name'"
    fi
}

# Interactive commit creator
create_commit() {
    print_header "Interactive Commit Creator"
    
    # Check for staged changes
    if ! git diff --cached --quiet; then
        print_success "Found staged changes"
    else
        print_warning "No staged changes found"
        echo ""
        git status --short
        echo ""
        read -p "Stage all changes? [y/N]: " stage_all
        if [ "$stage_all" = "y" ] || [ "$stage_all" = "Y" ]; then
            git add -A
            print_success "All changes staged"
        else
            echo "Please stage your changes first with 'git add'"
            return
        fi
    fi
    
    echo ""
    echo "Select commit type:"
    echo "  1) feat     - New feature (minor version bump)"
    echo "  2) fix      - Bug fix (patch version bump)"
    echo "  3) docs     - Documentation only (no version bump)"
    echo "  4) style    - Code formatting (no version bump)"
    echo "  5) refactor - Code refactoring (no version bump)"
    echo "  6) perf     - Performance improvement (patch version bump)"
    echo "  7) test     - Test changes (no version bump)"
    echo "  8) chore    - Maintenance (no version bump)"
    echo "  9) ci       - CI/CD changes (no version bump)"
    echo "  10) build   - Build system changes (no version bump)"
    
    read -p "Type [1-10]: " type_choice
    
    case $type_choice in
        1) type="feat" ;;
        2) type="fix" ;;
        3) type="docs" ;;
        4) type="style" ;;
        5) type="refactor" ;;
        6) type="perf" ;;
        7) type="test" ;;
        8) type="chore" ;;
        9) type="ci" ;;
        10) type="build" ;;
        *) print_error "Invalid choice"; return ;;
    esac
    
    # Optional scope
    echo ""
    read -p "Scope (optional, e.g., api, cli, core): " scope
    
    # Get description
    echo ""
    echo "Enter a brief description (imperative mood, lowercase):"
    echo "Example: add prometheus metrics support"
    read -p "Description: " description
    
    # Breaking change?
    echo ""
    read -p "Is this a BREAKING CHANGE? [y/N]: " breaking
    
    # Build commit message
    if [ -n "$scope" ]; then
        if [ "$breaking" = "y" ] || [ "$breaking" = "Y" ]; then
            commit_msg="${type}(${scope})!: ${description}"
        else
            commit_msg="${type}(${scope}): ${description}"
        fi
    else
        if [ "$breaking" = "y" ] || [ "$breaking" = "Y" ]; then
            commit_msg="${type}!: ${description}"
        else
            commit_msg="${type}: ${description}"
        fi
    fi
    
    # Optional body
    echo ""
    read -p "Add detailed description? [y/N]: " add_body
    
    if [ "$add_body" = "y" ] || [ "$add_body" = "Y" ]; then
        echo "Enter description (press Ctrl+D when done):"
        body=$(cat)
        commit_msg="${commit_msg}

${body}"
    fi
    
    # JIRA references
    echo ""
    read -p "JIRA ticket references (e.g., PROJ-123, PROJ-456): " jira_refs
    
    if [ -n "$jira_refs" ]; then
        commit_msg="${commit_msg}

Refs: ${jira_refs}"
    fi
    
    # Show preview
    echo ""
    echo -e "${BOLD}Commit message preview:${NC}"
    echo "────────────────────────"
    echo "$commit_msg"
    echo "────────────────────────"
    
    # Version impact
    echo ""
    if [ "$type" = "feat" ]; then
        if [ "$breaking" = "y" ] || [ "$breaking" = "Y" ]; then
            print_warning "This will trigger a MAJOR version bump (e.g., 1.0.0 → 2.0.0)"
        else
            print_info "This will trigger a MINOR version bump (e.g., 1.0.0 → 1.1.0)"
        fi
    elif [ "$type" = "fix" ] || [ "$type" = "perf" ]; then
        print_info "This will trigger a PATCH version bump (e.g., 1.0.0 → 1.0.1)"
    else
        print_info "This will NOT trigger a version bump"
    fi
    
    echo ""
    read -p "Create commit? [y/N]: " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        git commit -m "$commit_msg"
        if [ $? -eq 0 ]; then
            print_success "Commit created successfully!"
        else
            print_error "Commit failed - check the error message above"
        fi
    fi
}

# Show version bump rules
show_version_rules() {
    print_header "Version Bump Rules"
    echo ""
    echo -e "${BOLD}${CICD_ENTITY} Automatic Version Bumps:${NC}"
    echo ""
    echo "  ${GREEN}MAJOR${NC} (1.0.0 → 2.0.0) - Breaking changes:"
    echo "    • feat!: description"
    echo "    • fix!: description"
    echo "    • Any commit with 'BREAKING CHANGE:' in body"
    echo ""
    echo "  ${YELLOW}MINOR${NC} (1.0.0 → 1.1.0) - New features:"
    echo "    • feat: description"
    echo ""
    echo "  ${BLUE}PATCH${NC} (1.0.0 → 1.0.1) - Fixes & improvements:"
    echo "    • fix: description"
    echo "    • perf: description"
    echo ""
    echo "  ${MAGENTA}NO BUMP${NC} - Non-functional changes:"
    echo "    • docs: documentation changes"
    echo "    • style: code formatting"
    echo "    • refactor: code restructuring"
    echo "    • test: test changes"
    echo "    • chore: maintenance tasks"
    echo "    • ci: CI/CD changes"
    echo "    • build: build system changes"
    echo ""
    echo -e "${BOLD}Current version:${NC} $(cat VERSION 2>/dev/null || echo 'unknown')"
}

# Show branch naming conventions
show_branch_conventions() {
    print_header "${CICD_ENTITY} Branch Naming Conventions"
    echo ""
    echo -e "${BOLD}Format:${NC} {type}/{description} or {type}/{JIRA-ID}-{description}"
    echo ""
    echo -e "${BOLD}Valid Types:${NC}"
    echo "  • feature  - New features"
    echo "  • fix      - Bug fixes"
    echo "  • hotfix   - Urgent production fixes"
    echo "  • release  - Release preparation"
    echo "  • docs     - Documentation updates"
    echo "  • chore    - Maintenance tasks"
    echo "  • test     - Test improvements"
    echo "  • refactor - Code refactoring"
    echo "  • perf     - Performance improvements"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  ✅ feature/add-prometheus-metrics"
    echo "  ✅ feature/PROJ-123-add-api-endpoint"
    echo "  ✅ fix/memory-leak"
    echo "  ✅ hotfix/critical-security-patch"
    echo "  ✅ release/1.2.0"
    echo ""
    echo -e "${BOLD}Rules:${NC}"
    echo "  • Use lowercase only"
    echo "  • Use hyphens, not underscores"
    echo "  • Keep under 60 characters"
    echo "  • Be descriptive but concise"
}

# Setup git aliases
setup_aliases() {
    print_header "Setting Up Git Aliases for ${CICD_ENTITY}"
    echo ""
    echo "This will add helpful git aliases for the ${CICD_ENTITY} automated workflow:"
    echo ""
    
    aliases=(
        "feat:git commit -m 'feat: ':Create a feature commit"
        "fix:git commit -m 'fix: ':Create a fix commit"
        "docs:git commit -m 'docs: ':Create a docs commit"
        "chore:git commit -m 'chore: ':Create a chore commit"
        "branch-feat:git checkout -b feature/:Create feature branch"
        "branch-fix:git checkout -b fix/:Create fix branch"
        "validate:npx branch-name-lint .branchlintrc.json:Validate branch name"
        "release-dry:npm run release:dry-run:Test semantic release"
        "version:cat VERSION:Show current version"
    )
    
    for alias_def in "${aliases[@]}"; do
        IFS=':' read -r alias_name alias_cmd alias_desc <<< "$alias_def"
        echo "  ${BOLD}git $alias_name${NC}"
        echo "    → $alias_desc"
        echo "    Command: $alias_cmd"
        echo ""
    done
    
    read -p "Install these aliases? [y/N]: " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        git config alias.feat "commit -m 'feat: '"
        git config alias.fix "commit -m 'fix: '"
        git config alias.docs "commit -m 'docs: '"
        git config alias.chore "commit -m 'chore: '"
        git config alias.branch-feat "checkout -b feature/"
        git config alias.branch-fix "checkout -b fix/"
        git config alias.validate "!npx branch-name-lint .branchlintrc.json"
        git config alias.release-dry "!npm run release:dry-run"
        git config alias.version "!cat VERSION"
        
        print_success "Git aliases installed!"
        echo ""
        echo "Examples:"
        echo "  git feat 'add new feature'"
        echo "  git branch-feat my-feature"
        echo "  git validate"
    fi
}

# Check version impact
check_version_impact() {
    print_header "Version Impact Analysis"
    
    current_version=$(cat VERSION 2>/dev/null || echo "unknown")
    echo "Current version: ${BOLD}$current_version${NC}"
    echo ""
    
    # Get commits since last tag
    last_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    
    if [ -z "$last_tag" ]; then
        echo "No previous releases found"
        commits=$(git log --format="%s" HEAD)
    else
        echo "Analyzing commits since $last_tag..."
        commits=$(git log --format="%s" ${last_tag}..HEAD)
    fi
    
    # Analyze commits
    has_breaking=false
    has_feat=false
    has_fix=false
    
    while IFS= read -r commit; do
        if echo "$commit" | grep -qE "^[a-z]+!:" || echo "$commit" | grep -q "BREAKING CHANGE"; then
            has_breaking=true
            echo "  💥 Breaking: $commit"
        elif echo "$commit" | grep -qE "^feat(\(.+\))?:"; then
            has_feat=true
            echo "  ✨ Feature: $commit"
        elif echo "$commit" | grep -qE "^(fix|perf)(\(.+\))?:"; then
            has_fix=true
            echo "  🐛 Fix/Perf: $commit"
        fi
    done <<< "$commits"
    
    echo ""
    echo -e "${BOLD}Next version will be:${NC}"
    
    if [ "$has_breaking" = true ]; then
        print_warning "MAJOR version bump (breaking changes detected)"
    elif [ "$has_feat" = true ]; then
        print_info "MINOR version bump (new features detected)"
    elif [ "$has_fix" = true ]; then
        print_info "PATCH version bump (fixes detected)"
    else
        print_info "No version bump (no feat/fix/perf commits)"
    fi
}

# Prevent manual version bumps
prevent_manual_version() {
    print_header "Manual Version Bump (NOT Recommended!)"
    
    print_warning "Manual version bumps are strongly discouraged!"
    echo ""
    echo "The version is automatically managed by semantic-release based on your commits."
    echo ""
    echo "If you manually change the version:"
    echo "  ❌ It will be overwritten by the next automatic release"
    echo "  ❌ It will break the changelog generation"
    echo "  ❌ It will confuse the version history"
    echo ""
    echo "Instead, you should:"
    echo "  ✅ Use proper commit messages (feat:, fix:, etc.)"
    echo "  ✅ Let semantic-release handle versioning"
    echo "  ✅ Focus on writing good code and commits"
    echo ""
    
    read -p "Still want to proceed? [y/N]: " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        print_error "Please reconsider! The automated system will overwrite your changes."
        echo ""
        echo "If you REALLY need to bump the version for testing:"
        echo "  1. Create a commit with the appropriate type:"
        echo "     • 'feat: trigger minor bump' for minor"
        echo "     • 'fix: trigger patch bump' for patch"
        echo "     • 'feat!: trigger major bump' for major"
        echo "  2. Push and let automation handle it"
    fi
}

# Main loop
while true; do
    show_menu
    read -p "Enter choice [0-15]: " choice
    
    case $choice in
        1) create_branch "feature" "feature" ;;
        2) create_branch "bug fix" "fix" ;;
        3) create_branch "hotfix" "hotfix" ;;
        4) create_branch "release" "release" ;;
        5) 
            current_branch=$(git branch --show-current)
            echo "Validating branch: $current_branch"
            npx branch-name-lint .branchlintrc.json
            ;;
        6) create_commit ;;
        7) 
            read -p "Enter commit message to validate: " msg
            echo "$msg" | npx commitlint
            ;;
        8) 
            echo "Amending last commit message..."
            git commit --amend
            ;;
        9) check_version_impact ;;
        10) prevent_manual_version ;;
        11) 
            echo "Recent releases:"
            git tag -l --sort=-version:refname | head -10
            ;;
        12) show_version_rules; read -p "Press Enter to continue..." ;;
        13) show_branch_conventions; read -p "Press Enter to continue..." ;;
        14) 
            print_header "Commit Message Examples"
            echo ""
            echo "feat: add prometheus metrics integration"
            echo "fix(parser): resolve memory leak in log processing"
            echo "docs: update API documentation"
            echo "style: format code with black"
            echo "refactor: extract validation logic to separate module"
            echo "perf: optimize pattern matching algorithm"
            echo "test: add unit tests for config module"
            echo "chore: update dependencies"
            echo "ci: fix github actions workflow"
            echo "build: update webpack configuration"
            echo ""
            echo "feat!: redesign API (breaking change)"
            echo ""
            echo "fix: resolve connection timeout issue"
            echo ""
            echo "Fixes PROJ-123, PROJ-456"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        15) setup_aliases ;;
        0) 
            print_success "Goodbye!"
            exit 0 
            ;;
        *) 
            print_error "Invalid choice"
            sleep 2
            ;;
    esac
done