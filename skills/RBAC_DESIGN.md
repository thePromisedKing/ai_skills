# Design: Role-Based Access Control (Tenant + Admin)

> Status: **Draft for implementation.** Audience: AI coding agents and reviewers.
> Scope: a permission-based authorization model spanning the two operating areas
> (**Tenant** and **Admin**), with distinct roles and responsibilities, enforced
> across all current and future modules, and extensible to org-defined custom roles.
>
> Read [`AGENTS.md`](../AGENTS.md), [`INVOICING_MODULE_DESIGN.md`](./INVOICING_MODULE_DESIGN.md),
> [`TECHNICAL_REVIEW_TASKS.md`](./TECHNICAL_REVIEW_TASKS.md), and
> [`TENANT_ISOLATION_AND_STATE_MACHINE_DESIGN.md`](./TENANT_ISOLATION_AND_STATE_MACHINE_DESIGN.md)
> first. This design **implements review finding S1** (no authorization in tenant-api)
> as its first phase. Where this conflicts with `AGENTS.md`, `AGENTS.md` wins.
>
> **Relationship to the isolation doc.** That document defines a five-layer isolation
> model (L1 identity → L2 request context → L3 automatic row filter → L4 explicit
> ownership checks → L5 endpoint authorization). **RBAC *is* L5.** This document
> owns L5 and nothing else; it must not be used to make row-visibility decisions —
> those belong to L2–L4. In that doc's generic vocabulary, "tenant" = our
> **Organization** and `tenant_id` = `organization_id`.

---

## 1. Goals & Principles
- **Two independent areas.** Tenant and Admin authorization are separate. A platform
  admin is *not* a tenant member unless explicitly added (`AGENTS.md`). Admin
  permissions never grant tenant access and vice-versa.
- **Permission-based, role-driven.** Code checks **permissions** (fine-grained,
  e.g. `invoice:issue`), never role names. Roles are *bundles* of permissions. This
  lets us add/rename roles without touching enforcement code.
- **Per-organization tenant roles.** A user can be OWNER in org A and MEMBER in org
  B. Tenant permissions are resolved for the **currently selected organization**.
- **Least privilege.** A role gets only the permissions its responsibilities require.
  Destructive actions (issue/cancel/archive/suspend/delete) are gated above the base role.
- **Immediate effect.** Permissions are resolved **server-side per request** from
  the current role, not baked into the JWT — a role change takes effect on the next
  request, and access tokens stay small.
- **Auditable.** Privileged actions are recorded (reuse `AuditLogEntity`).
- **Extensible.** Static role→permission maps now; a clean seam to move to
  DB-defined **custom roles** per organization later, with no change to call sites.
- **Authorization ≠ isolation.** Permissions decide *which actions/endpoints* a
  caller may invoke (L5). They **never** decide *which rows* a caller may touch —
  that is tenant scoping (L2–L4 of the isolation doc). The two are orthogonal and
  both required: a tenant ADMIN of org A holding `invoice:issue` must still be
  unable to touch org B's data.
- **Cross-tenant visibility is area-driven, not permission-driven.** The ability to
  see across organizations is a property of the **ADMIN area** (a deployment-level
  fact), not of any permission or role bundle. No tenant permission — and no
  platform permission — ever widens row visibility; that is set by L2/L3 from the
  authenticated area. This prevents a role-mapping mistake from silently granting
  global data access. (See §6 and §9.)

---

## 2. Current State (what exists today)
- **Areas:** `AuthArea { TENANT, ADMIN }`. Enforced by path in
  `JwtAuthenticationFilter.isAllowedForPath` (`/api/admin/**` → ADMIN, `/api/**` → TENANT).
- **Role enums:** `PlatformRole { NONE, SUPPORT, ADMIN, OWNER }` (admin side),
  `OrganizationMemberRole { OWNER, ADMIN, MEMBER }` (tenant side) — both in `common/domain`.
- **Authorities today:** only `ROLE_TENANT` / `ROLE_ADMIN` are granted
  (`JwtAuthenticationFilter.java:47`). **No permissions, no method security.**
- **Principal:** `AuthenticatedPrincipal(userId, email, area, platformRole)` — carries
  the platform role but **not** the tenant member role.
- **Tenant context:** `TenantContext` holds only `organizationId`
  (from the `X-Organization-Id` header, validated by `hasActiveMembership`).
- **Gap (review S1):** no controller/service checks any role/permission — any active
  member can perform any tenant action; platform-role granularity is unused.

