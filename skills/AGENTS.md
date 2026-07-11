# AGENTS.md — E-Invoicing Platform

Authoritative guide for AI agents (Claude Code and others) working anywhere in this repository.
Read this before implementing, refactoring, or optimizing. It describes the whole system — backend
and frontend — its architecture, design patterns, conventions, and the non-obvious gotchas that will
otherwise cost you a debugging cycle.

> This file replaces any other AGENTS.md in the project. It is the source of truth for cross-cutting rules.

---

## 1. What this is

A **UAE e-invoicing SaaS platform**. Organizations (tenants) manage customers, products, and invoices;
the system computes **VAT**, runs **FTA (Federal Tax Authority) compliance validation**, and submits
cleared invoices to the FTA through an **ASP (Accredited Service Provider)** integration. It is
**multi-tenant** with two separate front-ends: a **tenant portal** (organizations) and an **admin
portal** (platform operators).

Core domain flows:
- **Invoice lifecycle:** `DRAFT → ISSUED → (PARTIALLY_PAID) → PAID`, or `CANCELLED`. Draft is the only
  editable state. Issuing is gated on **FTA compliance = COMPLIANT**.
- **E-invoice submission workflow** (state machine): `RECEIVED → PLATFORM_VALIDATING → PLATFORM_VALIDATED
  → ASP_VALIDATING → SUBMITTING → AWAITING_CLEARANCE → COMPLETED` (plus `*_ACTION_REQUIRED` and terminal
  `FAILED/EXPIRED/CANCELLED`). Driven by **bulk Excel upload** and by **single-invoice issue-and-submit**.
- **Compliance** is validated against **data-driven rules** (FTA rules + per-ASP rules) and stored as a
  point-in-time snapshot on the invoice.

---

## 2. Repository layout

```
einvoicing/
├── AGENTS.md                 ← this file
├── backend/                  ← Spring Boot, Gradle multi-module (Java 21)
│   ├── settings.gradle       ← module list
│   ├── gradle.properties     ← centralized dependency versions
│   ├── app/                  ← bootstrap module (main app, config, Flyway migrations + seed SQL)
│   ├── common/               ← enums, exceptions, cross-cutting value types (validation)
│   ├── core/                 ← shared low-level helpers
│   ├── persistence/          ← JPA entities + Spring Data repositories (the DB layer)
│   ├── auth/                 ← security, JWT, TenantContext + filters, AuthArea
│   ├── web-common/           ← ApiPaths constants, springdoc/OpenAPI, shared web config
│   ├── vat/                  ← VatCalculator, VatRateService (VAT math + rate resolution)
│   ├── workflow/             ← generic state machine: FlowDefinition/FlowRegistry/StateMachineService
│   ├── asp-integration/      ← ASP client abstraction: AspClient, AspRegistry, AspClientRouter
│   ├── invoicing/            ← domain services (invoices, credit notes, recurring, submission, validation)
│   ├── tenant-api/           ← tenant REST controllers + request/response DTOs  (base /api/v1)
│   └── admin-api/            ← admin REST controllers + DTOs                     (base /api/v1/admin)
└── frontend/                 ← npm workspaces root (run npm here)
    ├── package.json          ← workspaces: ["shared","tenant-portal","admin-portal"]
    ├── shared/               ← @einvoice/shared — code shared by both portals (imported as @shared/*)
    ├── tenant-portal/        ← Refine + antd SPA for tenants
    └── admin-portal/         ← Refine + antd SPA for platform admins
```

---

## 3. Build, run, test

### Backend (from `backend/`)
- Compile just what you touched (fast feedback): `./gradlew :invoicing:compileJava`.
- Full build: `./gradlew build`. Run: `./gradlew :app:bootRun` (profile `local`).
- DB: PostgreSQL (`jdbc:postgresql://localhost:5432/einvoicing`, user/pass `postgres`), Flyway migrations
  in `app/src/main/resources/db/migration`, dev seed in `app/src/main/resources/db/seed`.
- After changing a service/DTO, compile the changed module(s) **plus `tenant-api`/`admin-api`** to catch
  breakage, then **restart the backend** for a running instance to pick up changes.

### Frontend (from `frontend/`)
- **Install at the `frontend/` root** (workspace root), always with legacy peers:
  `npm install --legacy-peer-deps`. Never install inside an individual portal.
- Dev: `cd frontend/tenant-portal && npm run dev`.
- Verify: `npm run build` = `tsc --noEmit && vite build`; `npm run typecheck` runs tsc alone.
  **Always run `npm run build` (or `typecheck`) after edits — Vite alone does not type-check.**

---

## 4. Backend architecture

