#!/usr/bin/env bash
# Run on a dedicated Debian 12 / Ubuntu 24.04 appliance, never inside Replit.
set -euo pipefail
umask 077
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROLE="${1:-}"; ACTION="${2:-}"; CONFIG="${3:-}"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$ROLE" == local || "$ROLE" == remote ]] || fail "Role must be local or remote"
[[ "$EUID" -eq 0 ]] || fail "Run with sudo"
[[ "$ACTION" == prepare || "$ACTION" == install ]] || fail "Usage: install-$ROLE.sh prepare | install /path/config.json"
[[ -r /etc/os-release ]] || fail "Cannot identify OS"
. /etc/os-release
[[ "$ID:$VERSION_ID" == debian:12 || "$ID:$VERSION_ID" == ubuntu:24.04 ]] ||
  fail "This installer targets Debian 12 or Ubuntu 24.04 only"
command -v systemctl >/dev/null || fail "systemd is required"
[[ -d /run/systemd/system ]] || fail "Boot this appliance with systemd"
command -v flock >/dev/null || fail "flock (util-linux) is required"
exec 9>/run/lock/sbc-installer.lock
flock -n 9 || fail "Another SBC installation is in progress"
STATE=/etc/sbc-edge
POLICY_CREATED=0
STAGE=""
cleanup() {
  if [[ "$POLICY_CREATED" == 1 ]]; then rm -f /usr/sbin/policy-rc.d; fi
  if [[ -n "$STAGE" ]]; then rm -rf -- "$STAGE"; fi
}
trap cleanup EXIT
if [[ "$ACTION" == prepare ]]; then
  [[ ! -e "$STATE/role" ]] || fail "Already installed; do not rotate the key"
  # Prevent package auto-start without replacing an administrator's policy.
  if [[ ! -e /usr/sbin/policy-rc.d ]]; then
    printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
    chmod 755 /usr/sbin/policy-rc.d
    POLICY_CREATED=1
  fi
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    wireguard-tools python3 nftables iproute2 ca-certificates
  install -d -m 700 "$STATE"
  if [[ ! -s "$STATE/private.key" ]]; then
    wg genkey > "$STATE/private.key"
    chmod 600 "$STATE/private.key"
  fi
  printf '\nDevice public key (share only this key with the other device):\n'
  wg pubkey < "$STATE/private.key"
  printf '\nNext: edit config.json and run sudo bash install-%s.sh install config.json\n' "$ROLE"
  exit 0
fi
[[ -r "$CONFIG" ]] || fail "Provide the path to config.json"
[[ -s "$STATE/private.key" ]] || fail "Run prepare on both devices first"
python3 "$HERE/sbc.py" validate --config "$CONFIG"
[[ ! -e "$STATE/role" ]] || fail "Already installed. Use rollback.sh before changing configuration"
for file in /etc/wireguard/wg-sbc.conf /etc/sysctl.d/90-sbc-forward.conf \
  /etc/systemd/system/sbc-firewall.service /etc/systemd/system/sbc-sip.service \
  /etc/systemd/system/sbc-media.service \
  /etc/systemd/system/wg-quick@wg-sbc.service.d/sbc.conf; do
  [[ ! -e "$file" ]] || fail "Refusing to overwrite existing file: $file"
done
ip link show wg-sbc >/dev/null 2>&1 && fail "wg-sbc interface already exists"
nft list table inet sbc_guard >/dev/null 2>&1 && fail "sbc_guard firewall table already exists"
get() { python3 "$HERE/sbc.py" get --config "$CONFIG" --field "$1"; }
[[ "$(wg pubkey < "$STATE/private.key")" != "$(get peer_public_key)" ]] ||
  fail "peer_public_key is this device's own key; use the OTHER device's public key"
if [[ "$ROLE" == local ]]; then
  ADDRESS="$(get lan_ip)"
  # A /32 PBX route must not also capture WireGuard's own public endpoint.
  ENDPOINT="$(get remote_endpoint)"
  ENDPOINT_IPS="$(getent ahostsv4 "$ENDPOINT" | awk '{print $1}' | sort -u)" ||
    fail "Cannot resolve remote_endpoint to IPv4"
  [[ -n "$ENDPOINT_IPS" ]] || fail "No IPv4 tunnel endpoint found"
  for routed in "$(get pbx_ip)" "$(get local_tunnel_ip)" "$(get remote_tunnel_ip)"; do
    if grep -Fxq "$routed" <<< "$ENDPOINT_IPS"; then
      fail "Endpoint DNS matches tunnel route $routed; use a separate gateway endpoint"
    fi
  done
else
  ADDRESS="$(get gateway_lan_ip)"
fi
ip -4 -o address show | awk '{split($4,a,"/"); print a[1]}' | grep -Fxq "$ADDRESS" ||
  fail "Configured interface address $ADDRESS is not assigned to this appliance"
WGPORT="$(get wireguard_port)"
if ss -H -lun | awk '{print $4}' | grep -Eq ":${WGPORT}$"; then
  fail "WireGuard UDP port $WGPORT is already in use"
fi
if [[ "$ROLE" == local ]]; then
  for vendor in kamailio.service rtpengine-daemon.service; do
    if systemctl cat "$vendor" >/dev/null 2>&1; then
      fail "Existing $vendor found. Use a fresh dedicated SBC; existing services are not replaced"
    fi
  done
  # Avoid interrupting another SIP/media service. No vendor configs are replaced.
  python3 - "$CONFIG" <<'PY'
