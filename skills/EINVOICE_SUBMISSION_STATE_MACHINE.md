# Design: E-Invoice Submission State Machine (bulk upload → ASP clearance)

> Status: **Draft for implementation.** Audience: AI coding agents and reviewers.
> Scope: model the full lifecycle of an e-invoice submission — bulk upload (Excel/CSV)
> or manual create → **platform validation** → **ASP validation** → **submit to ASP** →
> **await ASP clearance** (Success / Non-Compliant) → notify user — as an auditable,
> idempotent, crash-safe **state machine**, with **one session per bulk upload** and
> **per-invoice** outcome tracking.
>
> Read first: [`AGENTS.md`](../AGENTS.md),
> [`TENANT_ISOLATION_AND_STATE_MACHINE_DESIGN.md`](./TENANT_ISOLATION_AND_STATE_MACHINE_DESIGN.md)
> (this is the concrete instance of its Part 2), [`RBAC_DESIGN.md`](./RBAC_DESIGN.md),
> [`INVOICING_MODULE_DESIGN.md`](./INVOICING_MODULE_DESIGN.md), and
> [`TECHNICAL_REVIEW_TASKS.md`](./TECHNICAL_REVIEW_TASKS.md). Where this conflicts with
> `AGENTS.md`, `AGENTS.md` wins. Keep **ASP integration concerns separate** from tenant
> business workflows (`AGENTS.md`) — hence the dedicated `asp` module below.

---

## 1. What already exists (build on it, don't duplicate)
- `common/domain/EinvoiceSubmissionStatus` = `PENDING, SUBMITTED, CLEARED, REJECTED, FAILED`.
- `common/domain/ValidationStatus` = `UNCHECKED, VALID, INVALID`.
- `persistence/invoicing/entity/EinvoiceSubmissionEntity` (table `einvoice_submissions`,
  migration `V13`, `V18` adds `request_payload jsonb`) — **per-document** record with
  `organizationId, documentType, documentId, aspId, status, ftaUuid, submittedAt,
  clearedAt, rejectedAt, rejectionReason, validationStatus, validationErrors,
  requestPayload, rawResponse`. Unique on `(organization_id, document_type, document_id)`.
- `persistence/invoicing/repository/EinvoiceSubmissionRepository`.

**Two gaps this design fills:** (1) there is **no batch/session** concept — the thing
the user uploads and tracks as one unit; (2) the per-document record can't distinguish
*platform* vs *ASP* validation, and its unique constraint blocks a retry/attempt history.

---

## 2. Architecture — two coordinated levels

- **Batch session** (NEW): one row per bulk upload / manual-create action. The
  **state-machine instance** carrying the rich phase state. The single handle the user
  tracks. Table `einvoice_submission_batches`.
- **Per-invoice submission** (EXISTING, extended): one `einvoice_submissions` row per
  invoice. Where individual validation errors and ASP outcomes live.

The batch state is a **rollup** of its invoices' states (§6). This is what lets one
session own the whole lifecycle while still tracking per-invoice outcomes.

```
Upload/Create ─► [BATCH: RECEIVED]
                     │ create N einvoice_submissions (PENDING)
                     ▼
              PLATFORM_VALIDATING ──any invalid──► PLATFORM_ACTION_REQUIRED ─┐
                     │ all valid                          ▲ user fixes+resubmit│
                     ▼                                     └───────────────────┘
                 ASP_VALIDATING ─────any invalid──► ASP_ACTION_REQUIRED ──────┘
                     │ all valid
                     ▼
                 SUBMITTING ──► AWAITING_CLEARANCE ──ASP responds──► COMPLETED (terminal)
                                                                     (cleared / non-compliant mix)
   FAILED reachable from every non-terminal (safety net). EXPIRED from hold/await states.
   CANCELLED from RECEIVED and *_ACTION_REQUIRED.
```

**Session boundary rule:** pre-submission failures loop **inside** the session
(`*_ACTION_REQUIRED → PLATFORM_VALIDATING`). Post-submission non-compliance **ends** the
session at `COMPLETED`; correcting `REJECTED` invoices creates a **new** batch that
references the originals (see §12 D1).

---

## 3. Enums (module `common/domain`)

