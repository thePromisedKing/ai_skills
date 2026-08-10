# Skill authoring standards

Acceptance criteria for every skill this suite creates or materially changes. A
change that fails a dimension is not ready to propose.

A skill is not a one-shot prompt. It is progressively disclosed and selected by
the model from many candidates, so authoring is governed by **Trigger, Concise,
Freedom, Disclosure, Eval**.

Never copy this document's prose into a skill; reference it. Duplicated
authoring text across skills is itself a violation.

## Contents

- Trigger — the description that drives selection
- Concise — token cost
- Freedom — matching specificity to fragility
- Disclosure — progressive loading and file organization
- Eval — evaluations before documentation
- Feedback loops
- Output contracts
- Worked example
- Workflow checklists
- Content patterns
- Terminology
- Constants and dependencies
- Tone
- Known deviations
- Anti-patterns

## Trigger

The `description` field is the most important line in a skill. It is how the
model chooses this skill over every other installed option.

- Write in the imperative, naming the action: `Apply …`, `Own …`, `Resolve …`,
  `Run …`. Every skill in this suite does; a third-person description reads as
  the outlier.
- State both **what** the skill does and **when** to use it. A description that
  only lists capability cannot be selected reliably.
- Name the nearest sibling and redirect to it where it is the better owner, so
  overlapping triggers resolve deterministically. `review-pr` and `fix-pr` are
  the canonical pair: each names the other.
- Use concrete terms a caller would actually type.
- Under 1024 characters, no angle brackets.

## Concise

- Keep `SKILL.md` under roughly 500 lines.
- Assume the model is capable. Add only what it cannot infer: this project's
  contracts, ownership, gates, and conventions.
- Challenge every line with "does the model actually need this?" Delete restated
  general knowledge, narrated rationale, and motivational text.
- Never restate a dependency's procedure. Invoke the owner; when it cannot be
  invoked, return `NEEDS_INPUT` with its exact manual invocation.
- Every communication a skill emits — result, checkpoint prompt, progress note,
  error — is compact. Compactness never justifies dropping a finding, an
  approval request, a limitation, or evidence a reader needs to decide; cut
  restated context and filler instead.

## Freedom

Match specificity to fragility.

- **High freedom** — prose and stated objectives — where judgment is wanted:
  design assessment, classification, review reasoning.
- **Medium freedom** — a parameterized script or template — where a preferred
  pattern exists and bounded variation is fine.
- **Low freedom** — exact commands and fixed sequences — where the order is
  load-bearing and a wrong step is expensive: migrations, gates, base
  synchronization, commit sequences, credential handling.

State which mode a step is in when it is not obvious. Never give a fragile
operation prose latitude, or a judgment task a rigid script.

## Disclosure

- Treat `SKILL.md` as a table of contents: the contract, the ordered workflow,
  and pointers.
- Push detail one level into `references/<topic>.md`, loaded only when the step
  needs it. Do not nest deeper.
- Scripts are executed rather than loaded, so they cost no context. Prefer a
  script for deterministic repeated work, and handle its errors inside it rather
  than deferring them to the agent.
- A reference over 100 lines opens with a `## Contents` list naming its real
  headings, so a `head -100` preview reveals the file's full scope.
- Name files by content — `gate-resolution.md`, never `doc2.md`.
- Carry large context by pointer and fingerprint. Never inline a full diff, a
  requirement document, or a complete tracker payload.

## Eval

- Define at least three evaluations before writing extensive instructions.
- Baseline the model **without** the skill first, then write the minimum needed
  to pass. Instructions that change no outcome are noise.
- Exercise the real contract, including a `NEEDS_INPUT` path and a declined
  approval — not only the happy path.
- Record the evaluations and their outcomes.

What this suite actually has, stated plainly so a proposal does not claim more:

- `tests/suite-contract-test.sh` — the structural and contract-text regression
  layer. It is the suite's only automated check, and per the rule above **it is
  not an evaluation**.
- a proposal-time forward test — one representative prompt through the changed
  skill, judged against its result contract, recorded case by case.
- no stored behavioral evaluation harness and no per-skill baselines.

Treat the third as the suite's open gap. A change that adds or alters a
governance contract states which evaluations it ran, and records the absent
baseline as a limitation rather than implying three exist. Building the harness
is its own approved change, not a side effect of the next contract edit.

## Feedback loops

- Where output quality is checkable, structure the step as validate, fix,
  repeat, and say explicitly that the workflow proceeds only once validation
  passes.
- Make a validator's failure specific and actionable: name the offending item
  and the accepted alternatives. Never surface a raw stack trace for the agent
  to interpret.
- For a batch or high-stakes operation, emit a verifiable intermediate artifact
  and validate it before executing: analyze, plan, validate the plan, execute,
  verify. That catches an error while it is still reversible.

## Output contracts

Compact by construction: preserve the essentials, minimize tokens.

- Declare exactly one authoritative result contract, in `SKILL.md`.
- Never compress away the floor: `status` with its explicit enum, the payload
  the caller branches on, unresolved `conflicts`, `violations` with evidence
  pointers, and `limitations`.
- Compact in this order: flat keys over nested objects unless nesting carries
  meaning; enums over prose; one-line list items such as
  `[path, line, rule, evidence]` over an object per finding; pointers over
  inlined payloads; omit an empty collection rather than emitting scaffolding.
