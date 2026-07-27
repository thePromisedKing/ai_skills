# 11 — Development Guide for AI Agents (Claude Opus)

> **Audience:** Claude Opus agents (and humans) writing code for Supermind.
> **Status:** Load-bearing. Every task executed in this repo follows this guide. If a task conflicts with this guide, stop and surface the conflict — do not silently deviate.
> A condensed version of this guide lives in the root `CLAUDE.md` (auto-loaded each session). This file is the full reference.

---

## 0. Before writing any code (session startup ritual)

1. **Read the relevant plan docs first** — they are the spec:
   - Feature work → `01-product-summary.md` (scope/priority) + the studio's section in `03-mobile-app-plan.md` / `04-backend-plan.md`
   - Data/sync → `05-data-model.md` · Anything touching content/keys/analytics → `06-security-privacy.md`
   - Coach → `07-ai-coach-plan.md` · Pipelines → `08-devops-cicd.md` · Tests → `09-testing-qa.md`
2. **Check the feature's PRD ID** (e.g., JR-3, CS-5) and its priority. Do not build P1/P2 behavior into a P0 task "while you're there."
3. **Plan before code** on anything non-trivial: state the modules you'll touch, the tests you'll add, and the gates that apply. If the plan crosses a module boundary, re-read §3.
4. **Never assume an API exists.** Verify against `packages/api-client` (generated from OpenAPI) or the module's exported surface. If you need a new endpoint, change the contract first (OpenAPI/DTO), regenerate, then implement.

---

## 1. Invariants — violations are release-blocking, never "fix later"

These come from the PRD and are enforced by CI where possible, by review always:

| # | Invariant | Practical rule for agents |
|---|---|---|
| I1 | **Journal/vent/gratitude content is E2E-encrypted; servers never see plaintext** | Content fields go through `packages/crypto` before any storage/network call. Never add a code path that sends, logs, or indexes plaintext content. Server code never gains a decrypt capability |
| I2 | **Burn-after-venting content never persists** | No vent-content types in the API client (unrepresentable). Vent buffers only in the encrypted temp dir; wiped on session end + startup sweep. "Save to Journal" is the sole persistence path |
| I3 | **Analytics carry metadata only** | Emit events ONLY via `packages/analytics` catalog types. Never add a string property that could carry user text. Catalog changes require privacy-owner CODEOWNERS approval |
| I4 | **No clinical language** | UI copy uses fitness metaphors (train/session/reps/recovery). Banned in product copy: therapy, therapist, psychologist, diagnosis, symptom, disorder, treatment. Copy lives in i18n files / CMS, never hard-coded |
| I5 | **Safety is never gated** | Crisis directory, "Get more support", and escalation flows are never behind entitlements, flags-off states, auth walls, or rate limits that can fail closed |
| I6 | **Calm by default** | No red badges, no loss-aversion streak copy, no guilt mechanics, no infinite feeds. Notifications are invitations |
| I7 | **No third-party ad SDKs, ever** | New dependencies must pass the allow-list check; anything with tracking/ads capability is rejected |
| I8 | **No content or PII in logs** | Use the project logger only (it type-rejects content). `console.log` fails lint. user_id is the only identifier that may appear |
| I9 | **Strings are externalized, layouts are RTL-safe** | No literal user-facing strings (lint-enforced). Only logical style props (`start`/`end`, never `left`/`right`) |
| I10 | **Offline-first core** | Check-in, breathing, journal, gratitude, streaks must work in airplane mode. Never make first render depend on network |

---

## 2. Definition of Done (every task)

A task is done only when ALL of these are true — run them, don't assume them:

```bash
pnpm typecheck        # zero errors, no new `any`/`@ts-expect-error` without justification comment
pnpm lint             # includes boundary, i18n-literal, logger, analytics-import rules
pnpm test --filter=<touched packages>   # new logic has tests; all green
pnpm build            # affected apps build
```

