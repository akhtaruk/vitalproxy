#!/usr/bin/env bash
# Stop the SIP proxy and remove only its config and nftables table.
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
[[ "${1:-}" == --confirm ]] || {
  echo "This stops SIP proxy service. Run: sudo bash rollback-proxy.sh --confirm"
  exit 1
}
exec 9>/run/lock/sbc-proxy-installer.lock
flock -n 9 || { echo "A proxy installer is running" >&2; exit 1; }
[[ -e /etc/sbc-proxy/installed ]] || { echo "SIP proxy is not installed"; exit 0; }
systemctl disable --now sbc-proxy.service sbc-proxy-firewall.service
if nft list table inet sbc_proxy_guard >/dev/null 2>&1; then
  nft delete table inet sbc_proxy_guard
fi
rm -f /etc/systemd/system/sbc-proxy.service /etc/systemd/system/sbc-proxy-firewall.service
systemctl daemon-reload
rm -rf /etc/sbc-proxy
echo "Proxy stopped and its managed config removed. Kamailio package is retained."
