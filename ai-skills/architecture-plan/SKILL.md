---
name: architecture-plan
description: Compare genuinely different implementation approaches for a change against the grounded requirements and engineering standards, present them with honest trade-offs, and require an explicit human selection before any code is written. Use when spring-workflow, implement-task, or fix-pr reaches the point of deciding how to build something, when a later discovery invalidates a previously selected approach, or when the user asks for options before implementation.
---

# Architecture plan
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the decision of *how* to build the change. Present comparable approaches and
stop for a human selection. Never choose, never begin implementing, and never
return a plan the caller may treat as approved.

The value of this skill is not the plan. It is that the decision becomes
explicit, recorded, and attributable before the code exists — which is the only
point at which changing it is cheap.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Current-code evidence gathered
- [ ] 2 Two or more genuinely different approaches derived
- [ ] 3 Trade-offs, risks, and rejected options stated
- [ ] 4 Selection obtained from the user, or NEEDS_INPUT returned
```

## Invocation

Accept:

```yaml
caller: spring-workflow | implement-task | fix-pr | direct
requirements: [grounded DELIVERABLE requirements with their sources]
requirement_context: <REQUIREMENT_CONTEXT_RESULT>
standards: <ENGINEERING_STANDARDS_RESULT>
scope: {paths: [...], modules: [...]}
prior_decisions: [confirmed decisions this plan must not contradict]
superseded_plan: <a previously selected plan being revisited, or null>
```

## Derive the approaches

1. Read the code the change touches and the nearest analogous flow already in
   the repository. A plan written without reading the current code is a guess
   dressed as an option.
2. Derive at least two approaches that differ in something that matters — where
   the behavior lives, what it depends on, what it changes about existing
   contracts, how much it costs to reverse. Three variations of the same design
   are one approach with cosmetic differences, and presenting them as choices
   wastes the user's decision.
3. Always include the smallest approach that fully satisfies the requirements,
   even when it is unfashionable. It is the baseline every other option must
   justify itself against.
4. Where no genuine alternative exists — the repository has one established
   pattern for this and deviating would be worse — say so, present the single
   approach with the alternatives you rejected and why, and still require the
   selection. A forced choice between a real option and a strawman is worse than
   an honest single option.

## What each approach states

- **What changes** — the files, types, and boundaries, concretely enough that a
  reader can picture the diff.
- **Why it fits** — the requirement it satisfies and the standard or existing
  pattern it follows, cited.
- **What it costs** — new dependencies, new abstractions, migration, operational
  surface, and the tests it obliges.
- **What it risks** — the failure mode it introduces or fails to address:
  compatibility, concurrency, data, performance, security, rollback.
- **How reversible it is** — the single most under-weighted property in this
  comparison. An approach that is wrong but cheap to undo is usually better than
  one that is probably right and permanent.
- **What it forecloses** — the future change it makes harder.

State the trade-offs honestly, including for the approach you would recommend.
A comparison written to justify a preferred answer is not a comparison.

## Recommend, then stop

Give a recommendation with its reasoning. A comparison with no recommendation
pushes the analysis back to the user, who asked for it precisely because they
wanted it done.

Then stop. `architecture_selection` is in `approvals.required` by default: the
workflow may not proceed on a recommendation, an inferred preference, a previous
similar decision, or silence. Only an explicit selection counts.

When the user selects an approach with a modification, restate the modified
approach in full and confirm it. A modification carried forward as a remembered
aside is how the selected plan and the built thing diverge.

## Result

```yaml
ARCHITECTURE_PLAN_RESULT:
  status: SELECTED | NEEDS_INPUT | BLOCKED
  approaches:
    - id: A
      summary: one line
      changes: [file or boundary, what happens to it]
      fit: [requirement id, standard or pattern cited]
      cost: [dependency, abstraction, migration, test obligation]
      risk: [failure mode and its severity]
      reversibility: cheap | moderate | permanent, with why
      forecloses: [what becomes harder]
  rejected: [approach considered and the concrete reason it was dropped]
  recommendation: {id, reasoning}
  selected: {id, approver, modifications, timestamp} | null
  handoff:                                    # present only when selected
    implementation_outline: [ordered steps]
    boundaries: [what the implementation may and may not touch]
    invalidation_triggers: [evidence that would make this plan wrong]
  documentation_change_proposal: [source document that should change, and how]
  limitations: [unread code, unverified assumption]
```

`status: SELECTED` requires a non-null `selected` block with a real approver.
Returning `SELECTED` on anything else is a contract violation, not an
optimization.

`invalidation_triggers` is what a later phase checks against. Name the concrete
evidence — "the limit turns out to be per-currency", "the existing service is
not transactional" — not "if assumptions change".

## Revisiting a selected plan

When later evidence shows the selected approach is materially worse or unsafe,
the caller returns here with that evidence and the superseded plan. Present the
revision as a fresh comparison including the cost of what has already been
built, and require a new explicit selection. Record the supersession; never
delete or rewrite the original decision.

Do not revisit a plan because a test failed or because a different approach now
looks more appealing. Curiosity is not evidence.

## Example

An engine reaching the decision point:

```text
Claude Code: /architecture-plan for the grounded requirements of "reject a
checkout above the account limit", scope src/main/java/com/example/orders/checkout

Codex: Use $architecture-plan for the grounded checkout-limit requirements in
src/main/java/com/example/orders/checkout.
```

Returns `ARCHITECTURE_PLAN_RESULT` with `status: NEEDS_INPUT`, two approaches —
enforcing in the existing checkout service versus a separate limit-policy
component — the recommendation and its reasoning, and `selected: null` awaiting
the user. Only after the user names an approach does a `SELECTED` result with a
handoff exist.

## Guardrails

- Never select an approach. Never proceed on a recommendation.
- Never write, edit, stage, or commit code; this skill produces a plan only.
- Never present variations of one design as alternatives.
- Never omit the simplest viable approach.
- Never propose a new abstraction, dependency, or infrastructure component
  without naming the concrete benefit it buys over not having it.
- Never contradict a prior confirmed decision without surfacing it as a
  supersession requiring its own approval.
- Never claim to have read code that was not read; record it as a limitation.
