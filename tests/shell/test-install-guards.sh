#!/usr/bin/env bash
#
# scripts/install.sh — the two guards and the .env it writes.
#
# Both guards fail silently when they break. A typo that makes the
# already-installed guard never fire turns every hand-run install.sh on a live
# box into an upgrade with no snapshot and no pre-upgrade check; a typo that
# makes --upgrade always match does the same thing from the other direction. And
# the --tag refusal is the only thing standing between a release tarball and an
# instance pinned to a moving `latest` that reports its own version as the
# string "latest".

# shellcheck source=tests/shell/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

case_defaults() { export STUB_IMAGES_LOCAL=1; }
case_defaults


it "refuses to install over an instance that is already running"
new_sandbox install-live
write_env 2.13.0
STUB_DB_RUNNING=1 run_script scripts/install.sh --tag 2.14.0
assert_status 1
assert_says "already installed and running (2.13.0)"
assert_says "./scripts/upgrade.sh 2.14.0"
# The point of the guard: nothing was replaced.
assert_not_called 'compose up'
assert_not_called 'compose pull'
done_case


it "names the running version in the refusal, not the one asked for"
new_sandbox install-live-names
write_env 2.9.1
STUB_DB_RUNNING=1 run_script scripts/install.sh --tag 2.14.0
assert_status 1
assert_says "(2.9.1)"
done_case


it "lets --upgrade through that guard"
new_sandbox install-upgrade-flag
write_env 2.13.0
STUB_DB_RUNNING=1 STUB_HAS_USERS=1 run_script scripts/install.sh --tag 2.14.0 --upgrade
assert_status 0
assert_silent_about "already installed"
assert_called 'compose up -d'
# And the Caddy force-recreate, without which a bind-mounted Caddyfile change
# leaves the old proxy configuration serving.
assert_called 'compose up -d --force-recreate caddy'
done_case


it "moves IMAGE_TAG in place and leaves the rest of .env alone"
new_sandbox install-retag
write_env 2.13.0
before="$(grep '^SECRET_KEY=' "$SANDBOX/.env")"
STUB_DB_RUNNING=1 STUB_HAS_USERS=1 run_script scripts/install.sh --tag 2.14.0 --upgrade
assert_status 0
grep -qx 'IMAGE_TAG=2.14.0' "$SANDBOX/.env" || fail "IMAGE_TAG was not rewritten"
[ "$(grep '^SECRET_KEY=' "$SANDBOX/.env")" = "$before" ] || fail "SECRET_KEY changed"
assert_says ".env exists — leaving it alone"
done_case


it "does not treat a half-built install as a running one"
# .env written, nothing up. That is an install to finish, not one to refuse.
new_sandbox install-halfbuilt
write_env 2.14.0
STUB_DB_RUNNING=0 run_script scripts/install.sh --tag 2.14.0
assert_status 0
assert_silent_about "already installed"
done_case


it "refuses when no --tag is given and no git tag is reachable"
# What a release tarball and an rsynced deployment both look like: no .git.
new_sandbox install-notag
STUB_DB_RUNNING=0 DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" run_script scripts/install.sh
assert_status 1
assert_says "--tag is required here"
# Nothing at all may have happened: the refusal promises it.
[ -f "$SANDBOX/.env" ] && fail ".env was written despite the refusal"
assert_not_called 'compose pull'
assert_not_called 'compose up'
done_case


it "accepts --tag latest, since that is asking for it by name"
new_sandbox install-latest
STUB_DB_RUNNING=0 DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" \
    run_script scripts/install.sh --tag latest
assert_status 0
grep -qx 'IMAGE_TAG=latest' "$SANDBOX/.env" || fail "IMAGE_TAG=latest was not written"
done_case


it "writes a mode-600 .env and a POST-INSTALL.md on a first install"
new_sandbox install-fresh
STUB_DB_RUNNING=0 DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" \
    run_script scripts/install.sh --tag 2.14.0
assert_status 0
grep -qx 'IMAGE_TAG=2.14.0' "$SANDBOX/.env" || fail "IMAGE_TAG was not pinned"
[ "$(stat -c '%a' "$SANDBOX/.env")" = "600" ] || fail ".env is not mode 600"
[ -f "$SANDBOX/POST-INSTALL.md" ] || fail "POST-INSTALL.md was not written"
# No secret may reach this output: install.sh also runs from a deploy pipeline
# whose log can be public.
for var in SECRET_KEY MEMSHIP_SECRET_KEY DB_PASSWORD; do
    value="$(grep -E "^$var=" "$SANDBOX/.env" | cut -d= -f2-)"
    printf '%s' "$OUT" | grep -qF -- "$value" && fail "$var's value was printed"
done
assert_says "Run the setup"
done_case


it "says the instance is already set up rather than telling it to seed"
new_sandbox install-seeded
write_env 2.14.0
STUB_DB_RUNNING=1 STUB_HAS_USERS=1 run_script scripts/install.sh --tag 2.14.0 --upgrade
assert_status 0
assert_says "This instance is already set up"
assert_silent_about "Run the setup"
done_case


it "rejects an unknown option rather than guessing"
new_sandbox install-badopt
STUB_DB_RUNNING=0 run_script scripts/install.sh --tag 2.14.0 --no-such-flag
assert_status 1
assert_says "unknown option: --no-such-flag"
done_case


it "refuses to start when DNS does not resolve yet"
# Let's Encrypt rate-limits failed validations, so this has to be a check and
# not a discovery.
new_sandbox install-dns
STUB_DB_RUNNING=0 DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" \
    DOMAIN_OVERRIDE="" STUB_RESOLVES_TO="" \
    run_script scripts/install.sh --tag 2.14.0 --domain memship.example.org
assert_status 1
assert_says "does not resolve yet"
assert_not_called 'compose up'
done_case


it "starts when DNS resolves to this host"
new_sandbox install-dns-ok
STUB_DB_RUNNING=0 DATA_ROOT_OVERRIDE="$STUB_DATA_ROOT" \
    STUB_RESOLVES_TO=203.0.113.7 STUB_PUBLIC_IP=203.0.113.7 \
    run_script scripts/install.sh --tag 2.14.0 --domain memship.example.org
assert_status 0
assert_says "matches this host"
# SITE_ADDRESS alone is not enough — these three would otherwise still say
# http://localhost, which breaks email links, CORS and the SSO callback.
for var in FRONTEND_URL CORS_ORIGINS BACKEND_PUBLIC_URL; do
    grep -qx "$var=https://memship.example.org" "$SANDBOX/.env" \
        || fail "$var was not pointed at the domain"
done
done_case


summary
