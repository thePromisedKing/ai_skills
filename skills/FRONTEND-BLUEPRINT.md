# FRONTEND-BLUEPRINT.md — Master Build Plan for the Portal UI

> **Status: APPROVED direction (owner decision, 2026-07-14).** The owner chose to
> build the frontend on the headless stack with the custom design system from
> `design-prototype/`, replacing the frozen Refine + AntD scaffold in `frontend/`.
> Rationale and effort analysis: `docs/FRONTEND-DIRECTION.md`.
>
> **This document is the single entry point for any AI agent building the UI.**
> It assumes you have NO prior conversation context — only this repository.
> It supersedes `docs/FRONTEND_SKILL.md` (an older draft that predates these
> decisions: it mentions React 18, axios, React Router v6 — those parts are stale).

---

## 0. How to use this document

### 0.1 Reading order before writing any code

1. **`CLAUDE.md`** (repo root) — architecture constitution. Its rules are binding.
2. **This document** — what to build, with what, in what order.
3. **`AGENTS.md`** (repo root) — the backend: API surface (§6), envelope format,
   multi-tenancy model (§4.4), domain flows (§1). The backend is the source of
   truth for all business behavior.
4. **`design-prototype/COMPONENTS.md`** — the component registry. Every component
   has a stable code (`PIL-01`, `TBL-01`, `MDL-01`…) with copyable reference markup.
   **Do not duplicate that registry here — consult it.**
5. For each screen you build: open the matching `design-prototype/*.html` file in a
   browser (no build step needed) and read its markup. The prototype is the visual
   contract. `design-prototype/assets/theme.css` is the styling source of truth.

### 0.2 Authority map (when sources disagree)

| Question | Authoritative source |
|---|---|
| Architecture rules, stack, conventions | `CLAUDE.md`, then this doc |
| What an endpoint returns / accepts | Backend code: `backend/tenant-api/`, `backend/admin-api/` DTOs — not any doc |
| What a screen looks like | `design-prototype/<screen>.html` + `assets/theme.css` |
| Component markup/anatomy | `design-prototype/COMPONENTS.md` + `design-system.html` |
| What the old app did (behavior reference) | `frontend/` (frozen — read, never modify, never import from) |
| Prototype build status / known gaps | `design-prototype/ROADMAP.md` |

### 0.3 Standing rules for the building agent

- The `frontend/` directory is **frozen**: read it as a behavioral reference
  (e.g. how batch polling worked), never modify it, never import from it.
- The `design-prototype/` directory is **read-only reference**. Never modify it.
- Do not implement features not listed in the phase you were asked to work on.
- Never add a dependency outside §2's manifest without explicit owner approval.
- Every claim of "done" requires the verification gate in §11.1 to pass. Report
  failures honestly, with output.

---

## 1. What is being built

Two separate single-page apps against an existing Spring Boot backend
(UAE e-invoicing SaaS — invoices, VAT, FTA compliance validation, ASP submission):

- **Tenant portal** — organizations manage customers, products, invoices, credit
  notes, recurring invoices, bulk e-invoice submission, reports, settings.
  Base API `/api/v1`. Requires `X-Organization-Id` header on business calls.
- **Admin portal** — platform operators onboard and manage organizations.
  Base API `/api/v1/admin`. Must NEVER send the org header.

Hard boundary: the two portals never import each other's code and share only the
foundation package (§3). A tenant screen must never appear in the admin app.

The frontend is **thin**: it fetches, displays, submits. All validation rules, VAT
math, state machines, numbering, and tenant isolation live in the backend. If a
task appears to need business logic in the frontend, stop and flag it — propose a
backend endpoint instead.

---

## 2. Locked stack — library manifest

Decisions from the 2026-07-14 planning session (`CLAUDE.md`) plus the additions
approved with `docs/FRONTEND-DIRECTION.md` §6. Install with `--save-exact`
(no `^`/`~` — upgrades are deliberate, separate tasks).

### 2.1 Runtime dependencies

| Concern | Library | Notes |
|---|---|---|
| Framework | `react`, `react-dom` (19.x) | |
| Routing | `react-router-dom` (v7) | `createBrowserRouter` data router — **required** by the unsaved-changes guard (`useBlocker`, §9), which does not work under plain `<Routes>`. Used thinly: no loaders/actions, all data stays in TanStack Query; guards remain components |
| Server state | `@tanstack/react-query` (v5) | The ONLY data-fetching mechanism |
| Tables | `@tanstack/react-table` (v8) | Headless; wrapped once in `<DataTable>` |
| Forms | `react-hook-form` + `zod` + `@hookform/resolvers` | Zod also validates every API response |
| UI primitives | Radix packages pulled in by shadcn copy-in | Dialog, AlertDialog, Select, DropdownMenu, Popover, Tabs, Switch, Checkbox, RadioGroup, Tooltip, Toast |
| Styling | `tailwindcss` (v4) + `@tailwindcss/vite` | No UI kit. Tokens via CSS variables (§4) |
| Class utils | `clsx`, `tailwind-merge`, `class-variance-authority` | Standard shadcn tooling; wrap as `cn()` |
| Icons | `lucide-react` | The prototype's icon set (stroke 1.7) — recommended by COMPONENTS.md |
| Command palette / combobox | `cmdk` | Powers ⌘K palette AND searchable selects (customer/product pickers) |
| Date picker | `react-day-picker` | Inside a Radix Popover; prototype has no date-picker design — style it with the tokens (§16.1) |

### 2.2 Dev dependencies

`vite`, `@vitejs/plugin-react`, `typescript` (strict), `vitest`,
`@testing-library/react`, `@testing-library/user-event`, `jsdom`,
`@playwright/test`, `eslint` (flat config) + `typescript-eslint` +
`eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`, `prettier`,
`husky`, `lint-staged`.

### 2.3 Explicitly banned

`axios` (use `fetch`), any Refine package, `antd`/MUI/Chakra/Mantine/Bootstrap,
`moment`/`dayjs` (use `Intl` + string dates), `lodash`, `redux`/`zustand`/`jotai`
(TanStack Query + React context is the entire state story), `styled-components`/
Emotion, `i18next` (localization is deferred, §16), **any chart library**
(charts are ported SVG components, §5.6).

Formatting helpers: money via `Intl.NumberFormat("en-AE", { style: "currency" })`,
dates cross the wire as `"YYYY-MM-DD"` strings and display via
`toLocaleDateString("en-GB")` — one helper each in the foundation package.