**What must be added:** a permission catalog, role→permission maps, the tenant
member role loaded into the request context, permission authorities populated on the
`Authentication`, and `@PreAuthorize` enforcement.

---

## 3. Core Model

Three concepts:

1. **Area** — `TENANT` | `ADMIN`. Coarse boundary (already enforced).
2. **Role** — a named responsibility bundle. Two role dimensions already exist:
   - Tenant: `OrganizationMemberRole` (per-organization, from `organization_members.role`).
   - Platform: `PlatformRole` (per-user, from `users.platform_role`).
3. **Permission** — an atomic capability, format **`module:action`** (lowercase,
   colon-separated). This is what code checks.

### 3.1 Permission naming
`<module>:<action>` — e.g. `invoice:issue`, `customer:write`, `admin:org:onboard`.
Admin permissions are prefixed `admin:` so the two areas can never collide. Define
them as a single `Permission` enum in `common/domain` (type-safe, aligns with the
`AGENTS.md` "enums in common" rule); each constant exposes its wire string.

```java
public enum Permission {
    CUSTOMER_READ("customer:read"),
    INVOICE_ISSUE("invoice:issue"),
    ADMIN_ORG_ONBOARD("admin:org:onboard");
    // ...
    private final String code;
    Permission(String code) { this.code = code; }
    public String code() { return code; }
}
```

---

## 4. Permission Catalog

### 4.1 Tenant permissions
| Module | Permissions |
|---|---|
| Customers | `customer:read`, `customer:write`, `customer:archive` |
| Products | `product:read`, `product:write`, `product:archive` |
| Invoices | `invoice:read`, `invoice:write` (create/edit draft), `invoice:issue`, `invoice:cancel` |
| Credit notes | `credit_note:read`, `credit_note:write`, `credit_note:issue`, `credit_note:cancel` |
| Recurring | `recurring:read`, `recurring:write`, `recurring:manage` (pause/resume/end) |
| VAT | `vat:read`, `vat:manage` (future: returns/filing) |
| Payments (future) | `payment:read`, `payment:write` |
| Organization | `org:read`, `org:manage` (settings), `org:member:read`, `org:member:manage` |
| Billing (future) | `org:billing:manage` |

### 4.2 Platform (Admin) permissions
| Module | Permissions |
|---|---|
| Organizations | `admin:org:read`, `admin:org:onboard`, `admin:org:manage`, `admin:org:suspend` |
| ASP integration | `admin:asp:read`, `admin:asp:manage` |
| Platform users | `admin:user:read`, `admin:user:manage` |
| Roles (future) | `admin:role:manage` (custom-role administration) |
| Platform config | `admin:platform:settings` |
| Audit | `admin:audit:read` |
| Support | `admin:support:impersonate` **[CONFIRM]** (high-risk; see §9) |

> Adding a module = adding its permissions here + mapping them into the role matrices.
> No enforcement code changes.

---

## 5. Role → Permission Matrices

These are the **default (system) roles**. `●` = granted.

### 5.1 Tenant roles (`OrganizationMemberRole`)
| Permission | MEMBER | ADMIN | OWNER |
|---|:--:|:--:|:--:|
| `*:read` (all tenant read) | ● | ● | ● |
| `customer:write`, `product:write` | ● | ● | ● |
| `invoice:write`, `credit_note:write`, `recurring:write` | ● | ● | ● |
| `customer:archive`, `product:archive` | | ● | ● |
| `invoice:issue`, `invoice:cancel` | | ● | ● |
| `credit_note:issue`, `credit_note:cancel` | | ● | ● |
| `recurring:manage` | | ● | ● |
| `vat:manage` | | ● | ● |
| `org:member:read` | | ● | ● |
| `org:manage`, `org:member:manage`, `org:billing:manage` | | | ● |

Summary of responsibilities:
- **MEMBER** — day-to-day data entry: create/edit **drafts** and manage catalog/customers; cannot issue, cancel, archive, or touch org settings.
- **ADMIN** — full operational control: issue/cancel documents, archive, manage recurring, view members; not org settings/ownership/billing.
- **OWNER** — everything, including organization settings, member management, billing, and ownership.

**[CONFIRM]** Whether MEMBER may create customers/products or only invoices/drafts.

### 5.2 Platform roles (`PlatformRole`)
| Permission | SUPPORT | ADMIN | OWNER |
|---|:--:|:--:|:--:|
| `admin:org:read`, `admin:asp:read`, `admin:audit:read`, `admin:user:read` | ● | ● | ● |
| `admin:org:onboard`, `admin:org:manage`, `admin:org:suspend` | | ● | ● |
| `admin:asp:manage` | | ● | ● |
| `admin:user:manage` | | | ● |
| `admin:role:manage`, `admin:platform:settings` | | | ● |
| `admin:support:impersonate` **[CONFIRM]** | | | ● |

