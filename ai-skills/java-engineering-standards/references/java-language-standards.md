# Java language standards

Language-level rules that apply regardless of framework. Framework rules live in
`spring-boot-standards.md`; cross-cutting rules live in the shared baseline and
are not repeated here.

## Contents

- Types and immutability
- Null, Optional and absence
- Exceptions and error translation
- Resource safety
- Collections and streams
- Equality, comparison and hashing
- Numbers, money and time
- Concurrency
- Generics and API design
- Language features by release
- Static analysis and suppressions

## Types and immutability

- Default to immutable. Make fields `final`, expose unmodifiable views, and
  return defensive copies of mutable inputs stored on a long-lived object.
- Use `record` for a value carrier with no identity: DTOs, events, query
  results, configuration bindings, composite keys. A record with a compact
  constructor is the right place for its own validation.
- Use a `sealed` interface with record implementations to model a closed set of
  outcomes or states. It makes exhaustive `switch` a compiler guarantee rather
  than a convention, and it is strictly better than an `enum` plus a bag of
  nullable fields.
- Do not add a setter because a framework might want one. Constructor binding
  and factory methods cover the real cases; a setter on a domain object invites
  mutation nobody owns.
- A class with only static methods is a utility: make it `final` with a private
  constructor, or use a `record` with no components. Never let it accumulate
  state.
- Prefer a small purpose-built type over a bare `String` or `long` for an
  identifier, a currency, or a status that has rules. The wrapper is where the
  validation lives, and it stops two identifiers of different kinds being
  swapped at a call site.

## Null, Optional and absence

- Validated internal paths are non-null. Express absence explicitly rather than
  letting `null` propagate as a second meaning of a field.
- `Optional` is a return type. Do not use it for a field, a constructor
  parameter, a method parameter, or a collection element — it adds an allocation
  and a second empty state to something that already had one.
- Never call `Optional.get()` without proven presence. Use `orElseThrow` with a
  domain exception, `orElseGet`, `map`, or `ifPresentOrElse`.
- Never return `null` where an empty collection, an empty `Optional`, or a
  domain result is the contract. A caller that has to null-check a collection
  will eventually forget.
- Do not catch `NullPointerException`. Validate at the boundary with Bean
  Validation, `Objects.requireNonNull` with a message naming the parameter, or
  the repository's established guard.
- When a parameter genuinely accepts null, say so with the project's nullability
  annotation and test that path. An undocumented nullable parameter is a defect
  waiting for its first null.

## Exceptions and error translation

- Catch the most specific useful exception. Catch `Exception` only at a
  deliberate application boundary, and never catch `Throwable` or `Error`.
- Keep the protected region minimal: the operation that can throw the handled
  exception, plus the resource use inseparable from it. Split independent
  throwing operations when they need different translation or recovery.
- Translate an infrastructure or third-party exception once, at the boundary
  that owns the integration, into a domain exception. Pass the original as the
  cause; never discard the stack trace, and never re-wrap the same failure at
  every layer.
- Never use an exception for ordinary control flow, and never swallow one. An
  empty catch block, a catch that only logs at debug, and a catch that returns a
  default in place of a real failure are all the same defect.
- A custom exception carries the information a handler needs to act — the
  identifier, the state, the constraint that failed — as fields, not only in a
  formatted message a caller has to parse.
- Prefer unchecked domain exceptions. A checked exception is justified when the
  immediate caller can realistically recover and the compiler should force the
  decision; otherwise it propagates as boilerplate.
- Never let an exception message carry a secret, a token, a full identifier
  document, or a raw request body.

## Resource safety

- Use try-with-resources for every scope-owned `AutoCloseable`: streams,
  readers and writers, JDBC objects, HTTP response bodies, archive and file
  handles, `Scanner`. Declare resources in the try header so they close in
  reverse order on success, failure, and early return.
- Use `finally` only when try-with-resources cannot express the lifecycle. A
  try/catch that owns a resource needs unconditional owner-level cleanup.
- Preserve the primary exception when close also fails — through suppressed
  exceptions or the project's established utility. A cleanup failure must never
  mask the failure that caused it.
- Do not close a caller-owned or framework-managed resource. Ownership is
  explicit at the method or component boundary; closing someone else's stream is
  as much a defect as leaking your own.
- `Files.lines`, `Files.walk`, and `Files.newDirectoryStream` return closeable
  streams. They leak file handles when used in a bare for-each.
- An `ExecutorService` needs an owner that shuts it down, with `shutdown`, an
  awaited termination, and `shutdownNow` on timeout. A pool created in a method
  and never shut down is a thread leak.

## Collections and streams

- Return `List.of`, `Map.of`, or `Collections.unmodifiable*` from an accessor.
  Returning the internal collection hands out write access to your invariants.
- Choose the collection for its access pattern, not by habit. A membership test
  against a `List` inside a loop is the most common accidental O(n²) in a
  codebase.
- Streams express a transformation. When a loop reads more clearly — early
  termination with side effects, index arithmetic, exception handling — use the
  loop. A stream chain that needs a comment to explain its shape has lost the
  argument.
