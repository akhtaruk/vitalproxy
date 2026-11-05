---
name: Kamailio validation
description: Native configuration validation is required before distributing proxy scripts
---

Validate rendered configurations with the target Kamailio version's native
checker before delivering or refreshing the installation ZIP.

**Why:** Shell/Python checks passed while the user's Debian installation repeatedly
failed on unsupported core directives and missing SIP module dependencies.
Those checks do not validate Kamailio's configuration language or exports.

**How to apply:** Run native configuration validation as part of packaging. Keep
config-parser success separate from service startup, registration and real-call
verification; none implies the others.