---

## 3. Workspace layout

New workspace root **`web/`** (the frozen scaffold stays at `frontend/` until
decommission — see phase plan §11).

```
web/
├── package.json              # npm workspaces: ["foundation","tenant-portal","admin-portal"]
│                             # exact-version pins; single source of dependency truth
├── foundation/               # @foundation/* — shared FOUNDATION ONLY, never domain code
│   └── src/
│       ├── styles/
│       │   ├── tokens.css    # ported from design-prototype/assets/theme.css (§4)
│       │   └── prototype/    # scoped one-off CSS ports (invoice sheet, charts) (§14.4)
│       ├── ui/               # shadcn-style copy-in primitives + ported components (§5)
│       ├── components/       # DataTable, form kit fields, shell pieces (§5–6)
│       ├── api/              # createRequest (fetch wrapper factory), envelope types,
│       │   ...               # ApiError, pagination schema helpers (§7)
│       ├── auth/             # useMe, RequireAuth, Can, RequirePermission (§8)
│       ├── format/           # money.ts, date.ts, trn.ts
│       └── types/            # enums.ts (port from frontend/shared/src/types/enums.ts)
├── tenant-portal/
│   └── src/
│       ├── main.tsx, App.tsx, routes.tsx, nav.ts        # nav config array w/ permission field
│       ├── api/  request.ts  keys.ts  queryClient.ts    # portal-concrete instances (§7)
│       ├── tenant/ TenantContext.tsx  TenantSwitcher.tsx
│       └── pages/<resource>/                            # per-resource layout (§6)
├── admin-portal/             # same shape; no TenantContext; base /api/v1/admin
└── e2e/                      # Playwright root: tenant/ admin/ fixtures/ (§13)
```

