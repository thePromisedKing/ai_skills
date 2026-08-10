# Scanner handling

What each scanner covers, how to bound it, and how to read what it returns.

## Contents

- Secret sweeping
- semgrep
- trivy
- dependency_check
- Coverage each scanner does not provide
- Reachability
- Severity versus risk

## Secret sweeping

Run before everything else, over the frozen scope.

Where Trivy is available, its `secret` scanner is the cheapest complete sweep.
Where it is not, sweep with the patterns that matter most in a Java service:

- private key blocks (`BEGIN * PRIVATE KEY`);
- cloud provider access keys and their secret pairs;
- JDBC and AMQP connection strings containing a password;
- bearer tokens and API keys in properties, YAML, and test fixtures;
- `.env` files, keystores, and credential JSON added to the index.

Two rules:

- **A hit stops the workflow.** Not a finding to rank alongside others.
- **Rotation, not deletion.** Once a value has existed in a shared checkout it
  must be treated as compromised. Say so plainly; a workflow that removes the
  line and reports it fixed leaves a live credential in the world.

High-entropy strings in test fixtures are the common false positive. Resolve it
by confirming the value is obviously fake — and if it is not obviously fake,
that is itself worth fixing, because the next reader will have the same doubt.

## semgrep

**Covers** source-level patterns: injection, unsafe deserialization, weak
cryptography, path traversal, unsafe reflection, hardcoded credentials, missing
authorization annotations, and whatever custom rules the project has written.

Bound it to the frozen scope with the configured rule set. Scanning the whole
repository at every gate produces the same pre-existing findings every time,
which is how a scanner's output stops being read.

Custom rules are where Semgrep earns its place in a specific project: a rule
that catches "a repository method called without a tenant filter" or "a
controller method with no authorization annotation" finds what generic rules
cannot. When a project has such rules, they carry more weight than the generic
registry findings.

Read the JSON or SARIF output, not the console format.

## trivy

**Covers** three distinct things, selected by `gates.trivy.scanners`:

- `vuln` — known vulnerabilities in dependencies, resolved from the build's lock
  or dependency tree;
- `secret` — the secret sweep above;
- `misconfig` — Dockerfile, Kubernetes, and IaC misconfiguration;
- `license` — dependency licenses, where the project tracks them.

Filter to the configured `severity` list. Reporting every `LOW` alongside two
`CRITICAL` findings hides the two that matter.

For a Java project, the vulnerability scan is only as good as the dependency
resolution it was given. A `trivy fs` run against a source tree with no
resolved lock information sees less than one run after a build has resolved the
tree — state which one was performed, since the difference changes what the
clean result means.

## dependency_check

**Covers** dependency vulnerabilities via the NVD, through the build plugin.

Two practical properties worth knowing before enabling it as required:

- Its first run downloads the NVD database, which takes minutes and needs
  network access. A `BLOCKED_REQUIRED_MISSING` on an offline machine is a real
  and common outcome.
- Its false-positive rate on Java libraries is meaningfully higher than Trivy's,
  because it matches by CPE inference. Findings need confirmation against the
  actual coordinate before they are treated as real.

It overlaps heavily with Trivy's `vuln` scanner. A project running both should
know it is paying twice for mostly the same coverage; that is a configuration
decision, and this suite reports the overlap rather than deduplicating it away.

## Coverage each scanner does not provide

State these in `limitations` when the corresponding scanner is skipped, so a
reader knows what the gap actually is:

| Skipped | Uncovered |
| --- | --- |
| `semgrep` | source-level injection, crypto, authorization, and custom-rule patterns |
| `trivy` (vuln) | known CVEs in the dependency tree |
| `trivy` (secret) | staged credentials — unless swept another way |
| `trivy` (misconfig) | container and deployment misconfiguration |
| `dependency_check` | NVD-sourced dependency vulnerabilities |

No scanner covers: business-logic authorization defects, tenancy leaks,
insecure-by-design flows, or a missing audit trail. Those are found by the
standards review and the tests, which is why a green scanner roster is not a
security verdict.

## Reachability

A finding's severity describes the vulnerability. Its reachability describes
whether this application can reach it. Both belong in the report.

- **Reached on a request path** — highest urgency, regardless of score.
- **Reached only at startup or in a job** — real, but a different response.
- **Present but unreachable** — a transitive dependency of a module this
  application does not use, or a code path behind a disabled feature.
- **Test scope only** — a vulnerable test dependency does not ship. Fix it, but
  do not report it as a production exposure.

Assess reachability from the actual call graph and the actual dependency scope,
not from an assumption. When it cannot be established cheaply, say so rather
than guessing in either direction.

## Severity versus risk

A CVSS score is computed without knowledge of this application. Report it, then
report the risk: what an attacker would need, what they would get, and whether
anything in this deployment already prevents it.

A `CRITICAL` in an unreachable transitive test dependency is lower risk than a
`MEDIUM` on an unauthenticated endpoint. A result that ranks by score alone
sends the reader to the wrong finding first.
