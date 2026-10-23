#!/usr/bin/env bash
#
# Does each translated page still match the page it was translated from?
#
# Nothing used to ask. A source page could be edited and its translations left
# behind, and the result is worse than a missing translation: three pages that
# disagree while all three look equally current, with the stale one hardest to
# spot in the language its reader cannot check (#451). docs/ took 61 commits in
# 90 days, concentrated on installation, upgrading and email — where a stale
# translation is a data-loss incident, not a typo.
#
# A translated page declares what it came from, in the leading comment block:
#
#     <!-- source: en/getting-started/what-you-need.md -->
#     <!-- source-hash: 4f2b9c1d8e03 -->
#
# An HTML comment rather than YAML front matter because these pages render on
# GitHub, which turns front matter into a table above the title.
#
# The hash is the first 12 characters of the source file's git blob id, so there
# is no bespoke hashing to agree on: `git hash-object <file>`.
#
# A page with NO `source:` is itself a source and is skipped. That is what lets
# this land before the translations do and adopt pages one at a time. It also
# means the check fails on exactly one thing — a source edited without its
# translation following. Editing a translation's own prose cannot trip it,
# because only the source is hashed.
#
#   ./scripts/check-docs-translations.sh          # check
#   ./scripts/check-docs-translations.sh --fix    # restamp, after translating
set -euo pipefail

cd "$(dirname "$0")/.."

FIX=0
if [ "${1:-}" = "--fix" ]; then
    FIX=1
elif [ -n "${1:-}" ]; then
    echo "check-docs-translations: unknown argument '$1' (expected --fix or nothing)" >&2
    exit 2
fi

# The run of HTML comments at the top of a file, before any other content. The
# declaration has to live there: scanning the whole file would make a page that
# documents this convention declare a source of its own.
header() {
    awk '
      /^[[:space:]]*$/ { next }
      /^[[:space:]]*<!--/ { print; next }
      { exit }
    ' "$1"
}

field() {
    sed -n "s|.*<!--[[:space:]]*$2:[[:space:]]*\([^[:space:]]*\)[[:space:]]*-->.*|\1|p" <<<"$1" | head -1
}

blob() {
    git hash-object "$1" | cut -c1-12
}

drifted=0
broken=0
checked=0
fixed=0

while IFS= read -r page; do
    head_block="$(header "$page")"
    [ -n "$head_block" ] || continue
    source_rel="$(field "$head_block" source)"
    [ -n "$source_rel" ] || continue

    checked=$((checked + 1))
    source_path="docs/$source_rel"

    if [ ! -f "$source_path" ]; then
        echo "check-docs-translations: $page declares source '$source_rel', which is not a file in docs/." >&2
        broken=$((broken + 1))
        continue
    fi
    if [ "$source_path" = "$page" ]; then
        echo "check-docs-translations: $page declares itself as its own source." >&2
        broken=$((broken + 1))
        continue
    fi

    actual="$(blob "$source_path")"
    declared="$(field "$head_block" source-hash)"

    if [ "$declared" = "$actual" ]; then
        continue
    fi

    if [ "$FIX" -eq 1 ]; then
        if [ -n "$declared" ]; then
            sed -i "s|<!--[[:space:]]*source-hash:[[:space:]]*$declared[[:space:]]*-->|<!-- source-hash: $actual -->|" "$page"
        else
            sed -i "s|\(<!--[[:space:]]*source:[[:space:]]*$source_rel[[:space:]]*-->\)|\1\n<!-- source-hash: $actual -->|" "$page"
        fi
        echo "check-docs-translations: restamped $page to $actual."
        fixed=$((fixed + 1))
        continue
    fi

    if [ -z "$declared" ]; then
        echo "check-docs-translations: $page declares a source but no source-hash." >&2
    else
        echo "check-docs-translations: $source_rel changed since $page was translated from it." >&2
        echo "    declared $declared, now $actual" >&2
    fi
    drifted=$((drifted + 1))
# mindepth 2 covers every file inside a locale folder, the locale READMEs
# included, and skips the top-level language index, which belongs to no locale.
# The locale READMEs are not translations of each other — each links out to
# different locales by design — so they simply declare no source and are skipped.
done < <(find docs -mindepth 2 -name '*.md' -print | sort)

if [ "$FIX" -eq 1 ]; then
    echo "check-docs-translations: $checked declared translation(s), $fixed restamped."
    exit 0
fi

if [ "$broken" -gt 0 ] || [ "$drifted" -gt 0 ]; then
    echo >&2
    echo "check-docs-translations: $drifted stale, $broken malformed, out of $checked declared." >&2
    echo "Re-translate the page from its source, then run ./scripts/check-docs-translations.sh --fix." >&2
    exit 1
fi

echo "check-docs-translations: $checked declared translation(s), all current."
