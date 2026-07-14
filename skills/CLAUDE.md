# E-Invoicing Portal — Frontend Architecture Decisions

> **STATUS: PROPOSED, pending reconciliation with the existing codebase.**
> This document captures the architecture agreed in a planning session
> (2026-07-14). The repo currently contains a conflicting early frontend
> scaffold (`frontend/` — Refine + AntD + axios, npm workspaces:
> `shared`/`tenant-portal`/`admin-portal`) and a mature custom design system
> in `design-prototype/` (tokens, palettes, all tenant+admin screens in
> HTML/CSS, own COMPONENTS.md/ROADMAP.md). **Do not modify or delete the
> existing frontend based on this document.** Two tasks must happen first:
> 1. **Migration analysis** — Refine+AntD scaffold vs. the stack below,
>    assessed against the design prototype's custom look (AntD cannot
>    reproduce it without heavy fighting). Concrete effort estimates both
>    ways; the owner decides.
> 2. **Design blueprint** — extract from `design-prototype/` a full
>    inventory: design tokens/color schemes, screen list, reusable component
>    list (mapped to build strategy), reconciled with the backend API
>    surface. Reconcile with the prototype's own COMPONENTS.md/ROADMAP.md
>    rather than duplicating them.
> AGENTS.md (project history from earlier sessions) remains authoritative for
> what exists; this file is the proposed target architecture.

Multi-tenant e-invoicing web application: CRUD-heavy admin screens, dashboards,
compliance workflows (submission → clearance). Solo project: the owner is a
senior **backend** engineer with limited React depth and **no human frontend
reviewer**. Claude Code writes most frontend code; correctness is verified
through **behavior (Playwright E2E), not code review**. Every architectural
choice below follows from that constraint — do not deviate from these decisions
without flagging it explicitly and explaining the trade-off in plain terms.

## Architecture decisions (proposed in the 2026-07-14 planning session)

1. **No frontend framework** (no Refine, no React-Admin, no Next.js). We
   assemble best-in-class headless libraries with a thin, explicit glue layer
   that lives in this repo. Explicit code beats framework magic because the
   owner must be able to read what exists and debug without framework
   internals knowledge.
2. **Thin frontend.** All business logic — validation rules, tax calculation,
   invoice state machines, numbering, tenant isolation enforcement — lives in
   the backend. The frontend fetches, displays, and submits. If a task seems
   to require business logic in the frontend, stop and propose a backend
   endpoint instead.
3. **Logic engines from libraries, never hand-rolled:**
   - Data fetching/caching: **TanStack Query v5**
   - Table logic: **TanStack Table v8** (headless)
   - Forms: **React Hook Form + Zod** (via `@hookform/resolvers`)
   - Routing: **react-router-dom v7**
   - UI behavior primitives: **Radix** via **shadcn copy-in** components
   - Styling: **Tailwind v4** — fully custom design, no UI kit (no AntD/MUI)
4. **Zod at every API boundary.** Every response is parsed against a schema
   before use. Contract drift must fail loudly, never render silently wrong.

## Auth (cookie sessions — NOT localStorage JWT)

- Username/password login: `POST /auth/login` → backend sets an **httpOnly,
  Secure, SameSite=Lax session cookie**. Frontend never sees, stores, or
  refreshes any token. Never put credentials in localStorage/sessionStorage.
- All requests: `credentials: 'include'` in the shared fetch wrapper.
- `GET /auth/me` → `{ user, permissions, tenants }` — single source of truth,
  cached in the query cache until a 401.
- Any 401 anywhere → invalidate the `me` query → redirect to `/login`.
- Mutations send the CSRF token header (backend provides it).
- UI permission checks are UX only; the backend is the enforcement layer.

## Multi-tenancy

- Active tenant lives in a `TenantContext`; the fetch wrapper injects it into
  every request (header or path — match the backend contract).
- **Every query key starts with the tenant id**: `[tenantId, resource, ...]`.
  This makes cross-tenant cache leakage structurally impossible. Never write a
  query key that omits the tenant for tenant-scoped data.
- On tenant switch: `queryClient.clear()`.

## Data layer conventions

- One fetch wrapper: `src/api/request.ts` — base URL, `credentials:
  'include'`, tenant injection, Zod parse, normalized `ApiError`. All requests
  go through it; never call `fetch` directly in components.
