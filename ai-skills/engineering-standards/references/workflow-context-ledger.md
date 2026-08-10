# Workflow context ledger

A session-isolated record of every material decision a multi-phase workflow
makes, so a later phase cannot silently contradict an earlier one and a resumed
or handed-off session can see what was already settled.

## Why it exists

A long workflow makes decisions in Phase 1 that Phase 5 depends on: the selected
approach, the confirmed base, an approved deviation, a scope boundary the user
drew. Without a record, a later phase re-derives them from partial context and
quietly picks differently. The ledger makes contradiction detectable instead of
invisible.

## Where it lives

In the agent's private scratch storage for this session — never in a tracked
repository file, never in the work tree, never committed. It holds decisions and
pointers, not payloads: a source reference and fingerprint, never an inlined
document, diff, or tracker record.

Callers pass the ledger *reference and fingerprint* to downstream skills. They
do not re-embed its contents.

## What each entry records

```yaml
- id: stable within the session
  phase: the phase that made it
  kind: decision | assumption | discovery | approval | commit | gate_result | supersession
  statement: what was decided, in one sentence
  evidence: [source pointer and fingerprint, command and outcome, or file anchor]
  approver: user | derived-from-source | none
  supersedes: id or null
  status: active | superseded
```

- **decision** — an approach, a base branch, a test level, a named trade-off.
- **assumption** — something taken as true without direct evidence. Every
  assumption carries what would falsify it.
- **discovery** — evidence found mid-workflow that changes the picture.
- **approval** — an explicit human yes, with what exactly was approved.
- **commit** — the hash, stage, and slice, so evidence survives compaction.
- **gate_result** — which gate ran, its effective mode, and its outcome.
- **supersession** — see below.

## DECISION_INVARIANT_CHECK

Before every material edit, commit, gate remediation, and review fix, check the
proposed action against the active entries and return:

```yaml
DECISION_INVARIANT_CHECK:
  status: PASS | CONTRADICTION | INVALIDATED_ASSUMPTION
  entries: [ids checked]
  finding: the contradicted entry and the contradicting evidence, or null
```

`CONTRADICTION` and `INVALIDATED_ASSUMPTION` both return `NEEDS_INPUT` to the
user. Neither is resolved by the workflow choosing which side it prefers.

## Superseding a decision

A prior decision changes only through an explicit superseding entry. Never edit
or delete the original — the point of the ledger is that the moment a plan
became wrong stays visible.

A supersession records: the entry it replaces, the new evidence, the approver,
what the change invalidates downstream (test inventory, architecture handoff,
gate evidence), and what must be rebuilt. Everything derived from a superseded
decision is stale until rebuilt.

## Lifecycle

- **Initialize** at Phase 0, before the first material decision.
- **Revalidate** at the start of every phase and every fresh interaction:
  refresh any owner artifact whose fingerprint changed, and re-run the invariant
  check against entries whose evidence moved.
- **Append**, never rewrite.
- **Carry** its reference and fingerprint into every skill invocation and every
  returned result, so a reader can trace a conclusion to the decision behind it.
- **Discard** with the session. It is working memory, not a project artifact;
  anything that must outlive the session belongs in a commit body, the tracker,
  or the repository's own documentation.
