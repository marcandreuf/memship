#!/usr/bin/env bash
#
# Release a validated commit by creating and pushing an annotated version tag.
#
# Git tags are the single source of truth for the version — there is no VERSION file.
# Pushing the tag triggers the Release workflow, which PROMOTES the release-candidate
# image already built for this commit (and validated on staging) to :X.Y.Z + :latest
# without rebuilding. Run this only after staging has validated the commit.
#
# Usage:
#   ./scripts/release.sh <version> [commit-ish]
#
# Examples:
#   ./scripts/release.sh 1.3.0            # tag current HEAD
#   ./scripts/release.sh 1.3.0 abc1234    # tag a specific validated commit
#
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

VERSION="${1:-}"
COMMIT="${2:-HEAD}"

if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version> [commit-ish]" >&2
  echo "Latest tag: $(git describe --tags --abbrev=0 2>/dev/null || echo 'none')" >&2
  exit 1
fi

# Accept either "1.3.0" or "v1.3.0"; normalise to bare semver.
VERSION="${VERSION#v}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo -e "${RED}Invalid version '$VERSION' (expected X.Y.Z)${NC}" >&2
  exit 1
fi
TAG="v$VERSION"

# The tag must point at a real commit.
SHA="$(git rev-parse --verify "${COMMIT}^{commit}" 2>/dev/null)" || {
  echo -e "${RED}Not a valid commit: $COMMIT${NC}" >&2
  exit 1
}

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo -e "${RED}Tag $TAG already exists.${NC} Releases are immutable — bump the version." >&2
  exit 1
fi

# Mirror the CI release-table guard locally so failures surface before the push, not after.
if ! grep -qF "| v$VERSION " README.md; then
  echo -e "${YELLOW}Warning: v$VERSION is not in the README.md release table.${NC}"
  echo -e "${YELLOW}The Release workflow enforces this and will fail. Add the row first.${NC}"
  read -r -p "Continue anyway? [y/N]: " ok
  [[ "$ok" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

# Warn if releasing a commit that is not on the main branch (staging validates main).
if ! git merge-base --is-ancestor "$SHA" origin/main 2>/dev/null; then
  echo -e "${YELLOW}Warning: ${SHA:0:12} is not on origin/main.${NC}"
  echo -e "${YELLOW}Staging validates main; releasing off-main skips that gate.${NC}"
  read -r -p "Continue anyway? [y/N]: " ok
  [[ "$ok" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

echo -e "${GREEN}Tagging ${SHA:0:12} as $TAG${NC}"
git tag -a "$TAG" "$SHA" -m "Release $TAG"
git push origin "$TAG"

echo ""
echo -e "${GREEN}Pushed $TAG.${NC} The Release workflow will promote the images to :$VERSION + :latest."
