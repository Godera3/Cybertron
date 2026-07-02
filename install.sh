#!/usr/bin/env bash
# Project Cybertron — full installer (all Phases).
# Idempotent. Requires root (writes /opt, /etc, systemd).
set -euo pipefail

CYB_ROOT="/opt/cybertron"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '\e[36m[cybertron]\e[0m %s\n' "$*"; }
die() { printf '\e[31m[cybertron] %s\e[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root (sudo ./install.sh)"
command -v python3 >/dev/null || die "python3 not found"
command -v rsync   >/dev/null || die "rsync not found (apt install rsync)"

log "Ensuring cybertron group (for TUI <-> optimusd socket access)"
groupadd -f cybertron
if [ -n "${SUDO_USER:-}" ]; then
    usermod -aG cybertron "${SUDO_USER}"
fi

log "Creating state directories"
mkdir -p /etc/cybertron /var/lib/cybertron /var/lib/cybertron/incidents /var/lib/cybertron/quarantine

log "Installing code to ${CYB_ROOT}"
mkdir -p "${CYB_ROOT}"
rsync -a --delete \
    --exclude '.venv' --exclude '.git' --exclude '__pycache__' \
    "${SRC_DIR}/" "${CYB_ROOT}/"

log "Creating virtualenv + installing deps"
[ -d "${CYB_ROOT}/.venv" ] || python3 -m venv "${CYB_ROOT}/.venv"
"${CYB_ROOT}/.venv/bin/pip" install --quiet --upgrade pip
"${CYB_ROOT}/.venv/bin/pip" install --quiet -r "${CYB_ROOT}/requirements.txt" 2>/dev/null || true
"${CYB_ROOT}/.venv/bin/pip" install --quiet -e "${CYB_ROOT}/lib"

log "Initializing doctrine config if absent"
if [ ! -f /etc/cybertron/doctrine.json ]; then
    echo '{"interval":3600,"last_run":{},"blocklist":[]}' > /etc/cybertron/doctrine.json
fi

log "Installing tmpfiles + systemd units"
install -m 0644 "${CYB_ROOT}/tmpfiles/cybertron.conf" /etc/tmpfiles.d/cybertron.conf
systemd-tmpfiles --create /etc/tmpfiles.d/cybertron.conf

for unit in "${CYB_ROOT}"/systemd/cyb-*.service; do
    install -m 0644 "$unit" /etc/systemd/system/
done
install -m 0644 "${CYB_ROOT}/systemd/cybertron.target" /etc/systemd/system/

log "Making dinobot scripts executable"
chmod -R +x "${CYB_ROOT}/dinobots/"*.sh

log "Installing the optimus launcher -> /usr/local/bin/optimus"
install -m 0755 "${CYB_ROOT}/optimus/optimus" /usr/local/bin/optimus

systemctl daemon-reload
systemctl enable --now cybertron.target

log "Enabling all Prime services"
for unit in cyb-micronus cyb-optimus cyb-onyx cyb-alphatrion cyb-vector cyb-prima \
            cyb-nexus cyb-liege cyb-solus cyb-alchemist cyb-amalgamous cyb-quintus \
            cyb-megatronus cyb-doctrine-autobot cyb-doctrine-decepticon cyb-grimlock \
            cyb-maximals cyb-predacons cyb-bumblebee cyb-infinity; do
    systemctl enable --now "${unit}.service" 2>/dev/null || \
        log "WARN: ${unit} failed to start (may need missing dep)"
done

log "Done. Primus awakes."
echo
echo "  Verify all:   cat /run/cybertron/aggregate.json"
echo "  Launch HUD:   optimus"
echo "  Service list: systemctl list-units 'cyb-*'"
echo "  Logs sample:  journalctl -u cyb-infinity.service -n 20"
