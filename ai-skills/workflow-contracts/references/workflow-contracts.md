# Shared implementation workflow contracts

The owning document for every rule an implementation engine follows. No engine
may fork it; each references it and adds only what is genuinely specific to its
own build tool, gates, and test levels.

## Contents

- Invocation contract
- Holding the declared scope
- The engine and test-leg relationship is directional
- Escalation: returning to an earlier stage
- Result contract
- Phase 0 — Validate and preflight
- Phase 1 — Classify, then require architecture selection
- Phase 2 — Complete test inventory
- Phase 2A — Plan parallel execution
- Phase 3 — Synchronize the confirmed base
- Phase 4 — Committed TDD cycles
- Phase 4B — Simplicity retrospective
- Phase 5 — Regression, review, and the final gate
- Guardrails

## Invocation contract

Require the caller to invoke the engine through the runtime's skill mechanism
(`Skill` tool, `/<engine>`, or `$<engine>`) and pass:

```yaml
caller: implement-task | review-pr | fix-pr | api-test-workflow | direct
mode: feature | review-fix | recommendation-evaluate-fix
work_id: external identifier for Git metadata and scratch artifacts only; null when no tracker
title: human-readable change title
objective: requested outcome
requirements:
  - id: stable caller-local id
    text: requirement or confirmed real review finding
    evidence: source anchor when applicable
recommendations:            # required only for recommendation-evaluate-fix
  - id: stable caller-local id
    source: comment id, author, URL, path/line/side, state
    text: verbatim atomic recommendation or question
    chronology: relevant ordered thread context
scope:
  paths: [allowed repository paths]
  modules: [allowed modules when project.modules is configured]
context:
  tracker: <TRACKER_CONTEXT_RESULT | null>
  requirements: <REQUIREMENT_CONTEXT_RESULT>
  standards: <ENGINEERING_STANDARDS_RESULT reference and fingerprint>
  project_config: <PROJECT_CONFIG_RESULT reference and fingerprint>
decisions: [already confirmed user decisions]
architecture_plan: <SELECTED ARCHITECTURE_PLAN_RESULT, or null>
branch:
  current: branch name
  suggested_base: candidate only
  base_confirmed_by_user: false
review:
  parent_managed: false     # true only for a review-triggered nested fix
  parent_round: 0
test_link:
  direction: engine-to-tests | tests-to-engine | none
  origin: <skill that started the chain>
  hop: 0                    # ceiling 2
commit_subject: rendered from commit.subject_template; stable for the whole workflow
external_actions: caller-owned; never perform
```

If a field needed for safe execution is absent, return `NEEDS_INPUT` naming it.
Do not reconstruct tracker or pull-request context, and do not silently widen
scope.

Require `commit_subject` before the first mutation and retain it unchanged for
the entire workflow when `commit.require_stable_subject` is true. Reject a
stage, slice, or changing suffix.

`requirements` may be empty only for `recommendation-evaluate-fix`, where raw
`recommendations` are mandatory and the engine derives requirements from
confirmed `REAL_FIX` dispositions.

Reject an invalid recursion contract before doing any work:

- `caller: review-pr` with `mode: review-fix` requires
  `review.parent_managed: true` and `parent_round` in `1..max_rounds`;
- no other caller may set `review.parent_managed: true`;
- a parent-managed run may never invoke `review-pr`.

For a direct natural-language invocation, translate the request into this
contract, mark `caller: direct`, and confirm the missing scope, commit subject,
and base with the user before executing.

## Holding the declared scope

### With a tracker

When `context.tracker` carries a work item, that item defines the deliverable.
A parent, epic, child, or linked item is context; it does not authorize work.

When implementation, a review finding, or a test failure shows that work outside
the declared scope is also needed:

1. Stop before touching those paths. Never widen the change.
2. Identify the owner: search the item graph for an existing sibling or linked
   item that already covers it, and name it.
