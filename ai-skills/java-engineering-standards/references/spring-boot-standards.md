# Spring Boot standards

Framework-specific rules. Language rules live in `java-language-standards.md`;
cross-cutting rules live in the shared baseline.

## Contents

- Layering and dependency direction
- Dependency injection and bean lifecycle
- Configuration binding
- Web layer and validation
- Error handling
- Transactions
- Persistence
- Caching
- Messaging and events
- Scheduling and async
- Outbound calls and resilience
- Security
- Observability
- Startup, health and shutdown
- Build and dependency hygiene

## Layering and dependency direction

- Keep three responsibilities separate: a transport layer that validates and
  translates, an application/domain layer that owns business rules, and adapters
  that talk to infrastructure. Dependencies point inward, toward the domain.
- A controller validates the request contract, delegates, and maps the result.
  It never owns a business rule, never opens a transaction, and never touches a
  repository directly.
- A repository returns data. Business decisions about that data belong to the
  service that asked for it.
- Domain types do not import framework or transport annotations beyond what
  persistence genuinely requires. A domain object shaped by its JSON
  representation has the dependency backward.
- Never expose an entity as a request or response body. The two contracts change
  for different reasons, and coupling them turns a schema change into an API
  break.
- When `project.modules` is configured, respect the declared module graph: no
  new cycles, no dependency from a lower module on a higher one. Where the
  project has ArchUnit rules, they are the enforcement — a change that needs a
  rule relaxed needs that relaxation approved, not deleted.

## Dependency injection and bean lifecycle

- Constructor injection only. It makes dependencies explicit, allows `final`
  fields, and keeps the class testable without a container. Never field
  injection with `@Autowired`; never setter injection outside a genuine optional
  collaborator.
- A constructor with many dependencies is a class doing too much. Treat it as a
  design signal, not something to hide behind a builder or a facade.
- Beans are singletons by default and therefore shared. A mutable field on a
  bean is shared mutable state across every concurrent request.
- Prefer `@Component`/`@Service` on the project's own classes and `@Bean`
  methods in a `@Configuration` class for third-party types.
- Never call a business method from a constructor or `@PostConstruct` that
  depends on another bean being fully initialized; use `ApplicationRunner` or an
  event listener when startup work is genuinely needed.
- Do not use `ApplicationContext.getBean` in application code. Service-locator
  lookups hide the dependency graph the framework exists to make explicit.
- A self-invoked method does not go through the proxy: `@Transactional`,
  `@Cacheable`, `@Async`, and `@Retryable` are all silently inert when called
  from inside the same bean. Move the annotated method to a collaborator.

## Configuration binding

- Bind configuration with `@ConfigurationProperties` on an immutable record or
  a class with constructor binding, validated with Bean Validation and
  `@Validated`. Reserve `@Value` for a genuinely isolated single value.
- Name a property after the capability, not the implementation. Group related
  properties under one prefix owned by one type.
- Declare a conservative default in the application's own configuration file and
  allow environment or profile overrides through normal property resolution. Do
  not read environment variables directly in application code.
- Validate at startup and fail fast on an invalid combination. A misconfigured
  service that starts is a production incident with less context than a startup
  failure.
- Never place a secret in a properties or YAML file that is committed. Secrets
  come from the environment or the project's secret manager.
- Use profiles for environment differences, not for feature toggles. A profile
  that changes behavior in a way tests never exercise is an untested code path.

## Web layer and validation

- Validate request bodies with Bean Validation on the DTO and `@Valid` on the
  parameter. Validate path variables and request parameters too — they are as
  untrusted as a body.
- Use DTOs as records with validation annotations on the components. Keep
  request and response DTOs separate; they diverge as soon as one field becomes
  server-computed.
- Return the status that describes the outcome: 201 with a `Location` for a
  creation, 204 for a successful no-content operation, 400 for a malformed
  request, 401 versus 403 correctly, 404 for an absent resource, 409 for a
  conflicting state, 422 where the project distinguishes semantic failure.
- Paginate every collection endpoint that can grow. State the default and
  maximum page size and enforce the maximum server-side.
- Make a non-idempotent endpoint safe to retry. A client that times out will
  retry, and a duplicate order is worse than a failed one.
- Never accept a client-supplied identifier for authorization, ownership, or
  pricing. Re-derive it from the authenticated principal on the server.
- Document the contract where the project documents contracts, in the same
  change as the behavior.

