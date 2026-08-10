# Test standards

How to choose a test level, write the test, and judge whether it proves
anything. Cross-cutting rules live in the shared baseline; this document is
Java, JUnit 5, and Spring specific.

## Contents

- What a test is for
- Choosing the level
- Mocking discipline
- JUnit 5 conventions
- Spring slice tests
- Integration tests and Testcontainers
- ArchUnit boundary tests
- Contract tests
- Data, fixtures and builders
- Determinism and isolation
- Coverage
- Judging an existing test
- Anti-patterns

## What a test is for

A test exists to fail when the behavior it names breaks. Everything else — the
coverage number, the count of test methods, the mock verification — is
incidental. The single most useful question about any test is: *would this still
pass if the change it guards were reverted?* If yes, it proves nothing.

Name a test for the behavior and its expected outcome, not for the method under
test: `rejectsCheckoutExceedingAccountLimit`, not `testCheckout2`. A reader
scanning failures should learn what broke without opening the file.

## Choosing the level

Pick the cheapest level that can actually prove the behavior. Cheap here means
fast and stable, not shallow — a unit test that mocks the thing under question
is not cheap, it is empty.

| Level | Proves | Use when |
| --- | --- | --- |
| `unit` | pure owned logic, branches, boundaries, arithmetic | the behavior is decided in your own code with no framework or I/O |
| `slice` | one framework layer in isolation — web, JSON, persistence mapping, security rules | the behavior is the framework's translation of your contract |
| `integration` | real wiring, transactions, SQL, serialization, configuration, protocol semantics | a mock would have to encode the very semantics in question |
| `contract` | producer/consumer compatibility across a boundary | another team or service depends on the shape |
| `e2e` | a critical journey across deployed boundaries | the risk is in the composition, not in any single part |

Escalate a level only with a stated reason. "Integration, because a mocked
repository cannot prove the query's tenant filter" is a reason. "Integration,
for confidence" is not — and it buys a slow suite nobody trusts.

The inverse also holds: a behavior that only exists when the pieces are wired
together is not provable at unit level, and asserting it there with mocks
produces a test that passes while production is broken.

## Mocking discipline

- Mock the true boundary — the thing you do not own and cannot run cheaply.
  Never mock the class under test, a value object, or a type you own and could
  simply construct.
- Never make two mocks agree on a contract that no real test verifies. That is
  how a system passes every test and fails on first contact with itself.
- Prefer a hand-written fake or an in-memory implementation over a stack of
  `when(...).thenReturn(...)` when the collaborator has behavior worth
  simulating. A fake is reusable and readable; a long stub chain is a fixture
  written in the wrong language.
- Verify an interaction only when the interaction *is* the behavior — a message
  published, an audit record written, a payment captured exactly once. Verifying
  that a getter was called tests the implementation, and breaks on every
  refactor.
- Never use `verifyNoMoreInteractions` as a default. It turns every future
  addition into a failing test with no defect behind it.
- Use `@Mock`/`@InjectMocks` with `MockitoExtension`, or plain construction with
  hand-built collaborators. Do not mix a Spring context with `@InjectMocks`.
- Never stub what the test does not exercise. Mockito's strict stubs catch this;
  do not relax the strictness to silence it.

## JUnit 5 conventions

- One behavior per test. A test with three unrelated assertions reports one
  failure and hides two.
- Arrange, act, assert — visibly separated. If the arrange section needs a
  comment to be understood, the fixture wants extracting.