- Never mutate a collection inside a stream over it, and never rely on a stream
  side effect for correctness. `peek` is for diagnostics, not logic.
- `Collectors.toMap` throws on duplicate keys. Supply the merge function
  deliberately, or use `groupingBy` when duplicates are expected.
- Bound anything that reads external input into memory. `collect(toList())` on
  an unbounded query result is a heap exhaustion waiting for production volume.
- Prefer a parallel stream only with measurement. On a typical request-scoped
  workload it competes with the common pool and usually loses.

## Equality, comparison and hashing

- Override `equals` and `hashCode` together, or use a `record` and get both.
- Keep `equals` consistent with `compareTo` where both exist. `BigDecimal` is
  the standard trap: `equals` distinguishes scale, `compareTo` does not — always
  compare monetary values with `compareTo`.
- Never include a mutable field in `hashCode` for an object used as a map key or
  set element.
- For a JPA entity, base equality on the business key or a stable assigned
  identifier — never on a generated identifier that is null before persist, and
  never on all fields.
- Implement `Comparable` only for a natural ordering that is genuinely
  intrinsic. Otherwise supply a `Comparator` at the call site where the ordering
  choice belongs.

## Numbers, money and time

- Never use `float` or `double` for money. Use integer minor units or
  `BigDecimal` with an explicit scale and `RoundingMode` at every arithmetic
  step. A `BigDecimal` division without a rounding mode throws.
- State the currency alongside any amount that can be more than one currency. An
  amount without its currency is a bug that surfaces at the worst moment.
- Check for overflow on `int` and `long` arithmetic that can approach the
  bounds. `Math.addExact` and its siblings throw instead of wrapping silently.
- Use `Instant` for a machine timestamp, `LocalDate` for a calendar date with no
  time, and `ZonedDateTime` only when the zone is part of the meaning. Never
  `Date` or `Calendar` in new code.
- Never use the system default zone implicitly. Pass an explicit `ZoneId`, and
  inject a `Clock` so time-dependent behavior is testable without sleeping.
- Persist timestamps in UTC and convert at the presentation boundary.

## Concurrency

- Make the concurrency model explicit at the class level: is this instance
  shared, request-scoped, or confined to one thread? A field on a shared bean is
  shared state.
- Prefer immutability and confinement over locking. When shared mutable state is
  unavoidable, use the concurrent collections, atomics, or an explicit lock —
  never `synchronized` sprinkled on some methods and not others.
- Never synchronize on a `String`, a boxed primitive, or a public object. Use a
  dedicated private final lock object.
- `ConcurrentHashMap.computeIfAbsent` must not perform a blocking or recursive
  update on the same map.
- With virtual threads, avoid pinning: prefer `ReentrantLock` over
  `synchronized` around blocking I/O, and do not size a pool as though threads
  were scarce.
- Never protect a correctness invariant with JVM-local state alone when more
  than one instance runs. That belongs in a database constraint, an optimistic
  lock, or a distributed lock with a TTL.
- Bound every executor, queue, and retry loop. An unbounded queue converts a
  latency problem into an out-of-memory one.

## Generics and API design

- Prefer `List<? extends T>` for a producer parameter and `List<? super T>` for
  a consumer. Return a concrete parameterized type; wildcards in return
  positions leak into every caller.
- Never use a raw type. Never suppress an unchecked warning without a comment
  stating why the cast is provably safe.
- Keep a public method's parameter list short and its meaning obvious. Three
  same-typed parameters in a row is a call site waiting to be transposed —
  introduce a parameter object or purpose types.
- Overloads that differ only by a nullable parameter, or by types related by
  autoboxing, resolve in ways readers do not predict. Name the methods
  differently.
- Do not expose a mutable array from an API. Return a list or a copy.
- A builder is warranted for many optional fields. It is not warranted for three
  required ones — a constructor states the requirement, a builder defers it to
  runtime.

## Language features by release

Check `build.java_release` before citing a feature. Do not recommend one the
project cannot compile.

| Release | Available |
| --- | --- |
| 17 | records, sealed types, pattern matching for `instanceof`, text blocks, `switch` expressions, `Stream.toList` |
| 21 | pattern matching for `switch`, record patterns, sequenced collections, virtual threads |
| 25 | flexible constructor bodies, module import declarations, primitive patterns and compact source files where the project enables preview features |

Use a text block for embedded SQL, JSON, or multi-line messages instead of
concatenation. Use `switch` expressions with exhaustive arms over a chain of
`if`/`else if` on a closed type. Do not adopt a preview feature in production
code without an explicit approved decision.

## Static analysis and suppressions

- A suppression — `@SuppressWarnings`, `//NOSONAR`, a SpotBugs exclusion, a
  Checkstyle off/on pair — is a documented exception, never a way to close a
  finding. It carries the narrowest possible scope and a comment stating why the
  finding does not apply.
- Never widen a suppression to a class or a package when one line is at issue,
  and never add one to make a gate pass. Fixing the code or getting the
  exception approved are the only two outcomes.
- An existing unexplained suppression encountered in scope is a finding worth
  reporting, not something to copy.