### 4.1 Layering (dependency direction)
```
tenant-api / admin-api   (controllers + DTOs; HTTP boundary)
        │  calls
        ▼
invoicing / vat / workflow / asp-integration   (domain services + domain models; own the transactions)
        │  uses
        ▼
persistence   (JPA entities + repositories)      common / core   (enums, exceptions, value types)
```
- **Controllers** (`*-api`) are thin: resolve tenant context, call a service, map domain → DTO. No
  business logic. Base paths come from `ApiPaths` (`web-common`), property-driven (`/api/v1`,
  `/api/v1/admin`).
- **Services** (`invoicing`) own transactions and business rules.
- **Entities** (`persistence`) are the only things that touch the DB.
- **DTOs never leak into services**; services speak **domain records** (below).

### 4.2 The model triad — keep these distinct
- **Entity** (`persistence/.../entity/*Entity.java`): JPA-mapped, mutable, DB row. Holds behavior that
  enforces invariants (e.g. `InvoiceEntity.issue()`, `requireDraft()`, `applyTotals()`, `applyCompliance()`).
- **Command** (`invoicing/.../command/*Command.java`): immutable input to a service op
  (`InvoiceCommand`, `LineCommand`, `RecurringInvoiceCommand`). Request DTOs map to commands via `toCommand()`.
- **Document** (`invoicing/.../document/*Document.java`): immutable **read projection** returned by
  services (`InvoiceDocument`, `BatchSummaryDocument`). Response DTOs map from documents via `from()`/`summary()`.

Flow: `Request DTO → Command → service → Entity (persist) → Document → Response DTO`.

### 4.3 Design patterns in use (know these before adding features)
- **Command pattern** — service inputs.
- **Read projection / DTO assembler** — `InvoiceDocument`, `InvoiceView`, `BatchSummaryDocument`, and DTO
  static factories (`InvoiceResponse.from/summary`, `InvoiceDocumentResponse.from`).
- **State machine** (`workflow`) — `FlowDefinition` (per-flow allowed transitions + initial state),
  `FlowRegistry` (lookup), `StateMachineService.transition(...)` (validate & apply). E-invoice submission
  is `EinvoiceSubmissionFlow`. **A `FlowDefinition` must be a Spring `@Component`** or it won't register.
- **Registry + Strategy** — `AspRegistry.resolveDefaultAsp()` + `AspClientRouter.forCode(...)` pick the
  ASP client; `FlowRegistry` picks the flow definition.
- **Rule engine (data-driven validation)** — `ValidationRuleEngine` evaluates `ValidationRuleEntity` rows
  (seeded in the schema migration) against an `InvoiceView`. `InvoiceValidationService.validateFta` uses
  null-ASP rules; `validateAsp(aspId,…)` uses per-ASP rules. Findings are
  `ValidationError { code, field, message, severity, passCriteria }`.
- **Outbox (async ASP submission)** — `AspOutboxEntity` + `AspSubmissionService` (`enqueueForSession`
  creates outbox rows; `claimBatch` + `processOutbox` are the worker side). ASP calls happen out-of-band.
- **Snapshot** — FTA compliance is computed on write and **stored** on the invoice (`compliance_status`,
  `compliance_checked_at`, `compliance_isses` JSON). Reads return the snapshot; they do NOT re-validate.
  Use `POST /invoices/{id}/revalidate` to refresh.
- **Factory** — `WorkflowSessionFactory`; `InvoiceViewFactory` assembles supplier+buyer+lines+totals into
  an `InvoiceView` (used for validation and the printable document). It derives document totals from the
  line entities, not the (possibly-unset) header totals.

### 4.4 Multi-tenancy & auth (critical)
- `TenantContext` (in `auth`) is a **ThreadLocal** holding `organizationId` + membership role, set by
  `TenantContextFilter` from the **`X-Organization-Id`** header after auth.
- **Tenant endpoints require the header + an active membership** (`AuthArea.TENANT`). **Admin endpoints**
  (`/api/v1/admin`) must NOT send the org header (`AuthArea.ADMIN`). A platform/admin owner has no tenant
  membership and cannot call tenant endpoints — that's a 403 by design.
- Tenant-scoped **async** work has no ThreadLocal — pass context explicitly.
- Controllers use `tenantRequestContext.organizationId()/userId()/requireTenantAdmin()`.

### 4.5 Transaction rules (these have bitten us — follow exactly)
- Put `@Transactional` on the **public service method the controller actually calls**. Overloaded/
  delegating entry points each need their own.
- **Self-invocation does not trigger `@Transactional`** — calling another method on the same bean bypasses
  the proxy. Symptom of getting this wrong: *"No EntityManager with actual transaction available … cannot
  reliably process 'flush'."*
