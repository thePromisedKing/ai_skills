# Technical Review — Invoicing + JPA Implementation

> Source: technical review of the merged auth-module + invoicing/persistence/vat
> implementation (commit `52d3219`, branch `feature/auth-module`).
> Audience: AI coding agents. Each finding is self-contained: location, severity,
> problem, fix, and acceptance criteria. Work by priority (CRITICAL → HIGH →
> MEDIUM → LOW). Read [`AGENTS.md`](../AGENTS.md) and
> [`INVOICING_MODULE_DESIGN.md`](./INVOICING_MODULE_DESIGN.md) first — both are binding.

## How to use this file
- Pick the highest-priority unchecked item. Read the referenced file before editing.
- Keep changes scoped; match existing style (tabs, Lombok `@Getter`, constructor injection, records for DTOs).
- Add/adjust tests for every behavioral change; run `./gradlew test` before ticking the box.
- Verify a claim against the code before acting — some items are marked **[VERIFY]**.

## Overall assessment
The architecture is sound and the design doc was followed well: clean module split
(`persistence` owns entities/repos, feature modules own services, api modules own
controllers), FK-id associations instead of `@ManyToOne` (no N+1 / no cross-tenant
lazy traversal), `EnumType.STRING` everywhere, correct `BigDecimal`/`NUMERIC`
money types, per-line VAT rounding, pessimistic-locked document numbering, and a
disciplined `Clock` pattern. The issues below are concentrated in: authorization
(no RBAC), one cross-tenant validation gap, the `BaseEntity` id generator, two
incomplete entities, and test coverage of the new financial code.

## Findings summary

| ID | Sev | Area | One-line |
|----|-----|------|----------|
| S1 | HIGH | Security | No role-based authorization in tenant-api; any MEMBER can issue/cancel/archive |
| S2 | HIGH | Security | Credit note can reference another customer's invoice in the same org |
| P1 | HIGH | JPA | `BaseEntity` id generator produces random v4 UUIDs app-side, not DB `uuidv7()` |
| P2 | HIGH | JPA | `PaymentEntity` / `VatReturnEntity` have no constructor/mutators — cannot be populated |
| TEST1 | HIGH | Tests | No tests for any invoicing service, repository, or controller |
| S3 | MED | Security | org id comes from `X-Organization-Id` header (DB-validated, but header-based) |
| S4 | MED | Security | Line-table repositories are not tenant-scoped; rely on service discipline |
| S5 | MED | Security | `TenantContext` ThreadLocal won't survive async/parallel execution |
| P3 | MED | Design | `list()` in all four invoicing services returns `Page<…Entity>` (entity leak) |
| C1 | MED | Correctness | VAT totals computed twice per save (Invoice + CreditNote) |
| T1 | MED | Time | `AuthService:76` uses bare `Instant.now()` instead of injected `Clock` |
| T3 | MED | Time | JPA auditing timestamps not backed by the `Clock` bean |
| V1 | MED | Validation | `InvoiceRequest.type` not `@NotNull`; `LineRequest` allows empty line |
| M1 | MED | Migrations | Fragmented history (V7 then V11 patch core invoice fields; V18 patches all) |
| P4 | LOW | JPA | `@Modifying` queries missing `clearAutomatically` |
| C2 | LOW | Correctness | Document-number first-issue insert race (mitigated by unique constraint) |
| C3 | LOW | Correctness | Number string embeds year but counter never resets per year |
| C4 | LOW | Cleanup | `InvoiceService` dead `lineNumber` variable |
| T2 | LOW | Time | `Clock` bean declared inside `AuthSecurityConfig` (infra bean in wrong place) |
| V3 | LOW | Validation | Currency/TRN/country fields accept non-ISO values |

---

## CRITICAL
*(none — no data-loss or auth-bypass defect found; the HIGH items are the top priority)*

## HIGH

### [ ] S1 — Add role-based authorization to tenant-api
**Problem.** `OrganizationMemberRole` (OWNER/ADMIN/MEMBER) exists but is **never
checked**. No `@PreAuthorize`/`@Secured`/`hasRole` anywhere in `tenant-api`. Every
mutation — create/update/`issue`/`cancel`/`archive`/`end` — is available to any
active member, including a plain MEMBER. The role isn't even carried past
`AuthMembership` onto the authenticated principal or into `TenantContext`.
**Files.** `auth/.../security/AuthenticatedPrincipal.java`, `TenantContextFilter.java`,
`TenantContext.java`, all `tenant-api/.../controller/*Controller.java`.
**Fix.**
1. Carry the caller's `OrganizationMemberRole` for the resolved org into
   `TenantContext`/principal (the membership row is already loaded in
   `TenantContextFilter`).