- [ ] New/changed behavior covered by tests at the right layer (see §6) — **write the test with the code, not after review asks**
- [ ] OpenAPI updated + client regenerated if the contract changed; breaking-change check passes
- [ ] DB changes follow expand→migrate→contract; migration runs cleanly against a seeded DB
- [ ] i18n keys added for all user-facing strings (English), pseudo-locale renders without overflow
- [ ] Accessibility props on any new interactive UI (role, label, 44pt target); reduced-motion path if animated
- [ ] Feature-flagged if incomplete or user-visible ahead of its release phase
- [ ] Relevant gate checklist from §7 satisfied when the task touches a gated area
- [ ] **Verification statement in the PR/report: what you ran, what passed, what you did NOT verify.** Never report done without having executed the gates. If a check fails, report the failure and output honestly — do not paper over it.

---

## 3. Architecture rules

### Module boundaries (both app and API)
- Features/modules communicate ONLY through their exported public API (`features/*/index.ts`, Nest module exports) or domain events. Importing another module's internals fails `eslint-plugin-boundaries` — never suppress that rule; restructure instead.
- A backend module never reads another module's tables. Need data? Call the module's service or subscribe to its events (outbox pattern).
- New studio/domain = new package/module following the existing contract (`routes`, `api`, `events`). Copy the structure of `features/gratitude` as the reference implementation.
- Shared logic goes to `packages/core` only if it's genuinely domain-generic; resist dumping-ground growth.

### Dependency policy
- Adding a dependency requires: allow-list check (I7), OSV/audit clean, license check (no copyleft in app), a one-line justification in the PR, and preference order: platform API > existing dep > well-maintained new dep > write it.
- Pin exact versions; Renovate handles bumps. Never mix package managers.

### Contract-first
- API changes: DTO/Zod + OpenAPI first → regenerate `packages/api-client` → implement server → implement client. Additive-only within `/v1`; idempotency keys on all mutations; cursor pagination; RFC 9457 errors.

---

## 4. Coding standards

