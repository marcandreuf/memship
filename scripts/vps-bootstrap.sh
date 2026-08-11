#!/usr/bin/env bash
#
# memship — prepare a fresh VPS to host an instance. The root half of host prep:
# deploy user, Docker Engine, firewall, automatic security updates, fail2ban,
# timezone and a weekly image prune. It does NOT install memship — run
# scripts/install.sh as the deploy user afterwards.
#
# Run once, as root, on a fresh Debian 12 or Ubuntu 24.04 server:
#
#   ./scripts/vps-bootstrap.sh                                  # user 'deploy', key copied from root
#   ./scripts/vps-bootstrap.sh --user deploy --ssh-key-file ~/id_ed25519.pub
#   ./scripts/vps-bootstrap.sh --timezone UTC --no-firewall
#
# It deliberately does NOT harden SSH. A script cannot verify you can still log
# in from a second terminal, and applying PermitRootLogin/PasswordAuthentication
# in the wrong order locks you out of the box. The commands are printed at the
# end for you to run and verify yourself.
#
# Safe to re-run: every step checks before it acts.

set -euo pipefail

DEPLOY_USER="deploy"
SSH_KEY=""
SSH_KEY_FILE=""
TIMEZONE="Europe/Madrid"
DO_FIREWALL=1
DO_PRUNE_TIMER=1

die() { printf '\nError: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf '\n!!  %s\n' "$*" >&2; }
skip() { printf '  - %s\n' "$*"; }

usage() {
    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --user)         DEPLOY_USER="${2:-}"; shift 2 ;;
        --ssh-key)      SSH_KEY="${2:-}"; shift 2 ;;
        --ssh-key-file) SSH_KEY_FILE="${2:-}"; shift 2 ;;
        --timezone)     TIMEZONE="${2:-}"; shift 2 ;;
        --no-firewall)  DO_FIREWALL=0; shift ;;
        --no-prune-timer) DO_PRUNE_TIMER=0; shift ;;
        -h|--help)      usage ;;
        *) die "unknown option: $1 (try --help)" ;;
    esac
done

# ---------------------------------------------------------------- preflight

step "Checking prerequisites"

[ "$(id -u)" -eq 0 ] || die "run this as root. It creates users and installs packages.
    The deployment itself runs as an ordinary user — that is what install.sh is for."

[ -r /etc/os-release ] || die "cannot read /etc/os-release — unsupported system."
# shellcheck disable=SC1091
. /etc/os-release

case "${ID:-}" in
    debian|ubuntu) ;;
    *) die "this expects Debian or Ubuntu (found '${ID:-unknown}'). Docker's apt repository
    layout differs elsewhere; follow https://docs.docker.com/engine/install/ by hand." ;;
esac

command -v apt-get >/dev/null 2>&1 || die "apt-get not found."

[ -n "${VERSION_CODENAME:-}" ] || die "cannot determine the release codename from /etc/os-release."

info "${PRETTY_NAME:-$ID $VERSION_CODENAME}"

case "$DEPLOY_USER" in
    root) die "the deploy user must not be root — that is the point of it." ;;
    ''|*[!a-z0-9_-]*) die "invalid user name: '$DEPLOY_USER'" ;;
esac

# Resolve the public key before doing anything, so a missing key fails early
# rather than after half the box is configured.
if [ -n "$SSH_KEY_FILE" ]; then
    [ -r "$SSH_KEY_FILE" ] || die "cannot read $SSH_KEY_FILE"
    # First valid key line, so an authorized_keys file with several keys works
    # here as well as a single .pub — taking the whole file would append every
    # line again as one blob.
    SSH_KEY="$(grep -E '^(ssh|ecdsa)-' "$SSH_KEY_FILE" | head -1 || true)"
    [ -n "$SSH_KEY" ] || die "no SSH public key found in $SSH_KEY_FILE"
elif [ -z "$SSH_KEY" ] && [ -r /root/.ssh/authorized_keys ]; then
    # Most providers install your key for root on a fresh box. Reusing it means
    # the deploy user is reachable with the same key you are already using.
    SSH_KEY="$(grep -E '^(ssh|ecdsa)-' /root/.ssh/authorized_keys | head -1 || true)"
    [ -n "$SSH_KEY" ] && info "reusing the first key from /root/.ssh/authorized_keys"
fi

