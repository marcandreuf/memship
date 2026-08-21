#!/usr/bin/env bash
#
# The quickstart cannot include ./Caddyfile — it is a single file you curl with
# no clone behind it — so its proxy config is duplicated inside
# docker-compose.quickstart.yml. Duplication drifts: #56 added the header block
# to ./Caddyfile, the quickstart never got it, and the gap survived because the
# frontend sets four of the same headers itself, so only a direct curl of
# /api/v1/* shows it (#73).
#
# This compares the two header lists by directive name and fails if they differ.
# Add a header to one file, add it to the other.
set -euo pipefail

cd "$(dirname "$0")/.."

# Directive names inside the first `header { ... }` block of a file, sorted.
# Strips comments and blank lines, keeps the leading '-' of removals.
directives() {
  awk '
    /header[[:space:]]*\{/ { inblock = 1; next }
    inblock && /^[[:space:]]*\}/ { exit }
    inblock {
      sub(/#.*/, "")
      if ($1 != "") print $1
    }
  ' "$1" | sort
}

canonical=$(directives Caddyfile)
quickstart=$(directives docker-compose.quickstart.yml)

if [ -z "$canonical" ]; then
  echo "check-caddy-headers: no header block found in ./Caddyfile" >&2
  exit 1
fi

if [ "$canonical" != "$quickstart" ]; then
  echo "check-caddy-headers: the two Caddy header blocks have drifted." >&2
  echo >&2
  diff <(echo "$canonical") <(echo "$quickstart") \
    --label "Caddyfile" --label "docker-compose.quickstart.yml" -u >&2 || true
  echo >&2
  echo "Add the missing directive to both, or update this check if the" >&2
  echo "difference is deliberate." >&2
  exit 1
fi

echo "check-caddy-headers: both header blocks list $(echo "$canonical" | wc -l | tr -d ' ') directives, matching."
