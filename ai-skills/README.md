# ai-skills — agent skills for Java / Spring Boot services

A portable, project-agnostic agent skill suite that enforces engineering
standards and code quality on any Java Spring Boot codebase, under Claude Code
or the OpenAI Codex CLI.

The standards, the implementation engine, and the review lenses are Java and
Spring Boot. The gate roster reaches wider: a repository whose Java service
ships alongside a JavaScript or TypeScript tree gates that tree too, so the
front end is not the one directory nothing checks.

It is a generalization of a production suite: the same lifecycle, evidence, and
approval contracts, with every project-specific decision moved out of the skills
and into one configuration file.

## What is different from a project-bound suite

| Concern | How this suite handles it |
| --- | --- |
| Work tracker | Pluggable adapter — Jira, Odoo, GitHub Issues, local Markdown files, or none |
| Requirements | User prompt and/or Markdown flow documents. No HLD/LLD/FSD hierarchy |
| Build tool | Detected at runtime — Maven or Gradle |
| Quality gates | Declared per project; each gate is `enabled`, `auto`, or `disabled` |
| Front-end gates | ESLint, `tsc`, Vitest, and Playwright, each rooted at the package manifest it governs |
| Front-end standards | `web-engineering-standards`, aggregated for a `web` target |
| Code graph | `graphify` builds it; `project-config` resolves it and `review-pr` queries it when present |
| Missing tooling | An `auto` gate whose tool is absent is recorded `SKIPPED_UNAVAILABLE`, never silently passed |
| Module graph | Read from the project's own configuration, not hard-coded |

## Install

From the root of the Spring Boot repository you want to equip:

```bash
/path/to/ai-skills/init.sh
```

This installs every skill into both `.claude/skills/` and `.agents/skills/`, so
Claude Code and Codex CLI stay interchangeable. Restart the agent afterward.

Then create the project configuration:

```bash
/path/to/ai-skills/init.sh --write-config
```

That writes `.ai-skills/config.yml` from the annotated template. Edit it before
the first skill-backed task — the suite refuses to guess a tracker, a protected
branch, or a required gate.

Optional:

```bash
/path/to/ai-skills/init.sh --install-hooks   # post-merge drift notice
/path/to/ai-skills/init.sh --check           # report drift, change nothing
```

## Configuration is the contract

`.ai-skills/config.yml` is the single source of project-specific truth. It
declares the tracker adapter, requirement sources, branch and commit rules, the
build tool, and the gate roster with each gate's mode. Every skill reads it
through `project-config` and none of them hard-code a command, a path, a branch
name, or a ticket prefix.

Start from `config/ai-skills.example.yml`, which documents every field.

## Route the task to its skill

| The user wants to | Use |
| --- | --- |
| Implement a tracked work item end to end | `implement-task` |
| Change Spring Boot code with no work item | `spring-workflow` |
| Review someone else's pull request | `review-pr` |
| Address reviewer feedback on their own PR, or re-check it | `fix-pr` |
| Understand a PR before reviewing it line by line | `pr-review-brief` (mode of `review-pr`) |
| Run the configured code-quality gate on staged changes | `quality-gate` |
| Run the configured security scanners | `security-scan` |
| Plan and implement API test coverage | `api-test-workflow` |
| Compare implementation approaches before writing code | `architecture-plan` |
| Review or plan front-end work under a `web` target | `web-engineering-standards` |
| Build or query a code graph of the repository | `graphify` |
| Create, split, merge, retire, or change a skill in this suite | `skills-manager` |
| Transfer an active workflow when a vendor quota runs out | `quota-handoff` |

## The skills

**Policy layer** — read-only, returns rules and violations, never edits.

- `engineering-standards` — the cross-cutting baseline and the aggregator. Every
  other skill invokes this rather than restating a rule.
- `java-engineering-standards` — Java language and Spring Boot specialization.
- `test-engineering-standards` — test level selection, JUnit 5, Testcontainers,
  ArchUnit, contract and coverage rules.

**Context layer** — resolves what the change is allowed to be.

- `project-config` — loads and validates `.ai-skills/config.yml`, detects the
  build tool, probes gate tool availability. The owner of every configurable
  value in the suite.
- `tracker-context` — the pluggable work-item adapter and its limited writes.
- `requirement-context` — grounds work in the prompt and the project's Markdown
  flow documents; produces the authority-ordered requirement map.
- `architecture-plan` — presents comparable approaches and requires an explicit
  human selection before any code is written.

**Engine layer** — owns every mutation.

- `workflow-contracts` — the shared lifecycle: invocation and result contracts,
  phase sequence, RED/GREEN/REFACTOR and commit contracts, guardrails.
- `spring-workflow` — the implementation engine.
- `implement-task` — the tracker-facing shell around the engine.

**Gates.**

- `quality-gate` — format, static analysis, coverage, ArchUnit, and Sonar,
  each per its configured mode.
- `security-scan` — Semgrep, Trivy, and OWASP Dependency-Check, same model.
- `api-test-workflow` — REST API coverage planning and implementation.

**Review.**

- `review-pr` — reviewer-perspective review generation, and the engine's
  internal independent review.
- `fix-pr` — author-perspective evaluation and resolution of reviewer feedback.

**Meta.**

- `skills-manager` — governs changes to this suite.
- `quota-handoff` — transfers an active workflow between Claude Code and Codex.

## Design rules the suite holds to

- **No silent pass.** A gate that did not run is reported as skipped with its
  reason. `PASS` never implies coverage the run did not produce.
- **No unattributed choice.** Implementation approach, base branch, scope
  expansion, and every external write require an explicit human decision.
- **Evidence or nothing.** A claim that tests, a scan, a build, or a review ran
  carries the command and its result, or it is recorded as a limitation.
- **One owner per rule.** A skill invokes the owner; it never copies the owner's
  procedure. Duplicated policy text is itself a defect.
- **The tracker is optional.** Every workflow runs end to end with
  `tracker.adapter: none`, taking requirements from the prompt and flow files.

## Keeping the suite current

`init.sh` copies the tracked source into the two installed trees. The agent
session loads the *installed* copies, so edits here are inert until a refresh
and a session restart. Run `init.sh --check` after a pull that touched this
directory.

## Changing a skill

Route it through `skills-manager`. It performs suite-fit analysis, human
approval checkpoints, and validation planning, and it usually concludes that an
existing skill should be extended rather than a new one created.
