# Local Network SIP SBC — first version

An installable, single-site SIP edge for local phones and a remote Asterisk/
VitalPBX server. No cloud account, API subscription, or Replit runtime is needed.
**This is a lab-ready first version, not a certified production SBC.** The source
is included. Real registration and call testing on your equipment is required.

## What you are installing

```text
Local voice LAN                 Encrypted tunnel          Remote PBX network
SIP phones → Linux SBC         ═══ WireGuard ═══       Linux gateway → VitalPBX
             Kamailio + RTPengine                      routes only SIP/RTP
             192.168.50.10        10.77.0.2 ↔ 10.77.0.1  192.168.100.10
                                                                    ↓
                                                           192.168.100.20
```

- **Local device:** dedicated Debian 12/13 or Ubuntu 24.04, systemd, two CPU cores/
  2 GB RAM suggested for a small lab. A single Ethernet interface is enough.
  Use static IP addressing or DHCP reservations. No Asterisk on this device.
- **Remote device:** separate Debian 12/13 or Ubuntu 24.04 gateway on the PBX's LAN,
  or a VM in the same routed network. It is **not** installed into the PBX OS.
  VitalPBX may use a different Linux distribution; leave that OS unchanged.
- The remote gateway needs a public IPv4 address or UDP port forwarding
  **51820 → gateway:51820**, plus a working path from gateway to PBX.
- Administrator access to both Linux devices and permission to change PBX
  extension settings, firewall and a return route are required.
- This version supports one local voice subnet, one PBX, IPv4, UDP SIP, and
  ordinary RTP/RTCP. It does not transcode codecs.
- Use phones whose registrar and outbound proxy can be configured separately.
  Their Contact and SDP addresses must be literal, reachable voice-LAN IPv4
  addresses. Disable STUN and public-IP advertisement on these LAN phones.
- LAN, tunnel and PBX addresses must not overlap. Use a dedicated voice VLAN.
  Devices on the voice LAN are trusted to attempt SIP authentication.

## Before installation

Use a maintenance window and console access. These scripts install OS packages,
add a WireGuard interface, create dedicated systemd units and an isolated nftables
guard. The remote gateway enables IPv4 forwarding. They do not flush firewall
rules, edit Asterisk files, change the default route, or NAT the voice traffic.
Existing firewall policies still apply; the guard's ACCEPT rules do **not**
override another firewall's DROP rules.

Back up the PBX and note its current extension/transport/firewall settings.
Do not install onto a machine already running SIP/media services. This installer
refuses to overwrite its reserved config paths or an existing SBC installation.
If `prepare` cannot install packages, fix the OS repositories before continuing.

## 1. Prepare both devices

Copy this entire `sbc` folder, including `templates`, onto each Linux device.
Python 3 is used for strict JSON validation and configuration rendering.

On the remote gateway:

```bash
cd sbc
sudo bash install-remote.sh prepare
```

On the local SBC:

```bash
cd sbc
sudo bash install-local.sh prepare
```

Each command generates a private key **on that device**, retaining it at
`/etc/sbc-edge/private.key`, and prints only the public key. Re-running `prepare`
before installation retains the same key.
Exchange only public keys. Never paste private keys or phone passwords into chat,
put them in config.json, or include `/etc/sbc-edge` in a support bundle.

## 2. Configure the site

On each device:

```bash
cp config.example.json config.json
nano config.json
python3 sbc.py validate --config config.json
```

Use the same site addresses and port ranges in both copies. **Only**
`peer_public_key` differs:

- Local copy: remote gateway's public key.
- Remote copy: local SBC's public key.

All example addresses must be replaced if they do not match your network.
`remote_endpoint` is the gateway's public IPv4/DNS hostname, without a scheme or
port. It must not resolve to `pbx_ip` or a tunnel address: the PBX /32 route would
otherwise capture WireGuard transport traffic. This topology uses a separate
gateway and normally a private PBX address.

| Field | Meaning |
| --- | --- |
| `lan_ip` / `lan_cidr` | Local SBC's actual voice-LAN IP / allowed phone subnet |
| `pbx_ip` | Remote PBX IP reachable from the remote gateway |
| `gateway_lan_ip` | Remote gateway's actual IP on the PBX network |
| `local_tunnel_ip` / `remote_tunnel_ip` | Unique WireGuard IPv4 addresses, configured as /32 |
| `remote_endpoint` / `wireguard_port` | Public gateway address and forwarded UDP port |
| `pbx_sip_port` | PBX's UDP SIP listener, commonly 5060 |
| `pbx_rtp_min` / `pbx_rtp_max` | Must match the PBX's configured RTP range |
| `sbc_sip_port` | SIP listener on the SBC's LAN and tunnel addresses |
| `sbc_rtp_min` / `sbc_rtp_max` | Local RTPengine UDP range, default 30000–40000 |
| `peer_public_key` | OTHER device's WireGuard public key |
| `mtu` | Tunnel MTU, default 1380; lower if the underlay needs it |

