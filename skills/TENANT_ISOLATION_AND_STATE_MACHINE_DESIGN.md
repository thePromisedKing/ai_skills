# Tenant Isolation & Workflow State Machine — General Design Document

**Audience:** AI agents and engineers implementing multi-tenant isolation and/or long-running
workflow state machines in a backend service. This document is **platform-agnostic**: it
describes the patterns in general terms (tenant, workflow session, partner system) so they can
be applied to any domain — SaaS, fintech, marketplaces, B2B integrations. Code sketches use
Java/Spring idioms because the reference implementation is a Spring Boot system, but every
mechanism has an equivalent in other stacks (see §C).

The document has two independent parts that compose well together:

- **Part 1 — Multi-Tenant Isolation:** how to guarantee that a tenant can only ever see and
  mutate its own data, with a controlled global-admin bypass.
- **Part 2 — Workflow State Machine:** how to model long-running, multi-step business flows
  (driven by external callbacks, schedulers, and async messaging) as an auditable,
  crash-safe state machine.

---

# Part 1 — Multi-Tenant Isolation

## 1.1 Problem statement

A single deployment serves many organizations ("tenants" — banks, partners, customers,
workspaces). Requirements:

1. A tenant-scoped user must never read or write another tenant's rows (**IDOR prevention**).
2. Isolation must be enforced **automatically** — a developer forgetting a `WHERE tenant_id = ?`
   clause must not create a leak.
3. A **global operator** role (platform admin, regulator, support) must be able to see across
   tenants, and optionally "scope into" a single tenant.
4. A denied cross-tenant access must not leak the existence of the resource
   (**enumeration prevention**).
5. Some channels of the same application may be scoped by a *different* axis (e.g. per end-user
   instead of per tenant) — the design must make this explicit, not accidental.

## 1.2 Design overview — five cooperating layers

Isolation is **defense-in-depth**. No single layer is trusted alone:

```
┌────────────────────────────────────────────────────────────────────┐
│ L1  Identity        single self-issued JWT; area (TENANT/ADMIN)    │
│ L2  Request context per-request TenantContext (scoped holder)      │
│ L3  Automatic data  ORM row filter activated per repository call   │
│ L4  Explicit checks service-layer ownership validation (IDOR gate) │
│ L5  Endpoint authz  roles/permissions — WHICH endpoints, not WHICH │
│                     rows (orthogonal to L2–L4)                     │
└────────────────────────────────────────────────────────────────────┘
```

The key separation of concerns: **authorization (L5) decides whether you may call an
endpoint; tenant scoping (L2–L4) decides which rows you may touch.** Keep them orthogonal —
mixing them produces both leaks and impossible-to-audit code.

## 1.3 L1 — Identity: a single self-issued token; `area` is the boundary

This system does **not** use an external IdP or per-tenant realms (no Keycloak).
Identity is a **self-issued JWT** signed with one secret (HS256), one issuer
(`einvoicing`), validated on every request (`JwtTokenService.parse`: constant-time
HMAC check + issuer + expiry). The token carries:

- `sub` (user id) and `email`,
- `area` — `TENANT` or `ADMIN` — the coarse isolation boundary, and
- `platformRole` (admin side).

The token deliberately does **not** carry an organization. There are no realms to
provision, no per-tenant signing keys, no multi-realm decoder, and no realm
discovery service. The **two areas** play the role that a "global realm vs tenant
realm" split plays in IdP-based systems:

- `area == ADMIN` → platform operator; eligible for cross-organization (global) access.
- `area == TENANT` → tenant user; every request is scoped to exactly one organization (§1.4).

