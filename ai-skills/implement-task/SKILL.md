---
name: implement-task
description: Tracker-facing shell for implementing a work item end to end — resolve its scope through tracker-context, ground the requirements through requirement-context, delegate every code mutation and gate to spring-workflow, then publish the implementation report and the pull request from the returned evidence. Use when the user names a work item to implement, asks to pick up or develop a ticket, or asks for a change to be delivered end to end including its pull request. Works with no tracker at all, taking requirements from the prompt and flow documents.
---

# Implement task
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the outside of the change: the work item, the requirement grounding, the
pull request, and the report. Own none of the inside — every file edit, test,
commit, and gate belongs to `spring-workflow`.

This separation is what lets the same engine serve a tracked ticket, an untracked
request, and a review-driven fix without three copies of the lifecycle.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Project configuration resolved
- [ ] 2 Work item scope resolved, or no-tracker run recorded
- [ ] 3 Requirements grounded and contradictions cleared
- [ ] 4 Architecture approach selected by the user
- [ ] 5 Engine run complete with a passing result
- [ ] 6 Pull request prepared and, with authorization, created
- [ ] 7 Report posted, or handed back for the user to post
```

## Phase 1 — Resolve

1. Invoke `project-config`. A failing validation stops here; nothing downstream
   is safe on a configuration the suite could not read.
2. Invoke `tracker-context` in `mode: read` with the work-item id or the
   discovery evidence from the branch and recent commits. With
   `tracker.adapter: none`, record a no-tracker run and continue — this is a
   normal path, not a degraded one.
3. Invoke `requirement-context` with `purpose: grounding`, passing the tracker
   result and the user's own words from this session verbatim. A `CONTRADICTED`
   row stops for the user to resolve; never choose between sources.
4. Render the commit subject from `commit.subject_template` and confirm the
   implementation title with the user. This subject is fixed for the whole
   workflow.

## Phase 2 — Decide

Invoke `architecture-plan` with the grounded requirements, the standards result,
and the scope. Present its comparison and stop for the user's selection.
`architecture_selection` is a required approval; a recommendation is not one.

## Phase 3 — Delegate

Invoke `spring-workflow` with the shared invocation contract: the selected
handoff, the grounded requirements, the scope, the confirmed branch and base,
and the stable commit subject. Pass the context results by reference and
fingerprint rather than re-embedding them.

Handle its result:

- `PASS` — continue to Phase 4.
- `NEEDS_INPUT` — surface exactly what it asked for. Never answer on the user's
  behalf, and never re-invoke with an invented value.
- `BLOCKED` — report the blocker and stop. A gate configured as required with no
  available tool is the common case, and it is resolved by the user.

Never implement anything here. If the engine cannot be invoked, return
`NEEDS_INPUT` with its exact manual invocation rather than doing its work.

## Phase 4 — Publish

Both external writes are gated on approvals that are required by default.

**Pull request.** Prepare the branch, the title, and a body built from the
engine's evidence: what changed and why, the requirement-to-test coverage map,
the gate roster including every skipped gate with its reason, and the remaining
limitations. Show it to the user. Create it only on an explicit yes, and only
after `push` is separately authorized — pushing and opening a pull request are
two decisions, and a project may allow one and not the other.

**Report.** Compose the implementation report and post it through
`tracker-context` in `mode: report`, with the user's approval of that exact
text. Require the engine's `PASS` result as the evidence; a report on an
incomplete run misrepresents the state to everyone who reads the item.

**Transition.** Only after the pull request exists, and only when the adapter
supports it and the configuration names a target status, invoke
`tracker-context` in `mode: transition` with explicit approval.

When the user declines any of these, that is a valid outcome. Return the
prepared text so they can post it themselves, and record the decline.

## Report contents

The report is read by someone who was not in the session. It states:

- what was implemented, in the requirement's terms rather than the code's;
- the branch, the base, and the pull-request link;
- each requirement mapped to its tests;
- the gate roster: what ran, what passed, what was skipped and why;
- decisions and approved deviations, with who approved them;
- limitations, including anything automation could not prove and the named
  manual scenario for it;
- deferred out-of-scope discoveries and where they went.

Never claim a gate ran when it was skipped. Never imply coverage the run did not
produce. A report that overstates is worse than no report, because it stops
anyone else from checking.

## Result

```yaml
IMPLEMENT_TASK_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  work_item: {id, url} | null
  engine_result: <SPRING_WORKFLOW_RESULT>
  branch: {name, base, head}
  pull_request: {url, created: true | false, declined_reason} | not_applicable
  report: {posted: true | false, target, text_reference}
  transition: {from, to, verified} | not_applicable | unsupported
  approvals: [action, approver, timestamp]
  limitations: [...]
```

## Example

Implementing a tracked item end to end:

```text
Claude Code: /implement-task ORD-482

Codex: Use $implement-task for ORD-482.
```

Resolves the item and its links, grounds the requirements against
`docs/flows/checkout.md`, presents two approaches and waits, delegates to
`spring-workflow`, then prepares the pull request and the report and waits again
before either external write. With `tracker.adapter: none`, the same invocation
with a described change runs identically, minus the item and the report target.

## Guardrails

- Never implement, edit, stage, or commit code. That is the engine's, without
  exception.
- Never create a pull request, push, post a comment, or transition an item
  without explicit approval of that specific action.
- Never post a report on a non-`PASS` engine result.
- Never answer a `NEEDS_INPUT` on the user's behalf.
- Never expand scope beyond the work item or the described change.
- Never claim an external write succeeded without the verification the adapter
  returned.
- Never reproduce a dependency's procedure; invoke it, or return its manual
  invocation.
