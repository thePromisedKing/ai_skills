---
name: spring-workflow
description: Implementation engine for rigorous Java Spring Boot code changes and evidence-backed evaluation of raw pull-request recommendations. Use directly for a code change with no work item, or when implement-task, review-pr, or fix-pr delegates the local engineering work — architecture selection, complete test planning, base synchronization, committed RED/GREEN/REFACTOR cycles, the configured quality and security gates, regression, and independent review. It owns every code mutation and commit; it never writes to the tracker, creates a pull request, or pushes.
---

# Spring workflow
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Execute the local engineering work a caller supplies. Own every code mutation,
test, and commit; orchestrate gates and review through their owning skills.
Return evidence to the caller and never duplicate the caller's external
responsibilities.

The lifecycle is owned by `workflow-contracts/references/workflow-contracts.md`
— the invocation and result contracts, Phases 0 through 5, the TDD and commit
contracts, escalation, scope holding, and the shared guardrails. Read it at
Phase 0 and follow it. This skill adds only what is specific to a Java Spring
Boot repository.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Phase 0 preflight validated; project config and standards resolved
- [ ] 2 Phase 1 classified; architecture selection obtained
- [ ] 3 Phase 2 test inventory complete; nothing unmapped
- [ ] 4 Phase 2A parallel plan approved, or single-slice recorded
- [ ] 5 Phase 3 base synchronized on the confirmed base
- [ ] 6 Phase 4 RED/GREEN/REFACTOR cycles committed
- [ ] 7 Phase 4B simplicity retrospective concluded
- [ ] 8 Phase 5 suite, review, and final gate passed with the full roster reported
```

## Invocation

Accept the shared invocation contract verbatim. Read it in
`workflow-contracts/references/workflow-contracts.md`; it is not restated here.

For a direct natural-language invocation, translate the request into that
contract, mark `caller: direct`, and confirm the scope, commit subject, and base
with the user before executing.

## What this engine adds

### Scope validation

Accept paths inside the repository's Java, test, build, and migration
directories. When `project.modules` is configured, reject a path in a module the
list does not name — a new module is a structural decision the user makes, not
one the engine infers from a path.

### Build and test commands

Every command comes from `project-config`. Never hardcode `./mvnw` or
`./gradlew`, and never assume a task name the project has not exposed. When a
needed command is absent from the resolved set and has no override, return
`NEEDS_INPUT` naming the command and the configuration field that supplies it.

At Phase 5, the "complete suite and build" is `build.commands.full_build`. It is
the first full build of the workflow; every earlier stage used the focused
selection from the `TEST_SCOPE_LEDGER`.

### Migration collisions

At Phase 3, after the base merge, scan the project's migration directory for
duplicate version prefixes. A collision that involves a migration this branch
created stops for manual resolution — never rename, renumber, or edit either
side. Recheck uniqueness again before returning `PASS`, since the base can
advance during a long workflow.

Never edit a migration that exists on the base branch. Its checksum is validated
on startup everywhere it has already run.

### The test leg

When the diff adds or changes HTTP API behavior, run `api-test-workflow` at
Phase 5 step 3 under the directional contract. The test files it produces are
workflow-owned: this engine stages and commits them under the stable subject
with body stage `TESTS`. Record its evidence, or an evidence-backed
not-applicable reason when no API surface changed.

Route a `PRODUCT_DEFECT` it reports by where the defective code lives. Code in
this repository is fixed here, following the same grouping and approval rules as
a review finding: collect the defects with their reproduction evidence, group
them by exclusive owned resource, present the grouping as a plan revision for
approval, derive a RED test from each failing scenario, integrate in dependency
order, then rerun the failing selection with `execution_only: true`. A defect is
resolved only when its originating scenario passes. A defect outside the
declared scope is a user decision, never a silent widening.

### Gates

At the final gate, invoke `quality-gate` and `security-scan` with
`checkpoint: final`. Both return a full roster including their skipped gates.
Report that roster unchanged in the result: a gate that did not run is named
with its reason, and the workflow never describes its output as having passed
checks that were skipped.

A gate whose effective mode is `BLOCKED_REQUIRED_MISSING` stops the workflow.
The project configured that gate as required; the resolution is to install the
tool or to change the configuration, and neither is the engine's to do.

## Result

Return a `SPRING_WORKFLOW_RESULT` containing every field the shared result
contract lists, plus:

```yaml
  migration_collision: {checked: true, duplicates: [], resolved_by: user | not_applicable}
  build_commands_used: [command, what it proved]
  gate_roster: [id, configured, effective, outcome, evidence]
```

The caller uses this result for tracker or pull-request reporting. Do not post
it anywhere.

## Example

Invoked directly for a change with no work item:

```text
Claude Code: /spring-workflow clamp the checkout page size to the configured
maximum, scope src/main/java/com/example/orders/checkout

Codex: Use $spring-workflow to clamp the checkout page size to the configured
maximum in src/main/java/com/example/orders/checkout.
```

It translates that into the shared contract with `caller: direct`, then asks for
the commit subject and the confirmed base before touching anything.

`implement-task` invoking the same engine after an approved architecture
selection passes the contract directly:

```yaml
caller: implement-task
mode: feature
work_id: ORD-482
scope:
  paths: [src/main/java/com/example/orders/checkout]
architecture_plan: <SELECTED ARCHITECTURE_PLAN_RESULT>
commit_subject: "ORD-482 :: Reject checkout above the account limit"
branch:
  base_confirmed_by_user: true
```

Runs the shared phases, commits RED/GREEN/REFACTOR under that stable subject,
runs the API test leg because the checkout endpoint's error contract changed,
then the full Gradle build with the `quality-gate` and `security-scan` rosters.
Returns `SPRING_WORKFLOW_RESULT` with the commit, test, and gate evidence — with
`sonar` recorded as `SKIPPED_UNAVAILABLE` when the CLI is not installed, rather
than omitted. An unconfirmed base returns `NEEDS_INPUT` before any mutation.

## Guardrails

The shared guardrails in `workflow-contracts/references/workflow-contracts.md`
apply in full. In addition:

- Never hardcode a build or test command; every one comes from `project-config`.
- Never target a module absent from a configured `project.modules`.
- Never rename, renumber, or edit a migration to resolve a version collision.
- Never edit a migration that exists on the base branch.
- Never report a gate roster with the skipped entries removed.
- Never treat `SKIPPED_UNAVAILABLE` as coverage.