3. Present to the user and stop for a decision: the concrete evidence, the named
   candidate item for the deferral or the statement that none exists, and the
   alternative of an explicit approved scope expansion.
4. On a deferral, ask the user to approve one comment through `tracker-context`
   in `mode: defect` on the named item. The engine never writes to the tracker;
   the caller owns the write and its approval.
5. Record the deferral in the result: the evidence, the named item, the posted
   comment or the decline, and the fact that this change's deliverable is
   complete without it.

Never convert an out-of-scope discovery into code in this run, and never return
`PASS` while one is unrecorded.

### Without a tracker

With `tracker.adapter: none` or a direct invocation, no item holds the boundary.
Before touching anything beyond what the user described:

1. Warn explicitly, naming the original scope and the addition.
2. State what is broken and why the addition appears necessary.
3. Stop and ask. Continue only on an explicit yes; a general instruction to
   "fix it" is not approval to widen scope.
4. Record the warning, the answer, and the resulting scope.

The absence of a tracker never means the scope is open.

## The engine and test-leg relationship is directional

The engine and its API test leg may call each other, so every invocation
declares which direction it travels. Without that, the two loop forever.

**`engine-to-tests`** — the engine runs its test leg at Phase 5, before the
independent review and the final gate. It sets `direction: engine-to-tests`,
`origin` to itself, and increments `hop`. The test workflow it invokes may not
invoke the engine back: it classifies its failures and returns them, and the
engine — already in its own run — performs the fixes.

**`tests-to-engine`** — a test workflow running standalone finds a
`PRODUCT_DEFECT` and, with explicit user approval, asks the engine to fix it. It
sets `direction: tests-to-engine`, `origin` to itself, and increments `hop`. The
engine may not run its test leg for that surface: it implements the fix, reruns
only the failing selection with `execution_only: true`, and returns.

Enforced before any work:

- reject `hop` greater than 2 with `BLOCKED`, naming the chain and its origin;
- reject a crossing that would reverse the direction, with `BLOCKED`. A chain
  terminates; it never turns around;
- reject a missing or inconsistent `origin` with `NEEDS_INPUT`; never infer it;
- require explicit approval before the first crossing in either direction, and
  again for `tests-to-engine`, since it turns a test run into a code change;
- carry `test_link` unchanged into every result.

Never repair, infer, or reset a `test_link` to make a chain continue.

## Escalation: returning to an earlier stage

A workflow that discovers its current stage rests on a wrong earlier decision
escalates to the stage that owns it. Pressing on with a plan the evidence no
longer supports produces work that has to be redone, and it buries the moment
the plan became wrong.

Escalation is available from every phase and is never treated as failure. A
workflow that reaches its result having ignored contradicting evidence has
failed; one that stops and returns has not.

**Valid triggers.** The selected approach is materially worse or less safe than
an alternative the current evidence supports; a requirement or source is now
understood differently; the test inventory misses a risk the implementation
exposed; the problem is materially larger, smaller, or differently shaped than
assumed; a gate finding cannot be resolved inside the current approach without
weakening a standard; another skill owns the work better; a prior decision is
contradicted by new evidence.

Curiosity is not a trigger. Escalate on evidence, naming it.

**How.** Stop at the phase boundary, leaving no partial mutation or running
gate. State the trigger, the evidence, the decision it contradicts, and the
owning stage. Name what the return invalidates — the architecture handoff, the
test inventory, downstream gate evidence — because everything derived from a
superseded decision is stale until rebuilt. Obtain explicit approval; declining
is valid and recorded. On approval, return with the evidence attached and record
the supersession in the workflow context ledger. Rebuild only what was
invalidated; preserve committed work that remains correct.

**Bounds.** Escalate at most twice for the same decision; a third time means the
disagreement is not resolvable inside the workflow, so stop with `NEEDS_INPUT`
and hand the user the competing options. Never escalate to widen scope. Never
escalate merely because a test failed — treat that as a regression first.

## Result contract