If your PBX sends media from additional hosts/IPs, uses IPv6, TLS/SRTP/WebRTC,
or needs multiple simultaneous PBXs/sites, this baseline needs extending first.
It does not promise compatibility with every Asterisk distribution.

## 3. Install remote first, then local

Remote gateway:

```bash
sudo bash install-remote.sh install config.json
```

Local SBC:

```bash
sudo bash install-local.sh install config.json
```

The local SBC initiates the tunnel and sends keepalives every 25 seconds.
No inbound port-forward is needed at the local site.
Private keys and generated configs remain on each device.

## 4. Required PBX/network changes

These are manual so the installer cannot overwrite VitalPBX-managed files.

### Return route — mandatory

The PBX must route the **local SBC tunnel address** through the remote gateway.
With the unmodified example addresses, run this on the PBX to test:

```bash
sudo ip route add 10.77.0.2/32 via 192.168.100.10
ip route get 10.77.0.2
```

If this route exists, inspect it; do not blindly replace it. Make it persistent
using the PBX OS's network manager, or add the route on its default router.
The gateway must be a directly reachable next hop. No route to the phone LAN is
needed because signalling and media return through the SBC.

### Asterisk PJSIP — mandatory

Use the PBX GUI or its supported persistent custom configuration mechanism:

- Enable **`support_path=yes` on each participating AOR**. Kamailio supplies a
  tunnel-reachable SIP Path during REGISTER; Asterisk must retain and use it
  for new inbound calls. This is an AOR option, not an endpoint option.
- Set **`direct_media=no` on the participating endpoints**. Otherwise Asterisk
  can redirect audio around the SBC.
- Keep normal username/password digest authentication for each extension.
  Do not create a trusted anonymous trunk or bypass authentication by IP.
- Ensure contact rewriting does not replace the phone's LAN Contact with the
  SBC tunnel address. For this Path topology start with **`rewrite_contact=no`**
  on these endpoints. `force_rport=yes` and `rtp_symmetric=yes` may be used.
- Set transport `local_net` to include the SBC tunnel address/subnet, so PBX
  NAT handling does not advertise an unreachable external media address.
  PBX SDP must advertise `pbx_ip`, not a different/public media IP.
- Disable SIP ALG on both routers. Keep matching codecs and RFC4733 DTMF on
  phones and PBX.

Illustrative **settings only** (do not paste incomplete objects over production
configuration; configure the existing objects in your PBX):

```ini
; Existing PJSIP AOR for the extension:
support_path=yes

; Existing PJSIP endpoint for the extension:
direct_media=no
rewrite_contact=no
force_rport=yes
rtp_symmetric=yes

; Existing PJSIP transport:
local_net=10.77.0.2/32
```

VitalPBX versions expose advanced PJSIP settings differently. If your version
cannot persist `support_path` or cannot retain a LAN Contact, **stop**: a
registration-anchoring design or PBX-specific integration is needed. Do not
assume outgoing registration means incoming calls will work. `chan_sip` is not
covered by this first version.

### Firewall rules — mandatory

Allow these narrowly in your existing firewall/security groups:

| Location | Allow |
| --- | --- |
| Remote router/gateway | Public UDP `wireguard_port` to remote gateway |
| Local SBC input | Voice subnet → `lan_ip`: UDP `sbc_sip_port` and SBC RTP range |
| Local SBC input via `wg-sbc` | `pbx_ip` → `local_tunnel_ip`: UDP SBC SIP/RTP |
| Remote gateway forwarding | `local_tunnel_ip` → `pbx_ip`: UDP PBX SIP/RTP |
| Remote gateway forwarding | `pbx_ip` → `local_tunnel_ip`: UDP SBC SIP/RTP |
| PBX input/output | SBC tunnel address ↔ PBX UDP SIP/RTP |

Stateful replies and the tunnel's outbound UDP must also be permitted. The
remote guard blocks other tunnel-originated access, including gateway services;
do not expect a ping to the remote tunnel IP to work. Use the handshake check.
RTPengine's UDP 2223 control interface binds only to loopback and is guarded.
Do not expose public SIP/RTP for this connection.

