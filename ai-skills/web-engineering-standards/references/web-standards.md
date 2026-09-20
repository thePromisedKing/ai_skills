# Web standards

The rules a React and TypeScript front end is judged against when the project
assembles headless libraries behind its own glue layer instead of adopting a
framework. Each rule carries the failure it exists to prevent; a rule whose
reason no longer holds should be changed rather than worked around.

## Contents

- The thin-client boundary
- Schema validation at the API edge
- Tenancy in the cache
- Session auth
- The data layer
- Shared kits and resource shape
- What proves a front end works
- Dependencies and guardrails

## The thin-client boundary

`WEB-01` — Validation rules, tax and total calculation, document state machines,
numbering, and tenant isolation live behind an endpoint. A front end fetches,
displays, and submits.

The failure this prevents is two implementations of one rule drifting apart,
with the client's copy winning on screen and the server's winning in the
database. When a task appears to need logic in the client, stop and propose the
endpoint; that proposal is the deliverable, not a client-side approximation of
it.

`WEB-02` — Derived display values are the exception that proves the rule:
formatting a number the server computed is presentation, recomputing it is
logic. The test is whether the client would produce a different answer than the
server if the rule changed on one side only.

## Schema validation at the API edge

`WEB-03` — Every response is parsed against a schema before use. A contract
that drifts must fail loudly at the boundary rather than render a subtly wrong
screen, because a wrong number displayed confidently is worse than an error.

`WEB-04` — Parsing belongs in the one shared request wrapper, not in components.
A component that calls the network directly bypasses the wrapper's base URL,
credentials, tenant injection, parsing, and error normalization at once.

## Tenancy in the cache

`WEB-05` — Every cache key for tenant-scoped data starts with the tenant id.
This makes cross-tenant leakage structurally impossible rather than a thing
reviewers must notice. A key that omits it is a blocking finding even when the
screen it feeds looks correct today.

`WEB-06` — Switching tenant clears the cache outright. Selective eviction
assumes a complete inventory of what was cached under the previous tenant, and
that inventory is exactly what nobody maintains.

`WEB-07` — Keys come from a single factory. An inline key array is a key nobody
can invalidate reliably, because invalidation matches a prefix the factory
knows and an inline array may not share.

## Session auth

`WEB-08` — The session is a server-set cookie. The client never sees, stores,
or refreshes a token, and no credential is written to browser storage.

`WEB-09` — Sign-in is not one outcome. A login response can authenticate, or
demand a second factor, or demand enrolment before anything else is permitted.
A screen that navigates into the application on any successful response drops a
user into an application their cookie does not open. Treat the response's state
as the branch, never the absence of an error.

`WEB-10` — Identity and permissions come from one endpoint, cached until a
rejection invalidates it. Permission checks in the UI decide what to show; the
server decides what is allowed. A UI check is never the enforcement point.

`WEB-11` — A rejection anywhere returns the user to sign-in, except on the
screens that present a credential rather than assume one. There a rejection is
the answer the screen asked for, and redirecting throws the user back to
sign-in with no message about what went wrong.

## The data layer

`WEB-12` — Mutations invalidate the whole resource family. Surgical cache
updates trade a refetch nobody notices for a staleness bug nobody catches.

`WEB-13` — Freshness is chosen per category, not per call: reference data
tolerates hours, tenant configuration minutes, list views under a minute,
anything opened for editing must be refetched, and compliance or submission
status polls. When the category is unclear, refetch. Correctness outranks saved
requests wherever a stale value could be acted on.

## Shared kits and resource shape

`WEB-14` — One table kit and one form kit. Pages supply columns, a resource, and
a schema; they do not reimplement pagination, sorting, filter-to-URL syncing,
field-error mapping, or the loading, empty, and error states.

`WEB-15` — Interactive primitives keep their library's behaviour engine. Focus
traps, keyboard navigation, and positioning are where hand-rolled components
fail for keyboard and screen-reader users, silently and only for them.

`WEB-16` — A new resource copies the exemplar's file layout exactly: the query
and mutation hooks, the schemas, the column definitions, the list, detail, and
form screens, and the tests. Sameness is the point; a second layout doubles what
a reader must hold.

## What proves a front end works

`WEB-17` — End-to-end tests are the primary gate, because on a project with no
human front-end reviewer they are what stands in for one. Every user-facing flow
gets one, including at least one negative case: a forbidden action hidden *and*
rejected, and one tenant's record invisible to another. A feature without one is
not finished.

`WEB-18` — Component and unit tests cover the glue — the request wrapper, the
key factory, the route guards — and non-trivial components. They are not a
substitute for a flow test; they prove a part, not a path.

`WEB-19` — Tests address the interface a user has. Query by role and label
before test ids, drive the component the way a person drives it rather than
firing synthetic events, and await the library's own arrival and removal
matchers instead of sleeping. A fixed delay is a test that fails on a slow
machine and passes on a fast one, which is worse than no test.

`WEB-20` — Assert what a user observes: rendered output, and effects such as a
callback firing or a request being sent. Component state, props passed to
children, which hooks ran, and render counts are implementation details; a test
that asserts them fails on every safe refactor and passes through real
regressions.

`WEB-21` — Mock at the network boundary, not by replacing modules. Unmocked
requests in a test run should fail the test loudly rather than pass silently;
silence is how a test comes to prove nothing.

`WEB-22` — Snapshots of rendered markup are not evidence. They break on every
style change, get regenerated without being read, and assert structure rather
than behaviour. Serialization of pure functions is the legitimate use.

## Dependencies and guardrails

`WEB-23` — Dependencies are added deliberately, by the owner, at exact versions.
This skill may name what a task would need and why; it never decides to add one.
A capability the chosen libraries already cover is not a reason for another.

`WEB-24` — Type checking and linting run with warnings treated as failures.
A warning nobody must fix is a warning nobody reads.

`WEB-25` — A tree the project has frozen is read as behavioural reference and
never modified or imported from. Code that imports a frozen tree has extended
its life indefinitely.
