# Frontend Design & Implementation Guide (Tenant + Admin Portals)

> Status: **Draft for implementation.** Audience: AI coding agents building the React
> dashboards for the e-invoicing platform. Covers stack, architecture, reusable components,
> every module, API contracts, forms/validation, the FTA compliance + bulk-submission UX,
> security, and accessibility. Companion to the backend docs in `backend/docs/`
> (`FTA_VALIDATION_DESIGN.md`, `EINVOICE_SUBMISSION_STATE_MACHINE.md`, `RBAC_DESIGN.md`,
> `TENANT_ISOLATION_AND_STATE_MACHINE_DESIGN.md`).
>
> Note: `docs/frontendDesign.md` in this repo is an **unrelated** doc (a React Native
> "Digital Dirham Wallet" design system) — it is not this project's frontend. This guide is the
> e-invoicing web frontend spec.

---

## 0. Two separate portals — a hard boundary

There are **two independent front-end applications** and they **must stay separate** — different
users, different needs, different auth, different builds and deploys. **Do not merge them, route
between them, or share domain code between them.** A tenant screen must never appear in the admin
app and vice-versa.

| | **`tenant-portal/`** | **`admin-portal/`** |
|---|---|---|
| Users | Tenant org members (SME staff) | Platform operators (our company) |
| Purpose | Manage the org's invoicing → FTA compliance → submit to ASP | Operate the platform: organizations, ASPs, rule catalog, users, monitoring |
| Auth base | `/api/v1/auth/*` | `/api/v1/admin/auth/*` |
| JWT area | `TENANT` | `ADMIN` |
| `X-Organization-Id` header | **Required** on every business call (tenant-scoped) | **Never sent** (global / cross-org) |
| Data visibility | one organization at a time | across all organizations |
| Modules | §9 (customers, products, invoices, credit notes, recurring, bulk e-invoice) | §14 (organizations, ASPs + rule catalog, users, audit, submission monitoring) |
| Deploy | its own origin/build; **tenant is the focus of this guide** | its own origin/build |

**Shared vs separate — the rule:**
- **Shared (foundation only):** tech stack, design tokens, the `components/ui` primitive library,
  and `lib/` (api client, auth, utils). Package these **once** as a build-time shared library
  (§3.1) — this is code reuse, **not** runtime coupling.
- **Separate (never shared):** all **domain features** (`features/*`), routes, navigation, page
  content, and `config/portalConfig.ts`. Each portal builds, deploys, and is secured independently.

**How this guide is scoped:** the foundation sections (§2–§8, §13, §15) apply to **both** portals;
**§9 is tenant-only** and **§14 is admin-only**. Keep the two apps' domain layers physically and
logically separate.

---

## 1. What exists today (reuse) vs. what's net-new

Both portals are minimal **Vite 5 + React 18 + TypeScript** SPAs. Reuse:
- **`src/components/DashboardShell.tsx`** — sidebar + topbar layout (evolve into `AppLayout`).
- **`src/config/portalConfig.ts`** + `PortalConfig` type — config-driven branding/nav (keep).
- **`src/api/authApi.ts`** — `fetch` login shape (evolve into the API client).
- **Design palette** in `src/index.css` — brand green `#28705f`, surfaces `#e8f4ef`/`#f6f9f7`,
  text `#172026`/`#53675f`, error `#9a341f`, radius `8px`, Inter font. Promote to design tokens.
- **Vite dev proxy** (`vite.config.js`): `/api → http://localhost:8080`. Keep; add prod base URL.
- **A11y seeds**: semantic landmarks, `aria-label`s, visible focus rings — keep and extend.

**Net-new (everything else):** routing, server-state/data-fetching, forms+validation, token
persistence + refresh, `X-Organization-Id` handling, RBAC-aware UI, a component library,
testing, linting. This guide specifies all of it.

---

## 2. Recommended stack (industry standard)

Keep Vite + React 18 + TS; add:

| Concern | Choice | Why |
|---|---|---|
| Routing | **React Router v6** (data router) | standard SPA routing, nested layouts, guards |
| Server state | **TanStack Query v5** | caching, polling (state machine!), retries, dedup |
| Forms | **React Hook Form** + **Zod** (`@hookform/resolvers`) | perf, schema validation mirroring backend |
| HTTP | **axios** instance + interceptors | clean auth/org-header/refresh interceptors |
| UI primitives | **shadcn/ui** (Radix UI + Tailwind) | accessible-by-default, unstyled+themeable, owned in-repo |
| Tables | **TanStack Table** (headless) | sortable/paginated `DataTable` |
| Toasts | **sonner** (or Radix Toast) | accessible notifications |
| Dates/money | **date-fns** + `Intl.NumberFormat`/`dinero.js` | correct formatting, no float bugs |
| File parsing (optional preview) | **PapaParse** (CSV), **SheetJS** (xlsx) | pre-validate bulk file before upload |
| Testing | **Vitest** + **React Testing Library** + **MSW** + **Playwright** | unit/integration + mocked API + e2e |
| Quality | **ESLint** (+ `jsx-a11y`, `typescript-eslint`) + **Prettier** + `tsc --noEmit` in CI | a11y lint + typecheck gate |

> Tailwind + shadcn/ui is recommended (accessible primitives, fast, standard). If the team
> prefers to avoid Tailwind, the fallback is **Radix primitives + CSS variables** using the
> existing `index.css` tokens — keep Radix either way for accessibility. **[CONFIRM D1]**

---

## 3. Project structure (modular, feature-first)

```
src/
├── main.tsx, App.tsx
├── app/                      # cross-cutting app wiring
│   ├── router.tsx            # route tree + guards
│   ├── providers.tsx         # QueryClientProvider, AuthProvider, ThemeProvider, Toaster
│   └── queryClient.ts
├── config/
│   ├── portalConfig.ts       # (existing) per-portal branding/nav
│   └── env.ts                # VITE_API_BASE_URL etc. (typed)
├── lib/
│   ├── api/ { client.ts (axios + interceptors), queryKeys.ts, errors.ts }
│   ├── auth/                 # AuthContext, useAuth, token store, refresh
│   └── money.ts, dates.ts, cn.ts
├── components/ui/            # reusable primitives (Button, DataTable, Dialog, ...)
├── components/               # composite shared (AppLayout, PageHeader, ...)
├── features/                 # ONE folder per module: { api.ts, schema.ts, hooks.ts, components/, pages/ }
│   ├── customers/ products/ invoices/ credit-notes/ recurring-invoices/ einvoice-batches/ dashboard/
├── types/                    # shared API types (enums, DTOs) — §11
└── test/                     # setup, MSW handlers
```
Each `features/<x>/` is self-contained. Shared UI lives in `components/ui`. No feature imports
another feature's internals — share via `components/` or `lib/`. **This structure is per-portal:
`tenant-portal/` and `admin-portal/` each have their own `src/` tree; only the foundation below is
shared.**

### 3.1 Shared foundation across the two portals (recommended)
Keep the two apps separate but avoid duplicating the plumbing. Extract a **build-time shared
library** that both portals depend on:
```
packages/ui-foundation/   # design tokens + components/ui primitives (Button, DataTable, ...)
packages/app-core/        # lib/api client, lib/auth, types/enums, utils
tenant-portal/            # imports the two packages; owns its features/, routes, portalConfig
admin-portal/             # imports the two packages; owns its features/, routes, portalConfig
```
Use an npm/pnpm workspace (monorepo) so both consume `@einvoice/ui-foundation` + `@einvoice/app-core`.
**Only** the foundation is shared; **domain features, routes, and navigation stay in each portal**
and are never cross-imported. (If a monorepo is not desired, duplicate the foundation per portal —
worse for consistency; see §19 D4.)

---

## 4. API layer, config & security-critical token handling

### 4.1 Base URL & env
`config/env.ts`: `apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ""` (`""` → relative, dev proxy).
Dev keeps the Vite proxy; prod sets `VITE_API_BASE_URL`.

### 4.2 Axios client (`lib/api/client.ts`)
- One instance, `baseURL: env.apiBaseUrl`.
- **Request interceptor:** `Authorization: Bearer <accessToken>` from the in-memory store; add
  **`X-Organization-Id: <selectedOrgId>`** for tenant `/api/v1/**` calls (NOT `/auth/**` or admin).
- **Response interceptor:** on `401` → single refresh (`POST /api/v1/auth/refresh`), queue &
  retry in-flight once; on failure → hard logout + redirect. Normalize errors to `ApiError` from
  `{ status, error, message, path, timestamp }`.

### 4.3 Token storage — **do this securely**
Login returns `{ accessToken, refreshToken, tokenType, expiresIn }`.
- **Access token:** in memory only (never `localStorage`/`sessionStorage` — XSS risk).
- **Refresh token:** target = **httpOnly, Secure, SameSite=Strict cookie set by backend**
  (**[BACKEND FOLLOW-UP §16]**). Interim: keep in memory + **silent refresh** before `expiresIn`;
  a full reload requires re-login. Never persist the refresh token in `localStorage`.