Each engine returns its own named result containing:

- `status`: `PASS`, `NEEDS_INPUT`, or `BLOCKED`;
- the complete raw-recommendation ledger with evidence-backed dispositions when
  `mode: recommendation-evaluate-fix`;
- response evidence for every non-fix disposition;
- the containing commit hash and solution path for every real or already-fixed
  recommendation;
- confirmed branch and original base;
- a requirement-to-code-and-test coverage map;
- the complete test inventory and its actual outcomes;
- decisions, assumptions, and approved deviations;
- every escalation — trigger, evidence, superseded decision, approver, what was
  rebuilt — including declined ones;
- the `ARCHITECTURE_PLAN_RESULT` and selected handoff;
- every `documentation_change_proposal`, carried unchanged for human follow-up;
- RED/GREEN/REFACTOR commit evidence with stable subject and body traceability;
- the approved parallel plan, group ownership ledger, collision events, and
  integration order;
- the full gate roster with each gate's effective mode and outcome, including
  every `SKIPPED_DISABLED` and `SKIPPED_UNAVAILABLE`;
- regression and build evidence;
- the test leg's evidence, or an evidence-backed not-applicable reason;
- the independent-review verdict and how each finding was handled;
- out-of-scope deferrals with their evidence and outcome;
- `test_link` carried unchanged;
- changed files and remaining limitations.

The caller uses this result for tracker or pull-request reporting. The engine
never posts it.

## Phase 0 — Validate and preflight

Maintain a `BRANCH_FRESHNESS_RESULT` throughout. At entry, before reusing an
architecture handoff, immediately before mutation, before freezing the final
snapshot, and before returning delivery evidence, refresh the relevant remote
refs with the user-authorized fetch command and record:

- local head, upstream head, confirmed-base head, fetch time, ref names;
- ahead/behind counts for local versus upstream and base versus feature;
- `CURRENT`, `REMOTE_FEATURE_AHEAD`, `BASE_ADVANCED`, or `DIVERGED`;
- whether a rebase would rewrite a published commit, and the safer merge
  alternative.

Do not continue from `REMOTE_FEATURE_AHEAD` or `DIVERGED` without a user
decision. A stale cached fetch is not current evidence. Never rebase, force
push, reset, or rewrite history automatically.

Then:

1. Read the work contract, the repository instructions, and the local status.
   Stop for unrelated worktree changes that overlap scope.
2. Invoke `project-config` and require a passing result. Every branch, command,
   gate, and approval decision below comes from it.
3. Load or initialize the workflow context ledger from `engineering-standards`
   before any material decision. Revalidate it at the start of every phase.
4. Refuse a detached HEAD and any branch in `branches.protected`. Ask the user
   to confirm the current feature branch or choose another.
5. Treat `suggested_base` as evidence, never authority. Infer candidates from
   upstream, reflog, fork-point, and merge-base, then ask the user to confirm
   the exact original base. For `recommendation-evaluate-fix`, defer that
   question until evaluation finds at least one `REAL_FIX` — a no-code result
   needs no merge decision. Set `base_confirmed_by_user: true` only from an
   explicit answer.
6. Invoke `engineering-standards` with the scope, source authority, and
   `purpose: implementation`. Require a passing result carrying the applicable
   specializations. Do not reinvoke a specialization the aggregator already
   returned. Cache passing tracker, requirement, and standards results by head
   object id, exact scope, and source fingerprint; reuse until one changes.
7. Defer `quality-gate` and `security-scan` to the final gate. At each TDD
   stage run focused tests and applicable hygiene only. An unrun gate is a
   pending obligation, never clean evidence.
8. Invoke `quota-handoff` only after a real quota, rate-limit, or session-budget
   signal — not at ordinary phase boundaries.

If a dependency cannot be invoked, return `NEEDS_INPUT` with its payload and its
exact manual invocation. Never copy a dependency's procedure into the engine.

## Phase 1 — Classify, then require architecture selection

