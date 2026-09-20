# Configuration schema

Validation rules for `.ai-skills/config.yml`. The annotated template lives at
`<suite>/config/ai-skills.example.yml`; this document is what `project-config`
checks it against.

## Contents

- Validation principles
- schema_version
- project
- build
- branches
- commit
- tracker
- requirements
- gates
- testing, review, parallel, approvals
- Placeholder detection
- Violation reporting

## Validation principles

- **The roster is closed.** An unknown top-level key or an unknown gate id is a
  violation, not an extension point. Adding one is a suite change, owned by
  `skills-manager`.
- **Absent is not default.** A required field that is missing returns
  `NEEDS_INPUT`. The suite has no implicit fallbacks for project identity,
  branch protection, or tracker selection.
- **A placeholder is not a value.** Template text left unedited fails
  validation; see below.
- **Credentials live in the environment.** A field holding a token, password, or
  key is a violation regardless of its name.

## schema_version

Required integer. Currently `1`. A higher value returns `NEEDS_INPUT` naming the
suite version that understands it; a lower one is a violation with the migration
note.

## project

| Field | Required | Rule |
| --- | --- | --- |
| `name` | yes | non-empty, not the template value |
| `base_package` | yes | valid Java package, at least two segments |
| `modules` | no | list of directory names that exist in the repository |
| `domain_notes` | no | free text |

When `modules` is non-empty it is authoritative: a workflow may not target a
module absent from the list.

## build

| Field | Required | Rule |
| --- | --- | --- |
| `tool` | yes | `auto`, `maven`, or `gradle` |
| `commands.*` | no | `null` or a non-empty shell command |
| `java_release` | yes | integer, 17 or higher |

`auto` detection evidence: `pom.xml` or `mvnw` for maven; `build.gradle`,
`build.gradle.kts`, or `gradlew` for gradle. Finding both, or neither, is
`NEEDS_INPUT` — the suite asks rather than picking.

A command override is used verbatim. `focused_test` may contain the literal
token `{selection}`, which callers substitute; no other token is interpolated.

## branches

| Field | Required | Rule |
| --- | --- | --- |
| `default_base` | yes | non-empty ref name |
| `protected` | yes | non-empty list; globs allowed |
| `feature_pattern` | no | may use `{type}`, `{work_id}`, `{slug}` |

`default_base` must itself appear in `protected`. A base branch nobody protects
is a configuration mistake worth catching here.

## commit

| Field | Required | Rule |
| --- | --- | --- |
| `subject_template` | yes | may use `{work_id}` and `{title}`; no other token |
| `require_stable_subject` | yes | boolean |
| `trailer` | no | free text, may be empty |

When `tracker.adapter` is `none`, `{work_id}` resolves to empty and any
surrounding separator is collapsed, so `"{work_id} :: {title}"` yields just the
title. A template that would produce a leading separator is a violation.

## tracker

`adapter` is required and must be one of `jira`, `odoo`, `github`, `file`,
`none`. Only the selected adapter's block is validated.

| Adapter | Required fields |
| --- | --- |
| `jira` | `base_url` (https), `project_key`, `key_pattern` (valid regex), `credentials_env` (2 names) |
| `odoo` | `base_url` (https), `database`, `project_id` (positive integer), `credentials_env` (2 names) |
| `github` | `repo` as `owner/name` |
| `file` | `root` — a path that exists |
| `none` | — |

`credentials_env` holds *variable names*, never values. A name that is not set
in the environment is reported as `credentials_present: false`, which is a
`NEEDS_INPUT` for any mode that writes, and a limitation for read-only modes.

`in_review_status` / `in_review_stage` / `in_review_label` may be empty, which
disables the post-PR transition entirely. That is a supported configuration, not
an omission.

## requirements

| Field | Required | Rule |
| --- | --- | --- |
| `sources` | yes | list, may be empty only when `allow_prompt_only` is true |
| `sources[].id` | yes | unique, kebab-case |
| `sources[].path` | yes | repository-relative |
| `sources[].glob` | yes | non-empty |
| `allow_prompt_only` | yes | boolean |
| `require_sources_populated` | yes | boolean |

List order is authority order, highest first. Two sources with the same `id` is
a violation; ambiguity in authority order is exactly what this ordering exists
to remove.

An empty `sources` list with `allow_prompt_only: false` is a violation: it
leaves no legal way to state a requirement.

## gates

Every gate id in the closed roster must be present with a `mode` of `enabled`,
`auto`, or `disabled`:

`format`, `checkstyle`, `pmd`, `spotbugs`, `errorprone`, `coverage`,
`archunit`, `sonar`, `semgrep`, `trivy`, `dependency_check`, `eslint`, `tsc`,
`vitest`, `playwright`.