case "$SSH_KEY" in
    ssh-*|ecdsa-*) ;;
    '') warn "no SSH public key found for '$DEPLOY_USER'.
    Pass --ssh-key-file <path> or --ssh-key '<key>'. Without one you will not be
    able to log in as '$DEPLOY_USER', and the SSH hardening printed at the end
    would lock you out of this box entirely." ;;
    *) die "that does not look like an SSH public key: ${SSH_KEY:0:40}..." ;;
esac

export DEBIAN_FRONTEND=noninteractive

step "Updating the package index"
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg git >/dev/null

# ---------------------------------------------------------------- deploy user

step "Deploy user: $DEPLOY_USER"

if id -u "$DEPLOY_USER" >/dev/null 2>&1; then
    skip "$DEPLOY_USER already exists"
else
    adduser --disabled-password --gecos "" "$DEPLOY_USER" >/dev/null
    info "created $DEPLOY_USER"
fi

usermod -aG sudo "$DEPLOY_USER"
info "in the 'sudo' group"

if [ -n "$SSH_KEY" ]; then
    USER_HOME="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
    install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$USER_HOME/.ssh"
    AUTH="$USER_HOME/.ssh/authorized_keys"
    touch "$AUTH"
    if grep -qxF "$SSH_KEY" "$AUTH" 2>/dev/null; then
        skip "key already authorised"
    else
        printf '%s\n' "$SSH_KEY" >> "$AUTH"
        info "authorised key added"
    fi
    chmod 0600 "$AUTH"
    chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH"
fi

# ---------------------------------------------------------------- timezone

step "Timezone"

# Celery beat schedules are wall-clock — the 02:00 billing run and the 03:00
# payment reminders. On a UTC host they silently fire at the wrong local time.
if [ "$(timedatectl show -p Timezone --value 2>/dev/null || true)" = "$TIMEZONE" ]; then
    skip "already $TIMEZONE"
else
    timedatectl set-timezone "$TIMEZONE" || warn "could not set the timezone to $TIMEZONE"
    info "set to $TIMEZONE"
fi

# ---------------------------------------------------------------- docker

step "Docker Engine and the Compose plugin"

# Docker's own repository, not the distro package — the distro one lags badly
# and the Compose plugin is packaged differently there.
if [ -f /etc/apt/sources.list.d/docker.list ] && command -v docker >/dev/null 2>&1; then
    skip "Docker apt repository already configured"
else
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc \
        || die "could not fetch Docker's signing key."
    chmod a+r /etc/apt/keyrings/docker.asc
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' \
        "$(dpkg --print-architecture)" "$ID" "$VERSION_CODENAME" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    info "added download.docker.com"
fi

apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
systemctl enable --now docker >/dev/null 2>&1 || true
info "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?')"

if id -nG "$DEPLOY_USER" | tr ' ' '\n' | grep -qx docker; then
    skip "$DEPLOY_USER already in the 'docker' group"
else
    usermod -aG docker "$DEPLOY_USER"
    info "$DEPLOY_USER added to the 'docker' group"
fi

warn "Membership of the 'docker' group grants effective root on this host.
    Anyone who can run 'docker' can mount / into a container and write anywhere.
    Treat '$DEPLOY_USER' as a privileged account: it is not a sandbox.
    The group takes effect on next login — '$DEPLOY_USER' must log out and back in."

# ---------------------------------------------------------------- unattended-upgrades

step "Automatic security updates"

apt-get install -y -qq unattended-upgrades >/dev/null

# dpkg-reconfigure is interactive; writing the file is the same outcome.
# This updates the HOST only. memship itself is updated by re-running
# install.sh with a new IMAGE_TAG, never by the OS.
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true
info "security patches applied automatically"

# ---------------------------------------------------------------- fail2ban

step "fail2ban"

apt-get install -y -qq fail2ban >/dev/null
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
bantime = 1h
EOF
systemctl enable --now fail2ban >/dev/null 2>&1 || true
info "sshd jail enabled (5 attempts, 1h ban)"

# ---------------------------------------------------------------- firewall

if [ "$DO_FIREWALL" -eq 1 ]; then
    step "Firewall"

    apt-get install -y -qq ufw >/dev/null

    # Order matters: allow SSH BEFORE enabling, or enabling drops this session.
    ufw allow 22/tcp >/dev/null
    ufw allow 80/tcp >/dev/null
    ufw allow 443/tcp >/dev/null
    info "allowed 22, 80, 443/tcp"

    # "Status: inactive" contains "active" — match the whole field, not a substring.
    if ufw status | head -1 | grep -qi "^Status: active"; then
        skip "ufw already active"
    else
        ufw --force enable >/dev/null
        info "ufw enabled"
    fi

    warn "ufw does NOT constrain Docker. Docker inserts its own iptables rules ahead
    of ufw's, so any port published with 'ports:' in a compose file stays reachable
    from the internet even while ufw denies it. The base compose publishes the API
    on 8003 and Postgres on 5433. Do not rely on these rules — verify from another
    machine once the stack is up:
      nmap -Pn -p 22,80,443,5433,8003 <this-host>"