### TypeScript (everywhere)
- `strict: true`; no `any` (use `unknown` + narrowing); no non-null assertions in `packages/*`; `readonly` by default on public types.
- Zod schema is the source of truth for any boundary type (request, queue payload, CMS read, storage row) — derive TS types via `z.infer`, never hand-duplicate.
- Errors: typed error classes per module; never throw strings; async code uses `Result`-style returns or thrown typed errors consistently per package (follow the package's existing pattern).
- Naming: `camelCase` values, `PascalCase` types/components, `SCREAMING_SNAKE` const enums-of-values; files `kebab-case.ts` except components `PascalCase.tsx`.
- Comments explain *why*, not *what*. Match the surrounding file's density. No TODO without a linked issue.

### React Native specifics
- **All animation on the UI thread** (Reanimated worklets / Skia). JS-driven animation (`Animated` with `useNativeDriver:false`, `setInterval` tweens) is banned in `packages/ui` and pacer/game code.
- Components: function components + hooks only; no default exports (except Expo Router routes, which require them); props typed explicitly, no `React.FC`.
- Lists use `FlashList`/`FlatList` with stable keys and memoized renderers; no anonymous inline renderItem closures on hot lists.
- No blocking work before first frame: heavy init behind `InteractionManager`/idle; SDK init deferred post-first-frame (see §8 cold-start budget).
- Every screen handles: loading (skeleton, not spinner), empty (designed state), error (retry affordance), offline (functional or explicitly degraded).
- Styling only via design tokens from `packages/ui` — hard-coded colors/spacing fail review. Dark mode and dynamic type must work by construction (tokens), not per-screen effort.

### Backend (NestJS) specifics
- Validation at EVERY boundary: HTTP (Zod pipes), queue consumers, webhooks, CMS reads. Trust nothing, including our own queue.
- Handlers are idempotent (jobs are at-least-once). Mutations use idempotency keys. DB + event writes use the outbox pattern — never dual-write.
- Transactions: smallest scope that preserves invariants; no network calls inside transactions.
- Every module implements the deletion-handler interface (privacy fan-out) — the registry test fails CI if you add a module that stores user data without one.
- Structured logging with trace context; one log per meaningful state change; no logs in hot loops.

### Git & PRs
- Conventional Commits (`feat(journal): …`, `fix(sync): …`). Small PRs — one concern, ideally < 400 lines of diff; split refactors from behavior changes.
- Commit messages state *why*; PR description lists: PRD IDs addressed, modules touched, tests added, gates run + results, screenshots/recordings for UI.
- Never commit: secrets, `.env`, generated client edits (regenerate instead), lockfile changes unrelated to the PR.

---

## 5. Privacy & security rules for agents (operational)

- Touching `packages/crypto`, key handling, or auth flows → **stop and request human security review** in the PR; never "improve" crypto ad hoc; never roll your own primitives (libsodium only).
- Never weaken an invariant to make a test pass or a feature easier. If an invariant blocks the requested feature, the invariant wins — escalate.
- Test fixtures use obviously-fake content (`"FIXTURE journal text"`); never realistic personal narratives; never real crisis-resource phone numbers in fixtures (use the designated test directory).
- Any new data collection (field, event, log) → check it against doc 06 §5 layers; when in doubt, treat it as content, not metadata.
- Crisis-flow code paths: changes require the crisis E2E suite locally green before pushing, and reviewer sign-off from the safety owner.

---

## 6. Testing requirements (what to write, per change type)

| You changed… | You must add/update… |
|---|---|
| Domain logic (streaks, score, sync merge, crypto, rules engine) | Unit tests incl. edge cases (TZ changes, clock skew, empty states); these packages target ~90% coverage — they are the app |
| A UI component in `packages/ui` | RNTL test (render + a11y roles/labels) + Storybook story |
| A feature screen/flow | RNTL interaction test; extend the relevant Maestro flow if it's on a critical path (doc 09 §2) |
| An API endpoint | Integration test (Testcontainers) + contract test; error + auth cases, not just happy path |
| A queue job / webhook | Integration test proving idempotency (run twice, assert once) |
| A migration | Forward-compat test against seeded snapshot; app N-1 compatibility respected |
| Sync protocol anything | Convergence property tests (two-device simulation) — this is the most-tested code in the repo |
| Coach prompts/filters/guardrails | Red-team suite run (`pnpm eval:coach`); failing cases attached to PR; no merge on regression |

Test quality bar: tests assert behavior, not implementation (no snapshot-everything); deterministic (no real timers/network/randomness — inject clocks); fast (unit suite < 2 min stays enforceable).

**Do not delete or skip failing tests to get green.** Fix the code or fix the test with justification, explicitly called out in the PR.

---

## 7. Gates (checklists that block merge/release)

### G1 — Every PR (CI-enforced)
typecheck · lint (boundaries, i18n, logger, analytics) · unit/component/integration for touched packages · OpenAPI breaking-change check · gitleaks · dependency scan · mobile bundle-size diff within budget.

### G2 — Privacy gate (when touching content, analytics, storage, logging)
- [ ] Plaintext scan: no content in logs/analytics/server fixtures (`pnpm check:plaintext`)
- [ ] Analytics catalog diff approved by privacy owner
- [ ] Deletion handler present for any new user-data store (registry test)
- [ ] Backup/export/erasure implications stated in PR

### G3 — Safety gate (when touching vent, crisis, coach, notifications copy)
- [ ] Crisis E2E suite green, including airplane-mode bundled-fallback case
- [ ] Burn-after-venting forensic test green (vent → kill → relaunch → no residue)
- [ ] Coach changes: red-team suite green per affected language; results archived
- [ ] Copy diff reviewed against I4/I6 (no clinical language, no dark patterns)

### G4 — Release gate (per release train — humans + agents jointly)
- [ ] Full Maestro critical-path suite on device matrix (incl. low-end Android)
- [ ] Perf budgets verified (§8) on real devices, not simulators
- [ ] Accessibility pass (VoiceOver/TalkBack scripted flows, dynamic type 200%, reduced motion)
- [ ] Crash-free ≥ 99.7% on the RC in internal track before promote
- [ ] Store metadata/age-rating unchanged or re-reviewed; no banned terms in listing
- [ ] Staged rollout plan + rollback path (OTA or halt) written in the release issue

---

## 8. Performance budgets & optimization playbook

**Budgets (regressions fail G4; measured on mid/low-end Android):**

| Metric | Budget |
|---|---|
| Cold start → Today interactive | ≤ 2.5s |
| Session start from app open | < 10s (warm target < 3s) |
| Breathing pacer / game loop | ≥ 58fps sustained, zero JS-thread frames |
| App initial download | < 30MB |
| API p95 (non-Coach) | < 300ms |
| Coach first token | < 2s chat |
| JS bundle diff per PR | flagged > +150KB |

**Optimization order of operations (do them in this order, measure between each):**
1. **Measure first** — Sentry TTI traces, `react-native-release-profiler`/Perfetto, React DevTools profiler, `EXPLAIN ANALYZE`. No speculative optimization; attach numbers to the PR.
2. **Do less work** — defer/lazy-load routes and SDKs, cache (TanStack/Redis/CDN), paginate, precompute in jobs (Mind Score is nightly, not per-request).
3. **Move work off the critical path** — UI thread for animation, workers/queues for backend, background sync, prefetch on idle.
4. **Make the work cheaper** — memoize hot renderers, FlashList, index the query (check `pg_stat_statements`), batch sync payloads, image sizes/formats (AVIF/WebP), Hermes-friendly code (no giant polymorphic objects).
5. **Only then** consider caching layers/denormalization that add invariant risk — with an ADR.

**Known hot paths to treat with care:** Today-screen first render (local DB read only), pacer worklets, sync push/pull batching, oplog queries (partitioned, indexed by `(user_id, seq)`), catalog endpoints (CDN, ETag), Coach context assembly (token budget — trim, don't dump).

---

## 9. Feature flags, config & content

- Unfinished work merges dark behind a flag (owner + expiry recorded). Never long-lived branches.
- Tunable behavior (recommendation rules, score weights, caps) reads from remote config with a **sane bundled default** — the app must behave correctly if config never loads.
- User-facing copy that product/clinical may iterate on belongs in CMS or i18n files, not in code.
- Kill switches exist for: Coach, push, cert pinning, each studio. Wire new risky surfaces to one.

## 10. Documentation duties

- Load-bearing decision (stack, protocol, boundary, security posture) → ADR in `docs/adr/` (context → decision → consequences, ~1 page).
- Module behavior that isn't obvious from types → short `README.md` in the module (what it owns, its events, its invariants).
- Keep `CLAUDE.md` current: new commands, new gates, changed conventions — stale agent docs cause repeated agent mistakes. Update it in the same PR that changes the convention.
- Plan docs (`docs/plan/*`) are updated when reality diverges — the plan tracks the build, not the other way around. Flag divergences; don't silently fork.

## 11. Agent workflow & escalation

- **One task, one concern.** Decompose big asks into PR-sized units along module boundaries; land them in dependency order (contract → server → client → UI).
- **Verify empirically.** Run the app/tests; don't reason your way to "it should work." For UI, capture a screenshot/recording. For perf claims, attach measurements.
- **Report honestly.** State what passed, what failed, what was skipped, and what you couldn't verify (e.g., "not tested on physical device"). A wrong "all green" is worse than a true "two failures."
- **Escalate instead of guessing** when: an invariant blocks the task · crypto/auth/crisis code needs changes · the PRD and plan docs conflict · a dependency fails the allow-list · a migration can't be expand-safe · scope creeps beyond the PRD ID's priority.
- Leave the campsite cleaner: fix trivial issues you touch (typos, dead imports); file issues for non-trivial ones; never drive-by refactor inside a feature PR.