**Shared vs per-portal rule** (same as the backend's module discipline): the
foundation package holds design system + glue with zero domain knowledge. All
domain features (pages, schemas, columns, nav) are per-portal. When both portals
need domain-ish code, duplicate it — never create a shared domain module.

Vite per portal: `@foundation` alias, `resolve.dedupe: ["react","react-dom"]`,
dev proxy `/api → http://localhost:8080`, ports 5174 (tenant) / 5175 (admin) to
avoid clashing with the old scaffold's 5173.

TypeScript: `strict: true`, `noUnusedLocals: true` (the old scaffold had this off —
turn it on), `noUncheckedIndexedAccess: true`, `moduleResolution: "bundler"`.

---

## 4. Design system adoption — tokens & theming

### 4.1 Port strategy

`design-prototype/assets/theme.css` (842 lines) is ported, not reinvented:

1. **Tokens block** (lines 1–120: `:root`, dark blocks, 7 `data-palette` blocks,
   5 `data-sidebar` blocks) → copy near-verbatim into
   `foundation/src/styles/tokens.css`. Keep the CSS-variable names (`--brand`,
   `--surface-2`, `--side-bg`, …) and the `color-mix()` derivations exactly — they
   are plain CSS and work unchanged under Tailwind v4.
2. **Expose tokens to Tailwind** via v4's `@theme inline` so utilities resolve them:
   `--color-brand: var(--brand); --color-surface: var(--surface);
   --color-surface-2: var(--surface-2); --color-border: var(--border);
   --color-text-2: var(--text-2); --color-danger-fg: var(--danger-fg);
   --radius-ctrl: var(--r-ctrl); --radius-card: var(--r-card);
   --shadow-card: var(--shadow); --font-sans/--font-mono` … (map every token).
   Components then use `bg-surface-2 border-border text-text-2 rounded-ctrl`.
3. **Component rules** from theme.css are NOT ported as global CSS. They become the
   styling of the corresponding React component (§5) — as Tailwind utilities for
   simple cases, or a scoped stylesheet ported as-is for complex one-offs (§14.4).

### 4.2 Theming mechanics (keep the prototype's design verbatim)

- Light/dark: `data-theme` attribute on `<html>`, persisted in `localStorage`
  (`eiv-theme`), OS-preference fallback via the `@media (prefers-color-scheme)`
  block. **Pitfall inherited from the prototype: dark tokens exist in BOTH the
  `[data-theme="dark"]` block and the `@media` block — edits must touch both.**
- Brand palette: `data-palette` (`eiv-palette`) — 7 palettes; only `--brand*` and
  `--side-accent` change; neutrals re-derive automatically via `color-mix`.
- Sidebar theme: `data-sidebar` (`eiv-sidebar-theme`) — independent of palette.
- A small `applyTheme.ts` in foundation sets these attributes **before first paint**
  (inline in `index.html` head or top of `main.tsx`) to avoid a flash.
- Semantic colors (success/warn/danger/info) never change with palette and are
  never used as brand accent.

### 4.3 Non-negotiable styling rules

- **No hex colors in components. Ever.** Tokens only.
- No arbitrary Tailwind values for colors/radii/shadows (`bg-[#0E7A64]` is a
  review-blocker); spacing may use the standard scale (prototype is 4-based).
- `tabular-nums` + mono font for money, TRNs, counts, and IDs (`.trn` convention).
- Focus ring: brand border + `0 0 0 3px var(--brand-weak)` — the `Field`/`Input`
  primitives own this; never restyle per page.
- RTL groundwork: use logical properties/utilities (`ms-*`/`me-*`,
  `margin-inline-start`) — the prototype already does; don't regress it.

---

## 5. Component build inventory

Complete list of what gets built in `foundation/`, mapped from the prototype.
Registry codes refer to `design-prototype/COMPONENTS.md`. Build strategies:

- **[CSS]** — pure markup + Tailwind/ported CSS; no behavior engine needed.
- **[RADIX]** — shadcn copy-in; keep the Radix engine (focus, keyboard, positioning,
  ARIA), replace ALL styling with prototype tokens. Never hand-roll these behaviors.
- **[ENGINE]** — custom component on a headless library (TanStack, RHF, cmdk, …).

### 5.1 Primitives

| Component | Code | Strategy | Notes |
|---|---|---|---|
| Button | BTN-01/02/03 | [CSS] | `cva` variants: `default`, `primary`, `danger`, `success`, `ghost` (toolbar `.tbtn`), sizes; 38px height, `--r-ctrl` |
| IconButton | IBT-01 | [CSS] | 36×36; row-action variant `.act` 32×32 |
| Input / Textarea | INP-01, TXA-01 | [CSS] | 40px; `mono` variant; leading-icon wrapper |
| Field | FLD-01, FLD-ERR | [ENGINE] | RHF-aware: label + required mark + control + hint + error (red border, `.field-error` row). All forms use it (§9) |
| Select (simple) | SEL-01 | [RADIX] | Radix Select styled as prototype's `.input`/`.filter` with chevron |
| Combobox (searchable) | — | [ENGINE] | `cmdk` inside Radix Popover; used for customer/product pickers |
| Checkbox / Radio / Switch | CHK/RDO/SWT-01 | [RADIX] | Switch = 40×22 track per prototype |
| SegmentedControl | SEG-01 | [CSS] | Radix ToggleGroup acceptable; visual is `.seg` |
| DatePicker | — | [ENGINE] | `react-day-picker` in Popover; emits/accepts `"YYYY-MM-DD"` strings only |
| Pill (status) | PIL-01 | [CSS] | Colored dot + tinted bg. One central `<StatusPill status={...}>` maps ALL backend enums → variant (port the mapping from `frontend/shared/src/ui/StatusTag.tsx`, keep the enum names) |
| TagSoft / CountBadge / Delta | TAG-01, BDG-01 | [CSS] | |
| Avatar | AVA-01 | [CSS] | Initials + deterministic tint class `a1–a6` (hash of name) |
| Alert banner | ALT-01 | [CSS] | `ok`/`warn`/`danger` |
| Progress / Skeleton / Spinner | PRG/SKL/SPN-01 | [CSS] | Skeleton respects `prefers-reduced-motion` |
| EmptyState | EMP-01 | [CSS] | Icon + title + subtitle + CTA slot |
| KV list | KV-01 | [CSS] | Detail-pane key-value rows |
| Divider, CodePill, Kbd | DIV, etc. | [CSS] | |
| Tooltip | TIP | [RADIX] | |
| Tabs | TAB-01 | [RADIX] | Underline-active style; also detail-tabs variant |
| Modal / ConfirmDialog | MDL-01/02 | [RADIX] | Dialog + AlertDialog; icon header, `danger` variant, footer on `--surface-2`. ConfirmDialog replaces the old `ConfirmActionButton` (used by every lifecycle action) |
| Popover / DropdownMenu | POP-01, MNU-01 | [RADIX] | Menu supports icons, kbd hints, separators, `danger` items |
| Toast system | TST-01/02 | [RADIX] | Radix Toast, two anatomies: status toast (bottom-right, auto-dismiss 3.2s) and rich notification (top-right, avatar + title + Close). Expose `toast.success/error/info/warn()` |
| Stepper | STP-01 | [CSS] | Numbered dots + connector, `done/active/error` states (import wizard, onboarding, batch workflow) |
| Pagination | PGN | [CSS] | `.pg` buttons + rows-per-page select (persist `eiv-page-size`); rendered by DataTable footer |
| BulkBar | BULK | [CSS] | Shown when DataTable rows selected |
| Dropzone | — | [ENGINE] | Real `<input type="file">` + drag events styled as `.dropzone`; used by all Excel imports |

### 5.2 Application shell (tenant + admin share these, config-driven)

| Component | Source in prototype | Notes |
|---|---|---|
| `AppShell` | `.app` grid | 244px sidebar + main; collapse → 64px rail (`eiv-sidebar` persisted); mobile off-canvas drawer + backdrop (<900px) |
| `Sidebar` | `.sidebar` | Always-dark shell; brand tile (gradient), nav sections from a config array `{ label, icon, to, permission, count? }`, "Getting Started" widget (optional slot), footer account block |
| `AccountMenu` | `.user-menu` | Pops above sidebar footer: identity, **active-org block with Switch action (tenant only)**, theme toggle, settings, logout (danger) |
| `Topbar` | `.topbar` | Global search field (focus opens command palette), quick-create menu (3-column, config-driven), notification bell + panel, icon buttons |
| `CrumbBar` | `.crumb-bar` | Breadcrumb strip under topbar, driven by route config |
| `AppFooter` | `.app-footer` | Slim, pinned; version chip reads the repo `VERSION` |
| `CommandPalette` | `.cmdk` | `cmdk` dialog: navigation + quick actions; ⌘K, `g`-then-key nav shortcuts, `?` cheatsheet modal |
| `NotificationPanel` | `.notif-panel` | Popover list, unread tint, mark-all-read (client-side until a backend endpoint exists — flag when wiring) |
| `AuthLayout` | `auth.html` | Centered card, brand header |
| `ErrorPage` | `error.html` | 404 / 403 / 500 / session-expired variants |
| `SettingsLayout` | `.settings-layout` | Sticky sub-nav + panels |
| `RecordLayout` | `.record-layout` | Master–detail: left record list (search, active row w/ inset accent bar) + right detail (header, tabs, scrollable body). **Layout pitfall from the prototype: every flex/grid child in the chain needs `min-h-0`, and the topbar needs `flex-none`** |
| `EditorLayout` | `.editor-grid` | Content + 320px sticky right rail (totals/compliance) + sticky action bar |

**Error boundaries (crash policy):** each portal wraps its router root in a React
ErrorBoundary rendering the 500 `ErrorPage` variant (include `traceId` when the
crash carries an `ApiError`), and each top-level route group gets its own boundary
so one crashed screen never takes down the shell. A render crash must never
white-screen the app. (Route-level `errorElement` from the data router may serve
as the per-group boundary.)

### 5.3 DataTable (the single generic table — spec in §10)

### 5.4 Form kit (spec in §9)

### 5.5 Domain-flavored foundation components

Port these concepts from the old scaffold (read `frontend/shared/src/ui/` for
behavior, restyle to prototype):

| Component | Replaces / prototype source | Notes |
|---|---|---|
| `LineItemsEditor` | `LineItemsField.tsx` / `.li-table` | RHF `useFieldArray`; borderless inline inputs, row remove, dashed add-line button, live line totals. **Do NOT port the client-side VAT estimate (`VAT_RATE_ESTIMATE`)** — VAT is backend business logic. Show server-computed totals from the draft response; any client-side preview must be labeled "estimated" and never submitted |
| `ComplianceBadge` + `ValidationIssuesList` | same names in old scaffold / `.issue-panel`, `.vid` | FTA issue chips: mono code (`BR-AE-08`), severity color, message + pass criteria |
| `ComplianceRail` | invoice-editor rail | Checklist rows (`.check-row`), status card, issue panel toggle |
| `InvoiceSheet` | `invoice-view.html` `.inv-sheet` | Printable tax-invoice document: corner status ribbon, doc table (dark header), totals box, FTA strip with UUID. Print stylesheet → browser print = PDF. Reused by credit-note view |
| `WorkflowSteps` | `batch-detail.html` | The 6-step submission stepper incl. `*_ACTION_REQUIRED`/failed states |

### 5.6 Charts (no library)

Port the prototype's hand-built SVG charts (inline JS in `dashboard.html` /
`reports.html`) into React SVG components: `TrendChart` (line/area, gradient fill,
hover crosshair + tooltip), `BarChart` (hover state), `StackBar` (CSS stacked bar +
legend), `CompLegend`. Theme-reactive via CSS variables automatically (the
prototype needed a MutationObserver; React re-render + `currentColor`/vars doesn't).
Axis text 11px `--text-3`, grid lines `--grid`, `tabular-nums`.

---

## 6. Screens — routes, APIs, components

Per-resource file layout (from CLAUDE.md — replicate exactly, no inventions):

```
src/pages/<resource>/
  api.ts          # query hooks + mutations (uses keys.ts)
  schema.ts       # Zod: entity, list response, create/update inputs
  columns.tsx     # DataTable column defs
  <Resource>ListPage.tsx | DetailPage.tsx | FormPage.tsx
  __tests__/
```

### 6.1 Tenant portal

staleTime presets (from CLAUDE.md): `reference` 1–24h · `config` 5–15m ·
`list` 30–60s · `detail-edit` 0 · `status-poll` 0 + refetchInterval · `me` ∞ ·
`dashboard` 1–5m. When unsure: 0.

| Route | Prototype file | Backend endpoints (base `/api/v1`) | Key components | staleTime |
|---|---|---|---|---|
| `/login` (+ forgot/reset/invite) | `auth.html` | `POST auth/login`, `GET auth/me` | AuthLayout, Field | — |
| `/` dashboard | `dashboard.html` | aggregates endpoint(s) — **verify what exists in `tenant-api`; if none, flag to owner (backend task)** | KPI tiles, TrendChart, StackBar, compact recent table, compliance card | dashboard |
| `/invoices` | `invoices.html` | `GET invoices` (paged) | DataTable, StatusPill, ComplianceBadge, submission actions | list |
| `/invoices/new`, `/invoices/:id/edit` | `invoice-editor.html` | `GET/POST/PUT invoices`, actions `issue`/`cancel`/`revalidate`/`submit` | EditorLayout, form kit, LineItemsEditor, ComplianceRail, ConfirmDialog | detail-edit |
| `/invoices/:id` | `invoice-view.html` | `GET invoices/{id}/document` | InvoiceSheet, doc toolbar (print/download) | detail-edit |
| `/customers` | `customers.html` | `GET customers` | DataTable, Avatar, summary strip, Excel import (`Dropzone` + template download) | list |
| `/customers/:id` (+ tabs) | `customer-detail.html` | `GET customers/{id}` + related lists | RecordLayout, KV, tabs | detail-edit |
| `/customers/:id/statement` | `customer-statement.html` | statement endpoint — **verify; flag if missing** | ledger table, aging | list |
| `/customers/new`, `/:id/edit` | `create-customer.html`, `edit-customer.html` | `POST/PUT customers` | form kit (bilingual name, TRN mono field, payment-terms select → `GET payment-terms`) | detail-edit |
| `/products` (+ detail/new/edit) | `products.html`, `product-*.html` | `GET/POST/PUT products`, `POST products/{id}/archive` | DataTable, form kit, RecordLayout | list / detail-edit |
| `/credit-notes` (+ editor/view) | `credit-note*.html` | `GET/POST/PUT credit-notes`, `issue`/`cancel` | as invoices, minus compliance rail; view reuses InvoiceSheet | list / detail-edit |
| `/recurring-invoices` (+ editor) | `recurring-*.html` | CRUD + `pause`/`resume`/`end` | DataTable, schedule form (frequency, next-runs preview), LineItemsEditor | list / detail-edit |
| `/einvoice/batches` | `einvoice-batches.html` | `GET einvoice/batches`, `POST einvoice/batches/upload` | DataTable, Dropzone upload | list |
| `/einvoice/batches/:id` | `batch-detail.html` | `GET einvoice/batches/{id}`, `submit`/`revalidate` | WorkflowSteps, per-invoice issue rows (ValidationIssuesList), counts | **status-poll: refetchInterval ~4s until terminal state** (port polling semantics from `frontend/.../einvoice-batches/index.tsx`; an invoice counts as submitted only per AGENTS.md Gotcha #7) |
| `/import` | `import.html` | template download + multipart upload endpoints | Stepper wizard: upload → map columns → review errors → commit | — |
| `/reports` | `reports.html` | report endpoints — **verify; flag gaps** | charts + tables | dashboard |
| `/settings/*` | `settings.html` | tenant config endpoints — **verify per panel; build panels only where backend support exists, stub the rest behind a "coming soon" card listed to the owner** | SettingsLayout | config |
| `*` errors | `error.html` | — | ErrorPage | — |

### 6.2 Admin portal (base `/api/v1/admin`, no org header)

| Route | Prototype file | Endpoints | Notes |
|---|---|---|---|
| `/login` | `auth.html` | `POST auth/login`, `GET auth/me` | Separate session from tenant — distinct cookie, see §8.1 |
| `/` dashboard | `admin-dashboard.html` | verify aggregates; flag gaps | KPIs, onboarding pipeline, FTA monitoring |
| `/organizations` | — (reuse list pattern) | `GET organizations?status=` | DataTable |
| `/organizations/:id` | — (RecordLayout) | `GET organizations/{id}`, `GET .../import-batches` | read view + import history |
| `/organizations/onboard/:id?` | `admin-onboarding.html` | `POST organizations`, `PATCH .../{id}`, `POST .../owner`, `POST .../activate`, `GET industries`, import endpoints + `GET organizations/import-templates/{type}` | 6-step Stepper wizard, **resumable draft** (each step PATCHes; re-entry loads draft). Port flow semantics from `frontend/admin-portal/src/pages/organizations/onboard.tsx` (449 lines — the most valuable behavior reference in the old scaffold): one-time owner password display + copy + confirm checkbox, TRN-expiry warning, already-active short-circuit |

Prototype gaps (ROADMAP ⬜): admin orgs list/detail screens have no dedicated
mockup — reuse the tenant master–detail and table patterns.

---

## 7. Data layer — exact specifications

### 7.1 The response envelope (every endpoint, success and error)

```
{ success, status, timestamp, traceId, path, data, errors }
```
- Success: payload in `data`; `errors: null`. Spring pages serialize **inside**
  `data` as `{ content, totalElements, totalPages, number, size }`.
- Error: `data: null`; `errors: [{ field, message }]` (multi-error capable).

### 7.2 `request.ts` — the single fetch wrapper (per portal, built on a foundation factory)

Signature sketch (implement to this contract):

```ts
request<T>(path, {
  method?, body?, query?,          // query → URLSearchParams
  schema: z.ZodType<T>,            // REQUIRED — parses envelope.data
  multipart?: boolean,             // FormData passthrough (imports)
  blob?: boolean,                  // template/document downloads (skips schema)
  idempotent?: boolean,            // attach X-Idempotency-Key (see below)
}): Promise<T>
```

Behavior, in order:
1. Prefix base URL (`/api/v1` tenant, `/api/v1/admin` admin). `credentials: 'include'`.
2. Tenant portal only: inject `X-Organization-Id` from `TenantContext` (skip `/auth/*`).
3. Mutating methods: attach the CSRF token header (name/source defined by the
   backend session work — see §8.1 prerequisite).
4. On HTTP error or `success: false`: throw normalized
   `ApiError { status, traceId, errors: [{field?, message}], message }`.
5. On 401: broadcast an `unauthorized` event → auth layer invalidates the `me`
   query and redirects to `/login` (§8.3). Never auto-retry.
6. Parse `envelope.data` with `schema` — **a parse failure throws loudly
   (`SchemaMismatchError` with the zod issues + traceId). Never render silently
   wrong data.**

No component or hook may call `fetch` directly. Multipart/blob calls go through
the same wrapper (the old scaffold's imports bypassing its provider was a smell —
don't repeat it).

**Idempotency (ported from the mithril portal's `request.ts`):** `idempotent:
true` attaches `'X-Idempotency-Key': crypto.randomUUID()`. Required on every
document-creating or lifecycle mutation — invoice/credit-note `issue`, `cancel`,
batch `submit`, batch upload — so a double-click or retry can never create two
legal documents or two FTA submissions. ⚠️ **Backend work item:** requires an
idempotency interceptor/table server-side; until it lands, the header is sent
and ignored — flag the gap to the owner in the Phase-0 report, don't silently
drop the flag.

### 7.3 Query keys — `keys.ts` factory (never inline arrays)

```ts
keys.list(tenantId, "invoices", params)   // [tenantId, "invoices", "list", params]
keys.detail(tenantId, "invoices", id)     // [tenantId, "invoices", "detail", id]
keys.me()                                  // ["me"] — the ONE tenant-less key
```
- **Every tenant-scoped key starts with `tenantId`** — this makes cross-tenant
  cache leakage structurally impossible. Admin portal uses a constant `"admin"`
  scope in place of tenantId.
- On tenant switch: `queryClient.clear()` (not invalidate — clear).

### 7.4 Mutations — `useResourceMutation`

One helper wrapping `useMutation`: takes `(resource, mutationFn)`, on success
invalidates the whole family `[tenantId, resource]` and shows a toast; on
`ApiError` with field errors returns them for form mapping (§9). **Broad
invalidation always — no surgical cache writes.** An extra refetch is cheaper
than a staleness bug nobody will catch.

### 7.5 Pagination contract

Backend is 0-based `page`/`size`. `pageSchema(itemSchema)` helper in foundation
parses `{ content, totalElements, totalPages, number, size }`. DataTable syncs
`page`, `size`, `sort`, and filters to URL search params (shareable/back-safe).

---

## 8. Auth & multi-tenancy workflow

### 8.1 Backend prerequisite (Phase 0 — blocks the vertical slice)

The backend currently issues **localStorage-style JWTs** (`auth/login|refresh`).
The approved target (CLAUDE.md) is **httpOnly, Secure, SameSite=Lax cookie
sessions + CSRF token for mutations**. This is a backend task that must land
first. The frontend is specified against cookies; **never store any token in
localStorage/sessionStorage — no fallback, no interim JWT mode.** If the session
endpoints are not ready, that phase is blocked; say so rather than improvising.

**Per-portal session cookies (required, part of the same backend task):** cookies
are host-scoped, NOT port-scoped — on `localhost` the two dev portals (5174/5175)
share one cookie jar, and in production both portals live on one origin (§12.1).
The backend must issue a **distinct session cookie per portal** (e.g.
`eiv_session` for tenant, `eiv_admin_session` for admin; final names decided in
the backend task), path-scoped where the deployment layout allows. Without this,
logging into one portal silently evicts the other's session — an undiagnosable
"random logout" bug. The CSRF token, if cookie-delivered, needs the same split.

### 8.2 Login / identity

- `POST /auth/login` (sets cookie) → then `GET /auth/me` →
  `{ user, permissions, tenants }` cached under `keys.me()`, `staleTime: Infinity`.
- `useMe()` is the single identity source. RBAC UI: `<Can permission>` for
  elements, `<RequirePermission>` route guard, nav items filtered by their
  `permission` field. **UI checks are UX only — the backend enforces.**

### 8.3 401 handling

Any 401 from anywhere → invalidate `me` → redirect `/login` (session-expired
variant of the error screen when mid-app). No refresh dance — sessions renew
server-side.

### 8.4 Tenant context & switcher (tenant portal only)

- `TenantContext` holds the active org id. **Per-tab isolation (ported from the
  mithril portal's `LfiSelectionGate`):** the active org lives in
  `sessionStorage` (`eiv-org`) — each browser tab holds its own tenant, so an
  accountant can work two client orgs side by side without cross-tab
  clobbering, and closing the tab clears it. New-tab seed order:
  `sessionStorage` → last-used org from `localStorage` (`eiv-org-last`) → first
  membership; the chosen id must still be present in `me.tenants`, else fall
  through. Switching writes both keys (session = this tab, local = seed for
  future tabs). An org *id* is not a credential — this storage is fine; tokens
  never are.
- The fetch wrapper reads it for the `X-Organization-Id` header (backend contract,
  AGENTS.md §4.4).
- Switcher UI lives in the sidebar `AccountMenu` (org block + "Switch"), per the
  prototype. On switch: set context → `queryClient.clear()` → navigate to `/`.
- The old scaffold had NO switcher (locked to first membership) — this is a
  required fix, and it gets an E2E test (§13).
- Admin portal: no TenantContext, header never sent; a platform admin calling
  tenant endpoints gets 403 **by design** (don't "fix" it).

### 8.5 Config-dependent feature gates

Screens gated on tenant config (FTA/ASP connection state, settings-panel
availability, feature toggles) use a **three-state guard** — pattern proven in
the mithril portal (`RequireOtcEnabled`):

1. Config query still loading → render a loading placeholder. Never redirect on
   first paint — a flash-redirect before config arrives is a bug, not a guard.
2. Config fetch errored → **deny** (redirect). Never decide from stale or absent
   config.
3. Resolved → allow or deny on the actual value.

Implement once as `<RequireConfig test={cfg => ...}>` in foundation; every gated
route uses it. Getting any of the three states wrong produces either a security
hole (2) or the classic bounce-on-refresh UX bug (1).

---

## 9. Form kit — `useResourceForm`

One hook used by every FormPage:

- Wraps RHF + `zodResolver(inputSchema)`.
- Edit mode: fetches the record (`staleTime: 0` — always refetch on open), maps
  entity → form defaults.
- Submit: create or update via `useResourceMutation`; on `ApiError` field errors,
  map each `{ field, message }` into `setError(field, ...)` (nested paths like
  `lines.2.quantity` supported); non-field errors → form-level alert banner.
- Success: toast → invalidate family → navigate to list (or detail).
- Unsaved-changes guard: react-router `useBlocker` + ConfirmDialog. (Works because
  the apps use `createBrowserRouter` — §2.1; under plain `<Routes>` it would
  silently never block.)

Form markup contract: `FormShell` (max-width 940) › `FormCard` sections ›
`SectionTitle` › `FieldGrid` (2-col; `col-2` spans) › `FormFooter` (actions +
required-note) — exactly the prototype's form anatomy.

Zod schema policy: schemas live in `pages/<resource>/schema.ts`, hand-derived
from the backend DTOs (`backend/tenant-api/.../dto/`, `backend/admin-api/.../dto/`).
**Open the Java DTO and mirror it field-by-field** (names are stable: e.g. enums
exposed as `vatCategoryEnum`). `.strict()` off, `unknown` keys ignored; dates as
`z.string()` (`YYYY-MM-DD`); money as `z.number()` (display formatting only —
never arithmetic in the frontend).

---

## 10. `<DataTable>` — the single generic table

TanStack Table v8 wrapped once; pages supply only `columns` + a query hook.

Required features (all visible in the prototype):
- URL-synced state: page, size (persist choice as `eiv-page-size`), sort, filters.
- Toolbar slot: search input, filter selects, primary action (`.toolbar` anatomy).
  The search input is **debounced (~300 ms)** via a shared `useDebounce` hook in
  foundation (port from the mithril portal) before it touches URL state or query
  keys — a keystroke must never become a backend request.
- Optional summary strip above (`.summary` 4-stat variant).
- Row hover; row actions cell fading in on hover; row click → detail route.
- Selection checkboxes → `BulkBar` slot.
- States: loading (skeleton rows), error (alert + retry), empty (EmptyState with
  contextual CTA), filtered-empty ("no matches" note).
- Footer: count (`Showing X–Y of Z`), pager, rows-per-page.
- Column defs typed via `createColumnHelper<Entity>()`; cells use StatusPill /
  Avatar / money & date formatters — never ad-hoc formatting in pages.
- No sticky header (prototype doesn't use one); horizontal scroll wrapper with
  `min-w` per prototype.

Server-driven pagination/sort only (`manualPagination: true`) — the backend pages;
the table never sorts client-side beyond the current page.

---

## 11. Build workflow — phases and gates

Follow strictly. Each phase ends with the verification gate (§11.1) plus its own
exit criterion. Do not start a later phase early "while waiting."

| Phase | Scope | Exit gate |
|---|---|---|
| **0. Prerequisites** | Backend: cookie session + CSRF + `GET /auth/me` shape + **per-portal cookie names/paths (§8.1)**. Decide + record deployment layout and env config (§12.1). Freeze `frontend/` (no new features). Scaffold `web/` workspaces + tooling (TS strict, ESLint flat `--max-warnings=0` w/ react-hooks, Prettier, husky + lint-staged, Vitest, Playwright) + **CI pipeline (§12.3)** | `npm run lint && npm run test && npm run build` green on empty apps AND in CI; login round-trip works via curl for both portals without evicting each other's session |
| **1. Design system core** | `tokens.css` port + Tailwind `@theme` map + `applyTheme.ts`; primitives batch 1 (Button, Input, Field, Pill, Tag, Alert, Skeleton, Spinner, EmptyState, Tooltip, Modal/Confirm, Menu, Tabs, Toast); AppShell (sidebar/topbar/footer, collapse, mobile drawer) | Storybook-less demo route rendering every primitive in light+dark; visual check vs `design-system.html` |
| **2. Glue layer** | request.ts + envelope/ApiError + keys.ts + queryClient presets + useResourceMutation + useResourceForm + DataTable + auth (login page, useMe, guards, 401 flow) + TenantContext + switcher | Vitest units for: envelope unwrap/error mapping, key factory, schema-mismatch loudness, guards. Login → app shell renders with real backend |
| **3. VERTICAL SLICE** (owner gate) | Login → tenant switcher → invoices list (DataTable) → invoice create (minimal form, no editor rail yet) → **one Playwright E2E covering the whole flow against the real backend** | Owner reviews & approves. Nothing fans out before this |
| **4. Golden exemplar** | Customers complete: list + master–detail + create/edit + Excel import + E2E (incl. tenant-isolation negative). This becomes THE template — its file layout and patterns are copied verbatim by every later resource | E2E green; owner spot-check |
| **5. Resource fan-out** | Products (+archive) → Credit notes → Recurring → full Invoice editor (LineItemsEditor, ComplianceRail, lifecycle actions, document view/print) → Batches (upload + polling detail) | Each: E2E incl. one negative case before "done" |
| **6. Breadth screens** | Dashboard + charts, Reports, Import wizard, Settings shell + panels-with-backend, Customer statement, error pages, command palette, notification panel | Flag every missing backend endpoint to the owner instead of mocking |
| **7. Admin portal** | Shell reuse → orgs list/detail → onboarding wizard (port semantics from old scaffold) → admin E2E | |
| **8. Decommission** | Screen-by-screen parity checklist vs `frontend/`; owner sign-off; delete `frontend/`; update AGENTS.md §5 + CLAUDE.md banner | |

Deferred (do NOT build unless asked): RTL polish, EN/AR localization, signup/2FA,
billing panels without backend, admin monitoring/audit screens (no backend),
mobile table→card, "Getting Started" checklist destination.

### 11.1 Verification gate (every task, no exceptions)

```
npm run lint          # --max-warnings=0
npm run typecheck
npm run test          # vitest
npm run build
npx playwright test <relevant spec>   # for any user-facing flow change
```
Report actual results. A feature without its E2E test is **not done**. If
something fails, say it failed and show the output — never claim green.

---

## 12. Environments, deployment & CI

### 12.1 Environment configuration

- Vite modes: `development` (local), `qa`, `production`. Config read in ONE
  place — `foundation/src/env.ts`, validated with Zod at module load (fail fast
  and loud on a missing/malformed var, never default silently). Only non-secret
  values (API base URL, environment name, feature toggles) — the bundle is public.
- **Runtime injection (ported from the mithril portal's `lib/env.ts`):** `env.ts`
  getters check `window.__ENV__` first (a JSON blob injected into `index.html` at
  container startup), falling back to build-time `import.meta.env` for local dev.
  Result: **one Docker image serves all environments** — config is an ops concern,
  not a rebuild (the Spring externalized-config philosophy). Zod validation runs
  on the merged result.
- Dev: Vite proxy `/api → http://localhost:8080` (§3), so cookies are first-party
  in development too.
- QA/prod: the SPAs are served **same-site with the API** — one origin, reverse
  proxy serving static assets and `/api`. This is a hard requirement, not a
  convenience: cookie auth is SameSite=Lax, and a cross-site deployment breaks
  login *silently*. If infrastructure ever forces cross-origin, STOP and flag to
  the owner (it would require SameSite=None + CORS + a CSRF re-review — an
  architecture decision, not a config tweak).
- The two portals deploy under one origin at distinct paths (e.g. `/app/` and
  `/admin/`, matching the per-portal cookie paths — §8.1). Vite `base` set
  accordingly per portal. The concrete layout is fixed in Phase 0 and recorded here.

### 12.2 Build & performance

- Route-level code splitting: `React.lazy` per top-level route group (invoices,
  customers, settings, …) with a skeleton-page Suspense fallback. No
  micro-splitting beyond that unless a measured problem exists.
- Browser support: evergreen only — the token system depends on `color-mix()`
  (Chrome/Edge ≥ 111, Safari ≥ 16.2, Firefox ≥ 113). No polyfills, no IE-era
  accommodations. State this in the README.
- Build gate: `npm run build` green with zero TS errors; flag any route chunk
  crossing ~500 kB gzip rather than silently shipping it.

### 12.3 CI (the enforcement backstop — pre-commit hooks are skippable)

- Pipeline on every push: install → lint (`--max-warnings=0`) → typecheck →
  vitest → build, across all workspaces. A red default branch blocks feature
  work until green.
- Playwright job: on-demand + nightly against a composed backend (bootRun +
  Flyway-seeded DB per the §13 fixtures contract) — not per-push until it proves
  itself fast enough.
- The pipeline is scaffolded in Phase 0 together with the workspace; "CI comes
  later" is not an option in a no-human-reviewer project.
- Husky install must degrade gracefully (mithril portal pattern):
  `"prepare": "node ./scripts/setup-husky.mjs || echo \"husky setup skipped\""` —
  hook installation never breaks CI, containers, or fresh clones where git hooks
  can't install.

---

## 13. Testing strategy (this replaces the human reviewer)

- **Playwright E2E is the primary quality gate** — the project has no human
  frontend reviewer; behavior verification substitutes for code review.
- Structure: `web/e2e/{tenant,admin}/<flow>.spec.ts`; auth via `storageState`
  fixtures (one login per portal per run); real backend with seeded dev DB
  (`backend` bootRun, Flyway seed) — no API mocking in E2E.
- **Fixtures are a written contract**: `web/e2e/fixtures/README.md` defines the
  seed identities every spec relies on. Minimum set: **two orgs** (A and B); a
  full-role user who is a member of BOTH orgs (tenant-isolation specs need to
  switch); a limited-role user in org A (RBAC negatives); one admin-portal
  operator; seeded reference data (payment terms, industries) and a handful of
  seeded invoices/customers in org A only. Seeds live in a dev-profile Flyway
  migration in `backend/`; a documented reset script restores the state between
  runs. Specs never create their own users — if a spec needs an identity the
  contract lacks, extend the contract first.
- Every user-facing flow gets a spec. **Every resource additionally gets at least
  one negative case**: (a) tenant isolation — a record created under org A is not
  visible when switched to org B (list + direct URL both); (b) RBAC — a forbidden
  action is hidden AND its direct invocation is rejected by the backend (assert
  on the error surface, not just absence of a button).
- Selectors: `data-testid` on interactive elements; naming
  `<resource>-<element>-<action>` (`invoices-row-actions-issue`).
- Vitest + Testing Library for glue (fetch wrapper incl. envelope/error paths,
  key factory, guards, form error mapping) and non-trivial components
  (DataTable states, LineItemsEditor, StatusPill mapping completeness against the
  enums file).
- Visual fidelity: for each screen, open the prototype HTML and the built screen
  side by side before calling it done; where practical add a Playwright screenshot
  assertion for stable shells (sidebar, table anatomy) in light AND dark.

---

## 14. Coding guidelines for the building agent

Written for any model, without this session's context. The repo owner is a senior
**backend** engineer (Java/Spring) with limited React depth — code must be boring,
explicit, and readable by a non-React specialist. When a React concept drives a
decision, explain it in the PR/summary in one sentence, ideally with a backend
analogy (query cache ≈ read-through cache with TTL; invalidation ≈ prefix
cache-bust; RHF ≈ form binding + bean validation).

### 14.1 Golden rules

1. Copy the exemplar. New resources replicate `pages/customers/` structure
   file-for-file. Inventing a new pattern requires flagging it first.
2. No business logic in the frontend. VAT, compliance, numbering, state
   transitions: display what the backend returns. If the backend response lacks
   something a screen needs, propose an endpoint change — don't compute it.
3. Zod-parse every response. No `as` casts on API data, no `any`.
4. All requests through `request.ts`; all keys through `keys.ts`; all mutations
   through `useResourceMutation`; all forms through `useResourceForm`.
5. Tenant-first query keys, always. Reviewer heuristic: any `useQuery` whose key
   doesn't start with `tenantId` (or `"admin"`) is a bug unless it's `me`.
6. Broad invalidation only. Never `setQueryData` surgical updates.
7. Tokens only in styling (§4.3). No hex, no arbitrary color values.
8. Radix engines are never re-implemented: no hand-rolled focus traps, dropdown
   positioning, or keyboard nav — if you're writing `onKeyDown` for arrow-key menu
   navigation, you've taken a wrong turn.
9. Exact dependency versions; nothing added beyond §2 without owner approval.
10. Commit only when asked. Small, compilable increments.

### 14.2 React pitfalls (for agents/models weaker on React)

- Hooks are called unconditionally at the top of components — never inside `if`,
  loops, or callbacks. `eslint-plugin-react-hooks` enforces; don't suppress it.
- Data fetching belongs to TanStack Query. Writing `useEffect` + `fetch` is
  always wrong here. `useEffect` is for actual side effects (focus, subscriptions,
  document title) and is rare in this codebase.
- Don't copy server data into `useState` (that creates a stale duplicate cache);
  render from the query result. Local `useState` is for pure UI state (open/closed,
  active tab).
- List rendering needs stable `key`s (entity ids, never array index for dynamic
  rows — LineItemsEditor uses RHF's field `id`).
- Derived values: compute inline or `useMemo` — never `useEffect`-then-`setState`.
- **Nothing that rotates goes into a dependency.** No token values, timestamps,
  or freshly-generated ids in query keys, hook dependency arrays, or context
  values consumed by data hooks — keys/deps hold stable ids only (`tenantId`,
  resource, params). War story from the mithril portal (`useFetch.ts`): keying
  auto-fetch on the auth token caused a full-page refetch on every ~10s token
  rotation — visible "blinking" and form resets; the fix was gating on a stable
  `authenticated` boolean. Cookie sessions remove the token, but the same bug
  reappears with any rotating value.
- Form inputs are RHF-controlled; don't mix `value`/`defaultValue`/`onChange`
  manually onto fields inside the form kit.
- Components must not mutate props or state; new arrays/objects on update.

### 14.3 TypeScript & style

- `strict` + `noUnusedLocals` + `noUncheckedIndexedAccess`; no `enum` (string
  literal unions per `types/enums.ts` — mirrors backend `*Enum` values, including
  the intentional misspelling `AWAIING_CLEARANCE`; match it, never "fix" it).
- Named exports only. Components `PascalCase.tsx`, hooks `useX.ts`, one component
  per file. Colocate small helpers; promote to foundation only on the second use.
- Comments: only for constraints the code can't express (e.g. "backend counts an
  invoice submitted only when session state ≥ SUBMITTING — Gotcha #7"). No
  narration, no change-log comments.
- Prettier formats; ESLint gates with `--max-warnings=0`. Fix, don't disable —
  a rule disable needs a justifying comment and should be rare.

### 14.4 Styling conventions

- Default: Tailwind utilities referencing the token names (§4.1).
- `cva` for variant-bearing primitives (Button, Pill, Alert).
- **Escape hatch:** visually complex one-offs whose prototype CSS is long and
  battle-tested (InvoiceSheet + ribbon, charts axes, stepper connectors) may be
  ported as scoped plain-CSS files under `foundation/src/styles/prototype/`,
  imported by that component only. Porting verbatim beats re-deriving in utilities
  — fidelity first. Never global, never `!important`.
- Dark mode: never write `dark:` overrides with raw colors — tokens already flip
  via `data-theme`. If a component needs dark-specific treatment, add a token.
- Print: InvoiceSheet ships a `@media print` stylesheet (hide chrome, white bg).

### 14.5 Honesty & reporting protocol

- Never claim tests pass without running them in this session; paste the summary.
- If a backend endpoint is missing/differs from this doc, stop and report the
  discrepancy (doc §6 tables mark known-unverified endpoints) — do not mock it,
  do not silently reshape the UI.
- If a design decision is genuinely ambiguous after checking the prototype +
  COMPONENTS.md, make the boring choice, implement it, and list it under
  "decisions I made" in your summary for owner review.

---

## 15. Definition of done — per feature checklist

- [ ] Matches the prototype screen visually (light + dark), checked side-by-side
- [ ] All states: loading, empty, error, filtered-empty, permission-hidden
- [ ] Zod schemas mirror the backend DTOs; 422 errors land on fields
- [ ] Query keys tenant-first; correct staleTime preset; broad invalidation
- [ ] `data-testid`s present; Playwright spec incl. one negative
      (isolation or RBAC) green against the real backend
- [ ] Unit tests for any non-trivial logic added to foundation
- [ ] Verification gate (§11.1) fully green; results reported verbatim
- [ ] No new dependencies; no hex colors; no direct `fetch`; no inline keys

---

## 16. Known gaps & decisions already made about them

1. **Date picker has no prototype design.** Decision: `react-day-picker` in a
   Popover, styled with the tokens (control-height trigger styled as `.input`,
   card-radius popover). Add a screenshot to the owner on first build.
2. **Dashboard/reports/statement/settings backend endpoints are unverified** —
   the prototype designs them, but AGENTS.md §6 doesn't list matching endpoints
   for all of them. Building agent must check `tenant-api` controllers first and
   report gaps as backend work items (§6.1 tables mark these).
3. **Notification center backend does not exist** — build the panel with a
   client-side placeholder feed clearly marked, or defer; flag to owner.
4. **Prototype's `eiv-*` storage keys** are kept for continuity — localStorage:
   theme, palette, sidebar, page-size, `eiv-org-last` (last-used org seed);
   sessionStorage: `eiv-org` (this tab's active org — §8.4). Never store
   credentials or tokens in either.
5. **RTL / Arabic** is groundwork-only (logical properties). Full RTL + EN/AR
   localization is explicitly deferred; do not add `i18next`.
6. **Old scaffold quirks NOT to replicate**: client-side VAT estimate, missing
   tenant switcher, `payment-terms` used-but-undeclared as a resource, dead CSS,
   `aria-lable` typo, localStorage JWTs.
7. **CLAUDE.md banner** still says "PROPOSED, pending reconciliation." Both
   prerequisite tasks are now complete (`docs/FRONTEND-DIRECTION.md` + this doc);
   updating that banner and AGENTS.md §5 happens at decommission (Phase 8) or
   when the owner asks.