else
    step "Firewall"
    skip "skipped (--no-firewall)"
fi

# ---------------------------------------------------------------- prune timer

if [ "$DO_PRUNE_TIMER" -eq 1 ]; then
    step "Weekly image prune"

    # Every deploy leaves another image layer set behind. Without this the disk
    # fills within a couple of months of daily deploys. 168h keeps the last
    # week's images so a rollback does not have to pull again.
    cat > /etc/systemd/system/docker-prune.service <<'EOF'
[Unit]
Description=Prune Docker images older than a week
Documentation=https://github.com/marcandreuf/memship

[Service]
Type=oneshot
ExecStart=/usr/bin/docker system prune -af --filter until=168h
EOF

    cat > /etc/systemd/system/docker-prune.timer <<'EOF'
[Unit]
Description=Weekly Docker image prune

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload
    systemctl enable --now docker-prune.timer >/dev/null 2>&1 || true
    info "docker-prune.timer enabled (weekly, keeps the last 168h)"
else
    step "Weekly image prune"
    skip "skipped (--no-prune-timer)"
fi

# ---------------------------------------------------------------- what is left

step "Done"

# Report sshd's actual state rather than assuming it needs hardening. Cloud
# images increasingly ship with all three already set, and telling someone to
# fix what is already correct is how the real instructions get skimmed past.
# Read the effective config once. Do NOT pipe `sshd -T` into an awk that exits
# early: awk closes the pipe, sshd takes SIGPIPE, and under `set -o pipefail`
# that is a 141 which `set -e` turns into an abort right here — with everything
# already done and none of the instructions below printed.
SSHD_CONF="$(sshd -T 2>/dev/null || true)"
sshd_val() { printf '%s\n' "$SSHD_CONF" | awk -v k="$1" '$1==k {print $2}' | tail -1; }

SSH_PORT="$(sshd_val port)"
SSH_PORT="${SSH_PORT:-22}"
SSH_ROOT="$(sshd_val permitrootlogin)"
SSH_PASSWD="$(sshd_val passwordauthentication)"

if [ "$SSH_ROOT" = "no" ] && [ "$SSH_PASSWD" = "no" ]; then
    cat <<EOF

  SSH is already hardened on this host — root login and password authentication
  are both off, on port $SSH_PORT. Nothing to do; skip to step 2.

EOF
else
cat <<EOF

  1. HARDEN SSH. This script does not touch sshd, on purpose: it cannot verify
     that you can still log in, and getting the order wrong locks you out of a
     box you may have no console access to.

     Currently: PermitRootLogin=${SSH_ROOT:-unknown}, PasswordAuthentication=${SSH_PASSWD:-unknown}, port $SSH_PORT.

     FIRST, in a SECOND terminal, confirm this works and keep it open:

       ssh -p $SSH_PORT $DEPLOY_USER@<this-host>
       sudo -v

     Only once that succeeds, edit /etc/ssh/sshd_config:

       PermitRootLogin no
       PasswordAuthentication no
       PubkeyAuthentication yes

     Then reload and, in a THIRD terminal, verify again before closing anything:

       sudo sshd -t && sudo systemctl reload ssh
       ssh -p $SSH_PORT $DEPLOY_USER@<this-host>

     'sshd -t' checks the config for syntax errors. Reloading a broken config
     is how people lock themselves out.

EOF
fi

cat <<EOF
  2. INSTALL MEMSHIP as $DEPLOY_USER — not as root:

       su - $DEPLOY_USER          # or log in again over SSH, so the docker group applies
       sudo install -d -o $DEPLOY_USER -g $DEPLOY_USER /srv/openmemship
       git clone https://github.com/marcandreuf/memship.git /srv/openmemship/app
       cd /srv/openmemship/app
       ./scripts/install.sh --data-root /srv/openmemship/data --domain <your-domain>

     Point the DNS A record at this host before running it. install.sh checks,
     because failed Let's Encrypt validations are rate-limited at 5 per hour.

EOF