For `mode: recommendation-evaluate-fix`, first read
`recommendation-evaluation.md` and evaluate every raw recommendation. Do not
trust the caller's technical conclusion and do not modify files during
evaluation. Evaluate each item against the tracker scope, the requirement map,
and the standards result, recording the applicable or contradictory evidence in
its ledger row. A workflow-level invocation of those skills does not satisfy the
per-item requirement.

Return `NEEDS_INPUT` for any `AMBIGUOUS` or `OUT_OF_SCOPE` item unless the caller
supplies an explicit approved scope expansion. Convert only in-scope `REAL_FIX`
items into requirements. When real fixes exist, complete the deferred base
confirmation before test planning. If no `REAL_FIX` remains, return `PASS` with
the complete ledger and mark base sync, TDD, gates, and review
`not_applicable_no_code_change`.

Invoke `architecture-plan` with the scoped requirements, the passing context
results, current-code evidence, the candidate base, and prior decisions. Require
a `SELECTED` result before test planning, base synchronization, worktree
creation, or any mutation. Reuse a caller-supplied handoff only when its scope,
head, and source fingerprints match; otherwise return its `NEEDS_INPUT`
unchanged. Never choose an approach in the engine.

The requirement source map stays active after this phase. Before every
implementation decision, test-strategy change, gate remediation, and newly
discovered finding, recheck the relevant evidence and record it. Treat a
discrepancy or missing backing as `NEEDS_INPUT`; never silently reconcile it.
Before each material edit, commit, or remediation, require a passing
`DECISION_INVARIANT_CHECK` from the ledger.

When later evidence reveals a materially different or safer approach, invalidate
the handoff and return to `architecture-plan`. Rebuild the test inventory only
after the user selects the revised plan. Revert only workflow-owned changes.

## Phase 2 — Complete test inventory

Before production code, invoke `test-engineering-standards` with
`purpose: inventory` and map every requirement and identified risk to:

- an exact test file and a behavior-oriented name;
- a test level drawn from `testing.levels`, with the reason a cheaper level
  cannot prove it;
- preconditions and fixtures;
- the action and the observable assertions;
- the expected RED failure;
- environment limitations.

Also produce, and carry through the workflow:

- a `FEATURE_FLAG_STATE_MATRIX` for every flag the change adds, removes, or
  depends on, covering both enabled and disabled topology and rollback;
- a `DOCUMENTATION_IMPACT_LEDGER` built through `documentation-maintenance.md`.

For `review-fix` and `recommendation-evaluate-fix`, map every confirmed finding
to at least one regression test or executable verification. Never invent a
meaningless test. When a non-behavioral finding cannot support RED/GREEN,
explain the verification plan and ask before using it as an explicit exception.

Do not continue while any requirement or confirmed finding is unmapped.

## Phase 2A — Plan parallel execution

Before any mutation, derive and present one `PARALLEL_PLAN` assigning every
slice to a group, containing: dependencies and precedence; exclusive paths,
types, tests, migrations, and build files; isolated worktree and branch names;
focused verification; integration order; and the number of active groups, never
more than `parallel.max_concurrent_groups`.

Group only slices with no overlapping owned resource and no dependency. Put
shared resources, migrations, build changes, and uncertain ownership into
ordered groups. Obtain explicit approval before creating worktrees or mutating a
group. The approval is invalid once source, tests, discovered dependencies, or
resource fingerprints change.

Each group works only in its isolated worktree and branch. It may commit its own
stages but must not stage, commit, merge, or push the feature branch — the
coordinator owns integration. After each group completes, run its focused tests
and an independent read-only revision of that group.

Monitor each active group's declared and observed path, symbol, test, migration,
and dependency fingerprints. On a collision, stop launching affected groups: let
the group that owns the resource finish its current atomic stage, block the
later group, and report the evidence. If two active groups already modified a
shared resource, integrate neither — return `NEEDS_INPUT` with both patches and
the options. Never auto-resolve a conflict or continue a blocked group.

