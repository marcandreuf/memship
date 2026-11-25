#!/usr/bin/env bash
#
# A reporter sent to the issue *list* lands on existing issues and a green
# "New issue" button, with the templates that preset the label and ask for the
# right fields one unmentioned click away. The picker,
# /issues/new/choose, is where an invitation to file should point.
#
# This has now been fixed three times in three scopes: #573 did CONTRIBUTING.md,
# #585 did six admin-guide pages and said so explicitly, and #618 found nine
# more across the READMEs and the troubleshooting pages. Each fix was correct
# and none of them stopped the next one being needed, because nothing checked.
# This is the check.
#
# Bare mentions of the tracker are fine — "see the issue tracker", a link to one
# issue, a link in prose about the project. What is refused is a markdown link
# whose target is the list itself, which is the shape all twelve took.
set -euo pipefail

cd "$(dirname "$0")/.."

LIST="https://github.com/marcandreuf/memship/issues"

# Markdown links pointing at the bare list: `](…/issues)` and `](…/issues/)`.
# `/issues/new/choose`, `/issues/123` and `/issues?q=…` all carry more after
# the segment and are left alone.
hits=$(grep -rn --include='*.md' -E "\]\(${LIST}/?\)" . \
  --exclude-dir=node_modules --exclude-dir=.git || true)

if [ -n "$hits" ]; then
  echo "check-issue-links: these link the issue list, not the template picker." >&2
  echo >&2
  echo "$hits" >&2
  echo >&2
  echo "Point them at ${LIST}/new/choose instead." >&2
  echo "ACCESSIBILITY.md is the file that gets this right." >&2
  exit 1
fi

# -prune, not -not -path: node_modules nests under frontend/ and e2e/ too, and
# a top-level-only exclusion counted 1577 files the grep above never read.
count=$(find . \( -name node_modules -o -name .git \) -prune -o -name '*.md' -print | wc -l)
echo "check-issue-links: ${count} markdown file(s), none links the issue list."
