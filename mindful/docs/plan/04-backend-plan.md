# 04 — Backend Plan

## 1. Shape: modular monolith, service-ready

Single NestJS deployable (`apps/api`) with hard module boundaries (see doc 02 §4), plus three planes that are separate from day one because their lifecycles differ:

| Plane | What | Why separate |
|---|---|---|
| **Core API** | All product modules | The monolith |
| **Content plane** | Payload CMS + CDN-cached read API | Content ships without app or API releases (CR-4, GR-2, CS-4 rules, crisis directory §6.2) |
| **AI plane** | Coach service (gateway + guardrails) | Different scaling, cost, and safety-review cadence; first extraction candidate (doc 07) |

Async work (highlight reels, deletion propagation, exports, notification scheduling, RevenueCat webhooks) runs on BullMQ workers in the same codebase, separately deployable.

## 2. API design standards

- **Contract-first OpenAPI 3.1**; spec generated from Nest decorators + Zod DTOs; TypeScript client generated into `packages/api-client`. Breaking-change check in CI (oasdiff).
- **Versioning:** URL major version (`/v1/...`); additive changes only within a version; deprecation headers + minimum-supported-app-version endpoint (the app checks it and prompts gentle upgrade).
- **Auth:** short-lived JWT access tokens (15 min) + rotating refresh tokens, issued after IdP verification; device-bound sessions; anonymous (guest) tokens with restricted scopes, upgradeable in place on account link.
- **Conventions:** cursor pagination everywhere; RFC 9457 problem+json errors; idempotency keys on all mutating endpoints (offline clients retry); request IDs propagated (OTel).
- **Rate limiting:** per-user + per-IP at gateway; stricter budgets on Coach endpoints (cost) and auth (abuse). Crisis directory endpoints are **never** rate-limited to failure — they degrade to cache.

### Endpoint groups (v1 surface)

```
/v1/auth/*                       token exchange, guest upgrade, devices
/v1/me                           profile, preferences, locale, entitlements summary
/v1/sync/*                       push/pull per collection (journal, gratitude, checkins, sessions)
/v1/workout/today                assembled Mind Workout (rules-engine output + content refs)
/v1/checkins                     mood check-ins (metadata)
/v1/streaks                      current streak, repair endpoint
/v1/mindscore                    score + components + history            (v1.0)
/v1/content/*                    CDN-cached: calm sessions, prompts, scenes, games config
/v1/media/stream-token           short-lived signed HLS URLs
/v1/safety/crisis-directory      region-aware; edge-cached; ETag'd for offline bundle refresh
/v1/coach/*                      chat (SSE), memory list/delete, opt-ins   (v1.0)
/v1/privacy/export|delete        DSAR self-serve
/v1/entitlements/*               RevenueCat webhook, restore, family plan  (v1.0)
```

## 3. Module specifications (key ones)

### workout — recommendation rules engine (CS-4)
- Rules live in remote config as versioned JSON: `[{ when: {mood: "low", timeOfDay: "evening"}, recommend: {studio: "calm", tag: "wind-down"}, weight }]`.
- Engine evaluates check-in + recent activity metadata → activity ref; deterministic + explainable ("because you checked in tired").
- Same rules bundle is served to clients for offline evaluation; server result wins when both exist.
- **Interface** `Recommender` so the P2 ML version is a drop-in.

### streaks (CS-5)
- Streak = any completed activity per local-day (user timezone, stored per user; handle TZ moves generously — never punish travel).
- Repair: missing yesterday offers a one-tap micro-session that back-fills a "repair" day (marked as such, still counts). No decay mechanics, no loss framing in any server-generated copy.

### mindscore (CS-6, Appendix B)
- Nightly job + on-demand recompute: `40% consistency (trailing 14d, diminishing returns >5/wk) + 30% balance (entropy across zones) + 30% mood trend (redistributed when absent)`.
- Weights in remote config; every change A/B-tested against guardrail metrics; formula version stamped on each score row for auditability.
- Inputs are **metadata only** — enforced because the score module literally has no access to content tables (they hold ciphertext anyway).

### journal / gratitude (content-bearing)
- Store: `{ id, user_id, created_at, updated_at, schema_version, ciphertext, nonce, key_id, metadata: {word_count_bucket, has_photo, tags[] (user-applied, client-encrypted? → plaintext tags allowed but user-warned), duration } }`.
- Server can order, sync, and count — never read. Photos: ciphertext blobs in object storage, referenced by key.
- Export job (JR-6): server returns ciphertext bundle; **decryption and PDF rendering happen on-device**. Erasure: hard-delete rows + blobs, tombstones to devices, backup propagation ≤ 30 days (doc 06 §6).

