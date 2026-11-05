---
name: SBC deployment scope
description: User's intended installation environment and network control
---

The user wants a simple SIP outbound proxy on one Debian 13 machine on their LAN
for their existing VitalPBX server. They explicitly do not want a VPN or a second
gateway computer. Their VitalPBX already has OpenVPN, but they said to forget VPN.

**Why:** The user narrowed the requirement to a LAN outbound proxy and rejected
the earlier two-endpoint VPN design.

**How to apply:** Deliver a one-machine Debian 13 Kamailio SIP proxy. Be explicit
that the current simple proxy forwards SIP only, not RTP/audio, and does not solve
new incoming calls to phones behind NAT. Do not install on the PBX without request.
