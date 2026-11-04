#!/usr/bin/env bash
#
# Is every vendored UI component still accounted for in THIRD_PARTY.md?
#
# Twenty-four components under `frontend/components/ui/` were generated from
# the shadcn/ui registry and copied into the tree rather than installed. MIT
# requires its notice to travel with the code, and a copied file carries no
# package metadata to carry it, so THIRD_PARTY.md is the only place that
# origin is recorded.
#
# Nothing enforced it, which is the failure mode this project keeps meeting:
# a convention held by hand until someone adds a file and does not know the
# convention exists. `npx shadcn add <component>` writes a new file into that
# directory in one step, and nothing would have said the notice went stale.
#
# The check is deliberately not "does the file mention shadcn". It is: every
# file under components/ui/ appears in one of the two lists in THIRD_PARTY.md —
# vendored, or Memship's own. A new component fails until it is classified,
# which forces the decision rather than defaulting to silence.
#
#   ./scripts/check-attribution.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

NOTICES="THIRD_PARTY.md"
UI_DIR="frontend/components/ui"

[ -f "$NOTICES" ] || { echo "check-attribution: $NOTICES is missing" >&2; exit 2; }
[ -d "$UI_DIR" ]  || { echo "check-attribution: $UI_DIR is missing" >&2; exit 2; }



missing=0
checked=0

for path in "$UI_DIR"/*.tsx; do
    file="$(basename "$path")"
    checked=$((checked + 1))
    # Word-boundary match so `skeleton.tsx` is not satisfied by `skeletons.tsx`.
    if ! grep -qE "(^|[^a-zA-Z0-9_-])${file//./\\.}([^a-zA-Z0-9_-]|$)" "$NOTICES"; then
        echo "UNLISTED  $UI_DIR/$file"
        missing=$((missing + 1))
    fi
done

# `cn()` ships with the registry and is vendored the same way.
if ! grep -q "frontend/lib/utils.ts" "$NOTICES"; then
    echo "UNLISTED  frontend/lib/utils.ts"
    missing=$((missing + 1))
fi

if [ "$missing" -ne 0 ]; then
    cat >&2 <<MSG

check-attribution: FAILED — $missing file(s) are in neither list in $NOTICES.

If the file came from the shadcn registry, add it to the vendored list so its
MIT notice covers it. If it is Memship's own, add it to the second list. The
point is that the choice is recorded, not that the file is third-party.
MSG
    exit 1
fi

echo "check-attribution: $checked components and lib/utils.ts all accounted for in $NOTICES."
