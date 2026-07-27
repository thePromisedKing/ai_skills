# Supermind — Agent Operating Rules (condensed)

Mental-fitness app ("gym for your mind"). React Native (Expo) iOS/Android + NestJS backend, TypeScript monorepo.
**Full development guide: `docs/plan/11-development-guide.md` — read it before non-trivial work. Plan docs in `docs/plan/` are the spec.**

## Invariants (never violate; escalate if a task conflicts)
1. Journal/vent/gratitude **content is E2E-encrypted** — plaintext never sent, stored server-side, logged, or indexed. All content crypto via `packages/crypto`; never hand-roll.
2. **Burn-after-venting**: solo vent content never persists — no vent-content API types, encrypted temp only, wiped on session end.
3. **Analytics = metadata only**, emitted solely through the typed catalog in `packages/analytics`. No free-text properties, ever.
4. **No clinical language** in product copy (banned: therapy, therapist, psychologist, diagnosis, symptom, disorder, treatment). Fitness metaphors only. Copy lives in i18n/CMS, never hard-coded.
5. **Safety is never gated** — crisis directory & "Get more support" sit behind no paywall, flag, auth, or failable rate limit; offline fallback always works.
6. **Calm by default** — no red badges, guilt copy, loss-aversion streak mechanics, or dark patterns.
7. **No ad/tracking SDKs, ever.** New deps need allow-list + audit + justification.
8. **No content/PII in logs** — project logger only; `console.log` fails lint.
9. **i18n + RTL from day one** — no literal UI strings; logical `start`/`end` props only.
10. **Offline-first core** — first render never blocks on network; check-in/breathing/journal/gratitude work in airplane mode.

## Before coding
- Read the relevant `docs/plan/` doc + PRD feature ID; build only that priority (P0/P1/P2) — no scope creep.
- Contract-first: OpenAPI/Zod DTO → regenerate `packages/api-client` → server → client. Never assume an endpoint exists.
- Respect module boundaries: features/modules talk only via exported APIs or domain events (lint-enforced — restructure, never suppress).

## Definition of Done — run, don't assume
```bash
pnpm typecheck && pnpm lint && pnpm test --filter=<touched> && pnpm build
```
Plus: tests written with the code (domain packages ~90% cov) · migrations expand→contract · i18n keys added · a11y props on new UI (roles/labels/44pt/reduced-motion) · flag anything unfinished · **report honestly what you ran, what passed, what you didn't verify**. Never delete/skip failing tests to get green.

## Gates
- **Privacy gate** (content/analytics/storage/logging changes): plaintext scan green, catalog diff approved, deletion handler registered.
- **Safety gate** (vent/crisis/coach/notification changes): crisis E2E suite (incl. airplane mode) green, burn-after-venting forensic test green, Coach red-team suite green per language.
- **Crypto/auth/crisis code → stop and request human security/safety review.**

## Standards (details in guide §4)
- TS `strict`, no `any`; Zod at every boundary, types via `z.infer`; typed errors.
- RN: all animation on UI thread (Reanimated/Skia) — JS-driven animation banned; tokens from `packages/ui` only (no hard-coded styles); every screen has loading/empty/error/offline states; heavy init deferred post-first-frame.
- Backend: idempotent handlers, idempotency keys on mutations, outbox for events, no network calls in transactions, deletion handler for every user-data store.
- Git: Conventional Commits; small single-concern PRs (<400 lines); PR lists PRD IDs, tests, gates run + results.

## Performance budgets (measured on low-end Android; regressions block release)
Cold start ≤ 2.5s · pacer ≥ 58fps (zero JS-thread frames) · session start < 10s · app < 30MB · API p95 < 300ms.
Optimization order: measure → do less work → move off critical path → make work cheaper → only then add caching complexity (with ADR).

## Escalate instead of guessing when
Invariant blocks the task · crypto/auth/crisis changes · PRD vs plan conflict · dep fails allow-list · non-expand-safe migration · scope exceeds the feature's priority tier.
