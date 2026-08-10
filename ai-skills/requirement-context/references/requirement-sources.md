# Requirement sources

How to read the project's flow documents and the user's prompt as requirements,
and how to tell a requirement from everything else in the same file.

## Contents

- The flow document convention
- Reading a large document
- Extracting requirements from a prompt
- What is not a requirement
- Diagrams and tables
- Conflict patterns worth catching
- Starting a flow document

## The flow document convention

A flow document describes one user-visible or system flow. The suite does not
impose a template, but it reads these headings when present, and a project that
uses them gets more precise grounding:

```markdown
# Checkout — account limit enforcement

## Purpose
One paragraph: what this flow is for and who uses it.

## Actors
Who or what participates.

## Preconditions
What must already be true.

## Flow
1. Numbered steps, each observable.

## Rules
- Numbered or bulleted business rules. This is the section requirements are
  most often extracted from.

## Errors
- The failure cases and what the caller sees.

## Out of scope
What this flow deliberately does not cover.

## Open questions
Unresolved decisions. Anything here is NOT a requirement.
```

`Rules` and `Errors` carry most of the requirements. `Out of scope` and
`Open questions` are the two sections that most often prevent a wrong
implementation, and both are routinely skipped by a reader in a hurry.

A document with none of these headings is still read; extract requirements from
its prose and record the section anchor. A document that is a design sketch,
meeting notes, or a proposal is `CONTEXT` at most — say so rather than mining it
for obligations.

## Reading a large document

- Locate the sections that bear on the change: the entities, the endpoints, the
  states, the error cases named in the tracker item or the prompt. Read those
  fully.
- Then read `Out of scope`, `Open questions`, and any section that qualifies a
  rule you already found. Requirements are frequently qualified two paragraphs
  after they are stated, and a partial read produces a confidently wrong
  implementation.
- Do not read a long document linearly from the top. It costs context and
  reaches the qualifying paragraph last, if at all.
- Record what you read. A requirement extracted from a section is anchored to
  that section; a requirement with no anchor is not grounded.
- When a document is too large to read the relevant parts within the session's
  budget, say so in `limitations` naming what went unread. A partial read
  reported as complete is worse than a stated gap.

## Extracting requirements from a prompt

The user's own words are the highest-authority source. Extract them verbatim,
one requirement per obligation, and do not paraphrase into something tidier —
paraphrase is where a requirement quietly changes meaning.

- A statement of desired behavior is a requirement: "reject a checkout above the
  account limit with 409".
- A statement of constraint is a requirement: "without changing the existing
  response shape".
- A statement of preference is a requirement when it is actionable: "use the
  existing limit service rather than a new one".
- An aside, a rationale, or an example is not a requirement, but it is evidence
  about intent. Record it as context.

When the prompt is ambiguous in a way that changes the implementation, that is
`NEEDS_INPUT` — not an assumption recorded and built on.

## What is not a requirement

- Anything under `Open questions`.
- Current behavior, unless a source states it must be preserved.
- A comment in the code.
- A reasonable inference about what the user probably also wants.
- A pattern from a neighbouring flow that nobody applied to this one.
- A best practice this suite's standards recommend. Standards constrain *how*
  the requirement is built; they do not add requirements.

Each of these can still be worth raising with the user. Raise it as a question,
not as a row in the requirement map.

## Diagrams and tables

- A table of states, transitions, error codes, or field rules is usually the
  most precise statement in the document. Read it before the prose that
  describes it, and prefer it when the two disagree at the same authority — but
  report that disagreement rather than silently preferring one.
- An embedded diagram (Mermaid, PlantUML, an image) carries requirements the
  prose may omit: a branch, a retry, an ordering. Read the diagram source when
  it is text. When it is an image, inspect it and record what it showed; when it
  cannot be read, record that in `limitations` rather than assuming the prose
  covers it.

## Conflict patterns worth catching

These are the disagreements that cause the most rework, and they are all
`CONTRADICTED` rather than something to resolve:

- the prompt and a flow document specify different status codes, limits, or
  field names for the same behavior;
- two flow documents describe the same rule with different thresholds;
- the tracker item's acceptance criteria contradict its own description, with no
  comment establishing which is later;
- a flow document's `Rules` section and its `Errors` section disagree about what
  happens on the same input;
- a source states a behavior the current code contradicts, with no indication
  whether the code is the bug or the document is stale.

The last one is worth a specific note: report it as `CONTRADICTED` between the
source and the code, and let the user say which is authoritative. Assuming the
document is stale is how a documented requirement gets quietly dropped;
assuming the code is wrong is how a deliberate exception gets removed.

## Starting a flow document

When a project has no requirement sources yet and wants them, the smallest
useful starting point is one document per flow the team argues about — not a
document per class or per endpoint. A flow document earns its place when it
settles a question that otherwise gets re-decided; one that restates the code
adds a second thing to keep current and answers nothing.
