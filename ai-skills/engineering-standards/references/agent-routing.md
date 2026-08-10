# Agent routing

Selecting which authenticated vendor CLI performs one bounded role — a reviewer
pass, a per-file gate worker, a helper analysis. Routing is per-role and
short-lived. Transferring an *active* workflow between vendors is
`quota-handoff`, a different skill, and is never launched from here.

## Roles

| Role | What it does | Typical need |
| --- | --- | --- |
| `coordinator` | drives the workflow, owns integration and approvals | strongest available reasoning |
| `reviewer` | independent read-only review of a diff | strong reasoning, no write tools |
| `helper` | bounded analysis returning a structured answer | moderate |
| `file-worker` | remediation confined to one file under an explicit contract | moderate, high parallelism |

A `reviewer` never receives write tools. A `file-worker` receives write access to
exactly the file it owns and nothing else — that boundary is what makes parallel
remediation safe.

## Procedure

1. **Determine what is authenticated.** Check each candidate vendor CLI's own
   authentication state with its documented non-interactive status command.
   Never infer authentication from the presence of a binary, a config file, or
   an environment variable.
2. **Honor the caller's preference** when that vendor is authenticated.
3. **Fall back** to `fallback_vendor` only on a concrete signal: an
   authentication failure, an explicit quota or rate-limit response, or a
   documented unavailability. Record the exact signal. Never fall back on a
   guess, a slow response, or a preference.
4. **Return `BLOCKED`** when a required route has no authenticated vendor. Name
   each vendor, its observed state, and the exact command the user runs to
   authenticate. Do not attempt an interactive login: the agent cannot complete
   one, and a half-finished login leaves a worse state than none.

## Reporting

Report `vendor`, `authenticated`, and `fallback_reason` factually.

- Never invent a usage percentage, a quota figure, a model identifier, or a
  capability class. If the runtime does not expose it, report `unknown`.
- `not_checked` is an honest value and is preferable to a probe that was not
  actually run.
- A route that succeeded says which vendor ran; a caller reading the result must
  be able to tell whether its evidence came from one vendor or two.

## Bounds

- One route per role invocation. A role that needs a different vendor mid-task
  is a new invocation, not a silent switch.
- Never route a role the caller did not request.
- Never print, log, or echo a credential, token, or session identifier while
  probing authentication.