Because there is a single issuer and key, issuer-allowlisting, JWKS rotation, and
last-known-good realm caching do not apply here. Key management reduces to protecting
the one signing secret (see the auth review's secret-handling item).

## 1.4 L2 — Request context: a scoped `TenantContext`

A small, dependency-free holder that carries the resolved tenant for the current unit of work
(thread-local in thread-per-request servers; async-local/context-propagated in reactive or
async runtimes):

```java
public final class TenantContext {
    // currentOrganizationId : the resolved organization UUID (used by the row filter)
    // currentArea           : TENANT | ADMIN (from the JWT)
    // globalAccess          : boolean, default (currentArea == ADMIN)
    static void setTenant(String tenantKey);
    static void setTenantDbId(UUID id);
    static void enableGlobalAccess();
    static boolean hasTenant(); static boolean hasGlobalAccess();
    static void clear();                       // MUST run in a finally block
    // scoped helpers for background jobs / consumers:
    static <T> T executeWithTenant(String tenant, Supplier<T> work);
    static <T> T executeWithGlobalAccess(Supplier<T> work);
}
```

Populate it in a filter/middleware that runs **after** authentication, and clear it in
`finally`. The resolution rules are the security-critical part:

| Caller type | Authoritative organization source | Client-sent header honored? |
|---|---|---|
| Tenant-scoped interactive user | `X-Organization-Id` header, **validated against `organization_members` on every request** | Only after the membership check confirms the authenticated user belongs to that **active** org (active membership + active org). An unverified header → 403. The user may switch among orgs they are a member of. |
| Platform operator (ADMIN area) | Optional `X-Organization-Id` header — lets an admin scope into one org ("view as tenant") | Yes (ADMIN is trusted to cross orgs; membership check may be relaxed for admins per policy) |
| Server-to-server partner (future ASP) | Bound to the authenticated partner credential, not a free header | Only after a dedicated S2S auth step binds the org to that credential |
| Channels scoped by a different axis | None — no org context is set | n/a (see §1.8) |

Also resolve and cache the tenant's **surrogate DB id** here (business key → PK lookup with a
small in-memory cache) so the data layer can filter on an indexed FK column instead of a join.

Expose an injectable façade (`TenantService`) for services:
`getCurrentTenant()` (throws if missing and not global), `hasAccessToTenant(key)`,
`validateTenantAccess(key)` (throws the access-denied exception of §1.7).

## 1.5 L3 — Automatic row filtering (the "forgot the WHERE clause" guard)

Mark tenant-owned entities and let infrastructure add the predicate — never rely on every query
author remembering it.

**Entity side** (Hibernate shown; Postgres RLS, Prisma/Sequelize scopes, or Django managers are
equivalents):

```java
@TenantAware                                    // marker read by the aspect below
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantDbId", type = UUID.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantDbId")
@Entity public class Wallet { @ManyToOne @JoinColumn(name = "tenant_id") Tenant tenant; ... }
```

Entities **without a direct tenant column** get a correlated-subquery condition through their
owning relationship(s). Example — a transaction is visible to a tenant if *either* side's
wallet belongs to it:

```java
@Filter(name = "tenantFilterForTransaction", condition =
  "EXISTS (SELECT 1 FROM wallets w WHERE (w.id = payer_wallet_id OR w.id = payee_wallet_id) " +
  "AND w.tenant_id = :tenantDbId)")
```

**Activation side** — an aspect/interceptor at highest precedence around every repository/DAO
call:

```
for each repository method call:
  domainType = resolve + cache the repo's entity type
  if entity is not @TenantAware            → proceed unfiltered
  if TenantContext has tenantDbId          → session.enableFilter(name).setParameter(...)
  else if globalAccess                     → proceed unfiltered      (admin sees all)
  else if no tenant context at all         → proceed unfiltered      (non-tenant channel, §1.8)
  else (tenant key set but DB id missing)  → THROW TenantContextMissing   // fail closed
```

The last branch matters: a *partially* established context is a misconfiguration and must fail
closed, not silently return the world.

> **Alternative:** database-native Row-Level Security (set `app.tenant_id` as a session GUC and
> write RLS policies). Stronger guarantee (enforced even for raw SQL), at the cost of
> connection-pool discipline. The ORM-filter approach above is the portable baseline; use both
> where the risk justifies it.

## 1.6 L4 — Explicit ownership checks (the IDOR gate)

Automatic filtering protects *list/search* paths. **Load-by-client-supplied-id paths need an
explicit re-check** before any mutation or detail read, because a filtered "not found" and a
cross-tenant "exists but not yours" must be handled deliberately:

```java
void validateOwnedByCurrentTenant(Wallet wallet) {
    if (TenantContext.hasGlobalAccess()) return;
    String callerTenant = TenantContext.getCurrentTenant();
    if (!wallet.getTenant().getKey().equals(callerTenant)) {
        throw TenantAccessDeniedException.forCaller(callerTenant);   // see §1.7
    }
}
```

