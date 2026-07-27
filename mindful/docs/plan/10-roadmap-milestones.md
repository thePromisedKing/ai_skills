# 10 — Roadmap & Delivery Plan

Working back from the PRD milestones: **closed beta Q4 2026** (≈ 3.5–4.5 months away from an Aug 2026 start), **v1.0 Q2 2027**, **human layer Q4 2027**, **super app 2028**.

## Team shape (recommendation)

| Phase | Team |
|---|---|
| Phase 0–1 (MVP) | 2 RN engineers · 2 backend/full-stack · 1 designer · 1 PM/founder · fractional: DevOps, QA, security review, clinical advisor, legal |
| Phase 2 (v1.0) | +1 RN (Focus Arena/widgets) · +1 AI engineer (Coach) · +1 QA · content team ramps (30+ sessions, 40+ scenes) |
| Phase 3+ | + marketplace squad + T&S staffing (per §6.3, before marketplace launch) |

Squads own studios end-to-end (feature package + backend module) — the module architecture exists precisely so this scales.

---

## Phase 0 — Foundations (Weeks 1–6)

The goal is that studio work in Phase 1 lands on rails.

- [ ] Monorepo + CI skeleton; Expo app boots with router, theming, i18n(+RTL), Storybook
- [ ] Design system v0: tokens, primitives, BreathingPacer prototype **spiked to 60fps on a low-end Android — do this in week 1–2; it de-risks the RN choice**
- [ ] Backend skeleton: NestJS modules, Postgres, migrations, OpenAPI → generated client
- [ ] Auth: guest identity → account link flow; device registry
- [ ] E2EE core (`packages/crypto`): keys, wrap/unwrap, recovery-kit design review — **decided and security-reviewed here, not retrofitted**
- [ ] Sync engine v1 (oplog, HLC, per-field LWW) with journal as the pilot collection
- [ ] CMS stood up; content schemas; crisis directory collection + CDN publish + in-app bundle pipeline
- [ ] Analytics catalog v1 + PostHog wiring; flags (Unleash); Sentry; staging env via Terraform
- **Exit:** walking skeleton — check-in → breathing session → encrypted journal entry syncs between two devices; crisis sheet works offline.

## Phase 1 — MVP build (Weeks 7–18) → Closed beta Q4 2026

Studio tracks in parallel (one squad each), platform track continuous:

| Track | Scope |
|---|---|
| Core loop | Onboarding (CS-1), check-in (CS-2), Mind Workout orchestration (CS-3), rules engine + remote config (CS-4), streaks + repair (CS-5) |
| Gratitude + Journal | GR-1/2/4; JR-1/3/4/5 (editor, prompts, app lock, tags/calendar) |
| Vent + Calm | VS-1/3 (burn-after-venting, cool-down offers); CR-1/2/4 (pacer patterns, session library, background audio) |
| Nature | NE-1/2/5: 10 scenes, HLS pipeline, battery-saver renditions, rights registry |
| Safety | §6.1–6.2: get-more-support everywhere, crisis directory + offline fallback, quarterly review workflow |
| Hardening | Perf budgets, accessibility pass, offline QA, beta program tooling, DPIA, scoped security review |

- Weeks 15–18: feature freeze → hardening → staged beta invites (100 → 1,000).
- **Exit = beta criteria (doc 09 §7).**

## Phase 1.5 — Beta iteration (Q4 2026 → Q1 2027)

Retention instrumentation review, habit-loop tuning via remote config, crash/perf burn-down, copy/tone iteration, pricing research for v1.0, Coach prototype behind internal flag.

## Phase 2 — v1.0 build (Q1–Q2 2027)

| Track | Scope |
|---|---|
| AI Coach | AC-1/2/3/7 + red-team harness + per-language gate (doc 07); clinical advisory cycle established |
| Mind Score | CS-6 (weights in config, A/B vs guardrails), score UI, history |
| Focus Arena | Game engine + 4 games (FA-1–4), legal copy review |
| Monetization | RevenueCat, paywall, Premium entitlements, family plan, regional pricing scaffolding |
| Content scale | ≥ 30 calm sessions, 40+ scenes, soundscape mixer (CR-3), offline downloads (CR-5) |
| Journal/Gratitude v2 | Voice journaling (JR-2), export/erasure self-serve (JR-6), Highlight Reel (GR-3), jar (GR-5) |
| Vent v2 | Guided release flows (VS-2) |
| Platform | Widgets (CS-7), quick actions, notifications v2, pen test, store launch program (ASO, phased rollout) |

**Launch gates:** all doc 09 §6 safety gates + Coach language certification (English) + pen-test findings closed + 99.9% SLO demonstrated over 30 days in staging/beta prod.

## Phase 3 — Human layer (Q3–Q4 2027)

Listener marketplace (VS-4–7) **gated on §6.3**: vetting/background checks, training & certification flows, T&S team + 24/7 coverage, escalation protocols, age verification (18+), payments/commission (open Q5 legal review first). New `marketplace` module + T&S console. Also: voice Coach (AC-5) groundwork.

## Phase 4 — Super app (2028)

Teams B2B (org model, admin console, aggregate-only reporting w/ min-cohort-20, SSO/SCIM), TV apps, wearables (CS-8), ML personalization (swap `Recommender`), proactive coaching (AC-6), localization waves per §7.1 gates (Arabic first — RTL debt is already zero by design).

---

## Milestone exit criteria (summary)

| Milestone | Must be true |
|---|---|
| Phase 0 exit | Walking skeleton demo; pacer 60fps on low-end Android; E2EE + recovery design signed off |
| Beta ship | All P0 features; crisis SLA suite green; DPIA done; crash-free ≥ 99.5% in RC |
| Beta exit | D7 ≥ 25%; zero sync-loss; zero crisis misses; qualitative trust signal positive |
| v1.0 ship | All P1; Coach English cert archived; pen test closed; store compliance review; pricing live |
| Marketplace ship | §6.3 fully operational (staffed T&S, 24/7 plan, protocols drilled); legal classification resolved |

## Risk register (top items)

| Risk | Likelihood | Mitigation |
|---|---|---|
| RN perf on low-end Android (pacer, cold start) | Medium | Week-1 spike; Skia/Reanimated-only animation; perf budgets in CI; low-end device in every pass |
| E2EE + multi-device/recovery UX confuses users | Medium-high | Device-to-device approval as default path; recovery phrase UX tested in beta; honest copy |
| Sync conflicts / data loss erodes trust | Medium | Conservative merge model; sync suite is the most-tested code; beta exit criterion = zero loss reports |
| Coach safety incident post-launch | Low-med, high impact | Defense-in-depth guardrails; deterministic crisis path; canary evals; kill switch; incident runbook |
| Store review friction (mental-wellness category, age rating) | Medium | Early store pre-review; no clinical wording; age-rating strategy resolved pre-beta (open Q6) |
| Content pipeline underestimated (30 sessions, 40 scenes, licensing) | High | Decide produce-vs-license (open Q1) at kickoff; rights registry from day one; content team ramp in Phase 2 |
| LLM cost at scale | Medium | Tiered models, caching, per-user budgets; cost instrumented from prototype (target < $0.05/DAU/day) |
| Single point of failure: small team + broad scope | High | Modular boundaries keep studios independent; ruthless P0 discipline — MVP has no AI, no payments, no games |