- Logout: `POST /api/v1/auth/logout` + clear the store.

### 4.4 Errors → toast + inline field errors. FTA issue rejections come back as 4xx with failed
rule codes in `message`; the compliance UI (§10) renders them.

---

## 5. Auth & multi-tenant context
- **Login** `/login` → `POST /auth/login` → store tokens → `GET /auth/me`.
- **`/auth/me`** → `{ id, email, fullName, avatarUrl, platformRole, memberships[] }`,
  membership = `{ organizationId, organizationLegalName, organizationDisplayName,
  organizationStatus, role, status }`.
- **Org selection:** >1 active membership → topbar **org switcher**; force a pick if none.
  Persist selected org id in memory + `sessionStorage` (non-sensitive); interceptor sends it as
  `X-Organization-Id`. **Switching org clears the TanStack cache.**
- **`AuthProvider`/`useAuth()`** → `{ user, memberships, currentOrg, role, setOrg, login, logout,
  can(permission) }`.
- **Route guards:** unauth → `/login`; auth+no org → picker; else render.
- **RBAC-aware UI:** gate action buttons by member role in the current org (OWNER/ADMIN/MEMBER per
  `RBAC_DESIGN.md`; e.g. MEMBER can edit drafts but not issue/cancel/submit). Server is
  authoritative; UI only hides/disables. Provide `<Can permission="invoice:issue">` + `can()`.

---