import json, subprocess, sys
c = json.load(open(sys.argv[1]))
for line in subprocess.check_output(["ss", "-H", "-lun"], text=True).splitlines():
    port = int(line.split()[3].rsplit(":", 1)[1])
    if port in (c["sbc_sip_port"], 2223) or c["sbc_rtp_min"] <= port <= c["sbc_rtp_max"]:
        sys.exit(f"ERROR: UDP port {port} in use; use a dedicated SBC")
PY
  if [[ ! -e /usr/sbin/policy-rc.d ]]; then
    printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
    chmod 755 /usr/sbin/policy-rc.d
    POLICY_CREATED=1
  fi
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    kamailio kamailio-extra-modules rtpengine-daemon
  # These packages were absent at preflight; use our dedicated units, not theirs.
  systemctl disable --now kamailio.service rtpengine-daemon.service
  if [[ "$POLICY_CREATED" == 1 ]]; then
    rm -f /usr/sbin/policy-rc.d
    POLICY_CREATED=0
  fi
  id kamailio >/dev/null || fail "kamailio package user is missing"
  command -v rtpengine >/dev/null || fail "rtpengine binary is missing"
fi
STAGE="$(mktemp -d)"
# Renderer creates its destination itself to avoid accidentally overwriting output.
python3 "$HERE/sbc.py" render --config "$CONFIG" --role "$ROLE" \
  --private-key-file "$STATE/private.key" --output "$STAGE/rendered"
nft -c -f "$STAGE/rendered/firewall.nft"
if [[ "$ROLE" == local ]]; then
  # -c checks config; it does not bind the not-yet-created WireGuard interface.
  kamailio -c -f "$STAGE/rendered/kamailio.cfg"
fi
# From here, rollback.sh can clean up even a partial/failed activation.
printf '%s\n' "$ROLE" > "$STATE/role"
cp -- "$CONFIG" "$STATE/config.json"
sysctl -n net.ipv4.ip_forward > "$STATE/ip-forward.before"
install -d -m 700 "$STATE/rendered"
install -m 600 "$STAGE/rendered/"* "$STATE/rendered/"
install -d -m 700 /etc/wireguard
install -m 600 "$STAGE/rendered/wg-sbc.conf" /etc/wireguard/wg-sbc.conf
install -m 600 "$STAGE/rendered/firewall.nft" "$STATE/firewall.nft"
cat > /etc/systemd/system/sbc-firewall.service <<'UNIT'
[Unit]
Description=SBC isolated firewall guard (does not replace host firewall)
Before=wg-quick@wg-sbc.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/sbc-edge/firewall.nft
ExecStop=/usr/sbin/nft delete table inet sbc_guard
[Install]
WantedBy=multi-user.target
UNIT
install -d /etc/systemd/system/wg-quick@wg-sbc.service.d
cat > /etc/systemd/system/wg-quick@wg-sbc.service.d/sbc.conf <<'UNIT'
[Unit]
Requires=sbc-firewall.service
After=sbc-firewall.service
UNIT
if [[ "$ROLE" == remote ]]; then
  install -m 644 "$STAGE/rendered/90-sbc-forward.conf" /etc/sysctl.d/90-sbc-forward.conf
  sysctl -w net.ipv4.ip_forward=1
else
  # Allow Kamailio to traverse only its own config directory.
  chgrp kamailio "$STATE" "$STATE/rendered"
  chmod 710 "$STATE" "$STATE/rendered"
  chown root:kamailio "$STATE/rendered/kamailio.cfg"
  chmod 640 "$STATE/rendered/kamailio.cfg"
  cat > /etc/systemd/system/sbc-media.service <<'UNIT'
[Unit]
Description=SBC RTPengine userspace media relay
Requires=wg-quick@wg-sbc.service
After=wg-quick@wg-sbc.service
BindsTo=wg-quick@wg-sbc.service
[Service]
Type=simple
RuntimeDirectory=sbc-media
ExecStart=/usr/bin/rtpengine --config-file=/etc/sbc-edge/rendered/rtpengine.conf --foreground --log-stderr --pidfile=/run/sbc-media/rtpengine.pid
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=strict
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
UNIT
  cat > /etc/systemd/system/sbc-sip.service <<'UNIT'
[Unit]
Description=SBC Kamailio SIP edge
Requires=wg-quick@wg-sbc.service sbc-media.service
After=wg-quick@wg-sbc.service sbc-media.service
BindsTo=wg-quick@wg-sbc.service
[Service]
Type=simple
User=kamailio
Group=kamailio
RuntimeDirectory=sbc-sip
ExecStart=/usr/sbin/kamailio -DD -E -P /run/sbc-sip/kamailio.pid -f /etc/sbc-edge/rendered/kamailio.cfg
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=strict
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
UNIT
fi
systemctl daemon-reload
systemctl enable --now sbc-firewall.service
systemctl enable --now wg-quick@wg-sbc.service
if [[ "$ROLE" == local ]]; then
  systemctl enable --now sbc-media.service sbc-sip.service
  systemctl is-active --quiet sbc-media.service sbc-sip.service ||
    fail "Service startup failed; inspect journalctl and run rollback.sh if needed"
fi
printf '\nInstalled %s appliance. A running service does NOT prove PBX connectivity.\n' "$ROLE"
printf 'Next: apply the PBX route, Path, direct-media and firewall settings in README.md.\n'
printf 'Then run sudo bash status.sh and complete the call acceptance checklist.\n'
