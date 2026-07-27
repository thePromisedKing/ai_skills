# Supermind — End-to-End Build Plan

> Build plan derived from `Supermind_PRD.docx` (v1.0, July 2026).
> Platforms: **iOS 16+ / Android 9+**, built with **React Native**. Backend: **TypeScript modular monolith → services**.
> Targets: Closed beta (MVP, all P0) **Q4 2026** · Public v1.0 (all P1) **Q2 2027** · Human layer **Q4 2027** · Teams/Super app **2028**.

## Document map

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Product Summary & Scope](./01-product-summary.md) | PRD analysis, personas, priorities, non-negotiables, open questions that block engineering |
| 02 | [System Architecture](./02-architecture-overview.md) | End-to-end architecture, tech stack decisions & rationale, modularity and future-extension strategy |
| 03 | [Mobile App Plan](./03-mobile-app-plan.md) | React Native architecture, monorepo layout, feature modules, navigation, state, offline-first, design system, animations, accessibility, i18n/RTL |
| 04 | [Backend Plan](./04-backend-plan.md) | Service/module breakdown, API design, content pipeline (CMS), media/streaming, notifications, payments, entitlements |
| 05 | [Data Model](./05-data-model.md) | Core entities, schemas, sync model, Mind Score data spine, retention & deletion |
| 06 | [Security & Privacy](./06-security-privacy.md) | E2E encryption design, key management & recovery, GDPR/UK GDPR/CCPA, metadata-only analytics, app lock |
| 07 | [AI Coach Plan](./07-ai-coach-plan.md) | LLM architecture, context engine, guardrails, crisis escalation, red-team eval gates, per-language certification, memory |
| 08 | [DevOps & CI/CD](./08-devops-cicd.md) | Environments, CI/CD pipelines, EAS/store releases, OTA updates, IaC, observability, feature flags & remote config |
| 09 | [Testing & QA Strategy](./09-testing-qa.md) | Test pyramid, RN testing stack, backend testing, performance budgets, accessibility QA, safety launch gates |
| 10 | [Roadmap & Delivery Plan](./10-roadmap-milestones.md) | Phase-by-phase epics, sequencing, team shape, milestone exit criteria, risk register |
| 11 | [Development Guide (AI agents)](./11-development-guide.md) | Operating rules for Claude Opus agents: invariants, Definition of Done, coding standards, merge/release gates, performance budgets, escalation rules. Condensed copy auto-loaded via root `CLAUDE.md` |

## How to read this plan

- **Start with 01 + 02** for the "why" and the shape of the system.
- **03/04/05** are the day-to-day engineering references for mobile, backend, and data.
- **06 and 07** are *launch gates*, not optional hardening — the PRD makes privacy and AI safety equal in weight to functional QA.
- **08/09/10** define how we ship: pipelines, quality bars, and the order of work.

## Guiding constraints (from the PRD — non-negotiable)

1. **Fitness, not illness** — training language everywhere; no diagnostic framing; legal/clinical review on benefit copy.
2. **Private by default** — journal/vent content is E2E encrypted, never in analytics or model training; burn-after-venting never touches server storage.
3. **Calm by default** — no dark patterns, no red badges, no guilt streak mechanics.
4. **7 minutes is enough** — every core loop completable in < 7 min; session start < 10s from app open.
5. **Works everywhere** — offline-first core, low-end Android performance (cold start ≤ 2.5s mid-range), data-saver modes.
6. **Safety is a launch gate** — crisis directory always reachable, escalation flows tested, AI Coach red-team suite passes per language before launch.
7. **No ads. No third-party ad SDKs. Ever.**

## Standing decisions (assumptions this plan makes)

| Decision | Choice | Alternatives considered |
|---|---|---|
| Mobile framework | React Native (New Architecture) + Expo (prebuild/dev clients, EAS) | PRD suggested Flutter; user directive is RN. Bare RN considered — Expo chosen for velocity + OTA + store tooling |
| Language | TypeScript everywhere (strict) | — |
| Backend | NestJS modular monolith on managed cloud (AWS or GCP), PostgreSQL + Redis + object storage | Firebase/Supabase (fine for prototypes; conflicts with E2EE/data-residency/modularity goals) |
| CMS | Headless CMS (Payload CMS, self-hosted) for sessions, prompts, games config, crisis directory | Contentful/Strapi/Sanity |
| Media | HLS adaptive streaming via CDN (Mux or CloudFront + MediaConvert) | DASH-only; self-hosted packaging |
| Subscriptions | RevenueCat over StoreKit 2 / Play Billing | Direct store APIs (more work, less insight) |
| Analytics | PostHog (self-hosted or EU cloud), typed metadata-only event catalog | Amplitude/Mixpanel (weaker privacy posture) |
| Auth | Managed IdP with anonymous→linked accounts (Firebase Auth or Cognito) behind our own `identity` module | Ory/Keycloak self-hosted (revisit at scale / for data-residency) |
| AI Coach | Provider-agnostic LLM gateway; Claude as primary model; guardrails + eval harness in our stack | Direct vendor lock-in |

Anything above that the founder/product lead wants changed should be changed **before Phase 0 ends** — these choices are load-bearing.