2. Enable method security (`@EnableMethodSecurity`) and gate destructive actions,
   e.g. `@PreAuthorize("hasAuthority('ORG_ADMIN')")` on issue/cancel/archive/end;
   or enforce in the service from the context role.
**[CONFIRM]** the role→action matrix with a human (who may cancel an invoice, archive a product, etc.).
**Acceptance.** A MEMBER receives 403 on gated actions; an OWNER/ADMIN succeeds; tests cover both.

### [ ] S2 — Credit note must belong to the referenced invoice's customer
**Problem.** `CreditNoteService.validateReferences` checks that the customer and the
invoice each exist in the org, but never asserts the invoice belongs to that
customer. A caller can credit customer A against customer B's invoice.
**File.** `invoicing/.../service/CreditNoteService.java` (`validateReferences`, ~line 120).
**Fix.** After fetching the invoice, assert
`invoice.getCustomerId().equals(command.customerId())`, else
`DomainRuleViolationException`.
**Acceptance.** Mismatched customer/invoice → 4xx domain error; matching pair succeeds; test covers it.

### [ ] P1 — Fix `BaseEntity` id generation (currently NOT uuidv7) **[VERIFY]**
**Problem.** `BaseEntity` (and `AuditLogEntity`) annotate the id with **both**
`@GeneratedValue` **and** `@Generated(event = INSERT)` + `@ColumnDefault("uuidv7()")`.
A bare `@GeneratedValue` on a `UUID` makes Hibernate 6 assign a **random v4 UUID
in-memory before INSERT**, so the DB `uuidv7()` default never fires and ids are
**not time-ordered** — defeating the whole reason for uuidv7 (index locality) and
contradicting `AGENTS.md`.
**File.** `persistence/.../BaseEntity.java:28-33`, `persistence/.../invoicing/entity/AuditLogEntity.java:28-31`.
**Fix.** Drop `@GeneratedValue`; keep `@Generated(event = INSERT)` + `@ColumnDefault("uuidv7()")`
so Hibernate omits id from the INSERT and reads back the DB-generated value. (Also
review `UserEntity`/`RefreshTokenEntity` constructors that call `super(id)` with an
app-supplied id — confirm intended.)
**[VERIFY]** Add a `@DataJpaTest` (Testcontainers PostgreSQL) that saves an entity
and asserts the persisted id is a **version-7** UUID (`id.version() == 7`) and that
two rows inserted in order are byte-ascending.
**Acceptance.** Test proves ids are DB-generated uuidv7; existing tests still pass.

### [ ] P2 — Complete `PaymentEntity` and `VatReturnEntity`
**Problem.** Both have only a protected no-arg constructor and `PROTECTED` setters,
with no public constructor or mutating methods — their mandatory fields
(`organizationId, invoiceId, amount, currency, method, paidAt`, etc.) can never be
populated. As written, payments and VAT returns cannot be created.
**Files.** `persistence/.../invoicing/entity/PaymentEntity.java`, `VatReturnEntity.java`.
**Fix.** Add public domain constructors (and any needed state-transition methods)
mirroring the other entities. If these tables are intentionally not wired up yet,
mark them clearly as placeholders and exclude from the active mapping.
**Acceptance.** An instance can be constructed with all non-null fields and persisted; a repository test inserts one.

### [ ] TEST1 — Add tests for the invoicing domain
**Problem.** Only `auth` and `VatCalculator` have tests. There are **no** tests for
`InvoiceService`, `CreditNoteService`, `CustomerService`, `ProductService`,
`RecurringInvoiceService`, `DocumentNumberService`, the invoicing repositories, or
the tenant-api controllers — for the money-handling core of the app.
**Fix (per `AGENTS.md` test patterns).**
- Service unit tests (`@ExtendWith(MockitoExtension.class)`): invoice draft→issue
  (numbering + VAT + snapshot), status-transition guards, tenant-scope enforcement, S2 above.
- Repository/isolation tests (`@DataJpaTest` + Testcontainers): `findByIdAndOrganizationId`
  returns nothing cross-org; line-table behavior (S4); id/version/auditing round-trip (P1).
- Controller tests (`@WebMvcTest` + `@MockitoBean`): validation (V1), 403 for RBAC (S1).
**Acceptance.** Meaningful coverage of issue/cancel/credit flows and tenant isolation; `./gradlew test` green.

---

## MEDIUM

### [ ] S3 — Harden tenant-context source
**Problem.** org id is read from the client `X-Organization-Id` header
(`TenantContextFilter.java:56`). It is safe today only because
`hasActiveMembership(userId, orgId)` is checked on **every** request before use.
Security depends on a header plus a per-request DB lookup.
**Fix.** Consider binding the selected org into the access token at login (or a
short-lived membership cache), so isolation doesn't hinge on a header. Add tests
for missing/blank header, non-member org, and non-tenant principal paths.
**Acceptance.** Documented, tested behavior for all three rejection paths; decision recorded.