## 6. Design system & tokens
Promote the palette to tokens: `--brand:#28705f`, surfaces, text, `--danger:#9a341f`,
`--radius:8px`, `--radius-pill:999px`, Inter. Semantic tokens: primary/surface/muted/border/
danger/success(green)/warning(amber)/info. **Status color map** (badges everywhere):
DRAFT=muted; ISSUED=info; COMPLIANT/CLEARED=success; NON_COMPLIANT/REJECTED/FAILED=danger;
PENDING/SUBMITTED/*_VALIDATING/SUBMITTING/AWAITING_CLEARANCE=info; *_ACTION_REQUIRED=warning;
EXPIRED/CANCELLED=muted; PLATFORM_VALIDATED=success.

---

## 7. Reusable component library (`components/ui`) — build once, compose everywhere
All keyboard-operable and labelled (§13).

`Button` (primary/secondary/ghost/danger, `loading`) · `Input`/`Textarea`/`Select`/`Combobox`/
`DatePicker`/`NumberInput`/`Checkbox`/`RadioGroup` (with `error`,`aria-invalid`,`aria-describedby`)
· `FormField` (label+control+error+hint, wires RHF+aria) · `DataTable` (TanStack: columns, sort,
paging, loading, empty, row-actions) · `Pagination` (server paging) · `Dialog`/`AlertDialog`
(focus-trapped) · `Drawer`/`Sheet` · `Badge`/`StatusChip` (status color map) · `Toast` (sonner,
aria-live) · `FileDropzone` (accept `.xlsx,.csv`, size limit, a11y) · `Card`/`StatCard`/
`PageHeader`/`EmptyState`/`Spinner`/`Skeleton`/`Tabs`/`Tooltip` · `MoneyText`/`DateText` ·
`ComplianceBadge` (ComplianceStatus → badge + issue count) · `ValidationIssuesList`
(`[{code,message,severity}]` grouped, links to fields) · `ConfirmButton` (button+AlertDialog for
issue/cancel/submit/archive) · `AppLayout` (evolve `DashboardShell`: RBAC nav, org switcher, user
menu, breadcrumbs, skip-link).

---

## 8. Shared conventions
- **Data:** feature `api.ts` (thin axios) + `hooks.ts` (typed TanStack Query hooks); centralize
  keys in `lib/api/queryKeys.ts`; mutations invalidate lists/details.
- **Polling:** non-terminal batch/compliance → `refetchInterval: q => isTerminal(q.state.data)?false:4000`.
- **Forms:** RHF + Zod (`schema.ts`) mirroring backend DTOs (§11); submit → mutation → toast +
  navigate; surface server field errors.
- **Pagination:** `Page<T>` (`content,totalElements,totalPages,number,size`); lists take `?page=&size=`.

---

## 9. Modules (tenant-portal). All under authenticated `AppLayout`; all send `Authorization` + `X-Organization-Id`.

### 9.1 Dashboard `/` — stat cards (Draft invoices, Non-compliant, In-progress batches, Cleared) + recent invoices + in-progress batches. (Some counts need backend filters §16.)

### 9.2 Customers `/customers`
- **API:** `GET/POST /customers`, `GET/PUT /customers/{id}`, `POST /customers/{id}/archive`.
- **Screens:** list (DataTable: name, TRN, email, city, status), create/edit, detail.
- **Fields/validation:** name*; trn `^\d{15}$` (opt); email format; currency `^[A-Z]{3}$`;
  countryCode `^[A-Z]{2}$`; paymentTermsDays ≥0; plus nameAr, customerCode, phone, website,
  addressLine1/2, city, emirate (UAE enum), notes.

### 9.3 Products `/products`
- **API:** `GET/POST /products`, `GET/PUT /products/{id}`, `POST /products/{id}/archive`.
- **Fields:** type(GOODS/SERVICE)*, name*, unitPrice*(>0), vatCategory*; nameAr, description,
  sku, unitOfMeasure, currency.

### 9.4 Invoices `/invoices` ⭐ (draft-first + FTA compliance)
- **API:** `GET/POST /invoices`, `GET/PUT /invoices/{id}`, `POST /invoices/{id}/issue`,
  `POST /invoices/{id}/cancel`.
- **Lifecycle:** create → **DRAFT** (editable) → **discard(cancel)** or **issue (only if FTA
  COMPLIANT)**; issuing non-compliant → 4xx with failed rule codes.
- **List:** DataTable (number|"Draft", customer, issueDate, total, StatusChip, **ComplianceBadge**);
  filters status/compliance (§16).
- **Editor:** header (customer Combobox, type, currency, supplyDate, dueDate/terms, poNumber,
  reference, notes, terms) + **line items** (RHF `useFieldArray`: product Combobox autofills,
  description*, quantity*>0, unitPrice*, vatCategory*) + **live totals preview** (§12.1) + **live
  compliance** (ComplianceBadge + ValidationIssuesList with inline field highlighting §10.2).
  Actions: Save draft; **Issue** (disabled/blocked when NON_COMPLIANT, tooltip lists gaps);
  Discard.
- **Detail:** read-only + compliance panel + actions.

### 9.5 Credit Notes `/credit-notes` — mirrors Invoices; adds original-invoice reference + reason.
`GET/POST /credit-notes`, `GET/PUT /credit-notes/{id}`, `POST /credit-notes/{id}/issue`, `.../cancel`.

### 9.6 Recurring Invoices `/recurring-invoices`
`GET/POST /recurring-invoices`, `GET/PUT /recurring-invoices/{id}`, `POST .../{id}/pause|resume|end`.
Form: name, customer, frequency (WEEKLY/MONTHLY/QUARTERLY/YEARLY), intervalCount, startDate,
endDate, currency, template lines. List shows status + nextRunDate.

### 9.7 Bulk E-Invoice Submission `/einvoice/batches` ⭐⭐ (state machine)
- **API:** `POST /einvoice/batches/upload` (multipart `file`, optional `Idempotency-Key`),
  `GET /einvoice/batches/{id}`, `POST /einvoice/batches/{id}/submit`,
  `POST /einvoice/batches/{id}/revalidate`. **[NEEDS §16]** list endpoint for "resume later".
- **Upload:** FileDropzone (.xlsx/.csv) + **Download template** (23 cols §12.3) + optional
  client preview (PapaParse/SheetJS).
- **Batch detail:** poll `GET /{id}` while non-terminal; **stepper** of states + counts + items
  table (invoice, InvoiceStatus, platform validation, ASP validation, ValidationIssuesList).
- **Actions per state** (§12.2): `*_ACTION_REQUIRED` → edit offending **draft invoices** (deep
  link to editor) → **Revalidate**; `PLATFORM_VALIDATED` → **Submit to ASP**;
  `AWAITING_CLEARANCE` → poll; `COMPLETED` → cleared/rejected per item.

---

## 10. FTA compliance UX
- Appears in the invoice/credit-note editor & detail (`ComplianceBadge` + `ValidationIssuesList`)
  and the bulk items table. Invoice responses should carry `complianceStatus` +
  `complianceIssues` (`[{code,message,severity}]`) — **[§16]**; bulk items carry `validationErrors`.
- **Rule code → field map** (inline highlight; ERROR blocks issue, WARNING is amber/advisory):
```
SUP-01→org.name SUP-02→org.trn SUP-03→org.address SUP-04→org.email        (Organization settings)
BUY-01→customer.name BUY-02→customer.trn BUY-03→customer.address BUY-04→customer.email/phone
INV-02→issueDate INV-03→type INV-04→currency INV-05→supplyDate
LINE-01→lines(≥1) LINE-02→line.description LINE-03→line.quantity LINE-04→line.unitPrice LINE-05→line.vatCategory
TOT-01/02/03→totals PAY-01→dueDate PAY-02→terms PAY-03→paymentTermsDays
REF-01→reference(credit notes) OPT-01→poNumber(WARNING) INV-01→auto at issue (hidden on draft)
```
SUP-* map to the **Organization profile** (provide an org-settings screen or link "fix in
Organization settings").

---

## 11. Shared types & validation
Mirror backend enums (uppercase) + DTOs; Zod schemas double as types (`z.infer`). Enums:
`InvoiceType`(STANDARD|SIMPLIFIED) · `VatCategory`(STANDARD|ZERO_RATED|EXEMPT|OUT_OF_SCOPE|
REVERSE_CHARGE) · `ProductType`(GOODS|SERVICE) · `InvoiceStatus`(DRAFT|ISSUED|PARTIALLY_PAID|PAID|
CANCELLED) · `ComplianceStatus`(UNCHECKED|COMPLIANT|NON_COMPLIANT) · `RecurringFrequency` ·
`UaeEmirate`(7) · `Currency`(AED|USD|EUR|GBP) · `WorkflowState`(RECEIVED|PLATFORM_VALIDATING|
PLATFORM_ACTION_REQUIRED|PLATFORM_VALIDATED|ASP_VALIDATING|ASP_ACTION_REQUIRED|SUBMITTING|
AWAITING_CLEARANCE|COMPLETED|FAILED|EXPIRED|CANCELLED) · `EinvoiceSubmissionStatus`(PENDING|
SUBMITTED|CLEARED|REJECTED|FAILED) · `ValidationStatus`(UNCHECKED|VALID|INVALID). Keep client Zod
in sync with backend Bean Validation; server stays authoritative.

---

## 12. Business-logic mirrors (client preview only)
- **12.1 VAT** (mirror `VatCalculator`, HALF_UP 2dp, per line): `lineSubtotal=round2(qty*price)`;
  `vatAmount=round2(lineSubtotal*rate)`; totals=sums. Rates STANDARD `0.05`, ZERO/EXEMPT/OUT `0`.
  Preview only — backend recomputes.
- **12.2 Batch state → actions:** wait (RECEIVED/*_VALIDATING/SUBMITTING/AWAITING_CLEARANCE);
  edit+Revalidate (*_ACTION_REQUIRED); Submit (PLATFORM_VALIDATED); view + "correct rejected → new
  batch" (COMPLETED); view-only (FAILED/EXPIRED/CANCELLED).
- **12.3 Bulk template (23 cols):** `customerName*, customerTrn, customerEmail, customerPhone,
  customerAddress, customerCity, invoiceRef*, issueDate*, supplyDate, dueDate, paymentTermsDays,
  currency, poNumber, reference, termsConditions, notes, lineDescription*, lineQuantity*,
  lineUnitPrice*, lineDiscount, lineVatType*(STANDARD/ZERO/EXEMPT), lineVatRate, lineVatAmount`.
  One row per line, grouped by `invoiceRef`.

---

## 13. Accessibility (target WCAG 2.2 AA)
Radix/shadcn primitives for all interactive components · every input labelled + `aria-describedby`/
`aria-invalid`, required not by color alone · full keyboard operability, visible focus, logical tab
order, dialog focus trap + return · landmarks + one `h1` + ordered headings + skip-to-content ·
color never the sole signal (badges include text/icon) · `aria-live` for toasts/async status ·
contrast ≥4.5:1 (verify `#28705f`) · `prefers-reduced-motion` · responsive to 320px · targets
≥24px · **enforce** with `eslint-plugin-jsx-a11y` + `jest-axe` in component tests.

---

## 14. Admin portal (separate app — admin-only)
A **distinct application** from the tenant portal (§0): its own `admin-portal/src/` tree, routes,
navigation, and `portalConfig.ts`; it shares only the foundation packages (§3.1). It must **not**
contain any tenant module from §9. Same foundation conventions (§2–§8, §13, §15) apply.
- **Auth:** base `/api/v1/admin/auth/*`; JWT area `ADMIN`; **global/cross-org → never sends
  `X-Organization-Id`**; gate the app to `platformRole` (per `RBAC_DESIGN.md`).
- **Modules:** Organizations (onboarding/list/status), ASPs (registry + status) + **validation-rule
  catalog** (list/toggle FTA + ASP rules), Platform users/roles, Audit log, Submission monitoring
  (DEAD outbox + requeue). Most admin business endpoints are backend follow-ups.

---

## 15. Security (OWASP-aligned)
Tokens per §4.3 (memory access + httpOnly refresh; never localStorage) · no
`dangerouslySetInnerHTML` (else DOMPurify) · strict **CSP** (`connect-src` = API origin, no inline
scripts) + `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'` · CSRF: bearer-in-
header (not cookie-auth for API) or SameSite+CSRF token if refresh cookie · **always send selected
`X-Organization-Id`; clear query cache on org switch** · Zod-validate before submit (never trust
client for authz) · lockfile + `npm audit`/Dependabot · only `VITE_*` public config, no secrets/API
keys in the bundle · file upload: restrict type + size client-side (server re-validates) + preview.

---

## 16. Backend follow-ups the frontend needs
1. Expose `complianceStatus`/`complianceIssues` on invoice & credit-note responses.
2. `GET /api/v1/einvoice/batches` (paginated) for the "resume later" list.
3. List filters `?status=&compliance=` on invoices/credit notes.
4. Refresh token as httpOnly cookie (§4.3).
5. RBAC (member role/permissions) in `/auth/me`/token for accurate UI gating.
6. Bulk template download endpoint (or FE ships a static template); confirm CSV + XLSX.
7. Prod CORS: allow portal origins + `X-Organization-Id`/`Idempotency-Key` headers.

---

## 17. Phased task plan
**Phase 0 — foundation (both portals):** deps + ESLint/Prettier/jsx-a11y/tsc + Vitest/RTL/MSW/
Playwright · design tokens + status map · `components/ui` primitives (+a11y tests) · API client +
interceptors + `ApiError` · `AuthProvider`/token store/refresh/guards · `AppLayout` (RBAC nav + org
switcher) + router/providers · shared types + query keys.
**Phase 1 — master data:** Customers, Products.
**Phase 2 — invoicing + compliance:** invoice list + badges; invoice editor (lines, live VAT,
compliance panel + inline highlight); issue(gated)/cancel + detail; credit notes; recurring.
**Phase 3 — bulk submission:** upload (dropzone/template/preview); batch detail (stepper + items +
polling); revalidate/submit + deep-link edits; batches list (after §16.2).
**Phase 4 — hardening:** CSP/headers + token review; axe/keyboard/contrast pass; Playwright e2e
(login→create→issue; upload→validate→submit).
**Phase 5 — admin portal** (§14) after admin backend endpoints exist.

---

## 18. API reference (tenant, base `/api/v1`; send `Authorization`+`X-Organization-Id` except `/auth/*`)
Auth: `POST /auth/login|refresh|logout`, `GET /auth/me` · Customers: `GET|POST /customers`,
`GET|PUT /customers/{id}`, `POST /customers/{id}/archive` · Products: same under `/products` ·
Invoices: `GET|POST /invoices`, `GET|PUT /invoices/{id}`, `POST /invoices/{id}/issue|cancel` ·
Credit notes: `GET|POST /credit-notes`, `GET|PUT /credit-notes/{id}`,
`POST /credit-notes/{id}/issue|cancel` · Recurring: `GET|POST /recurring-invoices`,
`GET|PUT /recurring-invoices/{id}`, `POST /recurring-invoices/{id}/pause|resume|end` · Bulk:
`POST /einvoice/batches/upload`, `GET /einvoice/batches/{id}`,
`POST /einvoice/batches/{id}/submit|revalidate` · Health: `GET /health` · Admin (base
`/api/v1/admin`): `POST /auth/login|refresh|logout`, `GET /auth/me`.
Auth response `{accessToken,refreshToken,tokenType,expiresIn}`; list = `Page<T>`; error
`{status,error,message,path,timestamp}`.

## 19. Open decisions [CONFIRM]
- **D1** Tailwind+shadcn/ui (recommended) vs Radix+plain CSS variables.
- **D2** Refresh-token httpOnly cookie (secure, needs backend) vs interim in-memory refresh.
- **D3** Client-side bulk preview now vs upload-only for MVP.
- **D4** Foundation sharing (§3.1): **monorepo workspace with shared `ui-foundation`+`app-core`
  packages** (recommended) vs duplicated foundation per portal. Either way, the two portals stay
  **separate apps** — only the foundation is shared, never domain features.
