# Engineering baseline

The canonical practices for every target in the repository. Apply the `java` and
`test` specializations afterward; they add language, framework, and level
detail, they never relax a rule stated here.

Nothing in this document names a specific project. Where a rule needs a project
value — a protected branch, a commit subject, a gate roster — it refers to
`project-config`, which owns it.

## Contents

- Authority and scope
- Design, simplicity and reuse
- Naming and readability
- Boundary validation and defensive behavior
- Resource, concurrency and lifecycle ownership
- Security, privacy and supply chain
- Observability and operational behavior
- Performance and capacity
- API and contract compatibility
- Data and persistence
- Configuration and feature flags
- Review and code hygiene
- TDD and commits

## Authority and scope

- Respect caller source authority, repository instructions, and confirmed human
  decisions. Do not silently resolve same-authority conflicts or substitute
  missing guidance with a plausible invention.
- Keep work inside the approved component, behavior, and file scope. Preserve
  unrelated developer changes; do not opportunistically clean nearby code.
- Prefer a narrow change with complete behavior over a broad refactor with
  partial evidence. Surface an unavoidable scope expansion for explicit
  approval; never infer one.
- Do not change generated artifacts, build output, or lockfiles except when the
  approved source or dependency change requires it. Keep generated and
  hand-written ownership explicit.
- A rule the repository states about itself outranks this baseline. When they
  conflict at the same authority, report both and stop.

## Design, simplicity and reuse

- Start from the existing architecture and the nearest maintained analogous
  flow. Preserve module ownership, dependency direction, and public contracts
  unless authoritative requirements demand a change.
- Establish the simplest approach that solves the complete problem. Compare it
  against each more complex alternative and require a concrete correctness,
  maintainability, security, or performance benefit before adding a class,
  layer, abstraction, dependency, process, or infrastructure component.
- Reuse or minimally extend an equivalent existing service, component, utility,
  adapter, constant, or extension point before creating another. Compare
  responsibility, contract, lifecycle, ownership, and change risk — similar
  naming alone is not reuse evidence.
- Apply SOLID to improve cohesion and substitutability, not to maximize
  indirection. Keep one clear owner for each business rule, state transition,
  integration, and side effect.
- Separate transport concerns from domain behavior and from external adapters.
  Keep dependencies pointing toward stable contracts; prevent cycles.
- Do not introduce a library when the current stack solves the problem safely
  and maintainably. When one is justified, assess maintenance, compatibility,
  security, license, transitive weight, operational cost, and rollback.
- An abstraction with exactly one implementation and no second caller in sight
  is speculation. Write the concrete thing; extract when the second case arrives
  and shows you what varies.

## Naming and readability

- Every variable, constant, type, function, and method name states the value,
  responsibility, or behavior it represents. Avoid cryptic abbreviations, vague
  placeholders, misleading names, and names that require reading the
  implementation to infer intent. Use domain terminology consistently.
- Keep code readable top to bottom. Avoid deep nesting, dense multi-purpose
  expressions, clever or implicit control flow, and unnecessary indirection.
  Prefer an early return over a nested conditional.
- Decompose around coherent responsibilities when it improves clarity. Do not
  split a method merely to hit a line count, and do not add a pattern to appear
  compliant with one.
- Use simple if/else over nested ternaries. Extract a magic number or string to
  a named constant at the narrowest owner that needs it.
- Match the surrounding formatting, ordering, and public API conventions. A
  change that reformats untouched code buries the actual diff.

## Boundary validation and defensive behavior

- Treat data from users, networks, storage, messages, files, URLs, third-party
  SDKs, deserialization, and older application versions as untrusted until its
  type, shape, bounds, encoding, authorization, and required fields are
  validated at the narrowest owning boundary.
- Keep validated internal paths strongly typed and non-null. Represent expected
  absence explicitly; never fabricate an empty string, a zero, an empty object,
  or a permissive default in place of invalid required data.
- Validate monetary values exactly. Use integer minor units or the established
  exact decimal type; never binary floating point for money.
- Translate infrastructure and third-party failures once into a stable domain
  error contract. Preserve the primary failure and safe diagnostic context
  without exposing sensitive input.
- Catch only what the current boundary can handle, translate, or enrich. Never
  use exceptions as ordinary control flow, swallow an actionable failure, or
  catch a process-fatal category indiscriminately.
- Define success, partial success, retryable failure, terminal failure,
  cancellation, timeout, and unknown outcome wherever they lead to different
  recovery behavior. "Unknown" is a real outcome for a remote call and needs its
  own handling, not a default to failure.
- Validate authorization and ownership on the authoritative side of every
  operation. A UI state, a client-supplied role, or a hidden action is not an
  access control.

## Resource, concurrency and lifecycle ownership

- Every acquired resource and registered lifecycle action needs one explicit
  owner and deterministic release on success, failure, cancellation, and early
  exit: streams, database and HTTP handles, temporary files, subscriptions,
  listeners, timers, threads and executors, locks, and native sessions.
