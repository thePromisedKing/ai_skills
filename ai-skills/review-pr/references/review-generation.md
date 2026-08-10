# Review generation

The lenses a review applies, how to route them, and what each one is looking
for. Applied against the grounded requirements — a review judges whether the
change does what it was required to do, correctly, not whether it is what the
reviewer would have written.

## Contents

- Routing
- The lenses
- Reading order
- Verifying a finding
- The brief mode
- Findings not worth reporting

## Routing

Each lens is one read-only reviewer with the diff, the grounded context, and its
own brief. Run independent lenses concurrently within
`parallel.max_concurrent_groups`.

Select lenses by what the change touches, not by running all of them every time:

| The change touches | Lenses |
| --- | --- |
| any code | correctness, testing, maintainability |
| an HTTP endpoint or public contract | contract, security |
| persistence or a migration | data, correctness |
| concurrency, async, scheduling, messaging | concurrency, resilience |
| authentication, authorization, crypto, PII | security |
| a hot path, a query, a loop over external data | performance |
| configuration or a feature flag | configuration |

A lens that finds nothing is a result. Record it, so the review's coverage is
visible; a review that lists three findings without saying what else it looked
at cannot be judged.

## The lenses

**correctness** — Does it do what the requirement says, on every path? Off-by-one
and boundary conditions, the negative and error paths, null and absent input,
the empty collection, the duplicate request. Does the failure path leave state
consistent? Is there a case the tests do not reach that the code claims to
handle?

**contract** — Does it break a published API, event, or persisted shape? A
removed or renamed field, a narrowed type, a tightened validation, a changed
status code, a new required parameter, an enum whose meaning shifted. Would the
previous version of the application read the new persisted data during a rolling
deployment, and the new version read the old?

**security** — Is authorization checked on the authoritative side? Is
client-supplied input trusted for ownership, pricing, or identity? Is untrusted
data concatenated into a query, a path, a URL, or a command? Does a secret or a
PII value reach a log, a metric, an error response, or a fixture? Is a new
endpoint deny-by-default? Does an error message disclose internals?

**concurrency** — What happens with two instances, two threads, or two
identical requests? Is shared mutable state protected, and by what? Is the
effect idempotent under retry and replay? Is a lock held across a remote call?
Does a scheduled job guard against running on every instance?

**data** — Is the migration re-executable and rolling-deployment safe? Does it
edit a migration that already ran? Is a new index justified by a real query and
weighed against write cost? Does a new or changed query preserve authorization
and tenancy scoping? Is a monetary value exact, with its currency?

**resilience** — Does every outbound call have both timeouts? Is retry bounded,
backed off, and applied only to idempotent operations? Is a post-timeout commit
on the remote side handled? Is a queue, cache, batch, or pool bounded?

**performance** — Is there an N+1, a query inside a loop, a full-collection load
of unbounded external data, a repeated identical call? Is a payload or page size
bounded? Is a new index or cache justified? Is complexity added for performance
without measurement?

**testing** — Would each new test fail if the change were reverted? Does the
suite cover the negative paths, the boundaries, and the authorization failure?
Is the level right — a mocked repository proving a query, or an integration test
proving arithmetic? Is anything flaky by construction: real time, real network,
order dependence, unseeded randomness?

**configuration** — Is a new property typed, validated, and defaulted
conservatively? Are both flag states defined and tested, including the disabled
topology and rollback? Does a flag weaken a security control? Is a secret in a
committed file?

**maintainability** — Would the next reader understand this without asking? Does
a name say what the thing is? Is there an abstraction with one implementation
and no second case? Is there duplicated logic, dead code, a commented-out block,
an unowned TODO, or a ticket key in a tracked file?

## Reading order

1. **The requirement, then the diff.** Reading the diff first anchors the review
   to the implementation's own logic, and it becomes hard to notice what the
   change does not do.
2. **The shape before the lines.** What moved, what is new, what got bigger. A
   change that adds a layer nobody asked for is a bigger finding than anything
   inside that layer.
3. **The tests before the implementation.** They state what the author believed
   the behavior was. The gap between that and the requirement is where the
   interesting findings are.
4. **The lines.**
5. **What is absent.** The error path with no test, the endpoint with no
   authorization rule, the migration with no rollback consideration, the flag
   with no disabled-state test. Absence is the category a diff-focused review
   misses, because there is no line to react to.

## Verifying a finding

Before a finding is reported:

- Open the file and read the surrounding code, not just the diff hunk. Most
  false findings come from reading a hunk without its context.
- Construct the concrete failure: the input, the state, the outcome. A finding
  that cannot be stated as "given X, this returns Y and should return Z" is not
  yet understood.
- Check whether something else already prevents it — a validation upstream, a
  constraint in the database, a filter in the chain.
- Check whether a test already covers it.

Anything that dissolves at this step is `DISCARDED`, recorded with the evidence
that dissolved it, and not reported. A review's value is proportional to the
author's trust that every finding is real.

## The brief mode

`mode: brief` produces orientation for a human about to review, not findings:

- what the change does, in the requirement's terms;
- its shape — files, modules, what is new versus modified;
- the two or three areas where a defect would be most costly, and why;
- the specific questions worth answering while reading;
- what the tests claim to prove;
- anything unusual: a migration, a dependency, a contract change, a flag.

It does not pre-judge. Its purpose is to make a human's read faster and better
aimed, not to substitute for it.

## Findings not worth reporting

- A preference the project's standards do not support.
- A style point the configured formatter or linter would have caught — if it did
  not fire, the project does not enforce it.
- A rewrite of working code into a different but not better shape.
- A pre-existing issue the change merely sits near, unless the change makes it
  worse.
- A hypothetical with no path to it in this codebase.
- Something already raised and answered in the existing discussion.
- A "consider" with no concrete problem behind it.

Every one of these costs the author time and dilutes the findings that matter.
A short review of real findings outperforms a long one padded with observations.