## Error handling

- Centralize translation in a `@RestControllerAdvice`. Controllers do not build
  error responses individually — that is how two endpoints end up reporting the
  same failure differently.
- Use one stable error response shape: a machine-readable code, a human-readable
  message, a correlation identifier, and the field errors when validation
  failed. `ProblemDetail` is a reasonable default when the project has no
  established shape.
- The error code is part of the API contract. A new failure mode gets a new
  code; overloading an existing one breaks the clients that branch on it.
- Never leak a stack trace, a SQL fragment, an internal path, or a framework
  exception name to a client. Log the detail with a correlation identifier and
  return the identifier.
- Map the exception to the status deliberately. An unmapped exception becoming a
  500 is a defect, not a default.

## Transactions

- Put `@Transactional` on the service method that owns the unit of work — not on
  the controller, not on the repository.
- Use `readOnly = true` for query paths. It lets the persistence provider skip
  dirty checking and makes the intent explicit.
- Keep transactions short and free of remote calls. An HTTP call inside a
  transaction holds a database connection for the remote system's latency and
  turns their outage into your connection-pool exhaustion.
- A checked exception does not roll back by default. State `rollbackFor`
  explicitly, or use unchecked domain exceptions.
- Understand what propagation you are choosing. `REQUIRES_NEW` suspends the
  outer transaction and takes a second connection — correct for an audit record
  that must survive a rollback, wrong as a way to work around a lock.
- Never rely on a transaction for cross-service consistency. Use an outbox, a
  saga, or a durable state machine, and define the compensation.
- Publish an external side effect — a message, a webhook, a notification — after
  commit, through `@TransactionalEventListener(phase = AFTER_COMMIT)` or an
  outbox. Publishing inside the transaction announces work that may still roll
  back.

## Persistence

- Every association is `LAZY` unless proven otherwise; `@ManyToOne` defaults to
  eager and is the usual source of unintended fetches.
- Solve N+1 with an explicit fetch join, an entity graph, or a projection —
  never by making the association eager, which fixes one call site and pessimizes
  every other.
- Use projections or DTO queries for read paths. Loading a full entity graph to
  return three fields costs memory, dirty checking, and a lock you did not want.
- Never expose a `Page` of entities. Map to a DTO inside the transaction, before
  the session closes.
- Use optimistic locking with `@Version` for concurrent updates, and handle the
  optimistic-lock failure with a defined retry or a conflict response.
- Write derived query methods only while they stay readable. Past three
  conditions, use `@Query` or a Criteria/Specification composition.
- Schema changes go through the migration tool, never through
  `ddl-auto: update`. In a non-local profile, `ddl-auto` is `validate` or `none`.
- Batch bulk work explicitly and clear the persistence context periodically. A
  loop that saves ten thousand entities in one transaction will exhaust heap
  before it exhausts the loop.
- Test repository behavior against the real database engine when the behavior is
  engine-specific: constraints, locking, JSON columns, upserts, full-text.

## Caching

- Cache a read that is expensive and tolerant of staleness. Name the staleness
  window; a cache with no stated tolerance is a correctness bug someone will
  find later.
- Every cache has a TTL and a bounded size. An unbounded cache is a memory leak
  with a helpful name.
- Include every input that affects the result in the key, including the tenant
  and the principal where results differ by them. A cache key missing the tenant
  is a data-leak defect.
- Never cache a mutable object by reference. Cache an immutable value.
- Define invalidation with the write path that makes the entry stale, in the
  same change.
- Never cache an authorization decision longer than the credential that produced
  it.

## Messaging and events

- Consumers are idempotent. Redelivery is normal, not exceptional — design for
  at-least-once and make the second delivery harmless.
- State the ordering guarantee you depend on and the partitioning that provides
  it. Ordering across partitions is not a guarantee you have.
- Never let a poison message block a partition forever. Use bounded retry and a
  dead-letter destination with enough context to diagnose the message.
- Acknowledge after the work is durable, not before.
- Version the event schema and keep consumers tolerant of unknown fields.
  Removing or repurposing a field is a breaking change with a migration.
- Use `ApplicationEventPublisher` for in-process decoupling only. It is not
  durable, it is not transactional unless bound to a phase, and it does not
  survive a restart.
- Publish to an external broker after commit or through an outbox — never inside
  the transaction that might roll back.

## Scheduling and async

