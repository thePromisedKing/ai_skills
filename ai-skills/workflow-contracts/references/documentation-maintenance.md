# Documentation maintenance

Which documents a change obliges, and when. Built at Phase 2 as a
`DOCUMENTATION_IMPACT_LEDGER`, rechecked before every commit, audited once at
the final gate.

## The distinction that matters

**Requirement sources** — the flow documents and tracker items configured under
`requirements.sources`. These are inputs. The workflow reads them and never
edits them. A change that contradicts one is a contradiction to surface, not a
document to update.

**Current-state documentation** — `README.md`, `CLAUDE.md`, `AGENTS.md`, module
guides, API documentation, runbooks, configuration references. These describe
what the code does. The workflow maintains them, in the same commit as the
behavior that made them stale.

Confusing the two produces either a silently rewritten requirement or a README
that has been wrong for a year.

## Building the ledger

For each changed behavior, ask what a reader would now find wrong:

| Change | Documents it obliges |
| --- | --- |
| new or changed HTTP endpoint | API documentation, the OpenAPI document if published, the module README |
| new or changed configuration property | the configuration reference, the example configuration, the deployment runbook |
| new or changed environment variable or secret | the deployment runbook, the local-setup instructions |
| schema change | the data-model document, the migration notes |
| new module or moved boundary | the root README's structure section, the repository instructions |
| new build, test, or gate command | the repository instructions, the contributing guide |
| changed operational behavior — retries, timeouts, health, degradation | the runbook, the alerting notes |
| new dependency with operational impact | the dependency notes, the deployment runbook |

Record each as `[document, section, what is now stale, obligation]` where the
obligation is `UPDATE`, `REVIEW`, or `NONE` with a reason.

A change with an empty ledger is normal — most changes oblige nothing. Record
the empty result rather than skipping the step, so a reader can tell the
difference between "nothing was stale" and "nobody looked".

## Updating

- Update in the same coherent slice as the behavior, not in a trailing
  documentation commit. A separate commit gets dropped in a rebase or reverted
  alone, and then the document is wrong again.
- Change the minimum that makes the document correct. A documentation update is
  not an invitation to rewrite the surrounding page.
- Match the document's existing voice and structure.
- Never add a ticket key, a pull-request number, or a person's name to a tracked
  document. That belongs in Git metadata and the tracker.
- Never document an intention. A document describes what the code does now.

## The final-gate audit

At the final gate, re-read the ledger against the immutable snapshot and
confirm every `UPDATE` obligation was met. Also scan the tracked Markdown the
change touched for statements the change falsified but the ledger missed —
ledgers are built from what was planned, and implementations discover things.

Report an unmet obligation as a finding, not as a limitation. A document the
workflow decided to update and then did not is a defect it introduced.
