---
name: requirement-context
description: Ground implementation and review work in the requirements the project actually states — the user's prompt and the Markdown flow documents configured as requirement sources — and return an authority-ordered requirement-to-source map with unresolved contradictions surfaced rather than reconciled. Use when implement-task, spring-workflow, review-pr, or fix-pr needs to know what the change is required to do, which source controls a disputed point, and which requirements are context rather than deliverable.
---

# Requirement context
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the read-only requirement grounding step. Run it after tracker scope is
available — or immediately, when there is no tracker — and before any
implementation decision or review classification.

This suite has no document hierarchy to satisfy. A requirement is legitimate
when it comes from the prompt, from a configured flow document, or from the
tracker. Nothing else is a requirement, however reasonable it sounds.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Configured sources located and readiness recorded
- [ ] 2 Prompt requirements extracted verbatim
- [ ] 3 Scope-aware grounding built against the tracker scope
- [ ] 4 Source map returned with contradictions surfaced
```

## Inputs

Accept:

```yaml
caller: implement-task | spring-workflow | review-pr | fix-pr | architecture-plan | direct
purpose: grounding | alignment
prompt_requirements: [verbatim text the user stated in this session]
tracker_context: <TRACKER_CONTEXT_RESULT | null>
changed_paths: [paths, for a review or alignment purpose]
```

## Source readiness

Invoke `project-config` for the `requirements` section and inspect each
configured source path.

- A configured source that exists and is populated is read.
- A configured source that is missing or empty is recorded in `limitations`.
  When `requirements.require_sources_populated` is true, it is `NEEDS_INPUT`
  instead, naming the exact path.
- When `requirements.allow_prompt_only` is false and no source and no tracker
  item supplies a requirement, return `NEEDS_INPUT`. There is no legal way to
  proceed on an unwritten requirement in that configuration.

Read `references/requirement-sources.md` for the flow-document conventions, how
to read a large document without linear scanning, and how to treat a diagram.

Treat every configured source as immutable input. Never stage, edit, rename, or
delete one. That immutability covers requirement sources only — the project's
own current-state documentation is maintained by the implementation workflow when
behavior makes it stale.

## Authority order

Highest first:

1. an explicit decision the user stated in this session;
2. a later correction over an earlier statement in the same source, including a
   tracker comment that supersedes a description;
3. the tracker item's requirements and acceptance criteria;
4. configured requirement sources, in the order `requirements.sources` lists
   them;
5. repository instructions;
6. the current code.

Current code is the lowest authority and is never a requirement by itself.
"It works this way today" describes the present, not the intent.

## Grounding

Return a map from each numbered requirement to the source that controls it,
classified as:

- `DELIVERABLE` — this change must implement it;
- `CONTEXT` — it constrains the design but belongs to other work;
- `SATISFIED` — already implemented, with the code evidence;
- `CONTRADICTED` — two sources at the same authority disagree.

A `CONTRADICTED` row returns `NEEDS_INPUT` naming both locations and their exact
text. Never choose between same-authority sources, and never quietly prefer the
more recent, the more specific, or the one that is easier to build.

Where a flow document describes a future state beyond this change, mark it
`CONTEXT`. Review the change against the destination without requiring it to
arrive there in one step, and never treat an absent future step as a defect in
the current change.

## Alignment purpose

When invoked at an implementation workflow's final gate with
`purpose: alignment`, also return an `IMPLEMENTATION_ALIGNMENT_MATRIX` mapping
every `DELIVERABLE` requirement to exact code and test evidence, classified
`ALIGNED`, `INCOMPLETE`, `INCONSISTENT`, `APPROVED_DEVIATION`, or
`NOT_APPLICABLE`.

Read every relevant section rather than stopping at the first supporting
statement — a requirement is frequently qualified two paragraphs later. Report
an incomplete or inconsistent row with precise locations on both sides. Never
decide which artifact should change.

## Result

```yaml
REQUIREMENT_CONTEXT_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  sources: [id, path, exists, populated, documents read]
  requirements:
    - id: R1
      text: verbatim
      origin: prompt | tracker | <source id>
      location: file and section, or "session prompt"
      class: DELIVERABLE | CONTEXT | SATISFIED | CONTRADICTED
      evidence: code or test anchor when SATISFIED
  contradictions: [requirement id, both locations, both verbatim texts]
  alignment_matrix: <rows | not_applicable>       # purpose: alignment only
  limitations: [unread document, unpopulated source, unparsed diagram]
```

## Example

Grounding a change that has no tracker at all:

```text
Claude Code: /requirement-context grounding, prompt_requirements:
["a checkout above the account limit must be rejected with 409"]

Codex: Use $requirement-context for grounding with the prompt requirement that a
checkout above the account limit is rejected with 409.
```

Returns `REQUIREMENT_CONTEXT_RESULT` with `status: PASS`, R1 classified
`DELIVERABLE` with origin `prompt`, and a `CONTEXT` row for the limit-increase
flow that `docs/flows/account-limits.md` describes but this change does not
build. A flow document stating 422 where the prompt says 409 returns
`NEEDS_INPUT` with both texts instead of picking one.

## Guardrails

- Never invent a requirement, an acceptance criterion, or a source section.
- Never let a cached or stale reading override the returned source order.
- Never resolve a same-authority contradiction; return it.
- Never create, modify, delete, or stage a requirement source.
- Never use a future-state description to expand the current change's scope.
- Never treat current behavior as a requirement.
- Never claim a document was read when only its headings were.