### 3.1 New — `EinvoiceBatchStatus`
```java
public enum EinvoiceBatchStatus {
    RECEIVED,
    PLATFORM_VALIDATING,
    PLATFORM_ACTION_REQUIRED,   // hold: user correction needed
    ASP_VALIDATING,
    ASP_ACTION_REQUIRED,        // hold: user correction needed
    SUBMITTING,
    AWAITING_CLEARANCE,         // submitted; waiting for ASP response
    COMPLETED,                  // terminal (carries summary counts)
    FAILED,                     // terminal (technical) — safety net
    EXPIRED,                    // terminal (abandoned in a hold/await state)
    CANCELLED;                  // terminal (user cancelled)

    private static final Set<EinvoiceBatchStatus> TERMINAL =
            EnumSet.of(COMPLETED, FAILED, EXPIRED, CANCELLED);
    public boolean isTerminal() { return TERMINAL.contains(this); }
    public boolean isHold() { return this == PLATFORM_ACTION_REQUIRED || this == ASP_ACTION_REQUIRED; }
}
```

### 3.2 New — `SubmissionTrigger` (audit-trail cause)
```java
public enum SubmissionTrigger {
    UPLOAD, MANUAL, PLATFORM_VALIDATION, ASP_VALIDATION, SUBMISSION,
    ASP_CALLBACK, TIMEOUT_SCHEDULER, USER_ACTION, SAFETY_NET
}
```

### 3.3 New — `BatchSource`
```java
public enum BatchSource { UPLOAD, MANUAL }
```

### 3.4 Change — `EinvoiceSubmissionStatus` (add `EXCLUDED` + `isTerminal()`)
```java
public enum EinvoiceSubmissionStatus {
    PENDING, SUBMITTED, CLEARED, REJECTED, FAILED, EXCLUDED;   // + EXCLUDED
    private static final Set<EinvoiceSubmissionStatus> TERMINAL =
            EnumSet.of(CLEARED, REJECTED, FAILED, EXCLUDED);
    public boolean isTerminal() { return TERMINAL.contains(this); }
}
```
`ValidationStatus` unchanged (reused for both platform and ASP validation fields).

---

## 4. Transition table — single source of truth

`invoicing/submission/SubmissionTransitionConfig.java`:
```java
public final class SubmissionTransitionConfig {

    private static final Map<EinvoiceBatchStatus, Set<EinvoiceBatchStatus>> TRANSITIONS = Map.of(
        RECEIVED,                 EnumSet.of(PLATFORM_VALIDATING, CANCELLED, FAILED),
        PLATFORM_VALIDATING,      EnumSet.of(ASP_VALIDATING, PLATFORM_ACTION_REQUIRED, FAILED),
        PLATFORM_ACTION_REQUIRED, EnumSet.of(PLATFORM_VALIDATING, CANCELLED, EXPIRED, FAILED),
        ASP_VALIDATING,           EnumSet.of(SUBMITTING, ASP_ACTION_REQUIRED, FAILED),
        ASP_ACTION_REQUIRED,      EnumSet.of(PLATFORM_VALIDATING, CANCELLED, EXPIRED, FAILED),
        SUBMITTING,               EnumSet.of(AWAITING_CLEARANCE, FAILED),
        AWAITING_CLEARANCE,       EnumSet.of(COMPLETED, EXPIRED, FAILED)
    );

    private SubmissionTransitionConfig() {}

    public static boolean canTransition(EinvoiceBatchStatus from, EinvoiceBatchStatus to) {
        return TRANSITIONS.getOrDefault(from, Set.of()).contains(to);
    }
    public static Set<EinvoiceBatchStatus> allowedFrom(EinvoiceBatchStatus from) {
        return TRANSITIONS.getOrDefault(from, Set.of());
    }
}
```
Rules: **`FAILED` reachable from every non-terminal state** (safety net). Terminal states
have no outgoing edges. `ASP_ACTION_REQUIRED` re-enters at `PLATFORM_VALIDATING` (a fixed
invoice is re-run through *both* gates — simplest correct choice). **Pin with tests** (§11).

---

## 5. Entities & migrations