### [ ] S4 — Scope line-table repositories to the tenant
**Problem.** `invoice_lines`, `credit_note_lines`, `recurring_invoice_lines` have no
`organization_id`; `findByInvoiceIdOrderByLineNumber` / `deleteByInvoiceId` (and
peers) trust the caller to have authorized the parent id first. Services *do* call
`findByIdAndOrganizationId` on the parent first, so no leak today — but it's one
missing call away from a cross-tenant read/delete.
**Files.** `persistence/.../invoicing/repository/{InvoiceLine,CreditNoteLine,RecurringInvoiceLine}Repository.java`.
**Fix.** Either add a join-based org filter, e.g.
`@Query("select l from InvoiceLineEntity l join InvoiceEntity i on i.id = l.invoiceId where l.invoiceId = :invoiceId and i.organizationId = :orgId order by l.lineNumber")`,
or codify the "parent must be tenant-verified first" invariant with a test that
proves the service path enforces it.
**Acceptance.** Cross-tenant line access is impossible or provably guarded by a test.

### [ ] S5 — Document/guard `TenantContext` ThreadLocal for async
**Problem.** `TenantContext` (`TenantContext.java:10`) is a `ThreadLocal`; any
`@Async`, reactive, or `parallelStream()` work in services silently loses tenant
scope.
**Fix.** Add a clear comment/invariant that tenant-scoped work stays on the request
thread; if async is introduced, propagate context explicitly (e.g. `TaskDecorator`).
**Acceptance.** Documented; no async tenant-scoped path exists without propagation.

### [ ] P3 — Stop returning entities from `list()`
**Problem.** `InvoiceService.list`, `CreditNoteService.list`, `CustomerService.list`,
`ProductService.list`, `RecurringInvoiceService.list` return `Page<…Entity>`,
leaking JPA entities past the service layer (violates design D1; risks lazy access
outside the tx). `get`/`create` correctly return documents.
**Fix.** Return `Page<…Document>` via `.map(this::toDocument)` (add list/summary
documents for Customer/Product, which lack them).
**Acceptance.** No service method returns a `*Entity`; controllers/DTOs unaffected downstream.

### [ ] C1 — Compute VAT once per save
**Problem.** `buildLines` runs `vatCalculator.calculate(...)` to produce line
totals, then `replaceLines`→`applyTotals` runs it **again** over the built lines
(Invoice `:135-141,:235-245`; CreditNote analogous). Wasteful and risks divergence.
**Files.** `invoicing/.../service/InvoiceService.java`, `CreditNoteService.java`.
**Fix.** Have `buildLines` return both the lines and the `VatDocumentTotals`; pass
the totals straight to `entity.applyTotals(...)`.
**Acceptance.** `calculate` invoked once per create/update; totals unchanged; test asserts single invocation.

### [ ] T1 — `AuthService` should use the injected `Clock`
**Problem.** `AuthService.java:76` uses bare `Instant.now()` for `updateLastLoginAt`,
while every other service uses `Instant.now(clock)`. `AuthService` doesn't inject `Clock`.
**Fix.** Inject `Clock` into `AuthService`; use `Instant.now(clock)`.
**Acceptance.** No bare `Instant.now()` in business services; a test with a fixed clock asserts the persisted `lastLoginAt`.

### [ ] T3 — Back JPA auditing with the `Clock` bean
**Problem.** `@CreatedDate`/`@LastModifiedDate` in `BaseEntity` are filled by Spring
Data's default `DateTimeProvider`, which reads the **system** clock — not the
injected `Clock`. So `created_at`/`updated_at` are not deterministic in tests even
though the rest of time is.
**Fix.** Register a `DateTimeProvider` bean backed by the `Clock` and point
`@EnableJpaAuditing(dateTimeProviderRef = …)` at it.
**Acceptance.** With a fixed `Clock`, a saved entity's `createdAt` equals the fixed instant in a test.

### [ ] V1 — Tighten request validation
**Problem/Fixes.**
- `InvoiceRequest.type` — add `@NotNull`.
- `LineRequest` — a line can have neither `productId` nor `description`; add a
  class-level `@AssertTrue` requiring at least one, and `@NotNull` on `quantity`,
  `unitPrice`, `vatCategory`.
- Cross-field date ordering: `dueDate >= supplyDate` (invoice), `endDate/nextRunDate >= startDate` (recurring).
**Files.** `tenant-api/.../dto/invoicing/{InvoiceRequest,LineRequest,RecurringInvoiceRequest}.java`.
**Acceptance.** Invalid payloads → 400 with the global error shape; tests cover each rule.

