# Local Network SIP SBC

Installable Kamailio SIP signalling proxy on one Debian 13 machine on the phone LAN,
forwarding local phone SIP traffic to an existing VitalPBX server. No VPN or second
gateway; media is not relayed. This is not a hosted web app.

## SBC deliverable

- `sbc/README.md` — installation, phone settings, firewall and rollback guide.
- `sbc/install-proxy.sh` — single-machine Debian 13 installer.
- `sbc/proxy-config.py` — strict configuration validation and rendering.
- `sbc/templates/` — Kamailio routing and isolated firewall configuration.
- `python3 sbc/build_download.py` — builds an offline HTML guide with embedded
  downloadable scripts/ZIP in ignored `generated-artifacts/`.
- Do not run the installer inside Replit. It targets a Debian 13 systemd machine
  on the local phone LAN and requires root.
- SIP signalling only: RTP/audio goes direct; new incoming calls behind NAT are
  not supported in this first version.
- Do not claim universal PBX compatibility or production readiness.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

_Populate as you build — short repo map plus pointers to the source-of-truth file for DB schema, API contracts, theme files, etc._

## Architecture decisions

_Populate as you build — non-obvious choices a reader couldn't infer from the code (3-5 bullets)._

## Product

_Describe the high-level user-facing capabilities of this app once they exist._

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