- Prefer the language's structured cleanup mechanism. Never rely on garbage
  collection, finalization, or process exit for correctness.
- Preserve the primary failure when cleanup also fails; retain the secondary
  evidence without masking the original.
- Make concurrency assumptions explicit. Protect shared state with a
  transactional, locking, immutable, or serialized mechanism — never with
  timing or process-local hope. Assume more than one instance is running.
- Externally triggered and retried effects must be idempotent or guarded by a
  durable state transition. Define behavior for duplicate, concurrent,
  out-of-order, and replayed requests.
- Prefer an existing client-generated, retry-stable identifier already in the
  request — `requestId`, `orderId`, a domain key — as the idempotency identity.
  Introduce a dedicated idempotency header only when no suitable identifier
  exists. Either way, bind it to the authenticated principal, the operation, and
  the canonical payload; enforce it durably across instances; define retention;
  and reject conflicting reuse. A server-generated or retry-varying value is not
  an idempotency key.
- For timeouts and partial failure, assume the remote side may have committed.
  Define reconciliation, compensation, or a safe status lookup before retrying
  anything irreversible.
- Bound retries, backoff, queues, caches, batches, and parallelism. Include
  cancellation, deadline, and overload behavior. Never create an unbounded
  recovery loop.

## Security, privacy and supply chain

- Never place a secret, token, private key, signing material, or real personal
  data in source, tests, fixtures, snapshots, logs, telemetry, prompts, command
  arguments, generated artifacts, or commit messages. Test values are obviously
  fake.
- Use the repository's approved credential, encryption, hashing, signing, and
  key-management abstraction. Do not invent a cryptographic primitive or bypass
  the owning security boundary.
- Apply least privilege to identities, permissions, data access, filesystem
  paths, network destinations, and external writes. Fail closed when an
  authorization prerequisite is missing or unverifiable.
- Minimize collected, transmitted, cached, and persisted personal or financial
  data. Define purpose, retention, deletion, backup, export, and redaction.
- Logs and telemetry carry structured, bounded, privacy-safe context. Never log
  a raw sensitive request or response; centralize redaction at the boundary.
- Validate paths, URLs, hosts, redirects, archive entries, and command arguments
  before use. Reject traversal, unexpected schemes or hosts, unsafe shell
  interpolation, and over-broad deletion.
- Pin dependency versions through the build's lock mechanism. Review a new or
  upgraded dependency for provenance, maintenance, license, known
  vulnerabilities, transitive behavior, and operational impact.
- Keep production security controls enabled in release configuration. Debug,
  test, mock, trust-all, and authentication-bypass paths are structurally
  excluded from production artifacts, not merely switched off by a property.
- Map material changes to the applicable OWASP guidance. A standards review
  complements the configured scanners; it does not replace them, and a scanner
  the project has disabled does not transfer its coverage to this review.

## Observability and operational behavior

- Observable flows record privacy-safe start context, successful business
  outcome, and every material failure path through the repository's established
  logger or telemetry facade. Avoid duplicating the same failure at every layer:
  the owning boundary records the actionable context, higher layers add
  correlation only when it changes diagnosis.
- Money movement, identity, authorization, key and crypto operations, and
  lifecycle transitions need an auditable correlation identifier and a recorded
  outcome.
- Distinguish developer diagnostics from production telemetry. Remove unbounded
  debug logging; keep log volume and cardinality controlled.
- Metrics, traces, and logs must make a timeout, retry, rejection, partial
  failure, or dependency failure diagnosable without sensitive payloads.
- A release-affecting change defines the signal that will show success or
  regression after delivery, and who responds when it degrades.
- Read a log economically. Prefer a health check, an exit code, a status
  command, or a targeted assertion over opening a log at all. When a log is the
  only source, filter at the source — a line range, `tail`, or a `grep` whose
  pattern names what is sought. Never read a log whole or stream one into the
  transcript: a local configuration emits thousands of lines a minute, and an
  unfiltered read buries the evidence it was meant to surface.
- Raising log verbosity is a last resort. When the level lives in a tracked
  file, treat the change as temporary and approved: record the original, raise
  the narrowest logger that covers the question rather than the root logger,
  capture the filtered evidence, restore the file, and verify with a diff that
  nothing remains. A verbosity change left behind ships noise and reappears in
  an unrelated diff later.

## Performance and capacity

- Optimize from evidence, but treat obviously unbounded work as a defect
  regardless of measurement. Measure the affected path in a representative
  configuration and record the environment and baseline.
- Establish owner-approved budgets for latency, startup, throughput, memory,
  CPU, connection use, and payload size where they matter. Do not invent one
  universal threshold.
- Avoid duplicate I/O, repeated scans, serial independent work, N+1 queries,
  unnecessary remote calls, and reprocessing of immutable inputs. Reuse
  fingerprinted results; parallelize bounded independent read-only work when
  ownership permits.
- Bound payloads, pagination, collection sizes, caches, queues, thread pools,
  and concurrency. Consider worst-case input and dependency degradation.