### 5.1 NEW entity — `EinvoiceSubmissionBatchEntity`
`persistence/invoicing/entity/EinvoiceSubmissionBatchEntity.java` (extends `BaseEntity`;
depends on review **P1** id-generation fix):
```java
@Getter @Setter(AccessLevel.PROTECTED)
@Entity @Table(name = "einvoice_submission_batches")
public class EinvoiceSubmissionBatchEntity extends BaseEntity {

    @Column(name = "organization_id", nullable = false) private UUID organizationId;
    @Column(name = "created_by_user_id") private UUID createdByUserId;

    @Enumerated(EnumType.STRING) @Column(name = "source", nullable = false, length = 16)
    private BatchSource source;
    @Column(name = "original_filename") private String originalFilename;
    @Column(name = "file_ref") private String fileRef;

    @Column(name = "idempotency_key", nullable = false, length = 128) private String idempotencyKey;
    @Column(name = "content_hash", length = 64) private String contentHash;

    @Enumerated(EnumType.STRING) @Column(name = "state", nullable = false, length = 32)
    private EinvoiceBatchStatus state;
    @Column(name = "state_reason") private String stateReason;

    // denormalized rollup counts (fast status without scanning children)
    @Column(name = "total_count", nullable = false) private int totalCount;
    @Column(name = "platform_valid_count", nullable = false) private int platformValidCount;
    @Column(name = "asp_valid_count", nullable = false) private int aspValidCount;
    @Column(name = "submitted_count", nullable = false) private int submittedCount;
    @Column(name = "cleared_count", nullable = false) private int clearedCount;
    @Column(name = "non_compliant_count", nullable = false) private int nonCompliantCount;
    @Column(name = "failed_count", nullable = false) private int failedCount;
    @Column(name = "excluded_count", nullable = false) private int excludedCount;

    @Column(name = "external_batch_reference", length = 128) private String externalBatchReference;
    @Column(name = "expires_at") private Instant expiresAt;

    // audit trail + breadcrumbs (see §7). Prefer typed JSON mapping over String:
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "data", columnDefinition = "jsonb")
    private SubmissionBatchData data = new SubmissionBatchData();

    protected EinvoiceSubmissionBatchEntity() {}
    public EinvoiceSubmissionBatchEntity(UUID organizationId, UUID createdByUserId,
            BatchSource source, String idempotencyKey, String contentHash) {
        this.organizationId = organizationId; this.createdByUserId = createdByUserId;
        this.source = source; this.idempotencyKey = idempotencyKey; this.contentHash = contentHash;
        this.state = EinvoiceBatchStatus.RECEIVED;
    }

    // domain methods (mutate in memory; caller persists — see §8)
    void setState(EinvoiceBatchStatus s) { this.state = s; }
    void setStateReason(String r) { this.stateReason = r; }
    void setExpiresAt(Instant at) { this.expiresAt = at; }
    void addTransition(EinvoiceBatchStatus from, EinvoiceBatchStatus to,
                       SubmissionTrigger trigger, String reason, UUID transitionId, Instant at) {
        data.transitions().add(new TransitionEntry(transitionId, from, to, trigger, reason, at));
    }
    void addTimelineEntry(String step, String status, Map<String,Object> ctx, Instant at) {
        data.timeline().add(new TimelineEntry(step, status, ctx, at));
    }
    void mergeTransitions(List<TransitionEntry> incoming) { /* dedup by transitionId, sort by at */ }
    public boolean isExpired(Instant now) { return expiresAt != null && !expiresAt.isAfter(now); }
    public boolean isTerminal() { return state.isTerminal(); }
    void applyCounts(SubmissionCounts c) { /* set the *_count fields */ }
}
```
`SubmissionBatchData` / `TransitionEntry` / `TimelineEntry` are plain records in the same
package (JSON-mapped). `TransitionEntry` carries a per-entry `UUID transitionId` so
`mergeTransitions` can dedup after optimistic-lock retries (isolation doc §2.3).

### 5.2 CHANGE entity — `EinvoiceSubmissionEntity` (add batch link + phase validation)
Add fields:
```java
@Column(name = "batch_id", nullable = false) private UUID batchId;
@Column(name = "submission_idempotency_key", nullable = false, length = 128)
private String submissionIdempotencyKey;                         // sent to ASP (§9 #4)
@Enumerated(EnumType.STRING) @Column(name = "platform_validation_status", nullable = false, length = 16)
private ValidationStatus platformValidationStatus = ValidationStatus.UNCHECKED;
@Enumerated(EnumType.STRING) @Column(name = "asp_validation_status", nullable = false, length = 16)
private ValidationStatus aspValidationStatus = ValidationStatus.UNCHECKED;
@Column(name = "asp_event_id", length = 128) private String aspEventId;   // callback dedup (§9 #5)
```
Keep the existing `validationStatus` for backward-compat or drop it in favour of the two
split fields (recommend: **drop** `validation_status`, migrate its meaning into the two).
Extend the constructor to accept `batchId` + `submissionIdempotencyKey`. Add domain
transition helpers: `markPlatformValid()/markPlatformInvalid(errors)`,
`markAspValid()/markAspInvalid(errors)`, `markSubmitted(idemKey, at)`,
`markCleared(ftaUuid, at, raw)`, `markRejected(reason, at, raw)`, `markFailed(reason)`,
`markExcluded()`, each guarding the current `status`.

