#!/usr/bin/env bash
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
[[ -f /etc/sbc-edge/role ]] || { echo "SBC not installed" >&2; exit 1; }
failed=0
ROLE="$(cat /etc/sbc-edge/role)"
for unit in sbc-firewall wg-quick@wg-sbc; do
  systemctl is-active "$unit" || failed=1
done
if [[ "$ROLE" == local ]]; then
  for unit in sbc-media sbc-sip; do
    systemctl is-active "$unit" || failed=1
  done
fi
printf '\nWireGuard peers: public keys and handshake ages only (no private keys)\n'
wg show wg-sbc latest-handshakes
if ! wg show wg-sbc latest-handshakes | awk -v now="$(date +%s)" '
  NF == 2 {seen=1; if ($2 == 0 || now - $2 > 180) bad=1}
  END {exit (!seen || bad)}'; then
  echo "FAIL: no recent handshake. Check endpoint DNS, peer keys, NAT and UDP firewall."
  failed=1
fi
printf '\nManaged firewall\n'
nft list table inet sbc_guard || failed=1
printf '\nUDP listeners\n'
ss -lun
printf '\nRegistration/calls are NOT verified by this check. Use the PBX and call checklist.\n'
exit "$failed"
