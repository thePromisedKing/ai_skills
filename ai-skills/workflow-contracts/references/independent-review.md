# Independent review

The engine's own end-of-workflow review, before the final gate. It exists
because the agent that wrote the code is the worst available judge of it: it
knows what it meant, so it reads the intent rather than the text.

## When it runs

Phase 5, after the full suite and the test leg, before the final gate lanes.
Skipped only when `review.parent_managed: true` — the parent review invocation
is already performing it — or when `review.independent_review` is `false` in the
project configuration, which is recorded as a limitation.

## How it runs

Invoke `review-pr` in `review-and-fix` mode with its local-branch contract:

```yaml
caller: <engine>
mode: review-and-fix
target: local-branch
base: <the confirmed base>
head: <current head>
round: <1-based, ceiling review.max_rounds>
context: {tracker, requirements, standards references}
```

The reviewer receives read-only tools. It does not fix what it finds; it returns
findings and the engine handles them.

## Handling findings

Each finding is dispositioned with evidence:

| Disposition | Requires |
| --- | --- |
| `REAL` | return to the phase that owns it, fix, and repeat the gate from there |
| `FALSE_POSITIVE` | concrete contradictory evidence — a line of code, a passing test, a contract — recorded in the result |
| `OUT_OF_SCOPE` | the scope-holding procedure; never fixed silently |
| `ALREADY_HANDLED` | the commit and line where it was handled |

A finding dismissed on reasoning alone is not dispositioned. "I considered this
and it's fine" is the disposition that lets real defects through, and it is
indistinguishable in a result from a genuine false positive — so it is not
accepted as one.

## Rounds

A round is one review plus the fixes it produced. Re-review after fixing, since
a fix introduces new code that has never been reviewed.

Stop at `review.max_rounds`. Reaching the ceiling with findings outstanding is
`NEEDS_INPUT` with the remaining findings, not a `PASS` with them listed as
limitations. A change that cannot converge in three rounds usually has a design
problem, which is an escalation to `architecture-plan`, not a fourth round.

## Recursion

A parent-managed run may never invoke `review-pr`. That is the whole recursion
guard: without it, review triggers a fix, the fix triggers a review, and the
workflow does not terminate. Reject an invalid `parent_managed` contract with
`BLOCKED` rather than repairing it.