- Use `assertThat` from AssertJ (or the project's established assertion library)
  for a readable failure message. `assertTrue(x.equals(y))` reports "expected
  true"; `assertThat(x).isEqualTo(y)` reports both values.
- Use `@ParameterizedTest` for the same behavior across inputs — boundaries,
  currencies, states. Do not use it to run three different behaviors through one
  method with an `if` inside.
- Use `@Nested` to group by scenario when a class covers several states. Keep
  the outer class's fixture to what all nested classes need.
- `@DisplayName` is for a sentence the test name cannot express. It does not
  excuse an unreadable method name.
- Assert the exception type *and* what it carries — the code, the identifier,
  the message key. `assertThrows(RuntimeException.class, ...)` passes for the
  wrong bug.
- Never write a test with no assertion. A method that only calls production code
  proves it does not throw, which is almost never the requirement.

## Spring slice tests

- Use the narrowest slice that covers the behavior:
  - `@WebMvcTest` for controller mapping, validation, status codes, error
    translation, and security rules — with services replaced by mocks;
  - `@DataJpaTest` for repository queries, constraints, and mapping;
  - `@JsonTest` for serialization contracts;
  - `@RestClientTest` for an outbound client's request shaping and error
    handling.
- A slice test must actually exercise the slice. A `@WebMvcTest` that calls the
  controller method directly instead of through `MockMvc` has skipped
  everything the slice exists to test: routing, binding, validation, and the
  advice.
- Test security in the web slice with the real filter chain and an
  authenticated principal, including the unauthenticated and wrongly-authorized
  cases. An endpoint's access rule is behavior, not configuration.
- Do not load the full application context with `@SpringBootTest` for something
  a slice covers. Context loading dominates a suite's runtime, and every
  unnecessary full context multiplies it.
- Share one context configuration across tests so the framework can cache it. A
  test that varies properties or adds a bean gets its own context — do that
  deliberately, not by accident.

## Integration tests and Testcontainers

- Use a real database when the behavior is the database's: constraints, unique
  violations, locking, isolation, upserts, JSON columns, full-text search,
  generated columns, migration correctness. An in-memory substitute with
  different semantics proves the substitute works.
- Run migrations in the integration test the same way production does. That is
  the only place a broken migration is caught before deployment.
- Reuse one container lifecycle across the suite — a static container or the
  project's established shared configuration. A container per test class turns
  a two-minute suite into twenty.
- Reset state between tests deliberately: a transactional rollback, a truncation
  hook, or per-test unique data. Never depend on test execution order.
- Use a container for a broker, cache, or object store when the protocol
  semantics matter — redelivery, ordering, TTL eviction, consumer groups. Use a
  lightweight fake when only the call shape matters.
- Weigh the cost honestly: image pull, startup time, CI resources, flakiness,
  and maintenance. State what the container proves that a cheaper test cannot.
  When nothing, use the cheaper test.
- A behavior that needs a real external institution, production identity, or
  hardware is a named manual QA scenario recorded as a limitation. It is never
  replaced by a mock asserting nothing.

## ArchUnit boundary tests

Where the project runs the `archunit` gate, these rules are executable and are
the enforcement mechanism for the layering rules in the Java specialization.

Rules worth having:

- layer access — controllers may not be accessed by services; repositories may
  only be accessed from the application layer;
- dependency direction — the domain package depends on no framework or adapter
  package;
- no cycles between the project's own top-level packages;
- naming and annotation consistency — classes in `..controller..` are annotated
  `@RestController`, repositories extend the project's base repository;
- prohibitions — no `System.out`, no `java.util.Date` in new code, no field
  injection, no direct use of a primitive the project bans.

A change that a rule blocks either changes, or gets the rule relaxed with an
explicit approval and a recorded reason. Deleting or weakening a rule to make a
build green is a defect, not a fix.

## Contract tests

- Where another service consumes an API or an event this project produces, a
  contract test pins the shape both sides rely on. It is cheaper than an e2e
  test and catches the same class of break.
- Version the contract and keep the old version's test until its consumers have
  migrated. A contract test deleted at the same time as the field it pinned
  proves nothing.
- Generate or validate the OpenAPI or schema document in the test where the
  project publishes one, so the document cannot drift from the code.

## Data, fixtures and builders

- Build test data with a builder or an object mother that defaults everything
  irrelevant and names only what the test cares about. A test whose arrange
  section sets fifteen fields hides which one matters.
- Use obviously fake values. Never a real name, email, card number, national
  identifier, token, or key — in a test, a fixture, a snapshot, or a container
  seed.
- Make the value under test visibly distinctive. Asserting on `"test"` in a
  suite full of `"test"` produces a passing test for the wrong reason.
- Keep fixtures near their tests. A shared fixture that everything depends on
  becomes the thing nobody dares change.

## Determinism and isolation

- No dependence on wall-clock time. Inject a fixed `Clock`; never `Thread.sleep`
  to wait for something. Use the project's awaiting utility with a bounded
  timeout when a test genuinely must wait for an asynchronous outcome.
- No dependence on execution order, a shared static, a leftover file, or the
  previous test's database rows.
- No network access to a real external service. A test that fails when the
  office WiFi drops is not a test of your code.
- No randomness without a fixed seed. A test that fails one run in fifty gets
  ignored, and then so does the suite.
- Never paper over flakiness with a blanket retry, a widened timeout, a
  swallowed assertion, or `@Disabled` with no owner and no date. A flaky test is
  a defect in the test or in the code; both are worth finding.
- A test that fails only in CI is evidence about the environment, not a reason
  to relax the assertion.

## Coverage

- Coverage is supporting evidence, never the goal. A hundred percent of lines
  with no meaningful assertions proves the code runs, not that it works.
- Where `gates.coverage` sets a floor for changed lines, meet it with tests that
  would fail if the change were reverted. Where `ratchet` is on, do not lower
  the project total.
- Prefer scenario completeness over line percentage for logic that decides
  money, identity, authorization, or a state transition: every branch, every
  boundary, both sides of every guard.
- Never add a test purely to raise a number, and never exclude a class from
  coverage to avoid writing one. An exclusion carries a stated reason.

## Judging an existing test

When reviewing tests a change ships, ask in order:

1. **Would it fail if the change were reverted?** If not, it is not a test of
   this change.
2. **Does it assert the outcome, or only that nothing threw?**
3. **Does it name the behavior, so a failure is diagnosable from the report?**
4. **Is it at the cheapest level that could prove this?** An integration test
   for pure arithmetic is a slow test; a unit test with a mocked query for a
   tenant filter is an empty one.
5. **Are the negative paths covered?** Invalid input, missing input, the
   unauthorized caller, the dependency failure, the duplicate request, the
   concurrent one.
6. **Is it deterministic?** Time, order, randomness, network.

A change whose tests fail any of the first two is not adequately tested,
regardless of what the coverage report says.

## Anti-patterns

- A test that mirrors the implementation line by line — it fails on every
  refactor and passes on every logic error.
- Asserting on a log message as a substitute for asserting on behavior.
- One giant test that walks a whole flow and reports a single failure for any of
  twenty possible causes.
- `@SpringBootTest` for something a unit test proves.
- A mocked repository used to prove a query.
- `@Disabled` with no owner, no reason, and no date.
- A test named after a ticket key.
- Catching the exception under test and asserting on its message string only.