- **Do not rely solely on dirty-checking for updates.** After mutating a managed entity, explicitly
  `repository.saveAndFlush(entity)` before building the response (see `InvoiceService.create/updateDraft/
  issue/cancel/revalidate`). Explicit flush also survives read-only nested calls that can suppress auto-flush.
- Batch cross-aggregate reads to avoid N+1 (see `InvoiceService.submissionsByInvoice`). List endpoints must
  not load per-row detail they don't render (list uses a no-lines summary projection).

### 4.6 Enums & conventions
- Enums live in `common.enums` with an **`Enum` suffix** (`InvoiceStatusEnum`, `VatCategoryEnum`,
  `ComplianceStatusEnum`, `WorkflowStateEnum`, `EinvoiceSubmissionStatusEnum`, …).
- Product/line VAT is exposed as **`vatCategoryEnum`** on request and response DTOs.
- Money is `BigDecimal`, scale 2, `RoundingMode.HALF_UP` (`VatCalculator`).
- Known misspelling: `WorkflowStateEnum.AWAIING_CLEARANCE` (missing “T”). Used consistently; do NOT rename
  casually — it's a persisted value needing a data migration. Match the existing spelling.
- Validation rule severity is data (`validation_rules.severity`): `ERROR` blocks compliance, `WARNING`
  does not. Which fields are mandatory (e.g. payment-terms `PAY-*`) is a **business/data decision**, not
  a code change.

---

## 5. Frontend architecture

### 5.1 Stack (pinned — do not drift)
- **Vite + React 19 + TypeScript**, **Refine v6 packages** (`@refinedev/core@5`, `@refinedev/antd@6`,
  `@refinedev/react-router@2`), **Ant Design v5**, **React Router v7**, **axios**.
- **`@refinedev/antd@6` requires antd v5 — NOT v6.** antd v6 yields two antd copies (dual
  ConfigProvider/React context), breaks `useTable` typings, and bloats the bundle. Keep `antd@^5.23`,
  `@ant-design/icons@^5`. Verify: `npm ls antd` → one v5.
- **React Router v7** — import `BrowserRouter/Routes/Route/Outlet/useParams/useNavigate` from
  **`react-router`** (NOT `react-router-dom`). Mixing RR6 throws *"useLocation() may be used only in the
  context of a `<Router>`"* at runtime.
- `tsconfig`: `moduleResolution: "bundler"` (TS 7 removed `node10`/`Node` and `baseUrl`). Path alias
  `@shared/*` → `../shared/src/*`.
- `vite.config`: `resolve.alias @shared`, `resolve.dedupe: ["react","react-dom","react-router","antd",
  "@refinedev/core"]` (monorepo safeguard against duplicate context), and `server.fs.allow` must include
  the shared dir.

### 5.2 The shared package (`frontend/shared`, imported as `@shared/*`)
Single source of truth for both portals. It is a workspace member **only so its deps hoist to
`frontend/node_modules`** (so `shared/src` can resolve antd/refine); code is imported via the `@shared`
source alias, not the package entry. Contents:
- `types/` — `enums.ts` (string-literal unions mirroring backend enums), `api.ts` (DTO/response shapes).
- `ui/` — `StatusTag` (central enum→colour map), `MoneyText`, `DateText`, `ComplianceBadge`,
  `ValidationIssuesList`, `ConfirmActionButton`, `LineItemsField` (reusable line-item editor),
  `AppHeader` (top bar: theme toggle + user menu with Logout).
- `http/` — `tokenStore` (localStorage tokens/org), `createHttp` (axios factory: Bearer + single-flight
  401 refresh + optional `X-Organization-Id`), `createAuthProvider`, `createDataProvider` (Refine ↔ Spring
  `Page<T>`; reads base URL from the injected axios instance).
- `theme/` — `themeConfig.ts` (**edit design tokens here**: `colorPrimary`, `borderRadius`, `compact`,
  per-mode overrides, per-component), `ThemeProvider` (ConfigProvider + antd `<App>` + persisted
  light/dark), `ThemeToggle` (sun/moon).

**Per-portal, NOT shared:** `config/env.ts` (base URL) and `lib/http.ts` (the concrete `createHttp({...})`
instance). Tenant: base `/api/v1`, `sendOrgHeader: true`. Admin: base `/api/v1/admin`, `sendOrgHeader: false`.

### 5.3 Refine conventions
- **Resources** array in `App.tsx` drives the left menu + routing (`list/create/edit/show`). Routes are
  declared as React Router routes inside `<ThemedLayout>`, which gets `Header={AppHeader}` and a custom
  `Sider` rendering nav items only (Logout lives in the header, not the sider).
