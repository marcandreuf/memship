#!/usr/bin/env bash
#
# scripts/upgrade.sh — every guard, both escape hatches, and the ordering.
#
# The orderings matter as much as the refusals. Each guard's promise is "nothing
# has been changed and the instance is still serving the version it was", and
# that promise is a statement about *when* it ran, which no exit code records.
# So the call log is asserted on directly.

# shellcheck source=tests/shell/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

# The baseline every case starts from: a running, seeded instance whose images
# are already local. `it` reapplies this before each case, after clearing
# whatever the previous one set.
case_defaults() {
    export STUB_DB_RUNNING=1 STUB_IMAGES_LOCAL=1 STUB_HAS_USERS=1
}
case_defaults

# A running instance on $1, with the deployment files matching what the image
# claims, so only the guard a case is about can fire. Sets STUB_LABEL, which is
# per-sandbox because it carries that sandbox's own checksums.
running_instance() {
    new_sandbox "$1"
    write_env "$2"
    STUB_LABEL="$(sandbox_manifest)"
    export STUB_LABEL
}


# ------------------------------------------------------------ argument handling

it "refuses without a version"
new_sandbox up-noargs
run_script scripts/upgrade.sh
assert_status 2
assert_says "usage: upgrade.sh"
done_case


it "rejects an unknown option rather than reading it as a version"
new_sandbox up-badopt
run_script scripts/upgrade.sh --no-such-flag
assert_status 2
assert_says "unknown option: --no-such-flag"
done_case


# ------------------------------------------------------------- downgrade guard

it "refuses to go backwards between two releases"
running_instance up-down 2.14.0
run_script scripts/upgrade.sh 2.13.0
assert_status 1
assert_says "Refusing to downgrade: this instance runs 2.14.0, you asked for 2.13.0"
assert_says "backups-and-restore.md"
# Before the pull, so it costs nothing.
assert_not_called 'compose pull'
assert_not_called 'compose up'
done_case


it "strips a leading v before comparing, so v2.13.0 is still a downgrade"
running_instance up-down-v 2.14.0
run_script scripts/upgrade.sh v2.13.0
assert_status 1
assert_says "you asked for 2.13.0"
done_case


it "compares by version order, not lexically"
# 2.9.1 -> 2.10.0 is forwards; a string compare would call it backwards.
running_instance up-order 2.9.1
STUB_HEALTH_VERSION=2.10.0 run_script scripts/upgrade.sh 2.10.0
assert_status 0
assert_silent_about "Refusing to downgrade"
done_case


it "lets --allow-downgrade through"
running_instance up-down-allow 2.14.0
STUB_HEALTH_VERSION=2.13.0 run_script scripts/upgrade.sh 2.13.0 --allow-downgrade
assert_status 0
assert_silent_about "Refusing to downgrade"
assert_called 'compose up -d'
done_case


it "re-applying the same version is not a downgrade"
running_instance up-same 2.14.0
STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_silent_about "Refusing to downgrade"
done_case


it "says nothing about ordering when the instance runs an RC"
# sha-<commit> has no ordering to reason about, so it is left alone rather than
# guessed at — including when the target is older than any release.
running_instance up-rc sha-abc123def456
STUB_HEALTH_VERSION=2.13.0 run_script scripts/upgrade.sh 2.13.0
assert_status 0
assert_silent_about "Refusing to downgrade"
done_case


# --------------------------------------------------------- .env settings check

it "refuses when .env has no IMAGE_TAG line to rewrite"
# sed changes nothing when there is no line to change, so the tag is accepted
# and dropped and the stack comes up on `latest`.
running_instance up-no-tag ""
run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says ".env has no IMAGE_TAG line"
assert_says "IMAGE_TAG=" # the remedy, spelled out
assert_not_called 'compose pull'
assert_not_called 'compose up'
done_case


it "reports settings this .env predates without refusing over them"
running_instance up-old-env 2.13.0
# An .env from before the installer learned to write the Resend block.
grep -v '^RESEND_' "$SANDBOX/.env" >"$SANDBOX/.env.trimmed"
mv "$SANDBOX/.env.trimmed" "$SANDBOX/.env"
STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "RESEND_API_KEY"
assert_says "check the release notes"
assert_called 'compose up -d'
done_case