Where to apply: any service method that (a) accepts a resource id from the client, and
(b) mutates it, returns detail data, or uses it to derive money/permissions. Cheap, explicit,
and testable — do not rely on the row filter alone here, since some lookups legitimately run
with the filter disabled (schedulers, cross-tenant flows like refunds between two tenants,
which must check *both* sides explicitly).

## 1.7 Denial semantics — enumeration-safe by default

One exception type, e.g. `TenantAccessDeniedException`, mapped to **403** (or 404 if your API
prefers full opacity — pick one and be consistent). Two factory forms:

- `of(callerTenant, targetTenant)` — for internal logs/audit where both sides are known and
  loggable.
- `forCaller(callerTenant)` — **the message and payload reference only the caller**, never the
  target tenant or whether the resource exists. Use this whenever the id came from the client:
  "wrong tenant" and "no such resource" must be indistinguishable to the caller.

## 1.8 Global access and mixed-axis channels

- **Global bypass is area-driven, not role-driven.** The context filter reads the token's
  `area`; `area == ADMIN` sets `globalAccess`. Roles/permissions (platform vs tenant) still gate
  endpoints (L5), but *row visibility* comes from the area, not a role. This keeps "who can see
  everything" a property of the authenticated area, not something a role-mapping typo can grant.
- A platform operator may **scope into one organization** by sending the `X-Organization-Id`
  header; the context then behaves exactly like a tenant user's (filter re-enabled for that one
  org). This gives admins a "view as tenant" mode with zero extra code paths.
- **Declare non-tenant channels explicitly.** If one API surface is scoped by a different axis
  (e.g. an end-consumer mobile API scoped per user rather than per tenant), the tenant filter's
  "no context → unfiltered" fall-through is only safe because *those* code paths apply their own
  user-level ownership checks (e.g. resource's user id == authenticated principal). Write this
  dual-model down in the code (filter skip-list) and in docs — it is the most common place a
  future change silently breaks isolation.

## 1.9 Tenant configuration storage

Keep a `Tenant` entity with: surrogate UUID PK, unique short business key, type/category enum,
soft-delete flag, and a **JSONB `data` column** for per-tenant settings (display names,
external identifiers, allowed networks, feature thresholds, inbound/outbound API credentials —
stored hashed/encrypted with primary+secondary rotation slots and expiry). JSONB keeps tenant
onboarding schema-migration-free; promote a field to a real column only when you need to index
or constrain it.

## 1.10 Implementation checklist (tenant isolation)

1. [ ] Tenant entity (UUID PK, unique business key, JSONB settings).
2. [ ] Self-issued JWT carrying `area` + user identity (no IdP/realms); single signing key,
       issuer, and expiry validated on every request.
3. [ ] Organization resolution from the `X-Organization-Id` header **validated against
       `organization_members`** (active membership + active org); ADMIN "scope into org" path.
4. [ ] `TenantContext` (+ scoped helpers for jobs/consumers) and `TenantService` façade.
5. [ ] Context filter after auth: resolution table of §1.4, DB-id resolution+cache,
       `clear()` in finally, explicit skip-list for non-tenant channels.
6. [ ] `@TenantAware` + ORM filters on every tenant-owned entity (subquery form for
       indirectly-owned ones); activation aspect with the fail-closed branch.
7. [ ] Explicit ownership checks on every load-by-id mutate/detail path;
       enumeration-safe denial exception.
8. [ ] Endpoint authz (roles/permissions) kept orthogonal; global bypass area-driven
       (`area == ADMIN`); admin "scope into org" header.
9. [ ] Tests: cross-tenant read/write rejected on list *and* by-id paths; global sees all;
       global-scoped-into-tenant sees one; forged-issuer token rejected; missing-DB-id fails
       closed.

## 1.11 Known pitfalls

- **Trusting a client header for org identity without validating it.** `X-Organization-Id` is
  honored **only** after confirming the authenticated user's active membership in that org (or an
  ADMIN operator scoping in). Never set org context from an unvalidated header.
- **Native SQL / raw queries bypass ORM filters.** Either route them through the same predicate
  manually, or add DB-level RLS for those tables.
- **Background jobs and message consumers have no request filter.** They must establish context
  themselves (`executeWithTenant` / `executeWithGlobalAccess`) — an unset context silently
  becomes "unfiltered" on tenant-aware repos only if your aspect allows it; decide per job.
