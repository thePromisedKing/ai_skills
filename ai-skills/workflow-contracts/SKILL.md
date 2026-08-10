---
name: workflow-contracts
description: Provide the shared implementation lifecycle every engine in this suite follows — invocation and result contracts, the ordered phase sequence, the RED/GREEN/REFACTOR and commit contracts, escalation, scope holding, and the common guardrails. Use when spring-workflow or another implementation engine needs the canonical lifecycle text, or when a reviewer must check that a workflow followed it. Reference material only; it runs no workflow of its own.
---

# Workflow contracts
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the lifecycle every implementation engine shares. This skill executes
nothing and has no workflow of its own, so it carries no progress checklist.

Change a rule here first, then sweep every consumer: `spring-workflow`,
`api-test-workflow`, `implement-task`, `fix-pr`, and the suite contract test.

## What lives here

| Reference | Contents |
| --- | --- |
| `references/workflow-contracts.md` | invocation and result contracts, Phases 0–5, TDD and commit contracts, escalation, scope holding, guardrails |
| `references/independent-review.md` | how an engine obtains and handles its own end-of-workflow review |
| `references/simplicity-retrospective.md` | the final challenge to the integrated implementation |
| `references/documentation-maintenance.md` | which project documents a change obliges, and when |
| `references/recommendation-evaluation.md` | evidence-backed disposition of raw review recommendations |

An engine reads the section it is in, when it is in it. Reading all five at
Phase 0 costs context for phases that may never run.

## Result

This skill returns no result contract of its own. A caller reads the reference
it needs and reports through its own engine result.

## Guardrails

- Never fork a rule from `references/workflow-contracts.md` into an engine. An
  engine references it and adds only what is genuinely specific to its target.
- Never execute a phase from here. This skill is text.
- Never let a consumer's paraphrase outrank this document; when they disagree,
  this document is correct and the consumer is a defect to fix.
