#!/usr/bin/env bash
# Removes only SBC-owned configuration. Installed packages and keys are retained.
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
[[ "${1:-}" == --confirm ]] || {
  echo "This disconnects SBC calls and the tunnel. Run: sudo bash rollback.sh --confirm"
  exit 1
}
exec 9>/run/lock/sbc-installer.lock
flock -n 9 || { echo "An SBC installer is running" >&2; exit 1; }
STATE=/etc/sbc-edge
[[ -f "$STATE/role" ]] || { echo "Nothing installed; keys, if prepared, are retained"; exit 0; }
ROLE="$(cat "$STATE/role")"
for unit in sbc-sip.service sbc-media.service wg-quick@wg-sbc.service sbc-firewall.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then
    systemctl disable --now "$unit" || { echo "Failed to stop $unit; refusing to delete configuration" >&2; exit 1; }
  fi
done
if nft list table inet sbc_guard >/dev/null 2>&1; then nft delete table inet sbc_guard; fi
rm -f /etc/systemd/system/sbc-sip.service /etc/systemd/system/sbc-media.service \
  /etc/systemd/system/sbc-firewall.service /etc/wireguard/wg-sbc.conf \
  /etc/systemd/system/wg-quick@wg-sbc.service.d/sbc.conf
if [[ "$ROLE" == remote ]]; then
  rm -f /etc/sysctl.d/90-sbc-forward.conf
  # Do not disable forwarding globally: another service may now depend on it.
  echo "Previous ip_forward value: $(cat "$STATE/ip-forward.before")"
  echo "Forwarding remains unchanged. Restore manually ONLY if nothing else uses routing."
fi
systemctl daemon-reload
rm -rf "$STATE/rendered"
rm -f "$STATE/role" "$STATE/firewall.nft"
echo "SBC stopped and managed config removed. Packages, private.key and config.json retained."
echo "Remove any PBX route/firewall rules you added manually. See README.md."