- **Cross-tenant business flows** (transfers, refunds between two tenants) can't use the
  ambient context alone — validate both sides explicitly.
- **Cache keys must include the tenant.** Any cache populated under one tenant's context and
  read under another is a leak (applies to Redis, in-memory caches, and HTTP caching).

---

# Part 2 — Workflow State Machine (long-running sessions)

## 2.1 Problem statement

Business flows span minutes-to-days and multiple actors: your service, an external partner
system (via HTTP callbacks), async messaging, schedulers, and human steps. Requirements:

1. Every flow instance has exactly one authoritative state at all times, persisted.
2. Only **legal** transitions may occur; illegal ones are rejected loudly (internal bugs) or
   ignored gracefully (external replays/out-of-order events) — deliberately, per entry point.
3. Full **audit trail** of every transition (who/what/why/when), embedded with the record.
4. Abandoned flows **time out** automatically, releasing any held resources.
5. Crashes, retries, duplicate callbacks, and concurrent writers must not corrupt state.

## 2.2 Design overview

```
                     ┌──────────────────────────────┐
   HTTP callback ───►│                              │
   scheduler ───────►│   StateMachineService        │──► session.state = X
   async consumer ──►│   (pure: validate+mutate,    │    + audit entry in JSONB
   internal service ►│    caller owns persistence)  │    + structured audit log
                     └──────────────┬───────────────┘
                                    │ consults
                     ┌──────────────▼───────────────┐
                     │  StateTransitionConfig       │
                     │  Map<Flow, Map<From, Set<To>>│  ← single source of truth,
                     └──────────────────────────────┘    pinned by tests
```

Deliberately **not** a framework state machine (Spring StateMachine, XState, etc.): the state
lives in the database row, the transition table is a plain static map, and the "machine" is a
stateless validator. This keeps the machine horizontally scalable (any node can process any
session), trivially debuggable, and free of framework persistence adapters.

## 2.3 The session entity

One table for all flows (`workflow_sessions`), one row per flow instance:

| Column | Notes |
|---|---|
| `id` UUID PK | surrogate |
| `session_id` unique | business key; **recommend: the id of the domain object the flow serves** (e.g. the transaction id) so lookups and Kafka keys align |
| `state` enum (STRING) | current state |
| `flow_type` enum (STRING) | which flow this instance runs (see §2.5) |
| domain FKs | `tenant_id`, `user_id`, `resource_id`, `amount`, … whatever the flows need to act without joins |
| `external_reference` | correlation id from the partner system |
| `expires_at` Instant, nullable | drives the timeout scheduler; **set to NULL when entering a terminal state** so terminal rows never match the expiry query |
| `last_state_reason` text | human-readable "why is it in this state" |
| `data` JSONB | flexible payload + embedded audit trail (below) |
| `version` bigint | **optimistic locking** (`@Version`) |
| `created_at` / `updated_at` | auto timestamps |

Use dynamic-update semantics (only changed columns in the UPDATE) — the JSONB column is large.

**Embedded audit trail** inside `data`:

```jsonc
{
  "transitions": [   // the authoritative audit trail
    { "transitionId": "uuid",        // per-entry UUID enables dedup on merge
      "fromState": "PENDING", "toState": "SETTLEMENT_COMPLETED",
      "trigger": "CALLBACK",         // CALLBACK | TIMEOUT_SCHEDULER | SAFETY_NET | API | ...
      "reason": "Partner confirmed settlement",
      "timestamp": "..." }
  ],
  "timeline": [      // free-form operational breadcrumbs (retries, notes)
    { "step": "partner_timeout_retry_enqueued", "status": "RETRYING",
      "at": "...", "data": { "retryCount": 2, "remainingBudgetMs": 41000 } }
  ],
  "errorCode": "...", "errorReason": "...", "...flow-specific fields..."
}
```

Entity helpers: `addTransition(from,to,trigger,reason)`; `addTimelineEntry(step,status,data)`;
`mergeTransitions(list)` that **dedups by `transitionId` and re-sorts by timestamp** — this is
what lets concurrent writers (callback path vs. timeout scheduler vs. recovery job) both append
history without clobbering each other after an optimistic-lock retry; `isExpired()`;
`isTerminal()` (delegates to the state enum).

