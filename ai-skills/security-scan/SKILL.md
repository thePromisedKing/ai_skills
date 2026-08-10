---
name: security-scan
description: Run the project's configured security scanners — Semgrep, Trivy, and OWASP Dependency-Check — against the change, link every finding to the diff, classify it, obtain approval for remediation, and return a full roster in which an unavailable or disabled scanner is reported as such rather than as a clean result. Use before a commit, at an implementation workflow's final gate, or when the user asks for a security check. Code-quality analysis belongs to quality-gate.
---

# Security scan
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the security scanners. Which scanners run, and whether each is required,
optional, or off, comes from `.ai-skills/config.yml` through `project-config`.

The rule that shapes this skill: **an unrun scanner is not a clean result.** A
project without Trivy installed does not have a vulnerability-free dependency
tree; it has an unmeasured one, and the result says so.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Scanner roster resolved with effective modes
- [ ] 2 Scope frozen and secrets swept first
- [ ] 3 Scanners executed; every result captured
- [ ] 4 Findings linked to the diff and classified
- [ ] 5 Remediation approved and applied, or deferred with evidence
- [ ] 6 Full roster returned including skips
```

## Invocation

```yaml
caller: spring-workflow | fix-pr | review-pr | direct
checkpoint: pre-commit | final
scope:
  mode: staged | range
  base: <ref>
  head: <ref>
scanner_ids: [optional subset]
remediate: true | false
```

## Secrets come first

Before any other scanner, sweep the scope for credentials: tokens, private keys,
passwords, connection strings, cloud keys, and anything matching the project's
secret patterns.

A staged secret stops everything. Report it immediately with the file and line,
and state plainly that the value must be treated as compromised and rotated —
removing it from the index is not sufficient once it has existed on disk in a
shared checkout, and it is certainly not sufficient once it has been pushed.

Never print the secret's value, in the result, in an error, or in a command.
Report its location and its kind.

This runs first because everything after it is less urgent, and because a
workflow that discovers a secret after twenty minutes of scanning has wasted the
time in which it mattered most.

## Resolve and execute

Invoke `project-config` with `need: [gates]` for the scanner subset. Handle the
four effective modes exactly as resolved — `RUN`, `SKIPPED_DISABLED`,
`SKIPPED_UNAVAILABLE`, `BLOCKED_REQUIRED_MISSING` — with the same semantics
`quality-gate` uses.

Read `references/scanner-handling.md` for what each scanner covers, how to bound
its scope, and how to read its output.

Freeze the analysis input into private temporary storage and scan that. Never
scan the live working tree, and never modify a file to make a scanner runnable.

## Link every finding to the diff

A scanner reports on the code it was given, not on the change. Before a finding
is actionable, establish its relationship to the diff:

| Class | Meaning | Handling |
| --- | --- | --- |
| `INTRODUCED` | the change created it | fix, or obtain an explicit approved exception |
| `TOUCHED` | pre-existing, in a line the change modified | fix when bounded; otherwise record |
| `PRE_EXISTING` | present at the base | report; never fix opportunistically |
| `NOT_LINKED` | in code the change did not touch | report as an observation |

A dependency finding is `INTRODUCED` when the change added or upgraded the
dependency, and `PRE_EXISTING` otherwise — even though it appears in every scan.
Reporting an inherited CVE as though this change caused it is how a scanner
becomes something people stop reading.

Then assess reachability. A vulnerability in a code path the application never
executes is a real finding with a different urgency from one on a request path,
and saying so is more useful than repeating the CVSS score.

## Remediate

Remediation requires explicit approval, per finding or per approved plan. A
dependency upgrade is a behavior change: it can alter transitive versions,
runtime semantics, and licensing.

- Fix the finding, not the detector. Never add an ignore rule, a baseline entry,
  a suppression comment, or a severity threshold change to close a finding.
- For a dependency upgrade, state the version delta, what the transitive tree
  does, and what tests will prove the upgrade is safe. Then run them.
- For a code finding, fix it and add the regression test that would have caught
  it. A security fix with no test is a fix that regresses silently.
- When a finding cannot be fixed in this change — an unfixed upstream CVE, a
  breaking major upgrade — record it as an accepted risk with its reason, its
  reachability assessment, and who accepted it. An accepted risk is a decision
  with a name on it, not a silent omission.
- Any mutation invalidates the frozen snapshot. Refreeze and rerun.

## Result

```yaml
SECURITY_SCAN_RESULT:
  status: PASS | FAIL | NEEDS_INPUT | BLOCKED
  checkpoint: pre-commit | final
  snapshot: {mode, base, head, fingerprint, file_count}
  secrets: {swept: true, findings: [path, line, kind, rotation_required]}
  roster:
    - id: semgrep | trivy | dependency_check
      configured: enabled | auto | disabled
      effective: RUN | SKIPPED_DISABLED | SKIPPED_UNAVAILABLE | BLOCKED_REQUIRED_MISSING
      command: exact command, or null
      outcome: PASS | FAIL | ERROR | not_run
      findings: [id, severity, path or package, class, reachability]
      evidence: report path
  remediation: [finding id, action, version delta, tests rerun, approver]
  accepted_risks: [finding id, reason, reachability, approver]
  limitations: [skipped scanner and the coverage it would have provided]
```

`status: PASS` means every `RUN` scanner passed and no `INTRODUCED` finding
remains unresolved. The roster states what actually ran.

## Example

A final gate on a project with Semgrep but no Trivy:

```text
Claude Code: /security-scan checkpoint: final, scope: {mode: range, base: origin/main, head: HEAD}

Codex: Use $security-scan at checkpoint final over origin/main..HEAD.
```

Returns `SECURITY_SCAN_RESULT` with the secret sweep clean, `semgrep` `RUN` with
one `INTRODUCED` finding for an unparameterized query, `trivy`
`SKIPPED_UNAVAILABLE` with `limitations` naming the dependency and container
coverage it would have provided, and `dependency_check` `SKIPPED_DISABLED`. The
calling workflow reports that roster rather than describing the change as
security-scanned.

## Guardrails

- Never print, log, or echo a secret's value; report its location and kind.
- Never treat removing a staged secret as sufficient — state that rotation is
  required.
- Never invent, add, or drop a scanner; the roster comes from the configuration.
- Never scan the live working tree or modify a file to make a scanner runnable.
- Never report a skipped scanner as a pass, and never omit it from the roster.
- Never add an ignore rule, baseline, suppression, or threshold change to close
  a finding.
- Never upgrade a dependency without approval and without running the tests that
  prove it safe.
- Never claim `PRE_EXISTING` without a base comparison.
- Never report a result from a snapshot a later mutation invalidated.
