---
name: SBC deployment scope
description: User's intended installation environment and network control
---

The user wants an SBC installed on their local network, connecting to Asterisk
servers such as VitalPBX. They confirmed they control both sides and can install
a remote tunnel endpoint.

**Why:** The user explicitly confirmed control of both sides; an administrator-
managed tunnel is feasible instead of relying on SIP-only access.

**How to apply:** Deliver scripts and deployment guidance for their own Linux
devices. Do not substitute a hosted dashboard or suggest publishing the SBC on
Replit. Do not assume access to the user's actual phone or PBX network.
