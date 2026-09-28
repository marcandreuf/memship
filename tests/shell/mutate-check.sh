#!/usr/bin/env bash
#
# Does the suite actually catch anything? A guard-checking suite that passes on a
# broken guard is worse than none, and #58/#117 are the same complaint about the
# Cypress suite: the tests exist, the trust does not.
#
# So each mutation below is a plausible one-character-ish mistake in a guard —
# the kind that passes review — applied to a COPY of the script, with the suite
# run against it. Every one must make the suite fail. A mutation the suite
# survives is a guard nothing is watching.
#
# This is a tool, not part of the suite: it is slow (a full suite run per
# mutation) and it is for the person adding a guard, who should add a mutation
# beside it. CI runs run.sh, not this.
#
#   ./tests/shell/mutate-check.sh

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

INSTALL="scripts/install.sh"
UPGRADE="scripts/upgrade.sh"

survivors=0
checked=0

# mutate <file> <description> <sed expression…>
mutate() {
    local file="$1" desc="$2"; shift 2
    local backup
    checked=$((checked + 1))
    backup="$(mktemp)"
    cp "$file" "$backup"
    sed -i "$@" "$file"
    if cmp -s "$file" "$backup"; then
        printf '  SKIP    %s (the mutation matched nothing — has the code moved?)\n' "$desc"
        cp "$backup" "$file"; rm -f "$backup"
        survivors=$((survivors + 1))
        return 0
    fi
    if bash "$HERE/run.sh" >/dev/null 2>&1; then
        printf '  SURVIVED  %s\n' "$desc"
        survivors=$((survivors + 1))
    else
        printf '  caught    %s\n' "$desc"
    fi
    cp "$backup" "$file"
    rm -f "$backup"
}

printf 'Mutating the guards. Every one must be caught.\n\n'

mutate "$INSTALL" "the already-installed guard never fires" \
    's/if \[ "\$FROM_UPGRADE" -eq 0 \] \&\& \[ -f "\$ENV_FILE" \]/if [ "$FROM_UPGRADE" -eq 9 ] \&\& [ -f "$ENV_FILE" ]/'

mutate "$INSTALL" "--upgrade is set for everyone, so the guard is dead" \
    's/^FROM_UPGRADE=0$/FROM_UPGRADE=1/'

mutate "$INSTALL" "a missing git tag falls back to latest again" \
    's/^    \[ -n "\$NEW_TAG" \] || die/    NEW_TAG="${NEW_TAG:-latest}"; [ -n "$NEW_TAG" ] || die/'

mutate "$UPGRADE" "the downgrade comparison is the wrong way round" \
    's/if \[ "\$OLDER" = "\$VERSION" \]; then/if [ "$OLDER" != "$VERSION" ]; then/'

mutate "$UPGRADE" "the downgrade guard trusts --allow-downgrade unconditionally" \
    's/^if \[ "\$ALLOW_DOWNGRADE" -eq 0 \] \&\& is_release/if [ "$ALLOW_DOWNGRADE" -eq 9 ] \&\& is_release/'

mutate "$UPGRADE" "a failed pull is not fatal" \
    's/^if \[ "\$pull_status" -ne 0 \]; then/if [ "$pull_status" -eq 99 ]; then/'

mutate "$UPGRADE" "the preflight runs with migrations left on" \
    's/-e RUN_MIGRATIONS=0 api python -m app.cli.preflight/api python -m app.cli.preflight/'

mutate "$UPGRADE" "a refusing migration no longer stops the upgrade" \
    's/^        1)  printf .\\nUpgrade stopped/        99) printf '"'"'\\nUpgrade stopped/'

mutate "$UPGRADE" "checks that could not run count as checks that passed" \
    's/^        0) ;;$/        0|2) ;;/'

mutate "$UPGRADE" "stale deployment files are reported and allowed" \
    's/^        \*)  printf .\\nUpgrade stopped: the deployment files/        99) printf '"'"'\\nUpgrade stopped: the deployment files/'

mutate "$UPGRADE" "a missing .env setting no longer refuses over IMAGE_TAG" \
    "s/            \*' IMAGE_TAG '\*)/            *' NOTHING_AT_ALL '*)/"

mutate "$UPGRADE" "the disk check never refuses" \
    's/^    if \[ -n "\$disk_short" \]; then$/    if [ -n "" ]; then/'

mutate "$UPGRADE" "the disk check charges two filesystems separately on one disk" \
    's/^    if \[ -n "\$DOCKER_DEV" \] \&\& \[ "\$DOCKER_DEV" = "\$DATA_DEV" \]; then$/    if [ -n "$DOCKER_DEV" ] \&\& [ "$DOCKER_DEV" = "no-such-device" ]; then/'

mutate "$UPGRADE" "the disk check uses the upgrade budget for a first install too" \
    's/^            IMAGES_NEEDED_MB="\$IMAGE_BUDGET_FIRST_MB"$/            IMAGES_NEEDED_MB="$IMAGE_BUDGET_STEP_MB"/'

printf '\n%s mutations, %s survived\n' "$checked" "$survivors"
[ "$survivors" -eq 0 ]