### 5.3 Migrations (Flyway, forward-only; next number after V18)
**`V19__create_einvoice_submission_batches.sql`**
```sql
CREATE TABLE einvoice_submission_batches (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    source VARCHAR(16) NOT NULL,
    original_filename VARCHAR(255),
    file_ref TEXT,
    idempotency_key VARCHAR(128) NOT NULL,
    content_hash VARCHAR(64),
    state VARCHAR(32) NOT NULL DEFAULT 'RECEIVED',
    state_reason TEXT,
    total_count INT NOT NULL DEFAULT 0,
    platform_valid_count INT NOT NULL DEFAULT 0,
    asp_valid_count INT NOT NULL DEFAULT 0,
    submitted_count INT NOT NULL DEFAULT 0,
    cleared_count INT NOT NULL DEFAULT 0,
    non_compliant_count INT NOT NULL DEFAULT 0,
    failed_count INT NOT NULL DEFAULT 0,
    excluded_count INT NOT NULL DEFAULT 0,
    external_batch_reference VARCHAR(128),
    expires_at TIMESTAMPTZ,
    data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version BIGINT NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX idx_einvoice_batches_org_idem_unique
    ON einvoice_submission_batches(organization_id, idempotency_key);
CREATE INDEX idx_einvoice_batches_organization_id ON einvoice_submission_batches(organization_id);
CREATE INDEX idx_einvoice_batches_state ON einvoice_submission_batches(state);
CREATE INDEX idx_einvoice_batches_expiry
    ON einvoice_submission_batches(expires_at) WHERE expires_at IS NOT NULL;
```
**`V20__extend_einvoice_submissions_for_batches.sql`**
```sql
ALTER TABLE einvoice_submissions
    ADD COLUMN batch_id UUID REFERENCES einvoice_submission_batches(id) ON DELETE CASCADE,
    ADD COLUMN submission_idempotency_key VARCHAR(128),
    ADD COLUMN platform_validation_status VARCHAR(16) NOT NULL DEFAULT 'UNCHECKED',
    ADD COLUMN asp_validation_status VARCHAR(16) NOT NULL DEFAULT 'UNCHECKED',
    ADD COLUMN asp_event_id VARCHAR(128);

-- allow retry/attempt history: a document may be submitted in more than one batch over time.
DROP INDEX IF EXISTS idx_einvoice_submissions_document_latest_unique;
CREATE UNIQUE INDEX idx_einvoice_submissions_batch_document_unique
    ON einvoice_submissions(batch_id, document_id);            -- no dup invoice within a batch
CREATE UNIQUE INDEX idx_einvoice_submissions_idem_unique
    ON einvoice_submissions(submission_idempotency_key) WHERE submission_idempotency_key IS NOT NULL;
CREATE INDEX idx_einvoice_submissions_batch_id ON einvoice_submissions(batch_id);
-- optional: enforce "one non-terminal submission per document" if desired (partial unique).
```
> After these migrations `batch_id`/`submission_idempotency_key` are nullable at the DDL
> level for the ALTER; make them `NOT NULL` in a follow-up once backfilled, or create the
> table fresh if `einvoice_submissions` has no production rows yet.

### 5.4 Repositories (`persistence/invoicing/repository`)
```java
public interface EinvoiceSubmissionBatchRepository extends JpaRepository<EinvoiceSubmissionBatchEntity, UUID> {
    Optional<EinvoiceSubmissionBatchEntity> findByIdAndOrganizationId(UUID id, UUID organizationId);
    Optional<EinvoiceSubmissionBatchEntity> findByOrganizationIdAndIdempotencyKey(UUID organizationId, String idempotencyKey);
    Page<EinvoiceSubmissionBatchEntity> findByOrganizationId(UUID organizationId, Pageable pageable);
    List<EinvoiceSubmissionBatchEntity> findByStateInAndExpiresAtBefore(Collection<EinvoiceBatchStatus> states, Instant cutoff);
}
public interface EinvoiceSubmissionRepository extends JpaRepository<EinvoiceSubmissionEntity, UUID> {
    List<EinvoiceSubmissionEntity> findByBatchId(UUID batchId);                    // for rollup + processing
    Optional<EinvoiceSubmissionEntity> findBySubmissionIdempotencyKey(String key); // callback resolve
    Optional<EinvoiceSubmissionEntity> findByIdAndOrganizationId(UUID id, UUID organizationId); // L4
}
```
**Tenant scope (review S4):** `findByBatchId` is not org-scoped; callers must first load the
batch via `findByIdAndOrganizationId`. Prefer a join-scoped query if used on a client path.

---

## 6. The rollup rule (how the batch advances)

`SubmissionOrchestrationService.advanceBatchAfterPhase(batch, phase)` recomputes counts
from the batch's submissions and picks the next state, then calls the state machine:

