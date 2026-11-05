# VitalPBX LAN SIP outbound proxy

This is a **simple SIP signalling proxy**, not a VPN or a complete media-relaying
SBC. It runs on one Debian 13 machine on the phone LAN and forwards phone SIP
requests to an existing VitalPBX server:

```text
SIP phone ── SIP (UDP) ──> Debian 13 / Kamailio ── SIP (UDP) ──> VitalPBX
  registrar remains VitalPBX       outbound proxy only
  RTP/audio goes directly between phone and PBX, not through this proxy.
```

No second gateway, VPN, or change to the VitalPBX operating system is required.
The configured PBX IPv4 address must already be reachable from Debian.

## Important limitations

- This forwards SIP signalling only. It does not relay RTP/audio, transcode codecs,
  or fix a network that cannot carry voice between the phone and PBX. Confirm
  VitalPBX SDP addresses and RTP firewall/NAT settings separately.
- The first version supports **outgoing phone requests only**. It does not make
  the PBX able to reach a phone behind NAT for new incoming calls. REGISTER may
  succeed while incoming calls do not. Incoming calls need additional PBX NAT/
  Path handling or a full media/registration-anchoring SBC.
- IPv4 and UDP only; no TCP, TLS, SRTP, WebRTC, VPN, or topology hiding.
- The proxy keeps normal VitalPBX extension authentication in place and always
  forwards LAN phones to one configured PBX. It is not an open relay.
- This is a lab-tested-by-you first version, not a certified/commercial SBC.
  Test with one extension and do not assume production readiness.

## Requirements

- One dedicated Debian 13 machine on the same LAN as the SIP phones.
- A static IP address or DHCP reservation for that machine.
- The VitalPBX IPv4 address and SIP UDP port. The PBX must be reachable from the
  Debian machine at that address and port.
- Local admin/root access to Debian 13. This script does **not** run on VitalPBX.
- An existing VitalPBX extension and a phone that supports a separate outbound
  proxy setting.

## Install

Extract the downloaded ZIP on the Debian machine, then open a terminal in its
`sbc` folder. Copy the example configuration and edit it:

```bash
cp config.example.json config.json
nano config.json
```

Set `proxy_ip` to the Debian machine's static LAN address; `lan_cidr` to the
phones' LAN subnet; and `pbx_ip` to VitalPBX's reachable IPv4 address. Keep the
default SIP ports unless your PBX uses a different UDP port. For example:

```json
{
  "proxy_ip": "192.168.50.10",
  "lan_cidr": "192.168.50.0/24",
  "pbx_ip": "198.51.100.40",
  "pbx_sip_port": 5060,
  "proxy_port": 5060
}
```

`198.51.100.40` is an example only; replace every example with your actual
network information. Validate before installing:

```bash
python3 proxy-config.py validate --config config.json
sudo bash install-proxy.sh install config.json
sudo bash status-proxy.sh
```

The installer adds Kamailio, writes its own config and firewall table, then
starts a dedicated service. It refuses an existing Kamailio installation or
reserved proxy firewall table rather than replacing them. It does not flush the
firewall, alter IP forwarding, modify VitalPBX, or install any VPN.

## Configure one phone

Keep the phone's **SIP server/registrar/domain** pointed at VitalPBX. Set its
separate **outbound proxy** to the Debian proxy IP and UDP port, e.g.
`192.168.50.10:5060`. Keep the VitalPBX extension, authentication ID, password
and normal authentication enabled. Test registration and an outgoing call.

The proxy must be the path used by the phone for SIP. It does not change the
phone's audio destination. A successful SIP registration or outgoing call does
not prove that audio or incoming calls work.

## Network/firewall

- Let phone-subnet devices reach Debian `proxy_ip` on UDP `proxy_port`.
- Let Debian reach PBX `pbx_ip` on UDP `pbx_sip_port`.
- Let SIP replies return to the Debian source port through stateful firewall/NAT.
- Separately allow the required RTP range between phone and VitalPBX. Audio does
  not pass through the Debian proxy.
- The local firewall guard allows only the phone subnet and configured PBX IP to
  reach the proxy UDP port. Other firewall policy is not removed. Router/firewall
  rules must not expose proxy SIP to the public internet.

## Troubleshooting

```bash
sudo bash status-proxy.sh
sudo journalctl -u sbc-proxy -n 100 --no-pager
sudo kamailio -c -f /etc/sbc-proxy/rendered/kamailio.cfg
```

`status-proxy.sh` checks the local service and firewall only; it does not test
registration, calls, or audio. If registration fails, check that phone SIP is
configured for UDP, the PBX address/port are correct, and firewall/NAT permit
the request and response. If signaling works but audio does not, investigate the
phone/PBX media route and RTP settings; this proxy does not touch RTP.

If the installer stops at Kamailio's config check, the proxy was not installed,
but the Kamailio package may have been downloaded. Newer ZIP builds support
retries after this point. For an older bundle, update to the latest ZIP or, on
this otherwise-dedicated Debian machine, remove the package the failed attempt
just installed (`apt remove kamailio`) before retrying with the corrected files.
Do not remove a Kamailio package that was already in use before this installer.

## Roll back

This stops the proxy. Run during a maintenance window:

```bash
sudo bash rollback-proxy.sh --confirm
```

Only the proxy's service, config and owned firewall table are removed. The
Kamailio package is retained. Restore the phone's outbound proxy setting if
needed.
