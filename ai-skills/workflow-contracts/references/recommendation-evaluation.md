# Recommendation evaluation

How an engine dispositions raw review recommendations in
`mode: recommendation-evaluate-fix`, before changing a single file.

The premise: a reviewer's comment is evidence that something looked wrong, not
proof that it is. Implementing every comment produces churn and occasionally
breaks working code; dismissing them produces an author who ignores review.
Neither is acceptable, so each item is evaluated on its own evidence.

## Rules of evaluation

- **Evaluate before mutating.** No file changes during evaluation. An engine
  that starts fixing while still classifying loses the ability to report what it
  found versus what it did.
- **Never trust the caller's label.** A caller that pre-classified an item as a
  real fix or a false positive is supplying an opinion. Verify it.
- **One recommendation per row.** A comment containing three points is three
  rows. A comment that mixes a question with a request is two.
- **Evidence, not reasoning.** A disposition cites a file and line, a test, a
  contract, a standard, or a requirement. "This is fine" is not a disposition.
- **Preserve the reviewer's words.** The row carries the verbatim text. A
  paraphrase drifts, and the response the caller eventually posts must answer
  what was actually said.

## The dispositions

| Disposition | Meaning | Required evidence |
| --- | --- | --- |
| `REAL_FIX` | correct and in scope | the defect, and what will change |
| `ALREADY_FIXED` | valid, but already handled | the commit and line |
| `FALSE_POSITIVE` | the premise does not hold | the code, test, or contract that contradicts it |
| `DUPLICATE` | same point as another row | the row it duplicates |
| `OUTDATED` | referred to code the branch no longer has | the commit that removed or changed it |
| `RESPONSE_ONLY` | a question, not a change request | the answer |
| `INFORMATIONAL` | an observation with no action | why no action follows |
| `OUT_OF_SCOPE` | valid but belongs to other work | the scope boundary and the owning item |
| `AMBIGUOUS` | cannot be dispositioned without the reviewer | what is unclear and what would resolve it |

## Per-item evidence

Every row records what the tracker scope, the requirement map, and the standards
result say about it. A workflow-level invocation of those skills does not
satisfy this — the question is what *this item* is grounded in, and the answer
differs per item.

A row that cites no evidence from any of the three is not evaluated; it is
`AMBIGUOUS`.

## Handling each outcome

- `REAL_FIX` items become requirements for the remaining phases, each mapped to
  a regression test in Phase 2.
- `AMBIGUOUS` and `OUT_OF_SCOPE` return `NEEDS_INPUT` unless the caller supplies
  an explicit approved scope expansion. Never resolve an ambiguity by picking
  the interpretation that is easier to implement.
- Everything else produces a response the caller posts, with its evidence. A
  non-fix disposition with no response is indistinguishable from an ignored
  comment.

When no `REAL_FIX` remains, return `PASS` with the complete ledger and mark base
synchronization, TDD, gates, build, and review
`not_applicable_no_code_change`. A no-code result is a legitimate and common
outcome; it is not a failure to find work.

## The ledger

```yaml
recommendations:
  - id: R3
    source: {comment_id, author, url, path, line, side, state}
    text: verbatim
    disposition: FALSE_POSITIVE
    evidence:
      - "src/main/java/.../LimitService.java:88 already null-checks before the call"
      - "LimitServiceTest#rejectsNullAccount covers it"
    scope_evidence: "in scope: requirement R1"
    response: the text the caller will post
    fix_commit: null
```

Every row is returned, including the ones that produced no work. A ledger that
lists only the fixes hides the reviewer's points that were dismissed, which is
exactly what a reader of the result needs to check.