| Phase just finished | Condition | Target state |
|---|---|---|
| PLATFORM_VALIDATING | `platform_invalid == 0` (of non-excluded) | `ASP_VALIDATING` |
| | else | `PLATFORM_ACTION_REQUIRED` |
| ASP_VALIDATING | `asp_invalid == 0` | `SUBMITTING` |
| | else | `ASP_ACTION_REQUIRED` |
| clearance | all non-excluded submissions terminal (`CLEARED/REJECTED/FAILED`) | `COMPLETED` |

**All-or-nothing gate (recommended) [CONFIRM D2]:** the batch advances to the ASP only
when *every* non-excluded invoice is valid. `excludeAndProceed(...)` lets the user drop
flagged invoices (`EXCLUDED`) so the valid subset proceeds. Alternative (partial
auto-advance) is more throughput but a more complex partially-advanced batch.

---

## 7. Audit trail (embedded JSONB, isolation doc §2.3)

`data` JSONB holds `transitions[]` (authoritative audit) and `timeline[]` (breadcrumbs):
```jsonc
{ "transitions": [ { "transitionId":"uuid","from":"PLATFORM_VALIDATING","to":"ASP_VALIDATING",
                     "trigger":"PLATFORM_VALIDATION","reason":"all 42 invoices valid","at":"..." } ],
  "timeline":    [ { "step":"asp_submit_retry","status":"RETRYING",
                     "ctx":{"attempt":2,"remainingBudgetMs":41000},"at":"..." } ] }
```
`mergeTransitions` dedups by `transitionId` and re-sorts — lets the callback path and the
timeout scheduler both append after an optimistic-lock retry without clobbering.

---

## 8. State machine service — pure validator, caller owns persistence

`invoicing/submission/SubmissionStateMachine.java` (stateless):
```java
@Service
public class SubmissionStateMachine {
    private final Clock clock;
    public SubmissionStateMachine(Clock clock) { this.clock = clock; }

    /** Validates + records the transition in memory. Does NOT save. */
    public EinvoiceSubmissionBatchEntity transition(EinvoiceSubmissionBatchEntity batch,
            EinvoiceBatchStatus target, SubmissionTrigger trigger, String reason) {
        EinvoiceBatchStatus from = batch.getState();
        if (from == target) return batch;                                  // no-op (idempotent)
        if (!SubmissionTransitionConfig.canTransition(from, target)) {
            throw new InvalidSubmissionTransitionException(batch.getId(), from, target);
        }
        Instant now = Instant.now(clock);
        batch.addTransition(from, target, trigger, reason, UUID.randomUUID(), now); // see note
        batch.setState(target);
        batch.setStateReason(reason);
        if (target.isTerminal()) batch.setExpiresAt(null);                 // stop timeout scans
        return batch;
    }
    public boolean canTransition(EinvoiceSubmissionBatchEntity b, EinvoiceBatchStatus t) {
        return SubmissionTransitionConfig.canTransition(b.getState(), t);
    }
    public Set<EinvoiceBatchStatus> allowedTransitions(EinvoiceSubmissionBatchEntity b) {
        return SubmissionTransitionConfig.allowedFrom(b.getState());
    }
}
```
`transition()` **mutates and does not save** — the orchestration service commits the batch
+ its invoice mutations in **one** transaction (isolation doc §2.6). `InvalidSubmission
TransitionException` carries `(batchId, from, target)`. (Note: `UUID.randomUUID()` — if
scripts can't use randomness in your runtime, pass the id in; here it's plain service code,
so `randomUUID` is fine.)

---

## 9. Idempotency — six boundaries (each explicit)

| # | Boundary | Mechanism |
|---|---|---|
| 1 | **Upload / create** | Client `Idempotency-Key` header (fallback: `content_hash` of the payload). `createFromUpload/Manual` first `findByOrganizationIdAndIdempotencyKey` → return existing batch if present. Unique `(organization_id, idempotency_key)` is the hard backstop. |
| 2 | **Invoice dedup in batch** | Unique `(batch_id, document_id)`; parser rejects/merges duplicate rows before insert. |
| 3 | **Async phase jobs** | Every phase method is a state-guarded transition under `@Version`. `runPlatformValidation` no-ops unless `state == PLATFORM_VALIDATING`; a re-run finds the batch already advanced. |
| 4 | **ASP submit** | `submission_idempotency_key` generated + persisted **before** the ASP call and passed to `AspClient.submit`. Never submit an invoice not in `(status=PENDING, asp_validation=VALID)`. On retry, ASP's "already received" reconciles to the stored `ftaUuid`/reference. |
| 5 | **ASP response / callback** | Dedup by `asp_event_id`; guard ladder in `AspCallbackService` (batch/invoice not found → ignore; already terminal → ignore replay; illegal transition → ignore out-of-order). |
| 6 | **Concurrent writers** | `@Version` on batch AND submission; on conflict reload → re-check `isTerminal`/`canTransition` → retry or ignore; `mergeTransitions` preserves both writers' audit entries. |

