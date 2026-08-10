---
name: review-pr
description: Generate an evidence-backed review of a pull request or a local branch — inspect the complete diff and existing discussion, route specialist read-only reviewers through engineering-standards, classify findings by confidence and severity, and optionally submit one GitHub review with explicit authorization. Also serves an implementation engine's internal independent review over a local base-to-head range. Use when the user asks to review or re-review a pull request, wants a pre-review brief before reading a diff, or when an engine requests its independent review. Addressing feedback on your own pull request is fix-pr.
---

# Review PR
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the reviewer's perspective. Read the change, judge it against the project's
grounded requirements and standards, and produce findings that carry evidence.

Two callers, one procedure. A human asking for a review of someone else's pull
request and an engine asking for its own independent review want the same
analysis; they differ only in what happens to the output.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Target resolved and diff fetched in full
- [ ] 2 Context grounded: requirements, standards, existing discussion
- [ ] 3 Specialist reviewers routed and results collected
- [ ] 4 Findings classified, deduplicated, and evidence-checked
- [ ] 5 Output delivered: returned to the engine, or submitted with authorization
```

## Invocation

```yaml
caller: spring-workflow | fix-pr | direct
mode: review | brief | review-and-fix
target: pull-request | local-branch
pr: <number or URL>            # target: pull-request
base: <ref>                    # target: local-branch
head: <ref>
round: 0                       # 1..review.max_rounds for review-and-fix
context: {tracker, requirements, standards references}
submit: false                  # true only with explicit authorization
```

`mode: brief` produces the orientation document a human reads before reviewing
line by line — the change's shape, its risky areas, and what to check — and
submits nothing. `mode: review` produces findings. `mode: review-and-fix` is the
engine's internal review; it returns findings to the engine and never touches
GitHub.

## Read the change

1. Invoke `project-config` and `engineering-standards` for the changed paths.
2. Fetch the **complete** diff. A truncated diff produces a review that misses
   what it never saw and reads as though it looked. When the diff is too large
   to read entirely, say so, name what was read, and review that — a partial
   review declared partial is useful; one presented as complete is not.
3. For a pull request, read the existing discussion first: prior review threads,
   the author's replies, and what has already been resolved. A finding someone
   already raised and the author already answered is noise, and repeating it
   costs the review its credibility.
4. Ground the change: invoke `requirement-context` so findings can be judged
   against what the change was required to do, rather than against what the
   reviewer would have built.

## Route specialist reviewers

Read `references/review-generation.md` for the lenses and how to route them.

Specialist reviewers are read-only. Give them the diff, the grounded context,
and one lens each; collect their findings concurrently within
`parallel.max_concurrent_groups`. A reviewer with write tools stops reviewing
and starts fixing, and then nobody has reviewed the fix.

## Classify

Every finding is classified before it leaves this skill:

| Confidence | Meaning |
| --- | --- |
| `CONFIRMED` | verified against the code; the failure scenario is concrete |
| `PLAUSIBLE` | consistent with the code read, not verified end to end |
| `DISCARDED` | contradicted by evidence found while checking it |

| Severity | Meaning |
| --- | --- |
| `BLOCKING` | correctness, security, data, or contract defect on a reachable path |
| `IMPORTANT` | a real problem that will cost later — resource, concurrency, missing test, maintainability in code that will be read |
| `MINOR` | style, naming, small simplification |

Verify before reporting. Open the file, read the surrounding code, and check
whether the failure scenario actually holds. A finding that dissolves on
inspection is `DISCARDED` and never reaches the output — the cost of a wrong
finding is not the reviewer's time, it is the author's, plus the credibility of
every other finding in the same review.

Deduplicate against the existing discussion and against the other reviewers'
results.

## Deliver

**To an engine** (`review-and-fix`): return the findings. Fix nothing. Record
the round.

**To GitHub** (`review`, `submit: true`): submitting is a required approval and
is never inferred from the request to review. Show the user the complete review
body and every inline comment, then submit exactly one review — `COMMENT` or
`REQUEST_CHANGES` — on an explicit yes. Never approve on the user's behalf:
approval is a human's judgment about accepting the change.

**To the user** (`submit: false`, the default): return the findings as text.
This is the common case and needs no authorization.

Read `references/review-style.md` before writing anything outward-facing.

## Result

```yaml
REVIEW_PR_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  target: {kind, pr, base, head, commits, files, additions, deletions}
  diff_coverage: complete | partial with what was read
  brief: <orientation text>              # mode: brief
  findings:
    - id: F1
      severity: BLOCKING | IMPORTANT | MINOR
      confidence: CONFIRMED | PLAUSIBLE
      category: correctness | security | concurrency | contract | performance | testing | maintainability
      path: file
      line: 1-indexed
      summary: one sentence
      failure_scenario: concrete inputs or state, and the wrong outcome
      evidence: [what was read to confirm it]
      suggestion: the smallest change that resolves it
  discarded: [what was checked and the evidence that dissolved it]
  duplicates: [finding, the existing thread it repeats]
  submitted: {review_id, event, url} | not_submitted with reason
  round: integer
  limitations: [unread portion, unverifiable claim, skipped lens]
```

Report `discarded` findings. They are evidence the review actually checked
rather than pattern-matched, and they stop the next round re-raising them.

## Example

Reviewing a pull request without submitting:

```text
Claude Code: /review-pr 214

Codex: Use $review-pr for pull request 214.
```

Returns `REVIEW_PR_RESULT` with the full diff read, two `CONFIRMED` findings —
an unbounded page size on a new collection endpoint, and a missing test for the
rejection path — one `DISCARDED` with the line that contradicted it, and
`submitted: not_submitted` because no authorization was given. Adding
`submit: true` shows the composed review and waits for an explicit yes.

## Guardrails

- Never modify, stage, or commit code in `review` or `brief` mode.
- Never submit a review, post a comment, or resolve a thread without explicit
  authorization of that exact content.
- Never submit an `APPROVE` event.
- Never report a finding without opening the code and checking it.
- Never present a partial diff read as a complete review.
- Never repeat a finding the existing discussion already resolved.
- Never review against a preference the project's standards and requirements do
  not support.
- Never invoke `review-pr` from a parent-managed run; that recursion is
  `BLOCKED`.
- Never fix findings in `review-and-fix`; return them to the engine.