- **NONE** — no admin permissions (a normal tenant-only user; the default).
- **SUPPORT** — read-only visibility across the platform to assist customers; no writes.
- **ADMIN** — onboard and manage organizations and ASPs.
- **OWNER** — full platform control incl. platform users, roles, settings.

### 5.3 Future roles (design for, don't build now)
- Tenant `VIEWER` (read-only), `ACCOUNTANT` (invoices + VAT + read, no catalog/customer writes).
- These slot in as new rows without touching enforcement — see §8 custom roles.

---

## 6. Enforcement Architecture (defense in depth)

This maps onto the isolation doc's five layers. RBAC **owns L5**; the other layers
are listed so the seams are explicit.

| Layer | Owner | Responsibility | Status |
|---|---|---|---|
| **L1 Identity** | auth | Authenticated area + user (and, target-state, org identity) from the token | exists (JWT) |
| **L2 Request context** | auth | `TenantContext` holds the resolved `organizationId` (+ member role, added here); `globalAccess` = (area == ADMIN) | partial |
| **L3 Automatic data scope** | persistence | Every tenant query filtered by `organizationId` | exists (explicit `…AndOrganizationId`) |
| **L4 Explicit ownership check** | services | By-id load/mutate re-checks org ownership; enumeration-safe denial | partial (review S2/S4) |
| **L5 Endpoint authorization** | **RBAC (this doc)** | Which actions the caller may invoke, via permissions | **to build** |

RBAC additions live entirely at L5:

- **Permission authorities** — the `Authentication` carries the caller's resolved
  permissions as `GrantedAuthority`s (see §7).
- **Method security** — `@PreAuthorize("hasAuthority('invoice:issue')")` on the
  **service** methods (authoritative) — business decisions live in services
  (`AGENTS.md`), can't be bypassed by a new controller. Controllers stay thin.
- **Resource ownership (future ABAC)** is L4, not L5 — e.g. "a MEMBER may edit only
  drafts they created." Out of scope now; seam noted (a `PermissionEvaluator` can add
  `hasPermission(#invoiceId, 'invoice', 'edit')` later).

### 6.1 Global access is area-driven (not a permission)
`globalAccess` (cross-org row visibility) is set at **L2 from the authenticated
area** — `area == ADMIN` ⇒ global; `area == TENANT` ⇒ scoped to the resolved org.
Platform **permissions** still gate *which admin endpoints* an operator may call
(e.g. `admin:org:suspend`), but they do **not** grant row visibility — that already
comes from the area. An ADMIN operator may **scope into a single organization** by
sending the org header, which re-enables org-scoped filtering for that request (the
"view as tenant" mode), with endpoint authz still governed by their platform role.

### 6.2 Check order is enumeration-safe
Enforce **L5 permission before loading the resource**, so a missing permission
returns **403 regardless of whether the row exists** — it can't be used to probe
existence. Ownership failures at L4 use the isolation doc's **enumeration-safe
denial** (§1.7 there): the response references only the caller, never the target
org or whether the resource exists ("wrong org" and "no such resource" are
indistinguishable). Pick one status for L4 (403 or 404) and apply it consistently.

### 6.3 RBAC composes with the workflow state machine
Document lifecycle transitions (invoice `DRAFT → ISSUED → CANCELLED`, credit note,
recurring) are governed by the state machine (isolation doc Part 2): a **transition
table** decides *whether* a transition is legal from the current state. RBAC and the
state machine answer **different questions and are both required**:

- **RBAC (L5):** *may this caller trigger this action?* → `@PreAuthorize("hasAuthority('invoice:issue')")`
- **State machine:** *is `currentState → targetState` legal for this flow?* → `StateTransitionConfig.canTransition(...)`

Order: check the permission first (fail closed, enumeration-safe), then let the state
machine validate the transition (illegal internal transition → throw; external
replay → ignore). Map permissions to the transitions they gate, e.g.
`invoice:issue` → `DRAFT→ISSUED`, `invoice:cancel` → `*→CANCELLED`,
`credit_note:issue`/`credit_note:cancel` likewise, `recurring:manage` →
pause/resume/end edges. A read permission (`*:read`) never gates a transition.

---

## 7. Populating Permissions on the Request