**Internal vs external asymmetry (isolation doc §2.9):** internal callers get exceptions on
illegal transitions (bugs); ASP callbacks *ignore* them (distributed messiness).

---

## 10. Services, ASP port, controllers — the full call map

### 10.1 Orchestration — `invoicing/submission/SubmissionOrchestrationService`
Owns transaction boundaries; calls `SubmissionStateMachine` + repositories + `AspClient`.
```java
@Service
public class SubmissionOrchestrationService {
    // deps: batchRepo, submissionRepo, invoiceRepository, platformValidator, aspRulesValidator,
    //       aspClient, stateMachine, bulkUploadParser, applicationEventPublisher, clock,
    //       SubmissionProperties (TTLs, batch-size)

    @Transactional
    public SubmissionBatchDocument createFromManual(UUID orgId, UUID userId,
            CreateSubmissionBatchCommand cmd, String idempotencyKey);      // idempotency #1,#2
    @Transactional
    public SubmissionBatchDocument createFromUpload(UUID orgId, UUID userId,
            UploadRef upload, String idempotencyKey);                      // parse → drafts → submissions

    @Transactional public void runPlatformValidation(UUID batchId);        // phase; #3
    @Transactional public void runAspValidation(UUID batchId);             // phase; #3
    @Transactional public void submitToAsp(UUID batchId);                  // phase; #4

    @Transactional public SubmissionBatchDocument resubmit(UUID orgId, UUID batchId);        // from *_ACTION_REQUIRED
    @Transactional public SubmissionBatchDocument excludeAndProceed(UUID orgId, UUID batchId, Set<UUID> submissionIds);
    @Transactional public SubmissionBatchDocument cancel(UUID orgId, UUID batchId);          // USER_ACTION
    @Transactional(readOnly = true) public SubmissionBatchDocument get(UUID orgId, UUID batchId);
    @Transactional(readOnly = true) public Page<SubmissionBatchDocument> list(UUID orgId, int page, int size);

    // internal: recompute counts + choose next state + stateMachine.transition(...)
    private void advanceBatchAfterPhase(EinvoiceSubmissionBatchEntity batch, Phase phase);
    private SubmissionCounts recomputeCounts(UUID batchId);
}
```
Phase methods process invoices in **per-invoice** units (one bad row ≠ dead batch — wrap
each in its own inner transaction via a helper bean, or collect failures and mark those
submissions `FAILED`), then `advanceBatchAfterPhase`. Seed `expires_at` when entering a
hold/await state (`SubmissionProperties` TTLs).

### 10.2 Validators (`invoicing/submission`)
```java
@Service class PlatformInvoiceValidator {   // our rules: totals, TRN format, required fields, VAT math
    List<ValidationError> validate(InvoiceEntity invoice, List<InvoiceLineEntity> lines);
}
@Service class AspRulesValidator {           // ASP pre-checks (may call AspClient.validate)
    List<ValidationError> validate(AspDocument document);
}
```
`ValidationError` = record `(String code, String field, String message)`, serialized into
`einvoice_submissions.validation_errors` JSONB keyed by phase.

### 10.3 ASP port — NEW module `asp` (keep ASP concerns separate — `AGENTS.md`)
`asp/.../client/AspClient.java` (port; a `StubAspClient` until the real ASP exists):
```java
public interface AspClient {
    AspValidationResult validate(AspDocument document);                 // optional pre-submission check
    AspSubmissionAck submit(AspSubmission submission);                  // MUST honor submission.idempotencyKey()
    AspClearanceResult poll(String externalReference);                  // if polling model
}
public record AspSubmission(UUID organizationId, String idempotencyKey, AspDocument document) {}
public record AspSubmissionAck(String externalReference, String ftaUuid, AspAckStatus status) {}
public record AspClearanceResult(String externalReference, String ftaUuid,
                                 AspClearanceStatus status, String reason, String rawResponse) {}
// AspAckStatus { ACCEPTED_FOR_PROCESSING, DUPLICATE, REJECTED }
// AspClearanceStatus { CLEARED, NON_COMPLIANT, PENDING }
```
`settings.gradle`: `include 'asp'`. `invoicing` depends on `asp`.

