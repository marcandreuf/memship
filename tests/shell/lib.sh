#!/usr/bin/env bash
#
# The harness for the deployment scripts' shell tests.
#
# WHY A PLAIN RUNNER AND NOT BATS. #215 asked for the decision to be made rather
# than defaulted. bats is the better tool for a large suite of small assertions;
# it is not the better tool here. What is under test is a handful of guards whose
# every assertion is "what exit code, what did it say, in what order did it do
# things" — three helpers' worth of vocabulary. Against that, bats is a package
# to install on every contributor's machine and in CI before a single line runs,
# and it brings its own execution model (file-level `setup`/`teardown`, a TAP
# reporter, `run`) between the reader and the script being exercised. A plain
# runner needs bash, which the thing under test needs anyway. Revisit if this
# grows past a few dozen cases.
#
# HOW A CASE WORKS. Each one builds a throwaway deployment directory — the real
# scripts/, docker-compose.yml and Caddyfile, copied from the repository — puts
# tests/shell/stubs first on PATH, and runs the real script. So what is being
# tested is the actual control flow, end to end, including install.sh and
# verify-deployment.sh being called by upgrade.sh. Only the world outside the
# scripts is fake.
#
# Deliberately not a git repository. install.sh reads `git describe` to default
# a version, and the absence of a tag is the condition its --tag refusal exists
# for — which is also what an rsynced deployment and an unpacked release tarball
# look like.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STUBS="$REPO_ROOT/tests/shell/stubs"

TESTS_RUN=0
TESTS_FAILED=0
CURRENT_CASE=""
CURRENT_FAILED=0

# Where sandboxes go. One per run, removed at the end unless KEEP_SANDBOX is set
# — which is how you debug a failing case: re-run with KEEP_SANDBOX=1 and read
# the directory the failure names.
SANDBOX_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/memship-shelltest.XXXXXX")"
cleanup() {
    if [ -n "${KEEP_SANDBOX:-}" ]; then
        printf '\nsandboxes kept in %s\n' "$SANDBOX_ROOT"
    else
        rm -rf "$SANDBOX_ROOT"
    fi
}
trap cleanup EXIT

# ------------------------------------------------------------------ sandbox

# new_sandbox <name> — a deployment directory holding exactly what a deployment
# holds: the release's files, and nothing else.
#
# `cp` rather than a symlink: install.sh resolves REPO_ROOT from
# ${BASH_SOURCE[0]}, and a symlinked scripts/ would resolve back into the
# repository and write a .env there.
new_sandbox() {
    SANDBOX="$SANDBOX_ROOT/$1"
    mkdir -p "$SANDBOX"
    cp -R "$REPO_ROOT/scripts" "$SANDBOX/scripts"
    cp "$REPO_ROOT/docker-compose.yml" "$REPO_ROOT/Caddyfile" "$SANDBOX/"
    # Outside the deployment directory, the way every deployment is told to keep
    # it — deliveries copy over the top of that directory.
    STUB_DATA_ROOT="$SANDBOX_ROOT/$1-data"
    mkdir -p "$STUB_DATA_ROOT/backups" "$STUB_DATA_ROOT/storage"
    STUB_BACKUP_DIR="$STUB_DATA_ROOT/backups"
    STUB_LOG="$SANDBOX_ROOT/$1.calls"
    : >"$STUB_LOG"
    export STUB_DATA_ROOT STUB_BACKUP_DIR STUB_LOG
}

# The checksums the deployment files in the current sandbox actually have, in
# the format the image label carries. Spelled the way both build-images.yml and
# upgrade.sh spell it — `sha256sum <file`, so the output carries no filename.
sandbox_manifest() {
    local out="" f
    for f in docker-compose.yml Caddyfile; do
        out="$out$f:$(sha256sum <"$SANDBOX/$f" | cut -d' ' -f1) "
    done
    printf '%s' "$out"
}

# write_env <IMAGE_TAG> [extra lines…] — a .env of the shape install.sh writes,
# so the settings check has nothing to complain about unless a case wants it to.
write_env() {
    local tag="$1"; shift
    {
        printf 'MEMSHIP_DATA_ROOT=%s\n' "$STUB_DATA_ROOT"
        printf 'SITE_ADDRESS=\n'
        [ -z "$tag" ] || printf 'IMAGE_TAG=%s\n' "$tag"
        printf 'HOST_UID=%s\nHOST_GID=%s\n' "$(id -u)" "$(id -g)"
        printf 'DB_PASSWORD=x\nSECRET_KEY=x\nMEMSHIP_SECRET_KEY=x\n'
        printf 'APP_ENV=production\nDEFAULT_LOCALE=es\n'
        printf 'FRONTEND_URL=http://localhost\nCORS_ORIGINS=http://localhost\n'
        printf 'BACKEND_PUBLIC_URL=http://localhost\n'
        printf 'RESEND_API_KEY=\nRESEND_FROM_EMAIL=\n'
        printf 'SMTP_HOST=\nSMTP_PORT=587\nSMTP_USER=\nSMTP_PASSWORD=\n'
        printf 'SMTP_FROM=noreply@memship.local\nSMTP_TLS=true\n'
        printf 'GOOGLE_CLIENT_ID=\nGOOGLE_CLIENT_SECRET=\n'
        printf 'APPLE_CLIENT_ID=\nAPPLE_TEAM_ID=\nAPPLE_KEY_ID=\nAPPLE_PRIVATE_KEY=\n'
        printf '%s\n' "$@"
    } >"$SANDBOX/.env"
    chmod 600 "$SANDBOX/.env"
}