- Prohibited: echoing the caller's input back, decorative prose inside the
  contract, per-field commentary the field name already conveys, and restating a
  sibling's result instead of referencing it.
- Target 25 lines or fewer. Exceed it only when every extra field is one a
  caller branches on. An aggregator sits near that ceiling; a terminal skill
  lands closer to ten.

## Worked example

Every skill carries at least one compact example: a realistic invocation and the
result it produces.

- Show the smallest invocation that exercises the real contract, not the fullest.
- Give both vendor forms, since the suite installs into Claude Code and Codex
  alike: `Claude Code: /<skill> …` and `Codex: Use $<skill> …`. A single-form
  example leaves half the users without a usable invocation.
- Name one failure or boundary path — a `NEEDS_INPUT` trigger, a rejected scope,
  a declined approval — so the example teaches the contract's edges.
- Use obviously fake values. Never a credential, token, key, or real personal
  data, and never an invented live payload.
- Claim only what the contract guarantees. An example asserting a field the
  contract does not define is a defect, not an illustration.
- The example illustrates use; it never restates the contract field by field.

## Workflow checklists

A skill with distinct sequential phases carries a checklist the agent copies
into its response and ticks off. It is what stops a long workflow silently
skipping a gate.

- One line per phase, in execution order, naming the phase's **completion
  condition** rather than its activity.
- Keep it near the top of `SKILL.md`, before the phases it tracks.
- Track phases, not tool calls.
- A single-step skill needs none. Say so rather than inventing ceremony.

Exempt in this suite, recorded so the absence is a decision: the read-only
standards skills (`engineering-standards`, `java-engineering-standards`,
`test-engineering-standards`) return one result from a single evaluation, and
`workflow-contracts` is reference material with no workflow. Every other skill
carries one.

## Content patterns

At every create or modify, classify which apply and record the choice with its
reason. "None" is a valid answer that still has to be stated.

| Pattern | Use when | Shape |
| --- | --- | --- |
| Template | the output has a required structure a reader or parser depends on | an exact block marked strict, or a default marked adaptable |
| Examples | quality depends on seeing the intended style | input/output pairs with obviously fake values |
| Conditional | the workflow branches on a decision the agent must make explicitly | a named decision point with each branch's route |

Mark a template strict or adaptable. An unmarked template gets followed
literally when it was a starting point, or freely when it was a contract.

Do not add an examples block where a result contract already pins the shape.

## Terminology

One term per concept, used everywhere — within the skill and across the skills
that call it. Drift between `check`, `gate`, and `validation`, or between `work
item`, `ticket`, and `issue`, makes a contract ambiguous exactly where precision
matters.

This suite's settled terms: **work item** (never ticket or issue), **gate**
(never check or validation), **finding** (never issue), **engine** (the skill
that owns mutations), **adapter** (a tracker transport), **roster** (the full
gate list including skips).

When a sibling names a concept, adopt its term. Renaming a shared concept is its
own change, swept across every skill that uses it.

## Constants and dependencies

- Every hard-coded constant carries its justification. A timeout, retry count,
  cap, or threshold with no stated reason cannot be adjusted safely later. If
  the right value is unknown, say so rather than inventing a precise-looking one.
- Never assume a package, binary, or service is installed. Name it, give the
  safe detection command, and provide the setup path.
- A script handles its own errors and reports them in terms the agent can act
  on. Surfacing a raw stack trace defers the work to the caller.

## Tone

Governs a skill's own communication — results, checkpoints, progress notes,
errors.

- Precise, neutral, factual. State findings and obligations plainly.
- Address the reader as a competent engineer. No filler, no motivational
  framing, no apology, no narration of the agent's process.
- Report outcomes faithfully. A failure, a skipped step, or an unverified
  assumption is stated as such.
- No emoji in a skill contract, result, or generated output.
- Outward-facing review and reply style is an explicit exception, owned by
  `review-pr/references/review-style.md` and
  `fix-pr/references/response-style.md`.

## Known deviations

Recorded so a conformance check does not silently pass.

**Description voice.** Upstream guidance prefers third-person descriptions; this
suite mandates the imperative and every skill follows it. Upstream's stated risk
is inconsistent point of view, which a uniformly imperative suite does not
carry, and converting one skill at a time would create exactly the mixed voice
the rule guards against. A conformance verdict records this as
`DEVIATION (documented)` rather than a pass.

**No per-skill README.** The suite `README.md` carries routing and each
`SKILL.md` is self-describing. A second human-facing copy of every contract is a
second thing to keep true, and it drifts first. Revisit if the suite is handed
to readers who will not open a `SKILL.md`.

## Anti-patterns

- A description that states capability but never when to use the skill.
- Offering several approaches where one default plus an escape hatch will do.
- `claude` or `anthropic` in a skill `name`; both are reserved.
- An MCP tool named without its server prefix.
- Time-sensitive content: dates, "new", "currently", version-of-the-day claims.
- Backslash or platform-specific paths; use forward slashes.
- A multi-phase workflow with no progress checklist.
- An unmarked template.
- A constant with no stated justification.
- Boilerplate role text that would read identically in any sibling.
- An example mirroring the result contract field for field, or carrying a
  credential, token, key, or real personal data.
- A rule stated in two skills. One of them is now wrong and nobody knows which.
