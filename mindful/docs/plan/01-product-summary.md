# 01 — Product Summary & Scope Analysis

## 1. What Supermind is

A **mental-fitness super app**: one membership covering the three need-states —

- **Release** — Vent Space (solo now, human listeners later), Journal
- **Train** — Gratitude Studio, Focus Arena (attention games)
- **Restore** — Calm Room (breathing/relaxation), Nature Escapes (ambient video)

…tied together by a daily **Mind Workout** (warm-up breathing → recommended activity → gratitude cool-down), a **Mind Score** (0–100 metadata-only composite), and an **AI Coach** with cross-studio context.

Two personas share one experience: **The Trainer** (performance-driven, cares about score/streaks) and **The Carrier** (stressed, cares about privacy). A third, **The HR buyer**, arrives in Phase 2 (Teams/B2B). Nothing in the product may label anyone as unwell; all copy uses fitness metaphors.

## 2. Release phases and what ships in each

| Phase | Target | Scope (feature IDs from PRD §5) |
|---|---|---|
| **MVP — closed beta** | Q4 2026, 1,000 invited users | All **P0**: onboarding (CS-1), check-in (CS-2), Mind Workout (CS-3), rule-based recommendations (CS-4), streaks w/ repair (CS-5), Gratitude core (GR-1/2/4), Journal core (JR-1/3/4/5), solo Vent + burn-after-venting (VS-1/3), Calm Room core (CR-1/2/4), 10 nature scenes (NE-1/2/5), safety §6.1–6.2 |
| **v1.0 — public** | Q2 2027 | All **P1**: Mind Score (CS-6), widgets (CS-7), Highlight Reel (GR-3), gratitude jar (GR-5), voice journaling (JR-2), export/erasure (JR-6), guided release flows (VS-2), Focus Arena 4 games (FA-1–4), soundscape mixer (CR-3), offline downloads (CR-5), nature backgrounds (NE-3), **AI Coach v1** (AC-1–4, AC-7), Premium tier |
| **Human layer** | Q4 2027 | Listener marketplace (VS-4–7) — hard-gated on safety stack §6.3 (vetting, training, T&S team, 24/7 coverage, age verification) |
| **Super app / Teams** | 2028 | Teams B2B, TV apps (NE-4), wearables (CS-8), ML personalization, voice Coach (AC-5), proactive coaching (AC-6), localization waves (Arabic → Telugu → Spanish → French) |

**Engineering implication:** MVP is deliberately buildable without any AI/ML — recommendations are a server-editable rules config. The AI Coach, payments, and Focus Arena are all v1.0. Architect for them from day one; build them second.

## 3. Success criteria we must instrument for (PRD §2.3, §10)

| Metric | Target | Engineering consequence |
|---|---|---|
| D30 retention | ≥ 20% | Habit funnel events from day one; cohort analysis in analytics |
| Daily Mind Workout completion | ≥ 35% of DAU | Workout funnel instrumentation |
| Free → paid conversion | ≥ 5% | Entitlement + paywall event tracking (v1.0) |
| Median session start | < 10s from app open | Cold-start budget, prefetching, 1-tap entry points, widgets |
| App store rating | ≥ 4.6 | In-app review prompts (calm, contextual), quality bar |
| Crisis signal SLA | 100% surfaced in-session | Crisis directory: edge-cached **and** bundled offline in the app |
| North star: Weekly Active Minds | ≥ 3 activities across ≥ 2 zones/week | Zone/activity taxonomy fixed early in the event schema |
| Guardrail metrics | streak-anxiety, post-notification uninstalls, distress tickets | Dedicated guardrail dashboard, reviewed weekly |

## 4. Non-functional requirements (PRD §7) — the ones that shape architecture

1. **Performance:** cold start ≤ 2.5s on mid-range Android; 60fps breathing pacer; session start ≤ 10s.
2. **Offline:** breathing, journaling, gratitude, downloaded content fully offline; **conflict-free merge** on reconnect.
3. **Accessibility:** WCAG 2.1 AA — screen readers, dynamic type, reduced motion, captions on all guided audio.
4. **Localization:** strings externalized from day one; **RTL support built in from day one** (Arabic is localization #1); region-aware content & crisis directory. A language ships only when all 7 adaptation workstreams are done (strings, audio, prompts, nature curation, crisis directory, listener pool, AI safety cert).
5. **Reliability:** 99.9% API availability; crisis directory on redundant edge cache + offline bundle.
6. **Battery/data:** adaptive streaming, data-saver (audio-only / still+audio), no background activity beyond scheduled local notifications.

## 5. Privacy & safety spine (PRD §6, §8) — treated as product features

- Journal/vent content: **client-side encrypted**, excluded from analytics/ads/model-training. Only metadata (counts, durations, studio) feeds Mind Score.
- **Burn-after-venting** content is never written to server storage — this must be *architecturally true*, not policy-true.
- Analytics events carry **metadata only** — enforced at the schema level (typed event catalog; no free-text fields).
- GDPR / UK GDPR / CCPA at launch; self-serve export & deletion; deletion propagates through backups ≤ 30 days.
- Crisis flow: region-aware directory, remotely served, quarterly reviewed, full-screen supportive sheet on user-initiated crisis signals. Scanning of private content is **off by default**, opt-in only, and gated on clinical+legal review.
- Teams (later): aggregate-only reporting, minimum cohort 20.
- AI Coach: never a clinician; hard scope limits at the model layer; per-language red-team certification is a launch gate (AC-4).

## 6. Monetization (PRD §9)

- **Free:** daily Mind Workout, basic journal + gratitude, 3 Calm sessions, 1 nature scene, solo venting, capped Coach check-in. Free tier must stay genuinely useful forever.
- **Premium:** $9.99/mo · $59.99/yr · family (5) $99.99/yr — everything, offline downloads, full Mind Score analytics, unlimited Coach.
- **Rules:** no ads ever; paywalls never gate safety features/crisis resources; regional PPP pricing (India explicitly).
- Engineering: entitlement service must support **feature-level flags per tier + region**, family plans, and later Teams seats and listener session credits/commission.

## 7. Open questions that block engineering work

| PRD Q# | Question | Blocks | Plan default until answered |
|---|---|---|---|
| 1 | Produce vs license nature content | Media pipeline sizing (MVP) | Assume licensed 4K library at MVP; rights registry either way (NE-5) |
| 4 | Mind Score weights / anti-gaming | CS-6 (v1.0 design) | Appendix B draft formula, server-tunable, A/B-tested |
| 6 | Age rating (13+ vs 16+ per region) | Store metadata, onboarding age gate (beta) | Build a configurable age gate; default 13+ |
| 9 | AI Coach model/provider, hosting region, unit cost | AC-1 design (v1.0) | Provider-agnostic gateway; Claude primary; region pinning supported |
| 2,3,5,7,8 | Launch markets, clinical board, listener legal, Arabic dialects, India pricing | Later phases | Track in roadmap; not MVP-blocking |

## 8. Explicitly out of scope (v1.0)

Therapy/diagnosis/clinical services · public social feeds & comparative mechanics · AI-as-clinician (permanently, absent regulatory path) · sleep hardware beyond standard health APIs · web app (marketing site only).

**Engineering note:** "no public social feed" removes moderation infrastructure from MVP/v1.0 entirely. The only shareable artifact is the Highlight Reel image, exported by explicit user action.