A single-slice change needs no groups. Say so rather than inventing ceremony.

## Phase 3 — Synchronize the confirmed base

Merge from the original base into the feature branch; never rewrite feature
history.

1. Show the exact confirmed base and ask the user to confirm proceeding.
2. Fetch it, record the feature-created migrations relative to it, then run
   `git merge --no-ff --no-commit origin/<confirmed-base>`.
3. Never resolve a merge conflict. Collect the unresolved paths with
   `git diff --name-only --diff-filter=U`, show them, and pause for the user to
   resolve every one manually. Do not edit conflict markers, choose a side,
   stage a resolution, abort, or continue until the user says the resolution is
   complete. Then verify no unresolved entries remain and inspect the merge.
4. Scan for duplicate migration version prefixes. A collision involving a
   feature migration stops for manual resolution; never rename or edit either
   side automatically.
5. If incoming changes affect the selected architecture, return to
   `architecture-plan` before rebuilding the test inventory.
6. Run the affected regression tests. Record the merged scope for the final
   snapshot; run no gate for the pending merge commit.

Recheck base advancement and migration uniqueness before returning `PASS`.

## Phase 4 — Committed TDD cycles

Execute approved groups, at most `parallel.max_concurrent_groups` active. Within
a group, run one coherent slice at a time with focused tests at each stage. The
coordinator integrates completed groups in dependency order, checks fingerprints
before every integration, and stops rather than resolving a conflict. Do not run
`quality-gate` or `security-scan` per commit: the final gate analyzes the
integrated snapshot once.

Before the first RED run, create a `TEST_SCOPE_LEDGER` mapping each slice's
changed behavior, symbols, and boundaries to the smallest test selection and
scoped build evidence that can prove it. Use that selection through RED, GREEN,
REFACTOR, and every remediation. Expand it only when an observed failure proves
the recorded scope incomplete, and update the ledger with that evidence. Do not
run the complete suite during an implementation cycle for reassurance — the
feedback loop is only useful while it is fast.

### RED

1. Add only planned tests.
2. Run them and prove the failure comes from missing behavior, not broken setup.
3. Stage only the RED files.
4. Rerun to confirm the same intentional failure.
5. Commit with the stable subject and the RED body.

### GREEN

1. Add the smallest production change that passes the slice.
2. Run the slice tests green.
3. Stage only the GREEN files.
4. Rerun the affected tests.
5. Commit with the stable subject and the GREEN body.

### REFACTOR

1. Improve structure using existing idioms without changing behavior.
2. Run tests before and after; stage only the refactor files.
3. Rerun and commit with the stable subject and the REFACTOR body.
4. When no refactor is warranted, record that fact. Never create an empty commit.

Before every commit: stop on a detached HEAD or a protected branch; enforce
every applicable hygiene rule from `engineering-standards`; stage only
workflow-owned files; recheck the documentation impact ledger and update stale
tracked documentation in the same coherent slice; record the evidence the final
gate remediation can use.

### Commit message contract

Every TDD-stage commit in one workflow uses the identical subject —
`commit_subject`, rendered from `commit.subject_template`. Never append the
stage, the slice, or any changing suffix.

Changing detail goes in the body:

```text
TDD stage: RED | GREEN | REFACTOR | TESTS

Slice: <coherent behavior; for TESTS, the covered scenario ids>

<what changed and why, with the test and hygiene evidence>

Traceability:
- Work item: <id and title>          # only when a tracker is configured
- Requirement: <id> from <source>    # every source that controls this slice
```

Include every source that actually controls the slice; omit the rest. The body
is Git metadata, not a tracked repository artifact.

## Phase 4B — Simplicity retrospective

