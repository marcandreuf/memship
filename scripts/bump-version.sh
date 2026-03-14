#!/usr/bin/env bash
set -euo pipefail

# Bump the semantic version in the VERSION file.
# Usage: ./scripts/bump-version.sh <patch|minor|major>

VERSION_FILE="$(cd "$(dirname "$0")/.." && pwd)/VERSION"

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
  exit 1
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')

if [[ ! "$CURRENT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: Invalid version format '$CURRENT'. Expected MAJOR.MINOR.PATCH" >&2
  exit 1
fi

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "${1:-}" in
  patch)
    PATCH=$((PATCH + 1))
    ;;
  minor)
    MINOR=$((MINOR + 1))
    PATCH=0
    ;;
  major)
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    ;;
  *)
    echo "Usage: $0 <patch|minor|major>" >&2
    echo "Current version: $CURRENT" >&2
    exit 1
    ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "$CURRENT → $NEW_VERSION"
