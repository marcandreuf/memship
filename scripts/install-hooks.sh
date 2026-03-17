#!/bin/bash
# Install Memship Git Hooks
# Run this script to set up version management hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_SOURCE="$SCRIPT_DIR/git-hooks"
HOOKS_DEST="$PROJECT_ROOT/.git/hooks"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Installing Memship Git Hooks${NC}"
echo ""

if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    echo "ERROR: Not a git repository"
    exit 1
fi

for hook in "$HOOKS_SOURCE"/*; do
    if [[ -f "$hook" ]]; then
        hook_name=$(basename "$hook")
        dest="$HOOKS_DEST/$hook_name"

        if [[ -f "$dest" ]] && [[ ! "$dest" =~ \.sample$ ]]; then
            echo -e "${YELLOW}Backing up existing $hook_name to $hook_name.backup${NC}"
            mv "$dest" "$dest.backup"
        fi

        cp "$hook" "$dest"
        chmod +x "$dest"
        echo -e "${GREEN}Installed: $hook_name${NC}"
    fi
done

echo ""
echo -e "${GREEN}Git hooks installed successfully!${NC}"
echo ""
echo "Hooks will now:"
echo "  - Prompt for version bump when committing backend/ or frontend/ changes"
echo "  - Optionally create git tags for releases"
echo "  - Automatically push tags on git push"
echo ""
echo -e "${YELLOW}To uninstall, remove the hooks from .git/hooks/${NC}"