it "says nothing when .env carries everything the installer writes"
# The only way a check like this earns its place: silent on a current instance.
running_instance up-env-ok 2.13.0
STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "every setting the installer writes is present"
done_case


# ------------------------------------------------------------------ disk check

it "refuses when there is not enough room for the images and the dump"
running_instance up-disk-short 2.13.0
# Sparse: only the size is ever read, and a real 200 MB file costs a real 200 MB.
truncate -s 200M "$STUB_DATA_ROOT/backups/memship_20260101_000000.sql.gz"
STUB_IMAGES_LOCAL=0 STUB_DF_FREE_KB=200000 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "not enough free disk"
assert_says "docker image prune"
# Before the pull that would have filled it.
assert_not_called 'compose pull'
assert_not_called 'compose up'
done_case


it "charges the images and the dump to one filesystem when they share a disk"
# Two comparisons against one free figure would each pass while their sum does
# not. 1000 MB for the step plus the doubled dump must not fit in 1024 MB.
running_instance up-disk-sum 2.13.0
truncate -s 100M "$STUB_DATA_ROOT/backups/memship_20260101_000000.sql.gz"
STUB_IMAGES_LOCAL=0 STUB_DF_FREE_KB=1100000 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "images and snapshot"
done_case


it "asks for nothing on account of images that are already local"
# Re-running to re-apply configuration against the installed version pulls
# nothing, so it must not be refused for want of room to pull it.
running_instance up-disk-local 2.14.0
STUB_IMAGES_LOCAL=1 STUB_DF_FREE_KB=60000 STUB_HEALTH_VERSION=2.14.0 \
    run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "all already local"
done_case


it "sizes the dump from this instance's own history, not from a guess"
running_instance up-disk-history 2.13.0
truncate -s 50M "$STUB_DATA_ROOT/backups/memship_20260101_000000.sql.gz"
STUB_IMAGES_LOCAL=1 STUB_DF_FREE_KB=4000000 STUB_HEALTH_VERSION=2.14.0 \
    run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "twice the largest dump"
done_case


it "asks for nothing for a dump it has no history to size"
running_instance up-disk-nohistory 2.13.0
STUB_IMAGES_LOCAL=1 STUB_DF_FREE_KB=4000000 STUB_HEALTH_VERSION=2.14.0 \
    run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "no previous dump to size it from"
done_case


it "lets --skip-disk-check through, for a host df misreports"
running_instance up-disk-skip 2.13.0
STUB_IMAGES_LOCAL=0 STUB_DF_FREE_KB=1 STUB_HEALTH_VERSION=2.14.0 \
    run_script scripts/upgrade.sh 2.14.0 --skip-disk-check
assert_status 0
assert_silent_about "not enough free disk"
done_case


# ------------------------------------------------------------- image pre-pull

it "stops on a failed pull with the old version still serving"
running_instance up-pull-fail 2.13.0
STUB_PULL_FAIL=1 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "could not fetch every image for 2.14.0"
assert_says "still"
assert_says "serving 2.13.0"
# The whole reason the pull moved to the front.
assert_not_called 'compose up'
assert_not_called 'compose exec .* pg_dump'
done_case


it "does not repeat compose's advice to build the image from source"
# Following it either fails for want of a source tree or builds an image no
# release ever published.
running_instance up-pull-advice 2.13.0
STUB_PULL_FAIL=1 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "manifest unknown"
assert_silent_about "must be built from source"
done_case


it "pulls before it snapshots, and snapshots before it applies"
running_instance up-ordering 2.13.0
STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_order 'compose pull' 'pg_dump'
assert_order 'pg_dump' 'app\.cli\.preflight'
assert_order 'app\.cli\.preflight' 'compose up -d'
done_case


# --------------------------------------------------- deployment file check

it "refuses when the deployment files are not the release's"
running_instance up-stale 2.13.0
# What an upgrade whose first step was skipped looks like: the Compose file is
# the previous release's, so its checksum is not the one the image carries.
printf '\n# left over from the previous release\n' >>"$SANDBOX/docker-compose.yml"
run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "the deployment files here are not 2.14.0's"
assert_says "stale: docker-compose.yml"
assert_says "--skip-file-check"
# Before the snapshot, so a missed refresh leaves no dump behind.
assert_not_called 'pg_dump'
assert_not_called 'compose up'
done_case