- **CRUD pages** use `useTable` + `<List>` and `useForm` + `<Create>/<Edit>`. Customers is the canonical
  template; Products/Credit Notes/Recurring follow it. Line-item documents use `<LineItemsField>`.
- **Custom pages** (not plain CRUD): invoice editor (`pages/invoices/editor.tsx`), printable invoice
  document (`pages/invoices/document.tsx`, browser print → PDF), submission status (`pages/einvoice-batches`,
  polling stepper wrapped in `<Show>` for breadcrumbs/back).
- **Refine v5 hook shapes** (differ from v4 tutorials):
  - `useList` → `{ query, result }`; read `result.data` / `result.total`.
  - `useOne`/`useCustom` → `{ query, result }`; `result` is the record / `{ data }`.
  - `useForm` → `{ formProps, saveButtonProps, query, id }` (record = `query?.data?.data`; NOT `queryResult`).
  - `useCustomMutation` → `{ mutate, mutation }`; loading is `mutation.isPending` (no `isLoading`).
  - `useNotificationProvider` is a **hook** — call inside antd `<App>` context. Layout is `ThemedLayout`
    (not `...V2`); `ThemedTitle`/`ThemedSider` (no `V2`).
- Dates cross the wire as `"YYYY-MM-DD"`; DatePicker needs dayjs — use the `dateItemProps`
  (`getValueProps`/`normalize`) pattern (see the invoice editor).

### 5.4 Two-portal boundary
Tenant and admin are **separate apps** and must not import each other; they share only via `@shared`. The
admin portal wires the same way: `Header={AppHeader}`, `ThemeProvider`, and its own `env`/`http` with
`sendOrgHeader: false` and base `/api/v1/admin`.

---

## 6. Tenant API surface (base `/api/v1`)
- `auth/login|refresh|logout`, `GET auth/me`.
- CRUD: `customers`, `products`, `invoices`, `credit-notes`, `recurring-invoices`.
- Invoice actions: `POST invoices/{id}/issue`, `/cancel`, `/revalidate`, `/submit` (issue-and-submit →
  returns the submission session), `GET invoices/{id}/document` (printable projection).
- Lifecycle: recurring `pause|resume|end`; credit-note `issue|cancel`.
- Submission: `POST einvoice/batches/upload`, `GET einvoice/batches` (list),
  `GET einvoice/batches/{id}`, `POST einvoice/batches/{id}/submit|revalidate`.
- Spring pages serialize as `{ content, totalElements, totalPages, number, size }`; errors as
  `{ status, error, message, path, timestamp }`. The data provider maps both.

---

## 7. Gotchas (hard-won — check these first when something breaks)
1. **`@Transactional` self-invocation** → no transaction. Annotate the real entry point.
2. **Updates not persisting** → add explicit `saveAndFlush` after mutating entities; don't trust
   dirty-checking here.
3. **`FlowDefinition` not registered** (*"No FlowDefinition registered for flow …"*) → the class needs
   `@Component`.
4. **antd v6 installed** → must be **v5** with `@refinedev/antd@6`. `npm ls antd` = one v5.
5. **`react-router-dom` / RR6** → use `react-router` (v7). Runtime `useLocation` Router error otherwise.
6. **Compliance looks stale** after out-of-band data change → reads are a snapshot; call `revalidate`.
7. **Submission status shown prematurely** → an invoice counts as submitted only when its **session state**
   is `SUBMITTING/AWAITING_CLEARANCE/COMPLETED` (or its item is terminal), not merely because an uploaded
   batch created a `PENDING` item. This governs both the displayed status and the re-submit guard.
8. **Install location** → `npm install --legacy-peer-deps` at `frontend/`, not in a portal.
9. **Vite doesn't type-check** → run `npm run build`/`typecheck` before claiming done.
10. **A default ASP must exist** (`asps.is_default = true`, seeded) or submission throws
    *"No default ASP configured."*

---

## 8. Working rules for agents
- **Match existing patterns** in the touched area before inventing new ones (command/document triad, rule
  engine, state machine, shared UI components). Reuse `LineItemsField`, `StatusTag`, `ConfirmActionButton`,
  DTO `from()` factories, etc.
- **Verify, don't assume:** compile the changed backend module(s); run the frontend `npm run build`. Report
  actual results, including failures.
- **Keep the tenant/admin boundary** and the shared-vs-per-portal split intact.
- **Business rules are data** (validation severities, mandatory fields, FTA/ASP rules) — flag them for a
  human decision rather than hard-coding, unless explicitly asked.
- **Don't commit or push** unless explicitly asked. Prefer small, compilable increments.
- When adding a field through the stack, thread it consistently: `Entity → Document → Response DTO` (and
  `Command ← Request DTO` for inputs), plus the frontend type in `@shared/types`.
