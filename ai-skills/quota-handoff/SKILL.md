---
name: quota-handoff
description: Preserve and transfer an active workflow between the authenticated Claude Code and Codex CLIs when a real quota, rate-limit, throttling, compaction, or explicit session-budget signal arrives at a phase boundary. Use when another skill hits such a signal mid-workflow and must continue safely in the other vendor without concurrent work on the same branch or lost decisions. Do not use for ordinary phase transitions or to pre-emptively poll remaining capacity.
---

# Quota handoff
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the transfer of an in-flight workflow from one vendor CLI to the other.

The failure this prevents is not running out of quota — it is running out
halfway through Phase 4 with three committed TDD stages, an approved
architecture selection, a confirmed base, and none of it written down anywhere
the other CLI can find. The transfer is cheap; reconstructing the context is
not, and reconstructing it wrong is worse than starting over.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Trigger verified as a real signal, not an assumption
- [ ] 2 Safe phase boundary confirmed; no partial mutation left behind
- [ ] 3 Target vendor confirmed authenticated
- [ ] 4 Handoff package written and verified readable
- [ ] 5 Transfer approved and the source session stopped
```

## Invocation

```yaml
caller: <the workflow that hit the signal>
signal:
  kind: quota | rate_limit | throttling | compaction | session_budget
  evidence: the exact message, header, or response observed
  observed_at: phase and step
workflow_state:
  ledger_reference: the workflow context ledger
  phase: current phase
  branch: {name, base, head}
preferred_target: claude | codex
```

## Verify the trigger

Continue only on a **real** signal with evidence: a rate-limit response, an
explicit quota message, a throttling header, a compaction event, or a
user-stated session budget.

Return `NOT_TRIGGERED` for anything else — a slow response, a long session, a
sense that capacity is running low, or a phase boundary that merely felt like a
good moment. A handoff performed without a trigger costs a session restart and
loses the working context it was meant to protect.

Never poll this skill at ordinary phase boundaries.

## Confirm a safe boundary

A handoff happens at a phase boundary, never mid-mutation. Before packaging:

- no uncommitted partial TDD stage;
- no in-progress merge with unresolved conflicts;
- no running gate or lane;
- no active worktree group mid-integration.

When the workflow is not at a safe boundary, return `NEEDS_INPUT` naming what
must complete first. Finishing the current atomic stage is almost always
possible and is the right answer; abandoning it is not.

## Confirm the target

Probe the target vendor's authentication with its documented non-interactive
status command, through `engineering-standards` with `purpose: routing`. Never
infer authentication from a binary on `PATH` or a config file on disk.

An unauthenticated target is `BLOCKED` with the exact command the user runs to
authenticate. Do not attempt an interactive login — the agent cannot complete
one, and a half-finished login leaves a worse state than none.

## Package the handoff

Write to private scratch storage, and verify it reads back:

```yaml
HANDOFF_PACKAGE:
  workflow: skill name and invocation contract, verbatim
  phase: where to resume, and what the next step is
  branch: {name, base, base_confirmed_by_user, head, clean: true}
  decisions: [every confirmed decision with its approver]
  approvals: [what was approved, by whom, and exactly what it covered]
  architecture_plan: the SELECTED handoff
  test_inventory: the plan and what has been proven so far
  commits: [hash, stage, slice]
  gates: [id, effective mode, outcome so far]
  open_items: [what remains, in order]
  limitations: [what could not be preserved]
  source_session: vendor and the signal that triggered the transfer
```

Carry pointers and fingerprints, not payloads. A handoff package that inlines
the diff, the requirement documents, and the full standards result is a package
the receiving session cannot read without spending the context it was given.

Never place a credential, token, or secret in the package.

## Transfer

1. Show the user the package and the exact invocation the target vendor runs to
   resume.
2. Obtain explicit approval. A handoff changes which tool is doing the work and
   requires a session switch; it is not automatic.
3. On approval, return `STARTED`. **The source session stops there.** It runs no
   further phase, makes no further commit, and touches the branch no more.

The one rule that makes this safe: **never two sessions on one branch.** Both
believing they own the integration produces interleaved commits, a corrupted
parallel plan, and evidence nobody can attribute. The source stops before the
target starts.

On a declined transfer, return `NEEDS_INPUT` with the package preserved, so the
user can continue in the current session or transfer later without repackaging.

## Result

```yaml
QUOTA_HANDOFF_RESULT:
  status: NOT_TRIGGERED | STARTED | NEEDS_INPUT | BLOCKED
  signal: {kind, evidence, observed_at} | null
  boundary: safe | unsafe with what must complete
  target: {vendor, authenticated, resume_invocation}
  package_reference: scratch reference and fingerprint
  approver: who approved the transfer
  limitations: [state that could not be preserved]
```

A caller continues only on `NOT_TRIGGERED`. On `STARTED` it stops. `NEEDS_INPUT`
and `BLOCKED` are handled explicitly, never by proceeding as though the handoff
had not been attempted.

## Example

An engine hitting a rate limit between phases:

```text
Claude Code: /quota-handoff signal kind rate_limit with the 429 observed at
Phase 4 step 2, preferred_target codex

Codex: Use $quota-handoff for a rate_limit signal observed at Phase 4 step 2,
targeting codex.
```

Verifies the 429 is real, confirms Phase 4's current stage is committed and the
tree clean, probes Codex authentication, writes the package, shows the resume
invocation, and waits. Returns `STARTED` only after an explicit yes — and the
Claude session then stops. An unauthenticated Codex returns `BLOCKED` with the
login command instead.

## Guardrails

- Never hand off without a real signal and its evidence.
- Never hand off mid-mutation, mid-merge, or mid-gate.
- Never leave both sessions active on the same branch.
- Never infer a vendor's authentication state; probe it.
- Never attempt an interactive login.
- Never place a credential or a large payload in the package.
- Never invent a quota percentage, a capacity figure, or a model identifier.
- Never continue the source workflow after returning `STARTED`.
- Never be invoked by polling; only a real signal starts this.