### [ ] M1 — Consider consolidating migration history **[CONFIRM]**
**Problem.** 18 migrations for an MVP schema, with `V11` adding core invoice fields
(`supply_date`, `exchange_rate`, `discount_total`, `po_number`, `reference`) to a
table created 4 versions earlier in `V7`, and `V18` adding `metadata JSONB` to
every table. Functionally correct (forward-only), but fragmented.
**Fix.** If **not yet deployed/shared**, consolidate V4–V18 into cohesive
per-table migrations. If already deployed anywhere, leave as-is (never edit applied
migrations — `AGENTS.md`).
**Acceptance.** Decision recorded; if consolidated, Flyway applies cleanly on an empty DB (integration test).

---

## LOW

- [ ] **P4** — Add `clearAutomatically = true` to `@Modifying` queries
  (`AuthUserRepository.updateLastLoginAt`, `RefreshTokenRepository.revokeAllForUser`
  + `deleteExpiredAndRevoked`; add `flushAutomatically` where dirty entities may precede the call).
- [ ] **C2** — Document-number first-issue insert race: two concurrent first-ever
  issues for one (org, type) both INSERT; unique constraint makes one fail
  ungracefully. Pre-seed sequence rows on org creation, or catch the unique
  violation and retry the locked read. (`DocumentNumberService.java:22-27`.)
- [ ] **C3** — Number format embeds `issueDate.getYear()` but the counter never
  resets per year. Confirm intent; if per-year numbering is required, reset
  `next_value` at year boundary (and key the sequence by year).
- [ ] **C4** — Remove dead `lineNumber` variable in `InvoiceService.buildLines`
  (incremented, never used — line index is used instead).
- [ ] **T2** — Move the `Clock` bean out of `AuthSecurityConfig` into a neutral
  shared `@Configuration` (it's general infrastructure used by `invoicing`/`vat`).
- [ ] **P5** — Optional: convert derived `deleteByInvoiceId`/`deleteByCreditNoteId`/
  `deleteByRecurringInvoiceId` (select-then-delete, N statements) to bulk
  `@Modifying` deletes (then add `clearAutomatically`).
- [ ] **P6** — `metadata` mapped as `String` + `columnDefinition="jsonb"` works but
  bypasses Hibernate JSON handling; consider `@JdbcTypeCode(SqlTypes.JSON)` if these
  columns get real use.
- [ ] **V3** — Add `@Pattern` for ISO formats: currency `[A-Z]{3}`, country
  `[A-Z]{2}`, TRN `\d{15}`; `@NotBlank` where mandatory.
- [ ] **C5** — `PageRequestFactory` hard-codes `Sort.by(DESC, "createdAt")`; safe
  today (all pageable entities extend `BaseEntity`) but will throw for any future
  entity without `createdAt`.
- [ ] **P7** — `AuditLogEntity` doesn't extend `BaseEntity` (intentional append-only,
  but inconsistent and repeats the P1 id-generation bug); align at least the id mapping.

---

## Appendix — The `Clock` vs `Instant` question (requested focus)

**Keep `Clock`. `Instant` cannot replace it — they play different roles.**

- `Instant` is a **value**: a single point on the timeline. `Instant.now()` reads
  the system clock **directly** and is not injectable/mockable.
- `Clock` is a **source** of "now" (plus a zone). You inject it so tests can pin
  time. `Instant.now(clock)` = "ask the injected clock for the current instant" —
  you still get an `Instant`, the `Clock` only controls where "now" comes from.

Time here **is** business logic (JWT expiry, refresh-token TTL, cleanup cutoffs,
VAT-rate effective dates, invoice issue dates), so deterministic time is required
for tests. The codebase already relies on this: `JwtTokenServiceTests` uses two
`Clock.fixed(...)` instances to create a token at `12:00` and prove it expired by
`12:16`. In production the bean is `Clock.systemUTC()` (`AuthSecurityConfig:35`),
so runtime behavior is identical to `Instant.now()` at zero cost.

Replacing `Instant.now(clock)` with bare `Instant.now()` would hardcode the system
clock and make all of the above untestable without `Thread.sleep` hacks — a
regression. The related action items are **T1** (one bare `Instant.now()` to fix),
**T2** (bean placement), and **T3** (make JPA auditing honor the same `Clock`).

---

## Done-definition
- All HIGH items resolved with tests; `./gradlew test` green.
- Security decisions (S1 role matrix, S3 context source) recorded in `AGENTS.md`.
- P1 verified by a uuidv7 round-trip test.