it "names a deployment file that is missing rather than stale"
running_instance up-missing 2.13.0
rm "$SANDBOX/Caddyfile"
run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "missing: Caddyfile"
done_case


it "lets --skip-file-check through for a deployment that maintains them"
running_instance up-skip-files 2.13.0
printf '\n# a customised compose file\n' >>"$SANDBOX/docker-compose.yml"
STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0 --skip-file-check
assert_status 0
assert_silent_about "not 2.14.0's"
done_case


it "says so and continues when the release carries no manifest"
# Releases built before the label existed have nothing to compare against, so
# they stay installable.
running_instance up-nolabel 2.13.0
STUB_LABEL="" STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "carries no deployment manifest"
assert_called 'compose up -d'
done_case


it "does not compare deployment files for an RC, which names no release"
running_instance up-rc-files 2.13.0
printf '\n# whatever\n' >>"$SANDBOX/docker-compose.yml"
STUB_HEALTH_VERSION=sha-abc123def456 \
    run_script scripts/upgrade.sh sha-abc123def456 --allow-downgrade
assert_status 0
assert_silent_about "deployment files here are not"
done_case


# --------------------------------------------------------------- preflight

it "runs the release's checks with migrations turned off"
# RUN_MIGRATIONS=0 is load-bearing: the api service sets it to 1 and the
# entrypoint runs `alembic upgrade head` when it is set, so without the override
# this applies the very migration it is checking, against the live database,
# while the old stack is still serving.
running_instance up-preflight-env 2.13.0
STUB_HEALTH_VERSION=2.14.0 run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_called 'compose run --rm --no-deps -e RUN_MIGRATIONS=0 api python -m app\.cli\.preflight'
done_case


it "stops when a migration would refuse, before anything is replaced"
running_instance up-preflight-block 2.13.0
STUB_PREFLIGHT_EXIT=1 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "Upgrade stopped"
assert_says "still serving the version it was"
assert_not_called 'compose up'
done_case


it "treats checks that could not run as different from checks that passed"
running_instance up-preflight-error 2.13.0
STUB_PREFLIGHT_EXIT=2 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "the checks could not be run"
assert_says "not the same as passing"
assert_not_called 'compose up'
done_case


# ----------------------------------------------------------- first install

it "skips every check that needs a database on a first install"
new_sandbox up-first
STUB_DB_RUNNING=0 STUB_IMAGES_LOCAL=0 STUB_HAS_USERS=0 \
    DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" STUB_HEALTH_VERSION=2.14.0 \
    run_script scripts/upgrade.sh 2.14.0
assert_status 0
assert_says "No running database — first install, nothing to snapshot"
assert_says "No running database — first install, nothing to check"
assert_not_called 'pg_dump'
assert_not_called 'app\.cli\.preflight'
# It still pulls, and it still gets to a verified stack.
assert_called 'compose pull'
assert_says "Deployment verified: 2.14.0"
done_case


it "budgets for the whole stack on a first install, not for one release step"
new_sandbox up-first-disk
# 1100 MB clears an upgrade's 1000 MB budget and not a first install's 1800 MB,
# so this distinguishes the two.
STUB_DB_RUNNING=0 STUB_IMAGES_LOCAL=0 STUB_DF_FREE_KB=1200000 \
    DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" \
    run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "not enough free disk"
assert_says "1.8 GB"
done_case


# ------------------------------------------------------------- verification

it "fails when the API comes back on a version nobody deployed"
running_instance up-verify-mismatch 2.13.0
STUB_HEALTH_VERSION=latest run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "deployed 2.14.0 but the API reports latest"
done_case


it "fails when the API never answers"
running_instance up-verify-silent 2.13.0
STUB_HEALTH_VERSION="" VERIFY_TIMEOUT=1 run_script scripts/upgrade.sh 2.14.0
assert_status 1
assert_says "did not answer"
done_case


summary
