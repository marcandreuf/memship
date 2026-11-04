#!/usr/bin/env bash
#
# Do the three UI locales still carry the same keys?
#
# `CLAUDE.md` says `frontend/locales/` is "kept at key parity" across `es`, `ca`
# and `en`. Nothing enforced it, so parity was maintained by hand and a missing
# key reached a user as the raw key string on screen (#509).
#
# The `Translation Drift` job sounds like it covers this and does not: it is
# gated on `docs/**` and checks the *documentation* translations. Nothing looked
# at `frontend/locales/` at all, so a PR adding a key to `en` and forgetting
# `ca` was green on every job.
#
# `es` is the default locale and most development happens there, so `ca` is both
# the one that drifts and the one least likely to be opened.
#
# Two rules, decided rather than assumed (#509):
#
#   - a key missing from ANY locale fails, in both directions. A key present in
#     `ca` but not `en` is a rename left half-done, not a Catalan extra.
#   - an EMPTY value fails. It passes a key-set comparison and still renders as
#     nothing, which is the same bug with a different cause.
#
# Locales are discovered from the directory, so adding a fourth needs no edit
# here — it starts being checked the moment its folder exists.
#
#   ./scripts/check-locales.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

LOCALES_ROOT="frontend/locales"

if [ ! -d "$LOCALES_ROOT" ]; then
    echo "check-locales: $LOCALES_ROOT does not exist" >&2
    exit 2
fi

if ! command -v jq > /dev/null 2>&1; then
    echo "check-locales: jq is required and was not found" >&2
    exit 2
fi

mapfile -t LOCALES < <(find "$LOCALES_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

if [ "${#LOCALES[@]}" -lt 2 ]; then
    echo "check-locales: need at least two locales to compare, found ${#LOCALES[@]}" >&2
    exit 2
fi

# Every namespace in any locale, so a file missing from one is caught too.
mapfile -t FILES < <(
    for loc in "${LOCALES[@]}"; do
        find "$LOCALES_ROOT/$loc" -maxdepth 1 -name '*.json' -printf '%f\n'
    done | sort -u
)

if [ "${#FILES[@]}" -eq 0 ]; then
    echo "check-locales: no .json files under $LOCALES_ROOT" >&2
    exit 2
fi

# Flattened key paths, one per line. Array indices become path segments, so a
# list that gained an item in one locale and not another is a difference too.
#
# `LC_ALL=C` on every sort, and never jq's own `sort`. `comm` demands that both
# inputs be ordered the same way, and jq sorts by codepoint while `sort` follows
# the locale's collation — which on a developer machine ignores punctuation. The
# two disagree on keys like `a.b` versus `ab`, and `comm` then reports every key
# as missing from every locale while printing "input is not in sorted order" to
# stderr, where a CI log buries it.
keys_of() {
    jq -r '[paths(scalars) | map(tostring) | join(".")] | .[]' "$1" | LC_ALL=C sort
}

empty_keys_of() {
    jq -r '[paths(scalars) as $p | select(getpath($p) == "") | $p | map(tostring) | join(".")] | .[]' "$1" | LC_ALL=C sort
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

failed=0

for file in "${FILES[@]}"; do
    missing_file=0
    for loc in "${LOCALES[@]}"; do
        path="$LOCALES_ROOT/$loc/$file"
        if [ ! -f "$path" ]; then
            echo "MISSING FILE  $loc/$file"
            missing_file=1
            failed=1
            continue
        fi
        if ! jq empty "$path" > /dev/null 2>&1; then
            echo "INVALID JSON  $loc/$file"
            missing_file=1
            failed=1
            continue
        fi
        keys_of "$path" > "$WORK/$loc.keys"
    done

    # A namespace missing from a locale has no key set to compare; the line
    # above already said so, and naming every key as missing would bury it.
    [ "$missing_file" -eq 1 ] && continue

    cat "$WORK"/*.keys | LC_ALL=C sort -u > "$WORK/union.keys"

    for loc in "${LOCALES[@]}"; do
        while IFS= read -r key; do
            [ -z "$key" ] && continue
            # Which locales DO carry it, so the reader can tell a missing
            # translation from a key that should be deleted everywhere.
            present=""
            for other in "${LOCALES[@]}"; do
                if grep -qxF "$key" "$WORK/$other.keys"; then
                    present="$present $other"
                fi
            done
            echo "MISSING KEY   $loc/$file  $key  (present in:$present)"
            failed=1
        done < <(comm -23 "$WORK/union.keys" "$WORK/$loc.keys")

        while IFS= read -r key; do
            [ -z "$key" ] && continue
            echo "EMPTY VALUE   $loc/$file  $key"
            failed=1
        done < <(empty_keys_of "$LOCALES_ROOT/$loc/$file")
    done

    rm -f "$WORK"/*.keys
done

if [ "$failed" -ne 0 ]; then
    echo
    echo "check-locales: FAILED — the locales are not at key parity."
    echo "Add the keys named above, or remove them everywhere if they are dead."
    exit 1
fi

echo "check-locales: ${#LOCALES[@]} locales (${LOCALES[*]}), ${#FILES[@]} namespaces, keys at parity and no empty values."