### vent
- No content endpoints at all for solo venting — the module stores only completion metadata. Burn-after-venting is enforced by absence of an API. (Marketplace sessions in Phase 3 get a separate, audited design.)

### safety
- Crisis directory: CMS-managed, keyed by region/locale, versioned; published to CDN; ETag polling lets apps refresh their bundled offline copy. Quarterly review workflow with owner + due dates in the CMS.
- Serves "Get more support" resource lists; logs **only** that a crisis sheet was shown (no context) for the SLA metric.

### notifications
- Scheduling service respects: user-chosen times, quiet hours, frequency caps, "invitations" copy register. Local-first (client schedules); server push only for flag-gated v1.0 use cases. Every push template lives in CMS with a review flag.

### entitlements (v1.0)
- RevenueCat as source of truth via webhooks → entitlement rows; feature gates resolved server-side and cached in the client (`features: {offline_downloads: true, coach_unlimited: false, ...}`).
- Regional pricing (PPP) via store price tiers + RevenueCat offerings; family plan (5 seats) as shared entitlement group.
- **Hard rule encoded in code review checklist:** safety features and crisis resources are never behind a gate.

### privacy
- DSAR export: async job → signed URL (ciphertext + metadata JSON) → in-app + email notification.
- Deletion orchestrator: fan-out domain event `user.deletion_requested` → every module implements a deletion handler (checked by a registry test: *any module without a handler fails CI*) → verification job confirms zero rows/blobs → backup expiry ≤ 30 days by retention policy.

## 4. Content pipeline (CMS plane)

- **Payload CMS** collections: calm sessions (audio refs, duration, goals, captions VTT, locale), gratitude prompts, journal prompt packs, nature scenes (+ **rights registry** fields per NE-5: license, territory, expiry — with expiry alerts), games config, recommendation rules, crisis directory, notification/copy templates.
- Editorial workflow: draft → review (legal/clinical flags on copy that claims benefits — §6.1) → publish → CDN purge. Preview builds in the app via staging content flag.
- Read path: CMS publishes to a denormalized read API / static JSON on CDN; the app never talks to the CMS directly.
- Media ingest: masters to object storage → transcode job → HLS ladder (incl. audio-only rendition for NE-2 battery-saver + still-image poster) → CDN with signed URLs.

## 5. Data stores

| Store | Used for | Notes |
|---|---|---|
| PostgreSQL | Users, entitlements, metadata, sync oplog, score history, catalogs read-models | Multi-AZ; PITR; row-level `user_id` scoping; partitioning on oplog/events by month |
| Redis | Sessions cache, rate limits, hot content cache, queues (BullMQ) | Nothing durable-only in Redis |
| Object storage | Ciphertext blobs (journal photos/audio), media masters + HLS, exports | SSE-KMS on top of client-side encryption; lifecycle rules; exports auto-expire 7 days |
| Analytics (PostHog) | Metadata-only events | Separate store; no joins back to content; schema-validated ingest (doc 06 §5) |

## 6. Non-functional implementation

- **99.9% availability:** multi-AZ, ≥ 2 replicas per service, health-checked rolling deploys, DB failover tested quarterly; status page.
- **Crisis directory reliability (100% SLA):** CDN edge cache with long TTL + stale-while-revalidate **plus** the in-app offline bundle — availability of the origin is irrelevant to the user-facing SLA.
- **Performance:** p95 API < 300ms (excluding Coach); catalog endpoints CDN-cached; sync batched.
- **Capacity:** MVP is 1,000 users — a single small cluster; the design above is about *not repainting* for v1.0 scale, not about launching big.

## 7. Backend best-practice checklist

- [ ] Zod validation at every boundary (requests, queue payloads, webhooks, CMS reads)
- [ ] Idempotent mutations + at-least-once job semantics (handlers written to be re-runnable)
- [ ] Outbox pattern for domain events (no dual-write bugs between DB and queue)
- [ ] Migrations: expand → migrate → contract; never destructive in one step; tested in CI against a snapshot
- [ ] Structured logs (no content, no PII beyond user_id), trace IDs end-to-end (OTel)
- [ ] Module-boundary lint + deletion-handler registry test + OpenAPI breaking-change check in CI
- [ ] Secrets in cloud secret manager; least-privilege IAM per service/worker; audited access to prod
- [ ] Load test the sync + workout endpoints before beta; chaos-test crisis-directory fallback
