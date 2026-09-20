---
name: tracker-context
description: Resolve work-item scope, hierarchy, requirements, and limited work-item writes through a pluggable tracker adapter — Jira, Odoo, GitHub Issues, local Markdown files, or none — without performing code changes. Use when implement-task, review-pr, or fix-pr needs to identify a work item from a branch, commit, or explicit key; fetch it with its parent, children, links, and comments; or post an approved implementation report, QA note, or status transition. Requirements that live only in the prompt or in flow documents belong to requirement-context.
---

# Tracker context
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own every work-tracker operation and translate it into an immutable,
evidence-backed scope context. Never implement code, review a pull request,
push, or mutate a Git branch.

The adapter is chosen by `tracker.adapter` in the project configuration. The
contract below is identical across adapters; only the transport differs.
`adapter: none` is fully supported and returns an empty scope without error —
the workflow then takes its requirements from `requirement-context`.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Adapter resolved and reachable
- [ ] 2 Primary work item identified from evidence
- [ ] 3 Read complete: hierarchy, links, comments, attachments
- [ ] 4 Scope boundary applied to every requirement
- [ ] 5 Allowed write performed, or read-only run recorded
```

## Inputs

Accept an explicit work-item id, or discovery evidence from a branch name, PR
title, and commit subjects. Extract candidate ids using the adapter's configured
pattern. No id, or several plausible primary ids, is `NEEDS_INPUT` — never
guess, and never infer an id from code paths alone.

Accept `mode`:

| Mode | Writes |
| --- | --- |
| `read` | none |
| `report` | one implementation-report comment on the primary item |
| `test-note` | one QA/test-coverage comment on the primary item or its test child |
| `transition` | one guarded status change after a PR exists |
| `defect` | one comment on a named related item reporting work that belongs to it |
| `file` | one new item for a confirmed defect, where the adapter permits it |

`file` is the one mode that creates rather than annotates, so it carries the
heaviest evidence bar: a defect someone confirmed, not a suspicion, and one item
per approval. Preview it with `--dry-run`, which returns the exact field payload
and writes nothing.

Every write requires: a passing engine or QA result as evidence, the exact text,
and the user's explicit approval of that text and target. `tracker_write` is in
`approvals.required` by default; a project that removed it is reported in
`limitations` so a reader knows the approval was configured away.

## Read workflow

1. Invoke `project-config` for the `tracker` section. Resolve the adapter and
   confirm its named credential variables are set. A missing credential is
   `NEEDS_INPUT` for any mode; for `read` it may instead be recorded as a
   limitation when the adapter supports unauthenticated reads.
2. Read `references/adapters.md` for the selected adapter and use
   `scripts/tracker.sh`. Never print, log, or echo a credential.
3. Fetch the primary item, then its parent, children, and linked items. Read
   full context only for a related item that constrains a shared entity,
   interface, release, or acceptance criterion.
4. Download attachments into private scratch storage and inspect them. Preserve
   comments in chronological order, including late corrections — a correction
   posted after the description was written outranks the description.
5. Build the item graph and the numbered requirement list. Mark every
   requirement `IN_SCOPE_PRIMARY`, `RELATED_CONTEXT`, or `OUT_OF_SCOPE_RELATED`.
   Surface contradictions and missing evidence as `NEEDS_INPUT`.

## Scope boundary

The primary work item defines the change's intended deliverable. A parent,
epic, child, or linked item provides context for the end state; it does not
authorize work outside the primary item.

When a review finding or a discovery is technically valid but not covered by the
primary item, return `OUT_OF_SCOPE_TRACKER` with the evidence. The calling skill
asks the user whether to defer it to the owning item or explicitly expand scope.
Never silently absorb work from a related item.

## Result

Return `TRACKER_CONTEXT_RESULT` with:

```yaml
TRACKER_CONTEXT_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  adapter: jira | odoo | github | file | none
  primary: {id, title, type, status, assignee, url}
  discovery_evidence: [what the id was derived from]
  graph: {parent, children, links}          # omitted when adapter is none
  requirements: [id, verbatim text, scope_class]
  acceptance_criteria: [verbatim]
  chronology: [ordered comment summaries with authorship and time]
  attachments: [name, scratch path, what it contained]
  conflicts: [contradiction between description, comments, and criteria]
  commit_subject: rendered from commit.subject_template
  writes: [mode, target, approver, evidence, resulting state]
  limitations: [unreadable attachment, disabled approval, absent credential]
```

With `adapter: none`, return `status: PASS`, `primary: null`, empty collections,
and the commit subject rendered without a work id. That is a normal run, not a
degraded one.

## Guardrails

- Never infer a work-item id from code paths alone.
- Never let a parent, epic, sibling, or linked item expand primary scope.
- Never discard related context merely because it is out of scope.
- Never expose a credential or place tracker data in a tracked repository file.
- Never perform a code, Git, GitHub-pull-request, or gate mutation.
- Never write without a passing result as evidence, the exact approved text, and
  an explicit user yes for that text and target.
- Never post the same report twice for one run; appending a second is a
  duplicate, not an update.
- Never transition an item backward from a terminal state, and never infer an
  ordering between statuses the adapter does not state.
- Never change an assignee, priority, sprint, or release field. Ownership and
  triage belong to the team.
- Never create a work item except where the adapter section explicitly permits
  it, one at a time and individually approved.

## Example

Resolving scope from an explicit id under the Odoo adapter:

```text
Claude Code: /tracker-context read ORD-482 with its parent and linked tasks

Codex: Use $tracker-context in read mode for ORD-482 with its parent and linked
tasks.
```

Returns `TRACKER_CONTEXT_RESULT` with the task, its project and parent, the
ordered comment chronology, numbered requirements classified against the primary
scope, and the rendered commit subject. An unset `ODOO_API_KEY` returns
`NEEDS_INPUT` naming the variable — never the value, and never a guess at the
task's contents.
