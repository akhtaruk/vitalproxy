# Local Network SIP SBC

Installable scripts for a self-managed Linux SIP SBC and a remote WireGuard gateway
connecting local phones to an Asterisk/VitalPBX PBX. This is not a hosted web app.

## SBC deliverable

- `sbc/README.md` — deployment, PBX settings, firewall, testing and rollback guide.
- `sbc/install-local.sh` / `sbc/install-remote.sh` — appliance entry points.
- `sbc/sbc.py` — strict JSON validation and offline config rendering.
- `sbc/templates/` — SIP, media and isolated firewall templates.
- `python3 sbc/build_download.py` — builds an offline HTML guide with embedded
  downloadable scripts/ZIP in ignored `generated-artifacts/`.
- Do not run appliance installation scripts inside Replit. They target dedicated
  Debian 12/13 or Ubuntu 24.04 systemd machines and require root.
- Asterisk integration requires PJSIP AOR `support_path=yes`, endpoint
  `direct_media=no` and a PBX return route to the SBC tunnel address.
- This is an initial lab build; no live PBX registration/audio validation has
  been performed. Do not claim universal PBX compatibility or production readiness.

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