### 10.4 Callback ingestion (S2S, NOT the tenant JWT)
`asp` (or `tenant-api` with its own security) — a dedicated endpoint authenticated by the
**ASP credential**, not a tenant token:
```java
@RestController @RequestMapping("/api/asp/callbacks")
class AspCallbackController {                       // secured by S2S filter (API key / mTLS), permitAll to JWT chain
    @PostMapping ResponseEntity<Void> onClearance(@Valid @RequestBody AspCallbackPayload payload);
}
@Service class AspCallbackService {
    @Transactional public void process(AspCallbackPayload payload);     // guard ladder + idempotency #5
    // resolve submission by submissionIdempotencyKey/externalReference → verify org →
    // dedup asp_event_id → if submission.status terminal: ignore → mark CLEARED/REJECTED →
    // recompute batch counts → if all terminal: stateMachine.transition(COMPLETED) → publish event
}
```
Add the callback path to the security config `permitAll` for the JWT chain and gate it with
a separate S2S auth filter; add it to `TenantContextFilter.shouldNotFilter`. If the ASP is
**poll-based** instead, replace the callback with a `SubmissionClearancePoller` `@Scheduled`
job that calls `AspClient.poll` for `AWAITING_CLEARANCE` batches.

### 10.5 Timeout scheduler (`invoicing/submission`)
```java
@Component class SubmissionTimeoutScheduler {
    @Scheduled(cron = "${app.einvoice.timeout-cron:0 */5 * * * *}", zone = "UTC")
    public void sweep();   // distributed-lock guarded; findByStateInAndExpiresAtBefore(HOLD+AWAITING, now)
                           // per-batch tx: hold states → EXPIRED; AWAITING_CLEARANCE overdue → poll or FAILED
}
```
Enable scheduling app-wide (`@EnableScheduling` — confirm it exists for `RefreshTokenCleanupJob`).

### 10.6 Controllers & DTOs (`tenant-api`)
`EinvoiceSubmissionController` (`/api/einvoice/batches`), thin, RBAC-gated, org from
`TenantRequestContext`:
```java
POST   /api/einvoice/batches/upload     (multipart + Idempotency-Key)  @PreAuthorize("hasAuthority('einvoice:upload')")
POST   /api/einvoice/batches            (manual: invoice ids/payload)  @PreAuthorize("hasAuthority('einvoice:upload')")
POST   /api/einvoice/batches/{id}/resubmit                            @PreAuthorize("hasAuthority('einvoice:submit')")
POST   /api/einvoice/batches/{id}/exclude                            @PreAuthorize("hasAuthority('einvoice:submit')")
POST   /api/einvoice/batches/{id}/cancel                             @PreAuthorize("hasAuthority('einvoice:submit')")
GET    /api/einvoice/batches            (list)                        @PreAuthorize("hasAuthority('einvoice:read')")
GET    /api/einvoice/batches/{id}       (status + per-invoice detail) @PreAuthorize("hasAuthority('einvoice:read')")
```
DTOs in `tenant-api/dto/einvoice/`: `SubmissionBatchResponse` (state, counts, timeline),
`SubmissionItemResponse` (per-invoice status + validation errors), `CreateSubmissionBatchRequest`,
`ExcludeItemsRequest`. Services return `SubmissionBatchDocument`/`SubmissionItemDocument`
(in `invoicing/submission/document/`) — never entities (review P3).

---

## 11. Testing
- **Transition table pinned:** `canTransition` exact allowed-sets per state; representative
  rejections (`RECEIVED → SUBMITTING` rejected; terminal has no edges); `FAILED` reachable
  from every non-terminal.
- **State machine:** transition appends audit with correct from/to/trigger; terminal nulls
  `expires_at`; illegal internal transition throws.
- **Rollup:** all-valid → advance; one invalid → `*_ACTION_REQUIRED`; `excludeAndProceed`
  advances the valid subset; all-terminal → `COMPLETED` with correct counts.
- **Idempotency:** duplicate upload (same key) returns the same batch; re-run phase job is a
  no-op; double `submitToAsp` doesn't double-call ASP; replayed callback ignored;
  out-of-order callback ignored; optimistic-lock conflict merges audit + retries.
- **Isolation (`@DataJpaTest` + Testcontainers):** cross-org batch/submission access denied;
  `batch_id` scoping.
- **Controllers (`@WebMvcTest`):** RBAC 403s; validation; multipart upload.
- **ASP:** `StubAspClient` drives CLEARED / NON_COMPLIANT / DUPLICATE paths.

---