Permissions are computed **per request**, never stored in the JWT (per-org tenant
roles + immediate revocation). A single resolver maps a role to its permission set:

```java
public interface RolePermissionResolver {
    Set<Permission> permissionsFor(OrganizationMemberRole tenantRole); // tenant
    Set<Permission> permissionsFor(PlatformRole platformRole);         // platform
}
```
MVP implementation: `StaticRolePermissionResolver` holding the §5 maps as immutable
`EnumMap`s. (Future: a DB-backed resolver — §8.)

### 7.1 Admin area (role known from JWT)
`platformRole` is already in the JWT/principal, so `JwtAuthenticationFilter` can grant
platform permission authorities immediately:
```java
// in authenticate(...), for ADMIN area:
authorities.add(new SimpleGrantedAuthority("ROLE_ADMIN"));
resolver.permissionsFor(claims.platformRole())
        .forEach(p -> authorities.add(new SimpleGrantedAuthority(p.code())));
```

### 7.2 Tenant area (role known only after org resolution)

> **Org source (settled).** There is no external IdP or realms (no Keycloak), so the
> org is resolved from the `X-Organization-Id` header, validated against
> `organization_members` on every request (isolation doc §1.4). One token can act for
> any org the user is an active member of; the org is **not** bound into the JWT, and
> the caller may switch orgs per request. (Future optional optimization: embed the
> currently selected org as a claim in the self-issued JWT to avoid the per-request
> lookup — not required, and not a one-token-per-org/realm model.)

The tenant member role is **per-organization**, resolved from the org context (today
the `X-Organization-Id` header). So `TenantContextFilter` — which already validates
membership — loads the role and augments the authentication:
1. Add a repository query returning the active role:
   `Optional<OrganizationMemberRole> findActiveRole(UUID userId, UUID organizationId)`
   (active member + active org) in `AuthMembershipRepository`.
2. In `resolveTenantContext`, after the membership check, load the role, store it in
   `TenantContext` (extend it to hold the role too), and **rebuild** the
   `Authentication` with `ROLE_TENANT` + the tenant permission authorities.
3. Also extend `AuthenticatedPrincipal` (or `TenantContext`) to expose the resolved
   `organizationId` + `OrganizationMemberRole` for services that need them.

> Because `TenantContextFilter` runs after `JwtAuthenticationFilter`
> (`AuthSecurityConfig` `addFilterAfter(tenantContextFilter, JwtAuthenticationFilter.class)`),
> the ordering is already correct.

**Consequence:** a tenant business call **must** carry `X-Organization-Id`; without
it there are no tenant permissions and `@PreAuthorize` yields 403. Document this
contract for the FE team. `/api/auth/**` and `/api/health` are exempt (already in `shouldNotFilter`).

### 7.3 Enable method security
Add `@EnableMethodSecurity` (on a security config in `app` or `auth`). Annotate
service methods, e.g.:
```java
@PreAuthorize("hasAuthority('invoice:issue')")
public InvoiceDocument issue(UUID organizationId, UUID invoiceId) { ... }
```

---

## 8. Data Model & Future Custom Roles

### 8.1 Now (system roles, code-defined)
No schema change. Keep `organization_members.role` (`OrganizationMemberRole`) and
`users.platform_role` (`PlatformRole`). The `StaticRolePermissionResolver` owns the
mapping. Ship RBAC entirely in code.

### 8.2 Later (org-defined custom roles) — design the seam now
When tenants need bespoke roles, introduce DB-driven roles **behind the same
`RolePermissionResolver` interface** (call sites unchanged):

- `roles(id, organization_id NULL, area, name, is_system, ...)` — `organization_id`
  NULL = system/global role; non-null = a custom role owned by that org.
- `role_permissions(role_id, permission VARCHAR)` — permission strings (uppercase VARCHAR, per `AGENTS.md`).
- `organization_members.role_id` (FK) — replaces/augments the enum column; keep the
  enum during migration for backfill.
- Platform equivalent for admin custom roles if ever needed.

A `DbRolePermissionResolver` reads these (cached) and returns the same
`Set<Permission>`. The `admin:role:manage` / `org:member:manage` permissions gate the
role-administration APIs. **Do not build this now** — just don't block it:
enforcement checks permissions, so swapping the resolver is transparent.

---

## 9. Cross-Cutting Concerns
- **Area separation is absolute.** Never grant an `admin:*` permission to a tenant
  role or a tenant permission to a platform role. Keep the two maps disjoint; a test
  asserts no permission appears in both.
