#!/usr/bin/env bash
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
[[ -e /etc/sbc-proxy/installed ]] || { echo "SIP proxy is not installed"; exit 1; }
failed=0
systemctl is-active sbc-proxy.service || failed=1
systemctl is-active sbc-proxy-firewall.service || failed=1
nft list table inet sbc_proxy_guard || failed=1
echo
echo "This confirms the proxy service and local firewall only; it does not test phone registration, PBX reachability, or audio."
exit "$failed"
