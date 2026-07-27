# 09 — Testing & QA Strategy

Quality bars come straight from the PRD: ≥ 4.6 store rating (trust-driven category), 100% crisis SLA, WCAG 2.1 AA, 60fps pacer, offline-first correctness, and AI safety gates equal in weight to functional QA.

## 1. Test pyramid & ownership

| Layer | Mobile | Backend | Runs |
|---|---|---|---|
| Static | TS strict, ESLint (boundaries, i18n literals, logger/PII, analytics imports) | same + OpenAPI diff | every PR |
| Unit | Domain logic in `packages/*` (streak rules, score math, crypto, sync merge) — Vitest | module services, rules engine, entitlement logic — Vitest | every PR |
| Component | React Native Testing Library for `ui` + feature screens; Storybook stories double as test fixtures | — | every PR |
| Integration | sync engine against a real local server; SQLite migrations forward-compat | Testcontainers (PG/Redis): repos, jobs, webhooks, deletion fan-out | every PR |
| Contract | generated client vs OpenAPI; mock-server drift check | provider tests per module API | every PR |
| E2E | **Maestro** flows on iOS sim + Android emulator (incl. one low-end profile) | API smoke suite post-deploy | main + release |
| Manual | exploratory + design QA + device lab (see §5) | — | weekly train |

Coverage philosophy: high coverage on domain packages (score, streaks, crypto, sync — target ~90%); pragmatic elsewhere; no coverage theatre on UI glue.

## 2. Critical-path E2E suites (Maestro)

1. **First-run:** install → ≤ 4-screen onboarding → guest mode → first session < 2 min (asserted).
2. **Mind Workout:** check-in → warm-up → activity → cool-down → streak increments; repeat with airplane mode on (offline parity).
3. **Journal privacy:** create entry → app lock engages on background → biometric unlock → entry intact; verify DB file contains no plaintext (fixture scan).
4. **Burn-after-venting:** vent → force-kill → relaunch → temp storage empty; vent → save to journal → appears encrypted.
5. **Crisis path:** "I need urgent help" from Vent + from settings → sheet < 1s, correct region resources, works in airplane mode (bundled fallback).
6. **Sync/conflict:** two devices, offline edits to same entry → both converge, no data loss.
7. **Streak repair:** simulated missed day → compassionate message → 1-tap repair works.
8. **v1.0 additions:** paywall/purchase (sandbox), restore purchases, family plan; Coach chat happy path + scripted escalation; downloads offline playback; widget deep links.

## 3. Non-functional testing

| Area | Method | Budget |
|---|---|---|
| Cold start | Firebase Test Lab / device farm on mid-range Android, per release | ≤ 2.5s to Today screen |
| Pacer FPS | Perf test harness with Reanimated/Skia frame callbacks, low-end device | ≥ 58fps sustained, zero JS-thread dependency |
| Session start | E2E timer app-open → session running | < 10s (target < 3s warm) |
| Bundle/app size | CI diff per PR | < 30MB initial (excl. on-demand media) |
| Battery/data | Manual profiling on nature streaming, data-saver assertions | audio-only rendition verified |
| API load | k6 on sync + workout endpoints before beta; soak test before v1.0 | p95 < 300ms at 10× projected load |
| Chaos | kill origin → crisis directory still serves (edge+bundle); DB failover drill | zero user-visible crisis failures |

## 4. Accessibility QA (WCAG 2.1 AA)

- Per-PR: RNTL a11y assertions on primitives (roles/labels/targets).
- Per release train: VoiceOver + TalkBack scripted passes on core flows; dynamic type 200%; reduced-motion pass (pacer alternative); contrast audit automated on tokens.
- Captions present for every published audio session — **CMS publish-time validation**, not QA-time.

## 5. Device & locale matrix

- iOS: current + previous major, incl. one small (SE-class) device; iOS 16 floor.
- Android: 9 → current; one 3GB-RAM low-end device in every regression; one tablet sanity pass.
- Pseudo-locale + RTL snapshot suite every PR (Arabic-readiness); real-locale passes begin with each localization wave.

## 6. Safety & privacy launch gates (release-blocking)

| Gate | When |
|---|---|
| Crisis E2E suite green (incl. offline) | every release |
| Burn-after-venting forensic check (no residue on device/server) | every release touching vent/storage |
| Plaintext scan: no journal/gratitude content in logs, analytics ingest, or server DB fixtures | every release |
| Analytics catalog diff signed off by privacy owner | when catalog changes |
| Deletion pipeline verification (module registry test + staged end-to-end erasure drill) | every release / quarterly drill |
| AI Coach red-team suite per language (doc 07 §6) + clinical sign-off | every Coach-affecting release |
| Copy review: fitness-not-illness language, no clinical claims (legal/clinical flag in CMS) | content publish workflow |
| Store-listing compliance (no "therapy/therapist" wording, correct age rating) | every store release |

## 7. Beta program (Q4 2026, 1,000 users)

- Staged invites (100 → 400 → 1,000); TestFlight + Play closed track; in-app feedback affordance + weekly survey.
- Instrumented explicitly for: habit funnel, D3/D7 return, crash-free ≥ 99.5%, guardrail metrics, qualitative privacy-trust signals.
- Exit criteria to v1.0 build phase: crash-free ≥ 99.7%, D7 ≥ 25% (leading indicator for D30 ≥ 20%), median session start < 10s verified in the field, zero crisis-SLA misses, sync-loss reports = 0.