The last four govern a JavaScript or TypeScript source tree. A repository with
no such tree declares them `disabled`, which is a decision on the record rather
than a gap in the roster.

Gate-specific rules:

- `format.tool` — `spotless` or `none`. `none` with mode other than `disabled`
  is a violation.
- `checkstyle.config`, `pmd.ruleset` — paths; existence is probed, not
  validated here, so a project can configure a gate before adding its rules.
- `coverage.min_changed_line_coverage` — `null` or 0–100.
- `coverage.ratchet` — boolean.
- `archunit.test_pattern` — non-empty glob.
- `sonar.project_key` — non-empty when mode is not `disabled`.
- `sonar.scope` — must be `staged`. Any other value is a violation; whole-project
  Sonar analysis is not a mode this suite offers.
- `trivy.scanners` — subset of `vuln`, `secret`, `misconfig`, `license`.
- `trivy.severity`, `dependency_check.fail_on_cvss` — recognized severity names
  and 0–10 respectively.
- `eslint.root`, `tsc.root`, `vitest.root`, `playwright.root` — repository-
  relative directory holding the package manifest that owns the gate. Non-empty
  when the mode is not `disabled`. There is no repository-wide default: a
  front end is one tree among several in a polyglot repository, and guessing
  which one would silently gate the wrong directory.
- `eslint.command`, `tsc.command`, `vitest.command`, `playwright.command` — the
  command to run, executed from the repository root. Non-empty when the mode is
  not `disabled`. Unlike the Java gates, these carry no build-tool inference:
  the suite detects Maven and Gradle, not package managers, so the command is
  stated rather than derived.

See `gate-resolution.md` for how a mode becomes an effective mode.

## context

Optional. Declares a code graph the workflow skills may query instead of
rediscovering structure by reading files.

| Field | Rule |
| --- | --- |
| `code_graph.mode` | `auto`, `enabled`, or `disabled`. `auto` means query it when it is present and proceed without it when it is not. |
| `code_graph.tool` | Executable that answers the queries. Probed on `PATH`; never assumed installed. |
| `code_graph.path` | Repository-relative path to the graph artifact. |
| `code_graph.query_command` | Command template containing the `{question}` placeholder. A template without it is a violation: there would be no way to pass a query. |

A graph is usable only when the tool resolves **and** the artifact exists at
`code_graph.path`. Either one missing under `auto` is a recorded limitation,
not a violation — the artifact is a rebuildable cache, and blocking a workflow
on a cache that any clone can regenerate would trade a real stop for a
convenience. Under `enabled`, the same absence is `BLOCKED`.

Omitting the `context` block entirely is equivalent to
`code_graph.mode: disabled`.

## testing, review, parallel, approvals

| Field | Rule |
| --- | --- |
| `testing.levels` | non-empty subset of `unit`, `slice`, `integration`, `contract`, `e2e` |
| `testing.testcontainers` | boolean; `true` requires `integration` in `levels` |
| `review.independent_review` | boolean |
| `review.max_rounds` | integer 1–5 |
| `parallel.max_concurrent_groups` | integer 1–5 |
| `approvals.required` | subset of the known approval ids |

Known approval ids: `architecture_selection`, `base_branch_confirmation`,
`scope_expansion`, `push`, `pull_request_creation`, `tracker_write`,
`parallel_plan`.

Removing an id from `approvals.required` weakens the suite's human-in-the-loop
guarantees. It is permitted — projects differ — but `project-config` reports each
omission in `limitations` so a reader of any result can see which approvals the
project turned off.

`parallel.max_concurrent_groups` has a ceiling of 5 so the coordinating agent
keeps capacity to monitor, integrate, and stop groups; a higher number turns
supervision into a bottleneck rather than the work.

## Placeholder detection

These fail validation as unedited template text:

- any URL whose host is `example.com`, `example.odoo.com`, or
  `example.atlassian.net`;
- `repo: example/...`;
- `project.name: order-service` combined with `base_package: com.example.orders`
  — either alone is legitimate, both together is the template;
- `odoo.project_id: 0`;
- an `id`/`path` pair under `requirements.sources` naming a directory that does
  not exist, when `require_sources_populated` is true.

Report a placeholder as its own violation class so the message can say "this is
still the template value" rather than the less useful "invalid host".

## Violation reporting

Return each violation as `[field, problem, accepted]`:

```yaml
violations:
  - [tracker.jira.base_url, "still the template host example.atlassian.net", "the project's Jira base URL"]
  - [gates.sonar.scope, "whole-project analysis is not offered", "staged"]
  - [branches.default_base, "main is absent from branches.protected", "a ref listed in branches.protected"]
```

Name the field by its full dotted path so the reader can find it in one search.
Never report a violation without an accepted alternative — a validator that only
says "invalid" moves the diagnosis back to the person it was meant to help.
