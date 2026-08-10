---
name: api-test-workflow
description: Plan and implement REST API test coverage for a change — derive scenarios from the grounded requirements and the actual API diff, stop at a plan checkpoint for the user's selection, implement the approved scenarios in the project's established test harness, execute them, and classify every failure as a product defect, a test defect, or an environment issue. Use when an implementation engine's diff changes HTTP behavior, when the user asks for API test coverage, or to re-execute a specific selection without changing files.
---

# API test workflow
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own API-level test coverage. Derive the scenarios, get them approved, implement
them, run them, and classify what fails.

Never touch product code. A misbehaving API is a finding this skill reports; the
engine that owns the code fixes it. That separation is what keeps a test suite
honest — a test author who can also change the implementation will eventually
change the implementation.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 API surface diff analyzed
- [ ] 2 Scenario matrix derived from requirements and diff
- [ ] 3 Plan checkpoint: user selected the scenarios to implement
- [ ] 4 Scenarios implemented in the established harness
- [ ] 5 Selection executed; every failure classified
- [ ] 6 Result returned with defects routed, not fixed
```

## Invocation

```yaml
caller: spring-workflow | implement-task | direct
mode: plan-and-implement | execution_only
code_evidence:
  kind: local-diff | branch-range
  base: <ref>
  head: <ref>
context: {tracker, requirements, standards references}
selection: [test ids]           # required for execution_only
test_link:
  direction: engine-to-tests | none
  origin: <skill that started the chain>
  hop: <incremented by the caller>
```

`execution_only` changes no files and starts no chain. It exists so an engine
can rerun exactly the scenarios that failed after fixing a defect, and prove the
fix against the test that found it.

## Phase 1 — Analyze the surface

Read the diff and identify what actually changed about the HTTP contract:

- new, removed, or renamed endpoints;
- changed request shape: a new field, a changed type, a tightened validation, a
  new required parameter;
- changed response shape or status codes;
- changed error contract: a new code, a changed meaning;
- changed authorization rules;
- changed pagination, filtering, or sorting;
- changed idempotency or retry semantics.

A change that touches a service but leaves the HTTP contract identical needs no
API coverage. Say so with the evidence — that is a legitimate not-applicable
result, not a skipped step.

## Phase 2 — Derive the scenario matrix

Build scenarios from the grounded requirements and the surface diff together.
Requirements alone miss what the implementation actually exposed; the diff alone
misses what the requirement asked for and the change did not deliver.

Cover, for each changed operation:

| Dimension | Scenarios |
| --- | --- |
| happy path | each documented success outcome and its status |
| validation | missing required, wrong type, out of range, malformed body, boundary values on both sides |
| authorization | unauthenticated, authenticated but unauthorized, authorized for a different owner's resource |
| absence | the resource does not exist, the collection is empty |
| conflict | duplicate creation, concurrent modification, state that forbids the operation |
| idempotency | the same request twice, where the operation claims to be safe to retry |
| pagination | first page, last page, past the end, over the maximum page size |
| contract | the response contains exactly the documented fields, and no more |

That last row catches the defect nobody looks for: an entity serialized straight
onto the wire, leaking fields the contract never promised.

Mark a scenario `NOT_AUTOMATABLE` only with the concrete reason — a real
external institution, production identity, hardware. Record it as a named manual
scenario. Never replace it with a test that asserts nothing.

## Phase 3 — The plan checkpoint

Present the matrix: each scenario, what it proves, its level, and whether it is
new or already covered by an existing test. Stop for the user's selection.

This checkpoint exists because a complete matrix is usually larger than the
change warrants, and the judgment about which scenarios earn their maintenance
cost is the user's. Implementing all of them by default produces a suite that is
slow, brittle, and eventually deleted wholesale.

## Phase 4 — Implement

Use the project's established API test harness and its conventions — the same
fixtures, the same setup, the same assertion library. A second harness beside an
existing one is a finding, not a contribution.

Follow `test-engineering-standards`: obviously fake data, deterministic, no real
network, no order dependence, named for the behavior.

The files produced are **workflow-owned when this skill was invoked by an
engine**. That engine stages and commits them under its stable commit subject
with body stage `TESTS`, so the independent review sees them and the final gate
scans them. This skill never commits.

## Phase 5 — Execute and classify

Run the selection. Classify every failure before returning it:

| Class | Meaning | Routing |
| --- | --- | --- |
| `PRODUCT_DEFECT` | the API is wrong | returned to the owning engine, never fixed here |
| `TEST_DEFECT` | the test is wrong | fixed here |
| `ENVIRONMENT_ISSUE` | infrastructure, data, or configuration | recorded as a limitation |

Classify from evidence: the request sent, the response received, and what the
requirement says it should have been. A failure classified `TEST_DEFECT` because
the fix is easier is how a real defect gets written out of existence.

Under `direction: engine-to-tests`, return the defects and let the engine — which
is already inside its own run — perform the fixes. Never invoke an engine from
here in that direction; that is what the hop ceiling in
`workflow-contracts/references/workflow-contracts.md` prevents.

Running standalone, a `PRODUCT_DEFECT` may be routed to the engine with explicit
user approval, setting `direction: tests-to-engine`. That crossing turns a test
run into a code change, so it needs its own approval even if one was given
earlier.

## Result

```yaml
API_TEST_WORKFLOW_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  surface_diff: [operation, what changed] | no_api_change with evidence
  matrix: [id, scenario, dimension, level, new | existing, selected]
  not_automatable: [id, reason, manual scenario]
  implemented: [test file, scenario ids]
  execution:
    command: exact selection command
    passed: integer
    failed: [test id, class, evidence]
    environment: what the run covered
  defects_routed: [id, class, owning target, reproduction evidence]
  test_link: {direction, origin, hop}
  limitations: [unrun selection, environment issue, declined scenario]
```

Never imply coverage the run did not produce. A scenario that stayed
`NOT_AUTOMATABLE` or was not selected is stated as such.

## Example

An engine's test leg after a checkout endpoint changed its error contract:

```text
Claude Code: /api-test-workflow plan-and-implement over origin/main..HEAD,
direction engine-to-tests

Codex: Use $api-test-workflow in plan-and-implement mode over origin/main..HEAD
with direction engine-to-tests.
```

Derives fourteen scenarios across the changed operation, presents them, and
waits. On the selected nine it implements and runs them; one fails because the
409 body omits the documented `code` field, which is classified `PRODUCT_DEFECT`
with the request and response captured and returned to the engine. The engine
fixes it and reruns that one test id with `execution_only`.

## Guardrails

- Never modify product code. A defect is reported, never fixed here.
- Never commit; the invoking engine owns the commit.
- Never invoke an engine while serving an `engine-to-tests` chain.
- Never cross into `tests-to-engine` without explicit approval for that crossing.
- Never exceed hop 2 or reverse a chain's direction.
- Never build a second test harness beside the project's established one.
- Never write a test that asserts nothing, or one that passes with the change
  reverted.
- Never classify a failure `TEST_DEFECT` without evidence that the test, not the
  API, is wrong.
- Never claim a scenario ran when it was skipped, deselected, or
  `NOT_AUTOMATABLE`.