Read `simplicity-retrospective.md` and challenge the integrated implementation
against the confirmed base, the selected architecture, and the simplest viable
alternative. Prefer the smallest change that preserves every requirement and
quality control. A bounded simplification needs explicit approval before another
REFACTOR cycle; a material one returns to `architecture-plan`. Never revert a
workflow-owned commit or replace the chosen approach without showing the exact
scope and receiving authorization. After any simplification, rerun the focused
tests and this retrospective.

## Phase 5 — Regression, review, and the final gate

1. Review the entire diff against the confirmed base.
2. Run the complete test suite and the project's build for the first time in
   this workflow, using the commands `project-config` resolved. Record what each
   command actually proved. When the project carries pre-existing failures,
   capture the baseline at the confirmed base first, so a failure this change
   did not introduce is reported as pre-existing rather than attributed to it or
   used to block it.
3. Run the API test leg when the diff changes HTTP behavior, before the
   independent review and the final gate. Supply the context and the
   confirmed-base-to-head diff as code evidence, and stop at its plan
   checkpoint. The test files it produces are workflow-owned: stage and commit
   them under the stable subject with body stage `TESTS`, so the review sees
   them and the final gate scans them. Treat its failures like review findings.
   Record its evidence, or an evidence-backed not-applicable reason.
4. Unless `review.parent_managed: true`, read `independent-review.md` and invoke
   `review-pr` in `review-and-fix` mode. When parent-managed, skip this, record
   the parent round, and return the regression evidence to the parent.
5. For review findings, return to the relevant phase and repeat the gate. Treat
   a finding as a false positive only with concrete contradictory evidence, and
   record that evidence.
6. Invoke `requirement-context` with `purpose: alignment` against the immutable
   final snapshot. Return to the relevant phase for implementation findings;
   return `NEEDS_INPUT` for unresolved source contradictions. Never return
   `PASS` with an `INCOMPLETE` or `INCONSISTENT` row.
7. Refresh and require a passing `BRANCH_FRESHNESS_RESULT`, freeze one clean
   base-to-head snapshot, and publish a `FINAL_GATE_PLAN` with no more than
   `parallel.max_concurrent_groups` independent read-only lanes. Run the
   complete regression, the applicable test suites in `execution_only` mode,
   `quality-gate` with `checkpoint: final`, and `security-scan` with
   `checkpoint: final`, concurrently where their resources do not conflict.
   Every lane records the same final commit and snapshot fingerprint.

   Gate skills materialize private temporary indexes; they never stage or change
   the live worktree. Do not begin remediation, edit documentation, or otherwise
   mutate the branch while a lane is running. Collect and classify every result
   first, obtain the required approvals, then remediate serially or in isolated
   owned groups. Any mutation invalidates every result from the old snapshot:
   rebuild it and rerun the plan. Never reuse a report or approval fingerprint
   from an invalidated snapshot.

## Guardrails

- Never fetch or mutate tracker or pull-request comments, create pull requests,
  push, reply, resolve threads, or publish caller-owned reports.
- Never accept a caller's false-positive or real-fix label without independent
  evidence in `recommendation-evaluate-fix`.
- Never modify files for a non-`REAL_FIX` recommendation.
- Never modify a requirement source identified as immutable.
- Never weaken behavior or add a suppression to satisfy a gate.
- Never violate a rule returned by `engineering-standards`.
- Never embed or partially reproduce `engineering-standards`, `project-config`,
  `quota-handoff`, `security-scan`, `quality-gate`, `review-pr`,
  `architecture-plan`, or the test leg.
- Never let an engine/test chain reverse direction or exceed hop 2.
- Never run the test leg for a surface while serving a `tests-to-engine` chain
  for it; rerun only the failing selection with `execution_only: true`.
- Never touch a path outside the declared scope. A discovery is a user decision.
- Never post a tracker comment directly; route it through `tracker-context` and
  let the caller own the write.
- Never discard unrelated changes.
- Never claim tests, a gate, a build, or a review ran without evidence.
- Never report a skipped gate as a pass.
- Never return `PASS` while required work remains.
- Never wait on a caller-owned external write before returning a result.