- Do not trade correctness, security, or maintainability for an unmeasured
  micro-optimization. Complexity added purely for performance carries
  before-and-after evidence or it comes back out.

## API and contract compatibility

- A published HTTP, event, or client-facing contract changes only through an
  approved, versioned transition. Removing a field, narrowing a type, tightening
  validation, changing a status code, or altering an enum's meaning is breaking
  even when the compiler is silent.
- Additive-first is the default: add the new field or endpoint, migrate callers,
  then remove the old one in a separate approved change.
- Persisted data, stored events, and in-flight messages must be readable by both
  the previous and the new version during a rolling deployment. State the
  compatibility window explicitly.
- Error responses are part of the contract. Keep the code, shape, and semantics
  stable; a new failure mode gets a new code rather than overloading an existing
  one.
- Document the contract where the project already documents contracts — an
  OpenAPI document, a schema registry, or the endpoint's own annotations — and
  keep that document in the same change as the behavior.

## Data and persistence

- Schema changes go through the project's migration mechanism, never through
  runtime DDL or an application-managed schema update.
- A migration script is safely re-executable and supports rolling deployment:
  old instances keep working against the new schema during rollout. Prefer
  additive, nullable changes first; a destructive or mandatory transition needs
  an explicit compatibility plan and human approval.
- Never edit a migration that has already been applied anywhere. Checksums are
  validated on startup and a rewrite breaks every deployed environment. Report
  the problem and add a corrective migration instead.
- Add an index for a real query shape and weigh its write cost. On a large
  table, follow the project's established non-blocking pattern rather than an
  unbounded locking change.
- New or changed queries preserve authorization and tenancy scoping. Prove
  absence, cross-tenant isolation, ordering, pagination, locking, and constraint
  behavior against a real database engine where the behavior is engine-specific.
- Define overflow, sign, scale, rounding, and currency semantics at every
  monetary conversion boundary.

## Configuration and feature flags

- Prefer typed, validated configuration binding with a conservative default over
  values scattered across the codebase. Name the property after the user-visible
  capability, not the implementation.
- Validate configuration at startup and fail fast on an invalid combination. A
  service that starts with a nonsensical configuration fails later, in
  production, with less context.
- When disabling a feature must make a capability absent — not merely inert —
  use an explicit composition boundary so the beans, endpoints, schedulers, and
  listeners do not exist. A boolean checked inside one method is insufficient.
- Define and test both the enabled and the disabled topology, including startup
  and rollback. Enabled behavior retains authorization, validation, audit, and
  idempotency; a flag never weakens a mandatory security control and never
  authorizes a user.
- Restart-applied configuration is the safe default. Dynamic refresh requires
  proof of atomic publication, in-flight semantics, cache invalidation,
  rollback, and thread safety.

## Review and code hygiene

- Review the approach before the line details: is it source-aligned,
  proportional, and simpler than what is proposed?
- Search for an equivalent existing owner before accepting a new class, service,
  or utility. Do not demand reuse when contract, lifecycle, or change risk makes
  separation safer.
- Every actionable reviewer comment receives a response. A fix response cites
  the reachable commit and the solution path; a non-fix response cites concrete
  code, test, or contract evidence. Resolve a thread only after its response is
  posted.
- Code comments explain a non-obvious invariant, motivation, lifecycle, safety
  property, or correct usage. They never narrate syntax or work history, name a
  ticket, pull request, branch, or person, preserve commented-out code, or leave
  an unowned TODO.
- No ticket key, PR number, or other work-tracking identifier belongs in tracked
  source. Git metadata and the external tracker are the only places for it.
- Reuse an existing structured logging, metric, or map key. Define a genuinely
  shared key once at the narrowest owner; do not create a global constant for an
  unrelated spelling or a local constant for a single use.
- Delete dead and commented-out code. Version control remembers it.

## TDD and commits

- The commit subject comes from `project-config` (`commit.subject_template`).
  When `commit.require_stable_subject` is true, every commit in one workflow
  reuses that identical subject and the changing detail goes in the body.
- Commit each non-empty RED, GREEN, and REFACTOR stage separately, after that
  stage's focused tests and hygiene checks pass. Never create an empty refactor
  commit; record that no refactor was warranted instead.
- One commit per logical change, in every workflow — not only TDD ones. A
  security remediation, a gate fix, a reviewer's point, a test-only addition, a
  documentation correction, and a dependency bump are each their own commit even
  when delivered together. The reason is revert granularity: one large commit
  forces a reviewer who rejects a part of it to unpick it by hand, while a
  series lets them drop exactly that commit.
- Each commit stands alone. It leaves the tree coherent, its body says what
  changed and why, and it does not depend on a later commit to make sense. Do
  not bundle an unrelated fix in because it was noticed at the same time, and do
  not split one logical change into individually incomplete commits.
- Never commit directly to a branch listed in `branches.protected`. Publishing
  is caller-owned; never push without explicit authorization.
