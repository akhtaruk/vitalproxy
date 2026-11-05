#!/usr/bin/env bash
# One Debian 13 machine on the phone LAN; no VPN or PBX-side gateway.
set -euo pipefail
umask 077
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-}"
CONFIG="${2:-}"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || fail "Run with sudo"
[[ "$ACTION" == install ]] || fail "Usage: sudo bash install-proxy.sh install /path/config.json"
[[ -r /etc/os-release ]] || fail "Cannot identify OS"
. /etc/os-release
[[ "$ID:$VERSION_ID" == debian:13 ]] || fail "This simple installer targets Debian 13"
[[ -d /run/systemd/system ]] || fail "systemd is required"
command -v flock >/dev/null || fail "flock is required"
[[ -r "$CONFIG" ]] || fail "Provide the path to config.json"
exec 9>/run/lock/sbc-proxy-installer.lock
flock -n 9 || fail "Another proxy installation is in progress"
STATE=/etc/sbc-proxy
[[ ! -e "$STATE/installed" ]] || fail "Already installed; use rollback-proxy.sh first"
for path in /etc/systemd/system/sbc-proxy.service \
  /etc/systemd/system/sbc-proxy-firewall.service; do
  [[ ! -e "$path" ]] || fail "Refusing to overwrite existing file: $path"
done
nft list table inet sbc_proxy_guard >/dev/null 2>&1 &&
  fail "Firewall table sbc_proxy_guard already exists"
if systemctl cat kamailio.service >/dev/null 2>&1; then
  fail "Kamailio already has a system service; this installer will not replace it"
fi
python3 "$HERE/proxy-config.py" validate --config "$CONFIG"
PROXY_IP="$(python3 - "$CONFIG" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["proxy_ip"])
PY
)"
ip -4 -o address show | awk '{split($4,a,"/"); print a[1]}' | grep -Fxq "$PROXY_IP" ||
  fail "Configured proxy_ip $PROXY_IP is not assigned to this Debian machine"
PROXY_PORT="$(python3 - "$CONFIG" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["proxy_port"])
PY
)"
if ss -H -lun | awk '{print $4}' | grep -Eq ":${PROXY_PORT}$"; then
  fail "UDP port $PROXY_PORT is already in use"
fi
STAGE="$(mktemp -d)"
POLICY_CREATED=0
cleanup() {
  [[ "$POLICY_CREATED" == 0 ]] || rm -f /usr/sbin/policy-rc.d
  [[ -z "${STAGE:-}" ]] || rm -rf -- "$STAGE"
}
trap cleanup EXIT
python3 "$HERE/proxy-config.py" render --config "$CONFIG" --output "$STAGE/rendered"
nft -c -f "$STAGE/rendered/firewall.nft"
if [[ ! -e /usr/sbin/policy-rc.d ]]; then
  printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
  chmod 755 /usr/sbin/policy-rc.d
  POLICY_CREATED=1
fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  kamailio nftables python3 iproute2
if [[ "$POLICY_CREATED" == 1 ]]; then
  rm -f /usr/sbin/policy-rc.d
  POLICY_CREATED=0
fi
command -v kamailio >/dev/null || fail "Kamailio install failed"
id kamailio >/dev/null || fail "Kamailio system user missing"
systemctl disable --now kamailio.service 2>/dev/null || true
kamailio -c -f "$STAGE/rendered/kamailio.cfg"

install -d -o root -g kamailio -m 750 "$STATE"
install -d -o root -g kamailio -m 750 "$STATE/rendered"
cp -- "$CONFIG" "$STATE/config.json"
chmod 600 "$STATE/config.json"
install -o root -g kamailio -m 640 "$STAGE/rendered/kamailio.cfg" "$STATE/rendered/kamailio.cfg"
install -m 600 "$STAGE/rendered/firewall.nft" "$STATE/firewall.nft"

cat > /etc/systemd/system/sbc-proxy-firewall.service <<'UNIT'
[Unit]
Description=Isolated firewall guard for the LAN SIP proxy
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/sbc-proxy/firewall.nft
ExecStop=/usr/sbin/nft delete table inet sbc_proxy_guard
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/sbc-proxy.service <<'UNIT'
[Unit]
Description=Kamailio SIP outbound proxy for VitalPBX
Requires=sbc-proxy-firewall.service
After=network-online.target sbc-proxy-firewall.service
Wants=network-online.target
[Service]
Type=simple
User=kamailio
Group=kamailio
RuntimeDirectory=sbc-proxy
ExecStart=/usr/sbin/kamailio -DD -E -P /run/sbc-proxy/kamailio.pid -f /etc/sbc-proxy/rendered/kamailio.cfg
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=strict
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
UNIT

touch "$STATE/installed"
systemctl daemon-reload
systemctl enable --now sbc-proxy-firewall.service sbc-proxy.service
systemctl is-active --quiet sbc-proxy.service ||
  fail "SIP proxy did not start; inspect journalctl -u sbc-proxy"
printf '\nSIP outbound proxy installed on this Debian 13 machine.\n'
printf 'Set phone outbound proxy to %s:%s (UDP).\n' "$PROXY_IP" "$PROXY_PORT"
printf 'This forwards SIP signalling only; RTP audio does not pass through the proxy.\n'
printf 'Run sudo bash status-proxy.sh to check service and firewall.\n'