Why JSONB-embedded rather than a separate audit table: the trail travels with the row (one read
gives full history), no fan-out writes, and flows are bounded (tens of transitions). If your
flows can produce unbounded histories or you need to query *across* sessions by transition,
add a projection table fed post-commit — keep the embedded trail as the source of truth.

## 2.4 States: one shared vocabulary, per-flow edges

- **One state enum for all flows**, organized in commented groups (common, screening,
  settlement, hold-pattern, expiry, terminal…). Shared vocabulary keeps dashboards, alerts, and
  queries uniform.
- The enum owns `isTerminal()` (explicit list — e.g. `SUCCESS`, `FAILED`, `CANCELLED`,
  `EXPIRED`, plus flow-specific terminals) and derives `isSuccess()`/`isFailure()` from it.
- **Legality is per-flow**: the same state may have different outgoing edges in different flows.

## 2.5 The transition table — single source of truth

```java
public final class StateTransitionConfig {
    static final Map<FlowType, Map<State, Set<State>>> TRANSITIONS = Map.ofEntries(
        entry(FlowType.ONLINE_TOPUP, onlineTopupTransitions()),
        entry(FlowType.ONBOARDING,   onboardingTransitions()),
        ...);

    private static Map<State, Set<State>> onlineTopupTransitions() {
        return Map.of(
            INITIATED,        Set.of(APPROVED, PENDING, DECLINED, FAILED),
            PENDING,          Set.of(SETTLEMENT_COMPLETED, SETTLEMENT_FAILED, SESSION_TIMEOUT, FAILED),
            SETTLEMENT_COMPLETED, Set.of(CREDITING, FAILED),
            CREDITING,        Set.of(CREDITED, CREDIT_FAILED, FAILED),
            CREDITED,         Set.of(SUCCESS));
    }
    static boolean canTransition(FlowType f, State from, State to) {
        return TRANSITIONS.getOrDefault(f, Map.of()).getOrDefault(from, Set.of()).contains(to);
    }
}
```

Design rules:

- **`FAILED` must be reachable from every non-terminal state in every flow.** This is the
  safety-net edge that lets error-recovery code fail a session from anywhere without fighting
  the machine.
- A flow type declared in the enum but absent from the table means "all transitions rejected" —
  a valid stance for flows that never use the machine; make it deliberate, not accidental.