## 12. Phased task plan
### Phase 0 — prerequisites
- [ ] E0.1 Apply review **P1** (BaseEntity id generation) — new entities depend on it.
- [ ] E0.2 Confirm `@EnableScheduling` is active (used by `RefreshTokenCleanupJob`).

### Phase 1 — model & persistence
- [ ] E1.1 Enums (§3): `EinvoiceBatchStatus`, `SubmissionTrigger`, `BatchSource`; extend `EinvoiceSubmissionStatus`.
- [ ] E1.2 `V19` + `V20` migrations (§5.3).
- [ ] E1.3 `EinvoiceSubmissionBatchEntity` (+ `SubmissionBatchData`/`TransitionEntry`/`TimelineEntry`) and extend `EinvoiceSubmissionEntity`.
- [ ] E1.4 Repositories (§5.4) with tenant-scoped finders.

### Phase 2 — state machine core
- [ ] E2.1 `SubmissionTransitionConfig` + `SubmissionStateMachine` + `InvalidSubmissionTransitionException`.
- [ ] E2.2 Table-pinning + state-machine tests (§11).

### Phase 3 — orchestration (no real ASP yet)
- [ ] E3.1 `BulkUploadParser` (Excel/CSV → line commands) + dedup (#2).
- [ ] E3.2 `SubmissionOrchestrationService.createFromUpload/Manual` (idempotency #1) → creates batch + submissions, transitions to `PLATFORM_VALIDATING`.
- [ ] E3.3 `PlatformInvoiceValidator` + `runPlatformValidation` + rollup + `advanceBatchAfterPhase`.
- [ ] E3.4 `resubmit`, `excludeAndProceed`, `cancel`.
- [ ] E3.5 `SubmissionTimeoutScheduler` (hold-state expiry).

### Phase 4 — ASP integration
- [ ] E4.1 `asp` module: `AspClient` port + records + `StubAspClient`; `settings.gradle` include.
- [ ] E4.2 `AspRulesValidator` + `runAspValidation`.
- [ ] E4.3 `submitToAsp` (idempotency #4) → `AWAITING_CLEARANCE`.
- [ ] E4.4 Clearance intake: `AspCallbackController`+`AspCallbackService` (guard ladder #5) **or** `SubmissionClearancePoller`; S2S auth; add to `shouldNotFilter`/`permitAll`.
- [ ] E4.5 `COMPLETED` rollup + outcome event.

### Phase 5 — API, RBAC, mapping
- [ ] E5.1 `EinvoiceSubmissionController` + DTOs + documents (no entity leaks).
- [ ] E5.2 RBAC: add `einvoice:upload`, `einvoice:submit`, `einvoice:read` to the catalog + role matrices (RBAC §4.1/§5.1); `@PreAuthorize` on service methods.
- [ ] E5.3 `InvoiceStatus` ↔ clearance mapping (D5): ASP `CLEARED` → invoice `ISSUED` (or add `InvoiceStatus.CLEARED`), `REJECTED` → stays `DRAFT`.
- [ ] E5.4 End-to-end integration test in `app`: upload → validate → (fix loop) → submit → callback → COMPLETED.

---

## 13. Composition with the other docs
- **Tenant isolation:** `einvoice_submission_batches` + `einvoice_submissions` carry
  `organization_id`; all client paths scoped via `findByIdAndOrganizationId` (L3/L4). The
  callback path is S2S and must **verify the resolved batch's `organization_id`** against
  the authenticated ASP credential's org binding (isolation doc Appendix A).
- **RBAC (L5):** `einvoice:upload/submit/read` gate the triggers; area = TENANT for the
  user-facing endpoints; the callback endpoint is outside the tenant JWT chain.
- **State machine ⟂ RBAC:** permission decides *who may trigger*; `SubmissionTransitionConfig`
  decides *whether the transition is legal* — both required (RBAC §6.3).

## 14. Open decisions [CONFIRM]
- **D1** Non-compliant corrections → **new batch referencing originals** (recommended) vs loop in-session.
- **D2** **All-or-nothing** gate + "exclude & proceed" (recommended) vs partial auto-advance.
- **D3** ASP offers **batch** submit/validate vs per-document (affects `external_batch_reference` and submit fan-out).
- **D4** Clearance delivery: **callback/webhook** vs **polling** (affects §10.4).
- **D5** `InvoiceStatus` ↔ clearance mapping (map `CLEARED`→`ISSUED`, or add `InvoiceStatus.CLEARED`).
- **D6** Drop legacy `einvoice_submissions.validation_status` in favour of the split fields (recommended) vs keep for compat.

Proceed with the recommended default for each unless a reviewer objects.
