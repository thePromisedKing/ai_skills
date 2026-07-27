# 02 — System Architecture

## 1. Architecture principles

1. **Modular monolith first, services when forced.** One deployable backend with hard module boundaries (enforced by lint rules and module APIs). Extract a module to a service only when scale, isolation, or team topology demands it (media, AI gateway are the first candidates). This is the industry-consensus path pre-PMF: microservice ops burden without microservice needs kills small teams.
2. **The privacy boundary is architectural.** Content the PRD says we can't read (journal, vents) is encrypted on-device before it ever reaches an API. Servers store ciphertext + metadata. There is no server code path that can decrypt user content.
3. **Offline-first client, server as sync authority for metadata.** The app is fully usable without network for core loops; sync is background, conflict-free, and invisible.
4. **Content is data, not code.** Sessions, prompts, game configs, recommendation rules, crisis directory, and copy variants live in a CMS/remote-config plane and ship without app releases.
5. **Everything behind an interface.** Auth provider, LLM provider, analytics, payments, media host — all wrapped in our own thin module so any vendor can be swapped (the PRD's 2028 scope guarantees requirements will change).
6. **Feature modules mirror studios.** Both app and backend are organized by studio/domain (gratitude, journal, vent, calm, nature, focus, coach, workout) plus platform modules (identity, entitlements, sync, content, notifications, safety, analytics). New studios (listener marketplace, Teams) drop in as new modules.

## 2. System context diagram

```mermaid
graph TB
    subgraph Clients
        A[React Native App<br/>iOS + Android]
        W[Widgets / Quick Actions]
        TV[TV Apps — Phase 3+]
    end

    subgraph Edge
        CDN[CDN<br/>media + crisis directory + content cache]
        GW[API Gateway / WAF<br/>rate limiting, authn]
    end

    subgraph Backend["Backend (modular monolith → services)"]
        API[Core API — NestJS]
        SYNC[Sync module]
        ENT[Entitlements]
        SAFE[Safety module<br/>crisis directory service]
        COACH[AI Coach service<br/>guardrails + context engine]
        NOTIF[Notification service]
    end

    subgraph Data
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        OBJ[(Object storage<br/>ciphertext blobs, media)]
        Q[[Queue / jobs]]
    end

    subgraph SaaS["External (behind our interfaces)"]
        IDP[Identity provider]
        LLM[LLM provider(s)]
        RC[RevenueCat + stores]
        CMS[Headless CMS]
        AN[PostHog analytics<br/>metadata-only]
        PUSH[FCM / APNs]
        MEDIA[Video pipeline<br/>Mux / MediaConvert]
    end

    A --> GW --> API
    A --> CDN
    A -.metadata-only events.-> AN
    API --> PG & REDIS & OBJ & Q
    API --> ENT & SYNC & SAFE
    COACH --> LLM
    API --> COACH
    NOTIF --> PUSH
    API --> IDP
    ENT --> RC
    CMS --> CDN
    MEDIA --> CDN
```

## 3. Technology stack — decisions and rationale

### Mobile

| Concern | Choice | Rationale / best practice |
|---|---|---|
| Framework | **React Native, New Architecture** (Fabric + TurboModules), latest stable | User directive; New Arch is now default and required for Reanimated 4 / modern libs |
| Tooling | **Expo (prebuild + custom dev client) + EAS Build/Submit/Update** | Industry default for new RN apps; native modules still fully available via config plugins; OTA updates for JS-level fixes |
| Language | TypeScript, `strict: true` | Non-negotiable modern practice |
| Navigation | **Expo Router** (file-based, typed routes) over React Navigation core | Deep links + widgets need robust URL routing; typed routes reduce nav bugs |
| Server state | **TanStack Query** | Cache, retry, offline mutation queue patterns are solved problems |
| Client state | **Zustand** (small, per-feature stores) | Avoid Redux ceremony; stores live inside feature modules |
| Local DB | **SQLite (op-sqlite) + Drizzle ORM**; MMKV for KV/prefs | Offline-first journals/gratitude/sessions; fast, typed queries |
| Crypto | **libsodium (react-native-libsodium)** + Keychain/Keystore via `react-native-keychain` | E2EE requirement (see doc 06) |
| Animation | **Reanimated 4 + React Native Skia** (breathing pacer, score rings), Lottie/Rive for illustrations | Only reliable way to hit 60fps pacer on low-end Android — runs on UI thread |
| Audio/video | `expo-audio`/`react-native-track-player` (background audio, sleep timer), `react-native-video` w/ HLS | Calm Room + Nature Escapes; background playback + lock-screen controls |
| i18n | `i18next` + ICU messages; `I18nManager` RTL from day one | Arabic is first localization; retrofitting RTL is a rebuild |
| Payments | **RevenueCat SDK** | Cross-platform entitlements, receipt validation, price experiments |
| Analytics | PostHog RN SDK behind our `analytics` package (typed event catalog) | Enforces metadata-only rule at compile time |
| Crash/perf | Sentry (RN) | Release health, cold-start and pacer-FPS monitoring |

### Backend

| Concern | Choice | Rationale |
|---|---|---|
| Runtime/framework | **Node.js (or Bun) + NestJS** modular monolith | Same language as app = shared types/validation; Nest enforces module boundaries + DI; hiring pool |
| API style | **REST + OpenAPI** (generated client for app); WebSocket/SSE for Coach streaming | Simple, cacheable, contract-first; tRPC considered but OpenAPI keeps future non-TS consumers (TV, partners) easy |
| Database | **PostgreSQL** (managed: RDS/Cloud SQL) | Relational core + JSONB flexibility; boring and correct |
| Cache/queues | Redis (cache, rate limits) + **BullMQ** jobs (or SQS) | Reminders, highlight-reel generation, deletion propagation |
| Object storage | S3/GCS with lifecycle policies | Ciphertext blobs, exports, media masters |
| CMS | **Payload CMS** (self-hosted, TypeScript) | Sessions/prompts/rules/crisis directory editable by non-engineers; publishes to CDN-cached read API |
| Remote config & flags | **Unleash** (self-hosted) or Statsig | CS-4 rule-based recommendations, Mind Score weights, kill switches, A/B tests |
| Media | Mux **or** S3 + MediaConvert + CloudFront (HLS ladder incl. audio-only rendition) | NE-2 adaptive + battery-saver mode maps directly to HLS renditions |
| Auth | Managed IdP (Firebase Auth or Cognito): anonymous → linked (Apple/Google/email) | CS-1 guest mode; account only for sync |
| Infra | **Terraform** IaC; containers on ECS Fargate / Cloud Run; multi-AZ | 99.9% availability; reproducible envs |
| Observability | OpenTelemetry → Grafana/Tempo/Loki (or Datadog) + Sentry | SLOs on availability + crisis-directory latency |

## 4. Backend module map (monolith boundaries)

```
apps/api
├── modules/
│   ├── identity/        # auth adapter, guest→account linking, devices
│   ├── profiles/        # user prefs, locale, notification windows, app-lock settings
│   ├── entitlements/    # tiers, RevenueCat webhooks, feature gates, regional pricing
│   ├── sync/            # offline sync protocol, per-collection cursors, conflict rules
│   ├── workout/         # Mind Workout assembly, recommendation rules engine (CS-4)
│   ├── checkins/        # mood check-ins (metadata)
│   ├── streaks/         # streak + repair logic (CS-5), compassionate semantics
│   ├── mindscore/       # score computation (server-tunable weights), history
│   ├── gratitude/       # entries (ciphertext), prompts read-model, highlight reel jobs
│   ├── journal/         # ciphertext blobs, tags, export & erasure jobs
│   ├── vent/            # solo vent metadata only; burn-after-venting = no content path
│   ├── calm/            # session catalog read-model, downloads entitlement checks
│   ├── nature/          # scene catalog, rights registry (NE-5), stream tokens
│   ├── focus/           # game configs, results, personal bests (v1.0)
│   ├── coach/           # AI gateway, context engine, memory, guardrails (v1.0)
│   ├── safety/          # crisis directory, escalation flows, "get more support"
│   ├── notifications/   # invitations-not-alarms scheduling, quiet hours
│   ├── analytics-gate/  # event schema registry & validation (metadata-only enforcement)
│   └── privacy/         # DSAR export, account deletion orchestration (30-day propagation)
└── platform/            # config, database, queue, telemetry, http, feature-flags
```

**Boundary rules (enforced):** modules communicate through their public API (Nest module exports) or domain events on the queue — never by importing another module's internals or touching its tables. `eslint-plugin-boundaries` + CI check. This is what makes later service extraction (coach, media, teams) mechanical instead of surgical.

## 5. Future-extension readiness (PRD phases 3–4)

| Future need | Provision we make now |
|---|---|
| Listener marketplace (VS-4–7) | `identity` supports roles; `entitlements` supports pay-per-session SKUs; session/booking domain isolated as a future `marketplace` module; T&S audit-log infrastructure designed in `safety` |
| Teams / B2B | `orgs` concept stubbed in identity (nullable org_id); aggregate-only reporting warehouse kept separate from product DB; min-cohort-20 enforced in the reporting layer, not the UI |
| TV & wearables | API is client-agnostic (OpenAPI); content catalog & stream tokens have no phone assumptions; watch app = separate target sharing domain packages |
| ML personalization (CS-4 → P2) | Recommendation engine is an interface: `RuleBasedRecommender` now, `MLRecommender` later; all inputs already flow through the metadata event spine |
| Localization waves | i18n + RTL from day one; all content entities carry `locale`; crisis directory keyed by region; Coach language gates modeled as flags |
| Data residency | Region field on user; storage abstractions take region hints; no cross-region PII joins in analytics |

## 6. Key end-to-end flows

### Daily Mind Workout (CS-3/CS-4)
1. App opens → local rules bundle (synced from remote config) + last check-in produce today's workout **offline-capable**; server recomputes and reconciles when online.
2. Warm-up (breathing, Skia pacer) → Workout (recommended studio activity) → Cool-down (gratitude over cached nature scene).
3. Completion events → streaks module → Mind Score inputs. All metadata.

### Burn-after-venting (VS-1) — the "architecturally true" version
1. Vent recorded to **memory / encrypted temp file only**; never enters the sync queue.
2. Session end → secure wipe of temp storage. Only a metadata event (`vent_completed`, duration bucket) is emitted.
3. "Save to Journal" is the only path that persists — it runs the normal journal E2EE write.

### Crisis surfacing (§6.2)
1. User taps "I need urgent help" (or keyword match on **user-initiated** search) → full-screen supportive sheet.
2. Directory source order: memory cache → CDN edge → **bundled offline fallback** shipped in every app binary. 100% SLA holds with zero connectivity.

### Sync (offline-first)
Per-collection append-oriented sync: client keeps a local oplog; push mutations with client timestamps + device id; server orders per-entity with last-writer-wins **per field**, and set-union for tags/attachments (conflict-free for our data shapes — journals/gratitude are single-author). Cursor-based pull. Full spec in doc 05.