- Flows may share a sub-map when genuinely identical (alias, don't copy).
- **Pin the table with tests** (§2.10). The table is behavior; treat edits like API changes.

## 2.6 The state machine service — pure validator, caller owns persistence

```java
@Service
public class StateMachineService {                       // stateless
    public Session transition(Session s, State target, String trigger, String reason) {
        if (s.isExpired() && !target.isTerminal()) throw new SessionExpiredException(...);
        if (!StateTransitionConfig.canTransition(s.getFlowType(), s.getState(), target))
            throw new InvalidStateTransitionException(s.getSessionId(),
                    s.getState(), target, s.getFlowType());
        s.addTransition(s.getState(), target, trigger, reason);   // JSONB audit entry
        s.setState(target);
        s.setLastStateReason(reason);
        auditLogger.logStateTransition(...);                       // structured log, 2nd channel
        return s;                                                  // NOT persisted here
    }
    public boolean canTransition(Session s, State target) { ... }  // read-only guard
    public Set<State> getAllowedTransitions(Session s) { ... }
}
```

**`transition()` mutates in memory and does not save.** The caller persists, so several
transitions plus the domain mutations (balance updates, holds, linked records) commit
**atomically in one DB transaction**. This is the single most important semantic choice:
the machine validates and records; the caller owns transactional boundaries.

`InvalidStateTransitionException` carries `sessionId, currentState, targetState, flowType` —
enough for the message `"Invalid state transition for session %s: %s -> %s not allowed for
flow %s"` to be actionable from a log line alone.

**Concurrency:** optimistic locking on the row. A version conflict means another actor
(callback vs. scheduler) won the race — classify it as *transient* (§2.9), reload, re-check
`isTerminal()`/`canTransition`, and retry or ignore. `mergeTransitions` keeps both writers'
audit entries.

## 2.7 Session lifecycle: factory and expiry seeding

A `SessionFactory` with one creation method per flow, which is the only place `expires_at` is
computed:

- terminal-at-birth → `expiresAt = null`;
- interactive/partner flows → `now + configured window` (e.g. 48h);
- SLA-driven flows → derived from the flow's SLA budget config;
- flows with a business expiry (e.g. a request-to-pay with user-chosen deadline) →
  `min(technicalCeiling, businessExpiry)`.

The factory also offers convenience terminal-setters (`completeSession`, `failSession`) that
walk any required intermediate states through the machine rather than jumping, keeping the
audit trail truthful.

## 2.8 Timeout scheduler — strategy handlers, distributed lock, per-session transactions

One scheduler for all flows; per-flow behavior via auto-discovered strategy beans:

```java
public interface TimeoutHandler {
    Set<FlowType> getSupportedFlowTypes();
    Set<State>    getExpirableStates();      // non-terminal states eligible to time out
    TimeoutResult handle(Session expired);   // transition + side effects
}
```

Scheduler loop (fixed rate, e.g. 60s), guarded by a **distributed lock** (ShedLock or
equivalent: `lockAtLeastFor=30s, lockAtMostFor=5m`) so exactly one node runs it:

```
for (flowType, handler) in discoveredHandlers:
    sessions = SELECT ... WHERE state IN handler.expirableStates
                            AND flow_type = flowType
                            AND expires_at IS NOT NULL AND expires_at < now
                            ORDER BY expires_at ASC LIMIT batchSize
    for each session:
        run handler.handle(session) inside ITS OWN transaction   // one bad row ≠ dead batch
        on commit: publish timeout event (keyed by sessionId) for notifications
        on error : log + count, continue
```

Handler responsibilities, by example:

- Simple pending flow → transition to `SESSION_TIMEOUT`, fail the linked domain record
  (**only if still PENDING** — the idempotent guard), notify the partner asynchronously.
- Hold-pattern flow (resources reserved mid-flow) → **release the hold first**, then
  transition, then notify. The release is the reason timeout handling is per-flow.
- Human-verification flow → transition through `SESSION_TIMEOUT` to `FAILED` with a clear
  reason; possibly no partner notification if the contract says so.

Idempotency comes from four reinforcing properties: the distributed lock; the query only
matching non-terminal expirable states (a transitioned session leaves the set, and terminal
states have `expires_at = NULL`); domain-record updates guarded by current-status checks; and
post-commit-only event publication.

## 2.9 External callbacks, retries, and compensation

**Callback entry (partner → you):** a dispatcher on the HTTP thread that resolves the session
and calls a single transactional processing service — "the single point of control for session
state during callback processing." Its guard ladder, in order:

1. Session not found → **ignore** (return success-ish; the partner's retry loop must converge).
2. `session.isTerminal()` → **ignore** ("already terminal") — the primary **replay guard**.
3. Linked domain record no longer pending → **ignore**.
4. `!canTransition(session, impliedTarget)` → **ignore** ("cannot transition from current
   state") — the **out-of-order guard**. Late or reordered callbacks are ignored, not errors.
5. Otherwise: apply transitions in memory via the machine, mutate domain records, save
   everything in **one** transaction, audit-log on success.

The asymmetry is intentional: **internal code paths get exceptions** on illegal transitions
(they indicate bugs); **external entry points get graceful ignores** (they indicate the
inherent messiness of distributed partners). On a *transient* DB conflict (optimistic lock,
deadlock, serialization failure) the dispatcher retries inline a small number of times with
linear backoff, then returns 5xx so the partner's retry takes over.

Also support the **sync/async duality**: a partner call made mid-flow may answer with the final
result synchronously *or* with "pending, callback later" — handle the sync result inline
through the same transition methods the callback path uses, so both paths share one legality
table.

**Retry layers (you → partner):**

1. HTTP-level resilience per partner × call-tier (REALTIME: short timeout, ≤1 retry;
   RETRY-tier: no HTTP retry — the message layer owns it; BACKGROUND: generous).
2. Message-level retry queue: on partner timeout, re-enqueue with an incremented retry count in
   headers until an SLA budget is exhausted. For observability, set the session to a visible
   `RETRY_PENDING` state with the retry context in the timeline (best-effort; overwritten by
   the final outcome).

**Compensation / failure classification:**

- Classify errors as **transient** (lock/serialization/deadlock conflicts → rethrow so the
  transaction rolls back and the message layer redelivers) vs **terminal** (map to an error
  code, mark the domain record FAILED).
- Safety-net helpers usable from *any* error path: `tryReleaseHold(...)` (best-effort,
  swallow), `tryFailSession(sessionId, reason)` (transition any non-terminal session to
  `FAILED` via the machine — legal because of the everywhere-reachable `FAILED` edge — and
  clear `expires_at`).
- Multi-record failure paths (fail domain record + release hold + walk session to terminal)
  run in one `REQUIRES_NEW` transaction so partial failure states can't be observed.
- Publish outcome events **post-commit only**; the database is the source of truth, the event
  stream is derived.

## 2.10 Testing — pin the transition table

The transition table *is* the behavior; tests must fail when it changes:

- Per flow: assert the exact allowed set for key states
  (`allowedFrom(ONLINE_TOPUP, INITIATED) == {APPROVED, PENDING, DECLINED, FAILED}`) and assert
  representative rejections (`INITIATED → SUCCESS` rejected; cross-flow states rejected).
- Assert transitions accumulate in the embedded audit trail with correct from/to/trigger.
- Assert the expired-session rule (non-terminal target on expired session → throws; terminal
  target allowed).
- Handler tests: expirable-state sets, hold released before transition, domain record failed
  only when still pending.
- Callback tests: replayed terminal callback ignored; out-of-order callback ignored;
  transient conflict retried.

## 2.11 Implementation checklist (state machine)

1. [ ] State enum with grouped states + explicit `isTerminal()`; flow-type enum.
2. [ ] Session entity: unique `session_id` aligned with the domain object id, `expires_at`
       (NULL on terminal), `last_state_reason`, JSONB `data` with `transitions[]`
       (per-entry UUID + `mergeTransitions` dedup) and `timeline[]`, optimistic `version`,
       dynamic update.
3. [ ] `StateTransitionConfig`: per-flow maps, `FAILED` reachable from every non-terminal
       state, `canTransition`/`getAllowedTransitions` lookups.
4. [ ] `StateMachineService`: validate → append audit → mutate → audit-log → return
       (no save); `InvalidStateTransitionException` with full context; expired-session rule.
5. [ ] `SessionFactory` per-flow creators owning `expires_at` seeding; terminal-setters that
       walk intermediate states.
6. [ ] Timeout scheduler: strategy `TimeoutHandler` beans (flows + expirable states +
       side effects), distributed lock, batch query ordered by `expires_at`, per-session
       transactions, post-commit timeout events, idempotent domain-record guards.
7. [ ] Callback path: dispatcher (inline transient-conflict retry, 5xx to trigger partner
       retry) + single transactional processor with the 5-step guard ladder
       (ignore, don't throw).
8. [ ] Retry queue with SLA budget + visible `RETRY_PENDING` state; transient-vs-terminal
       error classification; safety-net `tryFailSession`/`tryReleaseHold`;
       post-commit-only event publication.
9. [ ] Tests pinning the transition table, timeout handlers, and callback idempotency.

## 2.12 Known pitfalls

- **Persisting inside the machine.** If `transition()` saves, multi-step updates lose
  atomicity with domain mutations. Keep persistence with the caller.
- **Throwing on external replays.** Partners retry; late/duplicate/out-of-order callbacks are
  normal operation. Ignore-with-log at external boundaries, throw at internal ones.
- **Forgetting to null `expires_at` on terminal transitions** — the timeout scheduler will
  keep matching the row (defense: also exclude terminal states in the query).
- **Timeout handling without resource release** in hold-pattern flows strands reserved
  resources; release-before-transition inside the same transaction.
- **One transaction for the whole timeout batch** — one poisoned row kills the batch forever.
  Per-session transactions with error counting.
- **Deleting the "unused" `FAILED` edges** from the table because "nothing transitions there in
  the happy path" — they are the safety net for recovery code.
- **Letting the state enum fragment per flow.** Shared vocabulary with per-flow edges scales;
  N private enums do not.

---

# Appendix

## A. How the two parts compose

The session entity carries `tenant_id`, so sessions are tenant-scoped data like everything
else (Part 1 applies to it). Schedulers and consumers touching sessions run outside a request:
they must either establish global access explicitly (`executeWithGlobalAccess` — appropriate
for the timeout scheduler, which legitimately spans tenants) or per-tenant context. Partner
callbacks arrive on the S2S channel where tenant identity is bound to the API-key credential;
the callback processor should verify the session's tenant matches the authenticated caller —
this is one of the explicit L4 checks.

## B. Reference implementation map (this repository)

Generic term → where it lives (or would live) in `com.einvoicing.*`. **Status** is
honest about what exists today vs. what this doc proposes.

### Part 1 — Tenant isolation
| Generic (this doc) | This repository | Status |
|---|---|---|
| Tenant | `Organization` — `persistence/.../auth/entity/OrganizationEntity.java`; membership via `OrganizationMemberEntity` | implemented |
| `TenantContext` | `auth/.../security/TenantContext.java` (ThreadLocal, org id only) | implemented — partial (holds org id; member role to be added per `RBAC_DESIGN.md`) |
| Context filter | `auth/.../security/TenantContextFilter.java` | implemented |
| Current-user / principal | `auth/.../security/CurrentUser.java`, `AuthenticatedPrincipal.java` | implemented |
| Token issue / validate | `auth/.../security/JwtTokenService.java`, `JwtAuthenticationFilter.java` | implemented (self-issued HS256; no realms) |
| L3 automatic row filter | **none** — isolation is via explicit `…AndOrganizationId` queries (e.g. `persistence/.../invoicing/repository/InvoiceRepository.findByIdAndOrganizationId`) | not implemented — explicit scoping only; `@TenantAware` + Hibernate `@Filter` aspect is a future option |
| L4 explicit ownership check | service `getExisting(orgId, id)` methods (e.g. `invoicing/.../service/InvoiceService.getExisting`) | partial — see review S2/S4; line-table repos not org-scoped |
| Enumeration-safe denial | `common/.../exceptions/ResourceNotFoundException.java` (+ `ForbiddenAuthException`, `GlobalExceptionHandler`) | implemented — a dedicated tenant-access-denied type is optional |
| L5 endpoint authorization | see [`RBAC_DESIGN.md`](./RBAC_DESIGN.md) | not implemented — planned (review S1) |

### Part 2 — Workflow state machine
Nothing here is built yet; document/invoice lifecycle is the first candidate.
| Generic (this doc) | This repository | Status |
|---|---|---|
| Workflow session entity | — | not implemented — planned (document lifecycle, future ASP submission) |
| Transition table / machine | invoice/credit-note status guards live ad-hoc in entity methods (`persistence/.../invoicing/entity/InvoiceEntity.issue/cancel/requireDraft`, `CreditNoteEntity`) | not implemented as a machine — §2 is the target design |
| Timeout scheduler + handlers | `auth/.../service/RefreshTokenCleanupJob.java` is the only `@Scheduled` job today | not implemented for workflows — planned |
| Session factory | — | not implemented — planned |
| Callback dispatcher / processor | — | not implemented — planned (ASP callbacks) |
| Retry / compensation | — | not implemented — planned |
| Table-pinning tests | `vat/.../VatCalculatorTests.java` exists but is unrelated | not implemented — planned alongside the machine |

## C. Stack translation notes

| Mechanism (Spring/Hibernate) | Equivalent elsewhere |
|---|---|
| ThreadLocal `TenantContext` | Node `AsyncLocalStorage`, Python `contextvars`, Go `context.Context`, .NET `AsyncLocal` |
| Self-issued JWT `area` claim | Realm-per-tenant + `iss` allowlist in IdP-based systems (Keycloak/Auth0/Cognito) — **not used here** |
| Hibernate `@Filter` + aspect | Postgres RLS + session GUC; Prisma client extensions; Django custom managers; Rails default scopes |
| `@Version` optimistic locking | `version`/`updated_at` compare-and-set column in any ORM, or `WHERE version = ?` in raw SQL |
| ShedLock distributed lock | Redis `SET NX PX`, Postgres advisory locks, k8s leader election |
| `@Scheduled` fixed rate | cron + leader election, Sidekiq/Celery beat, Temporal timers |
| JSONB audit trail | Any document column (Postgres JSONB, MySQL JSON); append-only event table if unbounded |
| Kafka retry queue with header counters | SQS + visibility timeout & receive count, RabbitMQ DLX with TTL, Pub/Sub retry policy |
