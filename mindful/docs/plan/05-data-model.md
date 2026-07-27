# 05 — Data Model & Sync

## 1. Modeling principles

1. **Two classes of data, never mixed:**
   - **Content** (journal text/audio, gratitude text/photos, coach conversations under opt-in): client-side encrypted, server stores ciphertext, excluded from analytics and any server processing.
   - **Metadata** (counts, durations, studio, mood scale value, tags, timestamps): plaintext, powers sync, streaks, Mind Score, analytics.
2. **Single-author data → conflict-free by construction.** Every syncable entity is owned by one user and edited from that user's devices; per-field last-writer-wins + set-union for collections is sufficient (no CRDT library needed at MVP).
3. **Soft-delete via tombstones for sync; hard-delete via privacy pipeline.**
4. **Every row carries `schema_version`** — mobile DBs live long; migrations must be forward-compatible.

## 2. Core entities (PostgreSQL — server)

```sql
-- Identity & profile ------------------------------------------------------
users(id, idp_subject NULL, created_at, region, locale, timezone,
      account_state ENUM(guest,linked,deletion_pending), org_id NULL /* Phase 4 */)
devices(id, user_id, platform, push_token NULL, last_seen_at, app_version)
user_preferences(user_id, reminder_times JSONB, quiet_hours JSONB,
      app_lock ENUM(off,pin,biometric), coach_optins JSONB /* per-feature, default {} */)

-- Entitlements (v1.0) ------------------------------------------------------
entitlements(user_id, tier ENUM(free,premium,family_member,team_member),
      source ENUM(revenuecat,promo,team), expires_at, family_group_id NULL, raw JSONB)

-- Activity metadata spine (feeds streaks, score, analytics) ----------------
activities(id, user_id, studio ENUM(gratitude,journal,vent,calm,nature,focus,workout,coach),
      zone ENUM(release,train,restore), kind, duration_s, completed BOOL,
      occurred_at, local_day DATE /* user tz at time of activity */,
      workout_id NULL, meta JSONB /* schema-validated, metadata only */)
checkins(id, user_id, score SMALLINT /*1-5*/, tag_word NULL, occurred_at, local_day)
streaks(user_id, current INT, longest INT, last_active_day DATE, repairs_used INT)
mind_scores(user_id, as_of DATE, score SMALLINT, consistency, balance, trend,
      formula_version, PRIMARY KEY(user_id, as_of))

-- Content-bearing (ciphertext only) ----------------------------------------
journal_entries(id, user_id, created_at, updated_at, deleted_at NULL,
      ciphertext BYTEA, nonce, key_id, schema_version,
      tags TEXT[] /* user-applied; plaintext by design, user informed */,
      audio_blob_key NULL, transcript_in_ciphertext BOOL)
gratitude_entries(id, user_id, local_day, created_at, updated_at, deleted_at NULL,
      ciphertext /* 3 lines */, nonce, key_id, photo_blob_key NULL)
-- vents: NO content table. solo vent = activities row only (burn-after-venting).

-- Coach (v1.0) --------------------------------------------------------------
coach_threads(id, user_id, created_at, locale)
coach_messages(id, thread_id, role, ciphertext, nonce, key_id, created_at)   -- E2E-encrypted at rest
coach_memory(id, user_id, kind, summary_ciphertext, source, created_at)      -- inspectable/erasable (AC-7)

-- Catalog read-models (from CMS; denormalized, cacheable) -------------------
calm_sessions(id, locale, title, duration_s, goals[], audio_url, captions_url, tier)
nature_scenes(id, locale_curation[], title, hls_url, poster_url, rights JSONB, tier)
prompts(id, studio, locale, text, pack, active)
games(id, config JSONB, version)                                             -- v1.0
crisis_directory(region, locale, resources JSONB, version, reviewed_at)

-- Sync ----------------------------------------------------------------------
oplog(seq BIGSERIAL, user_id, collection, entity_id, op ENUM(upsert,delete),
      field_versions JSONB /* per-field HLC */, payload JSONB/ciphertext, device_id, server_ts)

-- Privacy -------------------------------------------------------------------
deletion_jobs(user_id, requested_at, modules_pending TEXT[], verified_at NULL)
audit_log(actor, action, subject, at)   -- admin/T&S actions only, append-only
```

Client SQLite mirrors the user-owned tables (entries, activities, checkins, streak cache, downloads registry) via Drizzle with identical `schema_version` discipline.

## 3. Sync protocol (offline-first, conflict-free merge — PRD §7)

**Model:** per-collection cursor sync over a server oplog, per-field LWW using **hybrid logical clocks (HLC)** so device-clock skew can't reorder edits badly.

```
PUSH  client → POST /v1/sync/{collection}
      [{entity_id, op, fields:{name:{value, hlc}}, base_version, idempotency_key}]
      server merges per field: keep higher HLC; arrays declared as sets merge by union
      (tags, attachments); returns canonical entity + new cursor.

PULL  client → GET /v1/sync/{collection}?cursor=N
      returns oplog entries > N for this user (tombstones included), next cursor.
```

- Ciphertext fields are opaque values to the merge (whole-field LWW). Gratitude's per-line autosave encrypts per entry, not per keystroke — an entry updated on two offline devices resolves to the later HLC; acceptable for single-author data and surfaced in UI ("edited on another device") if `base_version` mismatch is detected.
- Sync triggers: app foreground, post-mutation debounce, background fetch (OS-scheduled), connectivity regain.
- Guest → account link: local data re-keyed to the account (crypto doc 06 §3) and pushed with fresh IDs preserved via `idempotency_key`.
- Downloads (offline premium content) are **not** synced — they're a device-local registry with entitlement checks.

## 4. Analytics event spine (metadata-only)

Typed catalog in `packages/analytics` — the only way to emit events; free-text properties are unrepresentable in the types.

```ts
// examples (all enums/numbers/booleans/buckets — no strings from users)
session_started   {studio, source: 'today'|'widget'|'notification'|'deeplink'}
session_completed {studio, zone, duration_bucket, workout_part?: 'warmup'|'main'|'cooldown'}
workout_completed {parts_completed: 0|1|2|3}
checkin_logged    {score: 1|2|3|4|5, has_tag: boolean}
streak_repaired   {}
vent_completed    {mode: 'voice'|'text', duration_bucket, saved_to_journal: boolean}
paywall_viewed    {placement} · subscription_started {plan, region}    // v1.0
crisis_sheet_shown{source: 'user_request'|'coach_escalation'}          // no context payload
notification_outcome {kind, action: 'opened'|'dismissed'|'uninstall_window'}
```

North-star + habit funnel + guardrail metrics (doc 01 §3) are all derivable from this set. Schema registry (JSON Schema) validates at ingest; unknown/invalid events are dropped and alerted.

## 5. Retention & lifecycle

| Data | Retention |
|---|---|
| Journal/gratitude ciphertext | Until user deletes (entry or account); erasure ≤ 30 days incl. backups |
| Solo vent content | **Never stored server-side; device temp wiped at session end** |
| Coach messages | User-erasable any time (AC-7); default retention reviewed with clinical/legal |
| Activities/checkins metadata | Life of account (it *is* the Mind Score data spine / moat) |
| Analytics events | Pseudonymous; 24-month rolling window; aggregates kept |
| Exports | Signed URL, auto-delete after 7 days |
| Backups | 30-day max age → satisfies erasure propagation by expiry |