- Query keys come from the factory in `src/api/keys.ts`. Never inline key
  arrays in pages.
- Mutations go through `useResourceMutation`, which invalidates the whole
  resource family on success: `invalidateQueries([tenantId, resource])`.
  **Dumb, broad invalidation — never surgical cache updates** unless
  explicitly requested; an extra refetch is cheaper than a staleness bug
  nobody will catch.
- staleTime policy (encode as category presets, pick one per query):
  | Category | staleTime |
  |---|---|
  | Reference data (tax codes, currencies, units) | 1–24 h |
  | Tenant config | 5–15 min |
  | List views | 30–60 s |
  | Detail-for-edit | 0 (always refetch on open) |
  | Compliance/submission status | 0 + `refetchInterval` polling |
  | `/auth/me` | ∞ until 401 |
  | Dashboard aggregates | 1–5 min, visible refresh button |
  When unsure: `staleTime: 0`. Correctness beats saved requests in a
  compliance app.

## UI conventions

- Components: shadcn-style **copy-in** under `src/components/ui/` — we own
  every line; restyle freely with Tailwind. Interactive primitives (Dialog,
  Select, Dropdown, Popover, Tabs, Switch, Checkbox, Tooltip, Toast) keep
  their Radix engines — never hand-roll focus traps, keyboard nav, or
  positioning.
- One generic `<DataTable>` (TanStack Table + URL-synced pagination/sort/
  filters + loading/empty/error states). Pages pass columns + resource only.
- One form kit: `useResourceForm` (RHF + Zod, edit-mode record fetch, 422
  field-error mapping into `setError`, invalidate-and-navigate on success).
- RBAC in UI: `<Can permission="...">` for elements, `<RequirePermission>`
  route guard, sidebar items filtered by a `permission` field in the nav
  config array.
- New resources copy the golden exemplar (see below) — same file layout, same
  patterns, no inventing new ones.

## Resource file layout (per resource, e.g. invoices)

```
src/pages/invoices/
  api.ts          # query hooks + mutations for this resource (uses keys.ts)
  schema.ts       # Zod schemas: entity, list response, create/update inputs
  columns.tsx     # DataTable column defs
  InvoiceListPage.tsx
  InvoiceDetailPage.tsx
  InvoiceFormPage.tsx   # create + edit
  __tests__/
```

The first fully-built resource is the **golden exemplar**. When asked to add
a resource, replicate its structure exactly.

## Testing — this replaces the human reviewer

- **Playwright E2E is the primary quality gate.** Every user-facing flow gets
  an E2E test, including at least one negative RBAC/tenant-isolation case
  (e.g. tenant A's invoice invisible to tenant B; forbidden action hidden AND
  rejected). A feature without an E2E test is not done.
- Vitest + Testing Library for glue-layer units (fetch wrapper, key factory,
  guards) and non-trivial components.
- Never claim a task complete without running: `npm run lint && npm run test`
  (and the relevant Playwright spec for flow changes). Report failures
  honestly.

## Guardrails

- TypeScript `strict: true`. ESLint flat config with `--max-warnings=0`,
  including `eslint-plugin-react-hooks`. Prettier. Husky + lint-staged
  pre-commit.
- Exact dependency versions (no `^`); upgrades are deliberate, separate tasks.
- Do not add dependencies without asking. Especially not: axios, Redux,
  Zustand, moment, lodash, styled-components, i18next, any UI kit, any
  framework.
- Commit/push only when explicitly asked.

## Communication with the owner

- Explain frontend-specific concepts (hooks rules, effects, re-renders,
  portals) briefly when they drive a decision — owner is a strong engineer,
  just not a React specialist. Use backend analogies where natural (query
  cache ≈ read-through cache with TTL; invalidation ≈ prefix cache-bust).
- Prefer boring, explicit, well-trodden patterns over clever ones — the code
  must be readable by a non-React expert.

## Build order (phase 1)

Vertical slice first, before any breadth: login (cookie session) → tenant
switcher → invoices list in `<DataTable>` → invoice create form → one
Playwright test covering the whole flow against the real backend. Only after
the slice is approved: foundation hardening, then fan out resources from the
golden exemplar.