# run_script <relative path> [args…] — the script, in the sandbox, with the
# stubs in front. Output lands in $OUT (both streams, which is what the
# assertions read) and the exit code in $STATUS.
#
# `env -i`-style isolation is deliberately NOT used: these scripts read HOME and
# USER, and a caller's DATA_ROOT/DOMAIN would change what install.sh does. Only
# those two are cleared.
run_script() {
    local script="$1"; shift
    OUT="$(cd "$SANDBOX" && PATH="$STUBS:$PATH" DATA_ROOT="${DATA_ROOT_OVERRIDE:-}" \
        DOMAIN="${DOMAIN_OVERRIDE:-}" "./$script" "$@" 2>&1)"
    STATUS=$?
    return 0
}

# ---------------------------------------------------------------- assertions

# Every knob any stub reads, reset before each case.
#
# This is not tidiness. A variable assignment in front of a *function* call — the
# `STUB_PULL_FAIL=1 run_script …` shape every case below uses — is not scoped to
# that call in bash: it stays set afterwards. Without this, one case's failing
# pull silently becomes the next six cases' failing pull, and they pass for the
# wrong reason or fail for a reason that is not in the test.
STUB_KNOBS="STUB_DB_RUNNING STUB_PULL_FAIL STUB_PREFLIGHT_EXIT STUB_LABEL
            STUB_IMAGES_LOCAL STUB_HAS_USERS STUB_DOCKER_ROOT
            STUB_HEALTH_VERSION STUB_PUBLIC_IP STUB_RESOLVES_TO
            STUB_DF_FREE_KB STUB_DF_SPLIT
            VERIFY_TIMEOUT DATA_ROOT_OVERRIDE DOMAIN_OVERRIDE"

it() {
    local knob
    for knob in $STUB_KNOBS; do unset "$knob"; done
    # verify-deployment.sh polls for five minutes by default, which is right on a
    # real upgrade and is five minutes of nothing here. Set low for every case,
    # so a case that means to reach the "the API never answered" path costs two
    # seconds and a case that forgets to make the API answer fails fast instead
    # of looking like a hung suite.
    export VERIFY_TIMEOUT=2 VERIFY_LOG_LINES=5

    # A test file sets its own baseline here, since the reset above has just
    # cleared it.
    if declare -F case_defaults >/dev/null; then case_defaults; fi

    CURRENT_CASE="$1"
    CURRENT_FAILED=0
    TESTS_RUN=$((TESTS_RUN + 1))
}

fail() {
    if [ "$CURRENT_FAILED" -eq 0 ]; then
        printf '  FAIL  %s\n' "$CURRENT_CASE"
        CURRENT_FAILED=1
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    printf '          %s\n' "$*"
}

done_case() {
    [ "$CURRENT_FAILED" -eq 0 ] || {
        printf '        --- output ---\n%s\n        ---\n' \
            "$(printf '%s\n' "$OUT" | sed 's/^/        /')"
        return 0
    }
    printf '  ok    %s\n' "$CURRENT_CASE"
}

assert_status() {
    [ "$STATUS" = "$1" ] || fail "expected exit $1, got $STATUS"
}

assert_says() {
    printf '%s' "$OUT" | grep -qF -- "$1" || fail "expected output to mention: $1"
}

assert_silent_about() {
    printf '%s' "$OUT" | grep -qF -- "$1" && fail "output should not mention: $1"
    return 0
}

# assert_called <pattern> — some docker (or curl, or df) call matched.
assert_called() {
    grep -qE -- "$1" "$STUB_LOG" || fail "expected a call matching: $1"
}

assert_not_called() {
    grep -qE -- "$1" "$STUB_LOG" && fail "should not have called: $1"
    return 0
}

# assert_order <earlier> <later> — the first match of <earlier> precedes the
# first match of <later> in the call log. This is the whole point of logging
# argv: "snapshot before the data check" and "pull before anything is applied"
# are orderings, and an ordering is invisible to an exit code.
assert_order() {
    local first second
    first="$(grep -nE -- "$1" "$STUB_LOG" | head -1 | cut -d: -f1)"
    second="$(grep -nE -- "$2" "$STUB_LOG" | head -1 | cut -d: -f1)"
    if [ -z "$first" ]; then fail "never called: $1"; return 0; fi
    if [ -z "$second" ]; then fail "never called: $2"; return 0; fi
    [ "$first" -lt "$second" ] || fail "expected '$1' (line $first) before '$2' (line $second)"
}

summary() {
    printf '\n%s: %s run, %s failed\n' "$(basename "$0")" "$TESTS_RUN" "$TESTS_FAILED"
    [ "$TESTS_FAILED" -eq 0 ]
}