- A `@Scheduled` job in a multi-instance deployment runs on every instance.
  Guard it with a distributed lock or leader election, or accept and document
  concurrent execution.
- A scheduled job is idempotent, bounded in the work it takes per run, and
  logs its outcome. An unbounded job that grows with the table will eventually
  overlap itself.
- `@Async` needs an explicitly configured executor. The default is not a
  configuration you chose, and its rejection policy is not one you want to
  discover under load.
- Propagate the correlation identifier and the security context across an async
  boundary deliberately; neither travels by itself.
- Never fire-and-forget work whose failure matters. An async method returning
  `void` discards its exception into the executor's handler.

## Outbound calls and resilience

- Every outbound call has a connect timeout and a read timeout. A client with no
  timeout will eventually hold every thread in the pool.
- Retry only idempotent operations, with bounded attempts, exponential backoff,
  and jitter. Retrying a non-idempotent write duplicates it.
- A timeout does not mean the remote side did not act. Define the status lookup,
  reconciliation, or compensation before adding the retry.
- Use a circuit breaker or bulkhead where a dependency's degradation would
  otherwise consume the caller's capacity. Define the fallback behavior — a
  fallback that silently returns empty data is a correctness decision, not a
  resilience feature.
- Prefer the project's established HTTP client abstraction. Do not introduce a
  second client library for one call.
- Validate and bound the response: size, content type, and shape. A trusted
  partner still returns malformed data eventually.

## Security

- Authorize on the server, at the authoritative boundary, using the framework's
  method or request security. Re-verify ownership at the data access boundary —
  an authenticated user is not automatically the owner of the identifier they
  sent.
- Keep endpoint security explicit and deny-by-default. A new endpoint that is
  public because nobody added a rule is the most common access-control defect.
- Never build a query, a path, or a command by concatenating request input. Use
  parameter binding, and validate any value that must reach a filesystem, a URL,
  or a process argument.
- Disable or scope CSRF deliberately, with the reasoning recorded. Configure
  CORS to named origins; a wildcard with credentials is not a configuration, it
  is a hole.
- Keep actuator endpoints authenticated and expose only what operations needs.
  `env`, `heapdump`, `threaddump`, and `configprops` disclose secrets and
  internals.
- Use the project's approved crypto abstraction. Do not call primitives
  directly, and never hardcode an algorithm, key size, mode, or padding —
  select it through validated configuration so it can be rotated.
- Serialize deliberately. Never deserialize untrusted input into polymorphic
  types, and never enable default typing.

## Observability

- Use the project's structured logger. Never `System.out` or `printStackTrace`.
- Log at the boundary that owns the failure, once, with the identifiers a
  responder needs. Do not log-and-rethrow — that produces the same failure three
  times in the log with three different stack traces.
- Put context in structured fields, not in the message string. A message built
  by concatenation cannot be searched or aggregated.
- Propagate a correlation identifier across every boundary, including async and
  messaging.
- Record a metric for what an operator actually alerts on: error rate, latency
  distribution, saturation, and the business outcome. Keep tag cardinality
  bounded — an identifier as a metric tag will exhaust the metrics backend.
- Trace the paths where latency is diagnosed. Add a span for an outbound call, a
  database batch, and a significant business operation; do not trace everything.

## Startup, health and shutdown

- Keep liveness and readiness distinct. Readiness reflects whether this instance
  should receive traffic; liveness reflects whether it should be restarted.
- Do not make an optional dependency a hard readiness failure. A cache or an
  analytics sink being down should degrade the service, not remove every
  instance from rotation.
- Enable graceful shutdown and let in-flight requests finish. Deregister from
  discovery before the shutdown grace period, not after.
- Fail fast at startup on invalid configuration or an unreachable mandatory
  dependency, with a message naming what was wrong.

## Build and dependency hygiene

- Let the Spring Boot BOM manage versions. Pin an override deliberately, with a
  comment stating why — a security fix, a compatibility constraint — so the next
  person can remove it when it is no longer needed.
- Keep test-only dependencies in the test scope. A test library on the runtime
  classpath ships mocking infrastructure to production.
- Do not add a dependency for something the existing stack does. Every addition
  is a transitive tree, a license, a CVE feed, and an upgrade obligation.
- Keep the build reproducible: no snapshot dependencies in a release build, no
  dynamic version ranges.
- When the project runs a dependency vulnerability gate, a new or upgraded
  dependency is evaluated against it in the same change.
