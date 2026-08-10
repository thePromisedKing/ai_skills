---
name: quality-gate
description: Run the project's configured code-quality gate roster — format, Checkstyle, PMD, SpotBugs, Error Prone, coverage, ArchUnit, and SonarQube — against the change, classify every finding, route bounded remediation, and return an auditable roster in which a skipped gate is reported as skipped rather than as a pass. Use before a commit, at an implementation workflow's final gate, or when the user asks for a code-quality check. Dependency and vulnerability scanning belongs to security-scan.
---

# Quality gate
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the code-quality gates. Which gates exist, and whether each is required,
optional, or off, is the project's decision — read from `.ai-skills/config.yml`
through `project-config`. This skill never invents a gate and never quietly
drops one.

The single rule that shapes everything here: **the roster is reported in full.**
A reader of the result can always tell which gates ran, which were disabled,
which were unavailable, and what each one found.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Roster resolved with each gate's effective mode
- [ ] 2 Analysis scope frozen
- [ ] 3 Gates executed; every result captured
- [ ] 4 Findings classified against the change
- [ ] 5 Remediation approved and applied, or deferred with evidence
- [ ] 6 Full roster returned including skips
```

## Invocation

```yaml
caller: spring-workflow | fix-pr | review-pr | direct
checkpoint: pre-commit | final
scope:
  mode: staged | range
  base: <ref>        # required for range
  head: <ref>        # required for range
  paths: [optional narrowing]
gate_ids: [optional subset; omitted means the whole roster]
remediate: true | false
```

`pre-commit` analyzes the staged index. `final` analyzes the frozen
base-to-head snapshot the calling workflow published. A `final` checkpoint on an
unfrozen tree is `NEEDS_INPUT`: results from a moving tree are not evidence.

## Resolve the roster

Invoke `project-config` with `need: [build, gates]`. It returns each gate's
configured mode, its effective mode after probing, the command, and the probe
evidence. Read `references/gate-execution.md` for what each gate is asked to
prove and how its output is read.

Handle the four effective modes exactly as `project-config` resolved them:

- `RUN` — execute.
- `SKIPPED_DISABLED` — record. The project decided this; it is not a limitation.
- `SKIPPED_UNAVAILABLE` — record in `limitations` with the failed probe and the
  risk it leaves uncovered. Continue.
- `BLOCKED_REQUIRED_MISSING` — stop with `BLOCKED`, naming the gate, the probe,
  and the two resolutions: install the tool, or change its mode to `auto`.

Never upgrade or downgrade a mode. A caller may narrow which gates it asks
about; it may not change what they are.

## Freeze the scope

Materialize the analysis input into private temporary storage — a snapshot of
the staged blobs, or the diff between the two refs. Analyze that snapshot.

Never analyze the live working tree, and never stage, unstage, or modify a file
to make a gate runnable. A gate that changed the tree it was measuring would
invalidate its own result and everything downstream that trusted it.

For Sonar, the scope is the staged index only, never the whole project. A
whole-project scan reports the repository's accumulated debt as though this
change caused it, which buries the findings that belong to the change.

## Execute and classify

Run the `RUN` gates. Independent read-only gates may run concurrently within
`parallel.max_concurrent_groups` when they do not contend for the build's lock —
most build-integrated analyzers do contend, so run those serially unless the
build tool supports parallel task execution.

Capture, for every gate: the exact command, the exit status, the report path,
and the findings. A gate that errors is `FAIL` with its output, not a skip —
those are different facts and a reader needs to distinguish them.

Classify each finding:

| Class | Meaning | Handling |
| --- | --- | --- |
| `INTRODUCED` | the change created it | must be fixed or explicitly approved as an exception |
| `TOUCHED` | pre-existing, in a line the change modified | fix when bounded; otherwise record with evidence |
| `PRE_EXISTING` | present at the base, untouched | report, never fix opportunistically |
| `FALSE_POSITIVE` | the rule does not apply here | requires concrete contradictory evidence |

Establish `PRE_EXISTING` by comparing against the base, not by assertion. A
finding claimed pre-existing without a base comparison is `INTRODUCED` until
proven otherwise.

## Remediate

When `remediate: true`, fix `INTRODUCED` findings, and `TOUCHED` findings whose
fix is bounded and safe.

- Route per-file work to bounded workers, each owning exactly one file. That
  ownership is what makes concurrent remediation safe; two workers in one file
  produce a conflict nobody planned for.
- Rerun the tests protecting the changed behavior after each remediation, using
  the calling workflow's focused selection. A gate fix that breaks a test is a
  worse outcome than the finding.
- Never satisfy a gate by weakening behavior, deleting a test, loosening an
  assertion, excluding a file, or lowering a threshold.
- Never add a suppression to close a finding. A suppression is an approved
  exception with the narrowest possible scope and a comment stating why the rule
  does not apply — and it needs the user's explicit approval, every time.
- Any mutation invalidates every result from the frozen snapshot. Refreeze and
  rerun the affected gates; never report a pre-remediation result as final.

## Result

```yaml
QUALITY_GATE_RESULT:
  status: PASS | FAIL | NEEDS_INPUT | BLOCKED
  checkpoint: pre-commit | final
  snapshot: {mode, base, head, fingerprint, file_count}
  roster:
    - id: <gate>
      configured: enabled | auto | disabled
      effective: RUN | SKIPPED_DISABLED | SKIPPED_UNAVAILABLE | BLOCKED_REQUIRED_MISSING
      command: exact command, or null
      outcome: PASS | FAIL | ERROR | not_run
      findings: {introduced, touched, pre_existing, false_positive}
      evidence: report path or output pointer
  remediation: [gate, file, what changed, commit or working-tree, tests rerun]
  suppressions_added: [path, line, scope, justification, approver]
  coverage: {changed_line_coverage, floor, project_delta} | not_applicable
  limitations: [skipped gate and the risk it leaves uncovered]
```

`status: PASS` means every `RUN` gate passed and no `INTRODUCED` finding remains
unresolved. It never means the whole roster ran. The roster says that, which is
why it is always returned in full.

## Example

An engine's final gate on a project without Sonar installed:

```text
Claude Code: /quality-gate checkpoint: final, scope: {mode: range, base: origin/main, head: HEAD}

Codex: Use $quality-gate at checkpoint final over origin/main..HEAD.
```

Returns `QUALITY_GATE_RESULT` with `status: PASS`; `format`, `checkstyle`,
`spotbugs`, `coverage`, and `archunit` as `RUN` and passing; `pmd` and
`errorprone` as `SKIPPED_DISABLED`; and `sonar` as `SKIPPED_UNAVAILABLE` with
the failed `PATH` probe in `limitations`. The calling workflow reports that
roster verbatim rather than describing the change as Sonar-clean.

## Guardrails

- Never invent, add, or drop a gate; the roster comes from the configuration.
- Never change a gate's configured mode, and never edit the configuration file.
- Never analyze the live working tree or stage a file to make a gate runnable.
- Never run Sonar against the whole project.
- Never report a skipped gate as a pass, and never omit it from the roster.
- Never claim `PRE_EXISTING` without a base comparison.
- Never add a suppression, an exclusion, or a threshold change without explicit
  approval, and never as a way to close a finding.
- Never weaken behavior or a test to satisfy a gate.
- Never report a result from a snapshot a later mutation invalidated.