## 5. Configure a test phone

Keep the normal PBX registrar/domain, extension number, authentication ID and
password. Set its **outbound proxy** to the local SBC's LAN IP and SIP port.
Use UDP transport. Disable STUN, SIP ALG and TLS/SRTP for this baseline.
Do not change the registrar domain just to point at the SBC: that can change
the authentication realm or PBX domain matching.

Start with one test extension before migrating the site.

## 6. Diagnostics and acceptance

On each appliance:

```bash
sudo bash status.sh
sudo journalctl -u wg-quick@wg-sbc -n 50 --no-pager
```

On the local SBC:

```bash
sudo journalctl -u sbc-sip -u sbc-media -n 100 --no-pager
sudo kamailio -c -f /etc/sbc-edge/rendered/kamailio.cfg
```

On Asterisk:

```bash
sudo asterisk -rx 'pjsip show contacts'
sudo asterisk -rx 'pjsip show aor YOUR_EXTENSION'
sudo asterisk -rx 'pjsip show endpoint YOUR_EXTENSION'
```

Confirm the configured AOR supports Path and has a registered phone Contact,
and that Path leads to the SBC tunnel address. If needed temporarily use the
Asterisk PJSIP logger to inspect REGISTER/200 OK and incoming Route headers,
then turn it off. SIP traces may contain extension identifiers, digest material
and phone numbers: keep them private.

**Do not use for production until all pass:**

- Recent WireGuard handshake, including after router/NAT restart.
- REGISTER receives its normal 401 challenge, then succeeds with credentials.
- Outgoing and **new incoming** calls work, including after registration refresh.
- Two-way audio on both calls; codec and DTMF work.
- Hold/resume, transfer, re-INVITE and long calls work.
- Calls release correctly from either side and media allocations expire.
- Incoming calls still work after both appliances reboot.
- Unknown networks cannot use SIP/media or forward arbitrary traffic through
  the gateway. PBX authentication and toll restrictions remain enforced.

Registration with no incoming calls usually means missing Path support, wrong
Contact rewriting, or the missing PBX return route. One-way audio usually means
direct media, wrong SDP address, or blocked/mismatched RTP ranges.

## Rollback

This disconnects active SBC calls. On local, then remote:

```bash
sudo bash rollback.sh --confirm
```

This stops the dedicated services and removes their tunnel, firewall table and
configuration. It preserves OS packages, the private key and the site's JSON
configuration. It does not purge Kamailio/RTPengine or touch vendor config files.
If installation failed after activation began, the same rollback command applies.

Remote forwarding is intentionally **not** disabled automatically, since another
service could now rely on it. Rollback displays its previous value. If appropriate,
restore it manually after confirming no other routing service needs forwarding:

```bash
# Only when the previous value was 0 and nothing else needs forwarding:
sudo sysctl -w net.ipv4.ip_forward=0
```

Remove the route you added on the PBX/router, restore original phone proxy and
PBX settings, and remove the firewall/port-forward exceptions you added.
For the example route only:

```bash
sudo ip route del 10.77.0.2/32 via 192.168.100.10
```

For a clean reinstall on the same SBC, Kamailio/RTPengine packages may remain.
The installer deliberately refuses existing vendor units; after rollback inspect
their configuration, then use a fresh dedicated OS or remove those unused packages
under your normal system administration process. Do not delete production services
to force the installer to run.

## Security and scope

WireGuard encrypts the inter-site link. Phone-to-SBC traffic on the voice LAN and
gateway-to-PBX traffic on the remote LAN are ordinary SIP/RTP, not encrypted.
Use isolated, trusted LANs. This is not end-to-end encrypted voice.

Kamailio limits sources, destinations, methods, hop counts and per-source request
rates. It forwards digest authentication to the PBX; it is not a credential vault
or an independent registrar. This version does not provide commercial SBC
certification, topology hiding, HA, automated fleet management, billing-fraud
prevention, emergency-call guarantees, transcoding, TLS/SRTP or a web dashboard.

### Source references

- https://www.kamailio.org/docs/modules/5.6.x/modules/rr.html
- https://www.kamailio.org/docs/modules/5.6.x/modules/rtpengine.html
- https://www.kamailio.org/docs/modules/5.6.x/modules/path.html
- https://rtpengine.readthedocs.io/en/latest/rtpengine.html
- https://docs.asterisk.org/Latest_API/API_Documentation/Module_Configuration/res_pjsip/