- **Impersonation / SUPPORT.** `admin:support:impersonate` is high-risk. If adopted,
  require it be OWNER-only (or dual-control), time-boxed, and **always** audit-logged
  with the real admin identity. **[CONFIRM]** whether to include at all for MVP.
- **Audit privileged actions.** Log issue/cancel/suspend/onboard/role-change/
  impersonation to `AuditLogEntity` (actor user id, area, org id, permission, target).
- **Fail closed.** Missing/unknown permission → 403 via the existing
  `accessDeniedHandler` (`AuthSecurityConfig`) returning the standard `ApiErrorResponse`.
- **No role names in code.** Grep guard: enforcement must use permission codes, not
  `OrganizationMemberRole.ADMIN` comparisons, so role definitions stay declarative.
- **Async caveat.** Permissions ride the `SecurityContext`/`TenantContext`
  (thread-bound). Any future `@Async` work, scheduler, or message consumer must
  establish/propagate both explicitly — use the isolation doc's scoped helpers
  (`executeWithTenant` / `executeWithGlobalAccess`) rather than inheriting an
  ambient context (review S5; isolation doc §1.11).
- **Permission caches must be org-scoped.** When the DB-backed resolver (§8.2)
  caches role→permission sets, the cache key must include the organization (and, for
  custom roles, the role id). A permission set computed under one org must never be
  read under another — same rule as the isolation doc's "cache keys must include the
  tenant" (§1.11).

---

## 10. Phased Task Plan

### Phase 1 — Tenant RBAC (closes review S1)
- [ ] R1.1 `Permission` enum in `common/domain` with the tenant catalog (§4.1).
- [ ] R1.2 `RolePermissionResolver` interface + `StaticRolePermissionResolver` with the tenant matrix (§5.1).
- [ ] R1.3 `AuthMembershipRepository.findActiveRole(userId, orgId)`.
- [ ] R1.4 Extend `TenantContext` (+ `AuthenticatedPrincipal` or a tenant principal) to carry `organizationId` + `OrganizationMemberRole`.
- [ ] R1.5 `TenantContextFilter`: load role, rebuild `Authentication` with tenant permission authorities.
- [ ] R1.6 `@EnableMethodSecurity`; add `@PreAuthorize` to invoicing/customer/product/credit-note/recurring **service** methods per the matrix.
- [ ] R1.7 Tests: MEMBER blocked from issue/cancel/archive (403); ADMIN allowed; OWNER-only org actions; **cross-org denied even with the right permission** (RBAC ⟂ tenant scope).

### Phase 2 — Admin RBAC
- [ ] R2.1 Add the admin permission catalog (§4.2) to `Permission`.
- [ ] R2.2 Platform matrix in the resolver (§5.2).
- [ ] R2.3 `JwtAuthenticationFilter`: grant platform permission authorities from `platformRole`.
- [ ] R2.4 `@PreAuthorize` on admin-api services (onboarding/ASP/user/settings as they land).
- [ ] R2.5 Tests: SUPPORT read-only; ADMIN cannot manage platform users; OWNER full.

### Phase 3 — Hardening & audit
- [ ] R3.1 Audit-log privileged actions to `AuditLogEntity`.
- [ ] R3.2 Disjointness test (no permission in both tenant and platform maps); FE contract doc for the `X-Organization-Id` requirement.
- [ ] R3.3 Decide/record the impersonation policy (§9).

### Phase 4 — Custom roles (only when needed)
- [ ] R4.1 `roles` / `role_permissions` migrations; `organization_members.role_id`.
- [ ] R4.2 `DbRolePermissionResolver` (cached) behind the existing interface.
- [ ] R4.3 Role-admin APIs gated by `admin:role:manage` / `org:member:manage`.

---

## 11. Open Decisions to Confirm
Consolidated **[CONFIRM]** list:
- MEMBER write scope (customers/products, or invoices/drafts only) — §5.1.
- Whether to include `admin:support:impersonate` for MVP, and its guardrails — §4.2/§9.
- Enforcement altitude: **service-layer `@PreAuthorize`** (recommended) vs controller-layer.
- Whether tenant role should also be surfaced in `me()` so the FE can hide actions
  (recommended: return the current org's permission set from `/api/auth/me`).

> Confirm that **global/cross-org visibility stays area-driven** (§6.1) — no
> permission grants it — and that RBAC checks run **before** resource load for
> enumeration safety (§6.2). These are settled in this doc; flagged only so a
> reviewer can veto.

Proceed with the recommended default for each unless a reviewer objects.
