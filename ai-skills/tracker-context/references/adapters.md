# Tracker adapters

One contract, five transports. Read only the section for the configured
`tracker.adapter`; the others do not apply and reading them costs context for
nothing.

Every adapter is driven through `scripts/tracker.sh`, which takes credentials
from the environment variables the configuration names and never accepts one as
an argument — arguments appear in process listings and shell history.

## Contents

- The common contract
- Jira
- Odoo
- GitHub Issues
- File
- None
- Adding an adapter

## The common contract

Every adapter implements these operations. An operation an adapter cannot
support returns `UNSUPPORTED` with the reason; it is never emulated by
approximating it with a different write.

| Operation | Meaning |
| --- | --- |
| `probe` | credentials present and endpoint reachable |
| `get <id>` | the primary item |
| `graph <id>` | parent, children, links |
| `comments <id>` | ordered chronology |
| `attachments <id>` | download to scratch storage |
| `comment <id> <file>` | append one comment from a file |
| `transitions <id>` | the transitions actually available now |
| `transition <id> <target>` | perform one, after verification |

Two rules bind every adapter:

- **Refetch immediately before a write.** State read at the start of a long
  workflow is stale by the time the write happens.
- **Verify after a write.** Refetch and confirm the intended state. A write
  reported without verification is a claim, not evidence.

## Jira

Atlassian Cloud REST v3. Credentials: the two variables named in
`tracker.jira.credentials_env`, used as email plus API token in basic auth.

- Items are identified by `key_pattern` from the configuration, e.g. `ORD-482`.
- `graph` reads `fields.parent`, `fields.subtasks`, and `fields.issuelinks`. A
  link's type matters: `relates to` frequently carries the test or QA item, and
  it is a link rather than a subtask in many projects — search both.
- Comments come from `/comment` with `expand=renderedBody` so formatting is
  readable. Preserve author and creation time.
- `transition` is guarded: list live transitions, require exactly one whose name
  matches `in_review_status` exactly, and refuse when zero or several match.
  Never move an item whose status category is `done`, and never infer that one
  status precedes another.
- Creating an issue is permitted only for a confirmed defect, one at a time,
  each individually approved, with no assignee, priority, sprint, or fix version
  set.

## Odoo

Odoo external API over JSON-RPC at `/jsonrpc`, or `/web/session/authenticate`
followed by `/web/dataset/call_kw` where the deployment requires it.
Credentials: login plus API key from `tracker.odoo.credentials_env`, with
`database` from the configuration.

- Items are `project.task` records inside `tracker.odoo.project_id`. The id is
  numeric; the configuration's `key_pattern` is not used.
- Authenticate once with `common.authenticate` to obtain the uid, then call
  `object.execute_kw` for reads and writes. Cache the uid for the session.
- `get` reads `project.task` fields `name`, `description`, `stage_id`,
  `user_ids`, `parent_id`, `child_ids`, `tag_ids`, `date_deadline`.
- `graph` follows `parent_id` and `child_ids`. Odoo has no first-class "link"
  relation, so related items come from `depend_on_ids` where the deployment uses
  the dependency feature; when it does not, report links as `UNSUPPORTED` rather
  than inventing a relation from tags.
- `comments` reads `mail.message` filtered to `model = project.task` and
  `res_id = <task>`, ordered by `date`. Odoo's HTML bodies need converting to
  text before use.
- `comment` posts a **log note**, not a message to followers:
  `message_post` with `message_type: comment` and
  `subtype_xmlid: mail.mt_note`. A note is an internal record; a message emails
  every follower, which a routine implementation report should not do.
- `transition` writes `stage_id` to the id whose name matches
  `in_review_stage` exactly within the task's project. Resolve the name to an id
  through `project.task.type` scoped to that project — stage names are not
  globally unique. Refuse when zero or several stages match.
- Attachments are `ir.attachment` filtered by `res_model` and `res_id`; the
  `datas` field is base64.

## GitHub Issues

The `gh` CLI and its existing authentication. No credential variable is read;
`gh auth status` is the probe.

- Items are issue numbers in `tracker.github.repo`. A `#123` in a branch name,
  PR title, or commit subject is discovery evidence.
- `graph` uses sub-issues where the repository has them, and otherwise the
  issue's timeline cross-references. Report the mechanism used, since the two
  give different completeness.
- `comments` is `gh issue view --comments`, preserving author and time.
- `comment` is `gh issue comment --body-file`. Always a file: a body passed
  inline mangles newlines and can leak through shell history.
- `transition` applies `in_review_label` when configured. GitHub has no status
  model beyond open/closed, so a configured label is the whole mechanism; an
  empty `in_review_label` disables the operation and that is reported, not
  worked around by closing the issue.
- Never close an issue. Closing is a human judgment about whether the work is
  done, and a merged PR usually closes it anyway.

## File

Markdown work items under `tracker.file.root`, one file per item. The filename
stem is the id: `docs/work-items/ORD-482.md` is `ORD-482`.

Expected shape, all sections optional except a title:

```markdown
# ORD-482 — Reject checkout above the account limit

## Requirements
1. ...

## Acceptance criteria
- ...

## Links
- parent: ORD-400
- relates: ORD-503

## Log
### 2026-08-10 — implementation report
...
```

- `graph` reads the `Links` section. A referenced id with no file is reported as
  a dangling link, not silently dropped.
- `comment` appends a new `###` entry under `## Log` with the date and the
  mode's label. It never rewrites an existing section, never reorders the file,
  and never touches anything above `## Log`.
- `transition` is `UNSUPPORTED`; a Markdown file has no status model. Say so
  rather than inventing a status line.
- The file is a tracked repository artifact, so an append is a working-tree
  change the calling workflow stages and commits under its normal commit
  contract. It is never committed by this skill.

## None

No tracker. `probe` succeeds, every read returns empty, every write returns
`UNSUPPORTED`.

This is a first-class configuration, not a degraded one. The workflow takes its
requirements from `requirement-context` — the prompt and the project's flow
documents — and renders the commit subject without a work id. Nothing in the
suite requires a tracker to reach `PASS`.

## Adding an adapter

Adding a transport is a suite change, owned by `skills-manager`. It needs:

- the eight common operations, or an explicit `UNSUPPORTED` with a reason for
  each one the transport cannot honestly provide;
- a configuration block and its validation rules in `config-schema.md`;
- credentials read only from named environment variables;
- refetch-before-write and verify-after-write;
- a section here describing what its `comment` and `transition` actually do in
  that system, because those two differ most between trackers and are the two
  that are visible to other people.
