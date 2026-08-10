---
name: fix-pr
description: Author-side workflow for addressing every reviewer comment on your own pull request — fetch the complete comment and thread graph, pass raw atomic recommendations to spring-workflow for evidence-backed evaluation, implement the confirmed fixes through the shared TDD and gate pipeline, then reply to each comment with either the fix commit or the evidence behind a non-fix disposition and resolve the completed threads. Also re-checks whether earlier feedback was actually addressed. Use when the user asks to address, fix, handle, respond to, or re-check feedback on their own pull request. Reviewing someone else's pull request is review-pr.
---

# Fix PR
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the author's side of a review conversation. Collect the feedback, get it
evaluated on evidence, deliver the fixes, and answer every comment.

The discipline this skill exists to enforce: **a reviewer's comment is a
recommendation, not an instruction.** Implementing all of them uncritically
produces churn and occasionally breaks working code. Dismissing them produces an
author nobody reviews carefully again. Each one is evaluated on its own
evidence, and each one gets an answer.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Complete comment and thread graph fetched
- [ ] 2 Atomic recommendations extracted verbatim
- [ ] 3 Evaluation complete; every item dispositioned with evidence
- [ ] 4 Confirmed fixes implemented through the engine
- [ ] 5 Replies composed and, with authorization, posted
- [ ] 6 Threads resolved only where a reply was posted
```

## Invocation

```yaml
caller: direct
mode: address | recheck
pr: <number or URL>
scope_expansion: null           # explicit user approval, when an item needs it
post: false                     # true only with explicit authorization
```

`mode: recheck` skips implementation and answers one question: for each earlier
comment, was it actually addressed, and where is the evidence?

## Phase 1 — Collect

Use `references/comment-contract.md`. Fetch the **complete** graph, not the page
the API returned first:

- top-level issue comments;
- review summaries and their events;
- inline review comments with their file, line, side, and diff hunk;
- every reply in every thread, in order;
- each thread's resolved and outdated state;
- the commits pushed since each comment, so an item can be checked against what
  the branch now contains.

A comment missed here is a comment the author appears to have ignored. When
pagination or permissions prevent a complete fetch, say so and name what is
missing rather than proceeding on a partial graph.

Then split into **atomic recommendations**. One comment containing three points
is three items; a comment mixing a question with a request is two. Keep the
verbatim text on every item — the reply must answer what was actually written,
and a paraphrase drifts.

## Phase 2 — Evaluate

Do not evaluate here, and do not decide which comments are right. Pass the raw
items to `spring-workflow` in `mode: recommendation-evaluate-fix` with the
tracker, requirement, and standards context.

The engine evaluates each item against the code before touching a file, and
returns the dispositions defined in
`workflow-contracts/references/recommendation-evaluation.md`: `REAL_FIX`,
`ALREADY_FIXED`, `FALSE_POSITIVE`, `DUPLICATE`, `OUTDATED`, `RESPONSE_ONLY`,
`INFORMATIONAL`, `OUT_OF_SCOPE`, `AMBIGUOUS`.

Never pre-label an item before passing it. A caller-supplied conclusion is an
opinion the engine is required to verify independently, and supplying one
invites it to be rubber-stamped.

An `AMBIGUOUS` item is returned to the user, not resolved by choosing the
interpretation that is easiest to implement. An `OUT_OF_SCOPE` item follows the
scope-holding procedure: defer it to the owning work item with an approved
comment, or obtain an explicit scope expansion.

## Phase 3 — Deliver

The engine implements the confirmed fixes through the full pipeline — test
inventory, RED/GREEN/REFACTOR under the stable commit subject, the configured
gates, and independent review. Handle its result as `implement-task` does:
`PASS` continues, `NEEDS_INPUT` surfaces verbatim, `BLOCKED` stops.

When the engine returns `PASS` with no `REAL_FIX`, that is a complete and
legitimate outcome. Every comment still gets a reply; there is simply no commit
to cite.

## Phase 4 — Reply

Read `references/response-style.md` before composing anything.

Every actionable comment receives exactly one reply:

- **A fix reply** cites the commit hash and names the solution path — what
  changed and why that resolves the point. A reply that says "fixed" without
  either forces the reviewer to go looking.
- **A non-fix reply** cites the concrete evidence: the line of code, the passing
  test, the contract, or the requirement that contradicts the premise. Never
  reasoning alone; "I considered this and it's fine" is indistinguishable from
  not having checked.
- **A question** gets an answer.

Posting is a required approval. Show the user every reply and its target, then
post on an explicit yes. When they decline, return the composed replies so they
can post them, and record the decline.

Resolve a thread only after its reply is posted, and only when the point is
actually settled. Resolving an unanswered thread hides it from the reviewer,
which is the one outcome worse than not replying.

Never resolve a thread the reviewer opened to disagree with a non-fix
disposition. That conversation belongs to them.

## Recheck mode

For each earlier comment, produce one of:

- `ADDRESSED` — with the commit and the line that addresses it;
- `NOT_ADDRESSED` — with what the branch still contains;
- `PARTIALLY_ADDRESSED` — with what was done and what remains;
- `ANSWERED_NOT_FIXED` — a non-fix disposition with a posted reply carrying its
  evidence;
- `NO_RESPONSE` — no fix and no reply. This is the finding the mode exists to
  surface.

Check against the current branch state, not against what the session believes
was done. Recheck posts nothing and changes nothing; it reports.

## Result

```yaml
FIX_PR_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  pr: {number, url, head, base}
  graph: {comments, threads, complete: true | partial with what is missing}
  recommendations:
    - id: R1
      source: {comment_id, author, url, path, line, side, thread_state}
      text: verbatim
      disposition: <one of the nine>
      evidence: [what proved it]
      fix_commit: hash | null
      reply: {text, posted: true | false, url}
      thread_resolved: true | false
  engine_result: <SPRING_WORKFLOW_RESULT>
  recheck: [comment id, verdict, evidence]        # mode: recheck
  approvals: [action, approver, timestamp]
  limitations: [unfetched comments, declined posting, deferred item]
```

Every item is returned, including those that produced no work. A result listing
only the fixes hides the comments that were dismissed, which is exactly what a
reader needs to check.

## Example

Addressing feedback without posting yet:

```text
Claude Code: /fix-pr 214

Codex: Use $fix-pr for pull request 214.
```

Fetches all eleven comments across four threads, splits them into fourteen
atomic items, and passes them to the engine. The engine confirms four
`REAL_FIX`, one `ALREADY_FIXED`, two `FALSE_POSITIVE` with the contradicting
lines, six `INFORMATIONAL`, and one `AMBIGUOUS` — which is returned to the user
rather than guessed. After the fixes land, the composed replies are shown and
nothing is posted until an explicit yes.

## Guardrails

- Never edit, stage, or commit code here; the engine owns every mutation.
- Never pre-label a recommendation before passing it to the engine.
- Never post a reply, resolve a thread, or push without explicit authorization
  of that exact content.
- Never resolve a thread whose reply was not posted.
- Never resolve a thread where the reviewer is still disagreeing.
- Never leave an actionable comment without a reply.
- Never reply "fixed" without the commit and the solution path.
- Never dismiss a comment on reasoning without concrete contradictory evidence.
- Never widen scope to satisfy a reviewer; an out-of-scope item is a user
  decision.
- Never proceed on a partial comment graph while presenting it as complete.
- Never use this skill to review someone else's pull request.
