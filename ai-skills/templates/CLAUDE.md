# Repository instructions

> Template. Copy to the root of the Spring Boot repository as `CLAUDE.md` (and
> symlink or copy to `AGENTS.md` for Codex), then fill in the project-specific
> sections marked TODO. Delete this blockquote.

This repository is equipped with the `ai-skills` suite. Prefer the owning skill
over improvising: each one carries this project's contracts, approval gates, and
evidence requirements, and several reject work that belongs to a sibling.

## Configuration comes first

Every project-specific value — the tracker, the build commands, the protected
branches, the commit subject, the quality-gate roster — lives in
`.ai-skills/config.yml` and is read through the `project-config` skill.

Do not hard-code a build command, a branch name, a ticket prefix, or a gate.
Do not edit the configuration to make a gate pass; that is the user's decision.

If a skill named below is not available in the session, say so, explain that
`<suite>/init.sh` installs it, and ask before running the refresh. Do not
substitute your own reasoning for a missing skill's contract.

### Check for drift before relying on a skill

The session loads the *installed* copies under `.claude/skills/` and
`.agents/skills/`, so edits in the suite source are inert until a refresh and a
session restart:

```bash
<suite>/init.sh --check
```

Any difference means the session is running stale skills. Report which differ
and recommend a refresh; note that a new session is required for it to take
effect. Ask before running it — a refresh replaces both installed trees and
rewrites their rolling backups.

## Route the task to its skill

| The user wants to | Use |
| --- | --- |
| Implement a tracked work item end to end | `implement-task` |
| Change code with no work item | `spring-workflow` |
| Review someone else's pull request | `review-pr` |
| Address or re-check reviewer feedback on their own PR | `fix-pr` |
| Get oriented on a PR before reading it line by line | `review-pr` in `mode: brief` |
| Run the configured code-quality gate | `quality-gate` |
| Run the configured security scanners | `security-scan` |
| Plan or implement API test coverage | `api-test-workflow` |
| Compare implementation approaches | `architecture-plan` |
| Create, split, merge, retire, or change a skill | `skills-manager` |
| Transfer an active workflow when a vendor quota runs out | `quota-handoff` |

## Do not hand-roll what a skill owns

These are invoked by the entry points above rather than directly, and exist so
an agent never invents project policy:

- `engineering-standards` — the baseline, aggregating the
  `java-engineering-standards` and `test-engineering-standards`
  specializations. Never restate or reason around these rules.
- `workflow-contracts` — the shared lifecycle every engine follows.
- `project-config` — every configurable value in the suite.
- `tracker-context` — every work-item read and write.
- `requirement-context` — grounding in the prompt and the flow documents.

## Common mistakes

- Implementing a work item directly instead of through `implement-task`, which
  skips scope resolution, requirement grounding, and the architecture decision.
- Reviewing your own PR with `review-pr`, or answering feedback with it. Author
  work is `fix-pr`.
- Writing standards, lifecycle, or tracker logic inline when an owning skill
  already holds it.
- Reporting a gate roster with the skipped gates removed, so a change reads as
  having passed checks that never ran.
- Treating a skill's absence as permission to proceed without it.

---

## TODO — project specifics

Fill these in. They are what the standards layer cannot infer.

### Build and run

```bash
# TODO: the commands a developer actually runs
./mvnw spring-boot:run
./mvnw verify
```

### Architecture

TODO: the module graph and the dependency direction, or a pointer to where it
is documented. Name the rule an ArchUnit test enforces, if there is one.

### Domain conventions

TODO: anything a reviewer would need to know and could not infer. Examples:

- monetary amounts are `Long` minor units;
- every query is tenant-scoped through `TenantContext`;
- external calls go through `IntegrationClient`, never a raw HTTP client.

### Requirement sources

TODO: where flow documents live and what convention they follow. These paths
must match `requirements.sources` in `.ai-skills/config.yml`.
