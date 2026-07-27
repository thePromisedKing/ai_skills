# 03 — Mobile App Plan (React Native)

## 1. Repository & module architecture

Monorepo (pnpm or Bun workspaces + Turborepo) shared with the backend so types, validation schemas, and the event catalog are single-sourced.

```
supermind/
├── apps/
│   ├── mobile/                  # Expo app — thin shell: routing, providers, theming
│   │   ├── app/                 # Expo Router file-based routes
│   │   │   ├── (onboarding)/
│   │   │   ├── (tabs)/          # Today | Studios | Coach | You
│   │   │   ├── workout/
│   │   │   ├── studio/[studio]/
│   │   │   └── safety/          # crisis sheet — reachable from everywhere
│   │   └── src/                 # app-level composition only
│   └── api/                     # NestJS backend (doc 04)
├── packages/
│   ├── core/                    # domain types, Zod schemas, utilities (shared app+api)
│   ├── api-client/              # OpenAPI-generated client + TanStack Query hooks
│   ├── ui/                      # design system: tokens, primitives, composites
│   ├── analytics/               # typed event catalog (metadata-only, enforced)
│   ├── crypto/                  # E2EE: key mgmt, encrypt/decrypt, recovery kit
│   ├── storage/                 # SQLite + Drizzle schema, MMKV wrappers, sync engine
│   ├── i18n/                    # strings, ICU, RTL helpers, locale negotiation
│   └── features/                # one package per studio/domain — the heart of modularity
│       ├── onboarding/
│       ├── checkin/
│       ├── workout/             # Mind Workout orchestration
│       ├── streaks/
│       ├── mindscore/           # v1.0
│       ├── gratitude/
│       ├── journal/
│       ├── vent/
│       ├── calm/
│       ├── nature/
│       ├── focus/               # v1.0 — game engine + 4 games
│       ├── coach/               # v1.0
│       ├── safety/              # crisis directory, get-more-support
│       ├── paywall/             # v1.0
│       └── settings-privacy/    # export, delete, app lock, coach memory
```

**Feature package contract** — every `features/*` package exposes only:
```ts
export { routes }        // screens it contributes (registered by the shell)
export { api }           // public hooks/services other features may use
export { events }        // analytics events it emits (from the catalog)
```
Internals (`components/`, `store/`, `queries/`) are private. Cross-feature imports of internals fail lint (`eslint-plugin-boundaries`). This is what keeps the app modular as studios multiply (listener marketplace, Teams, TV surface reuse these packages).

## 2. App shell & navigation

- **Tabs:** `Today` (check-in + Mind Workout + streak), `Studios` (six studio grid), `Coach` (v1.0; hidden pre-launch by flag), `You` (score, history, settings).
- **Expo Router** with typed routes; every screen deep-linkable (`supermind://workout`, `supermind://vent/now`, `supermind://breathe`) — required for widgets (CS-7), notifications, and quick actions.
- **Safety escape hatch:** crisis sheet is a root-level route presentable over any screen; "Get more support" link in settings and on every Vent Space screen (§6.1).
- **Guest mode first:** onboarding ≤ 4 screens (CS-1); account creation deferred until the user wants sync. All local data is created under a device identity and migrated to the account on link — build this migration on day one, it's painful to retrofit.
- **Cold start budget (≤ 2.5s mid-range Android):** Hermes; `react-native-bootsplash`-style splash → inline requires/lazy route loading; no blocking network on launch (render from local DB, revalidate in background); defer non-critical SDK init (analytics, RevenueCat) post-first-frame. Track TTI in Sentry per release.
- **Session start < 10s:** Today screen renders the primary CTA immediately from cached state; widgets/quick actions deep-link straight into breathing/gratitude/vent.

## 3. State & data layer

| Layer | Tool | Rules |
|---|---|---|
| Server state | TanStack Query via `api-client` | Query keys namespaced per feature; offline `persistQueryClient` into MMKV |
| Local domain data | SQLite (op-sqlite) + Drizzle | Journals, gratitude, sessions, streak cache — source of truth for offline-first features |
| Sync | `storage/sync` engine | Local oplog → push/pull with cursors (spec in doc 05); runs on app foreground + background fetch |
| UI/client state | Zustand per feature | Ephemeral only; nothing durable in component state |
| Secrets/keys | Keychain (iOS) / Keystore (Android) | Master key, app-lock secret; `accessible: whenUnlockedThisDeviceOnly` |
| Prefs | MMKV (encrypted instance) | Locale, reminder times, flags cache |

**Encrypted content rule:** journal/vent/gratitude *content* columns store ciphertext (encrypted via `packages/crypto` before hitting SQLite); plaintext lives only in component memory while editing. Search over encrypted entries is local-only (decrypt-and-index in memory, or client-side searchable index — v1.0 refinement).

## 4. Design system & modern UX (`packages/ui`)

- **Tokens first:** color (light/dark, high-contrast), type scale (dynamic-type aware), spacing, radii, motion durations/easings — exported as a theme; no hard-coded values in features. Calm palette per brand; **no red badges anywhere** (product principle).
- **Primitives:** Button, Card, Sheet, Text, Input, ProgressRing, Tag — built on RN primitives + Reanimated; every primitive ships with accessibility props wired (roles, labels, min 44pt targets).
- **Composites:** CheckInScale (5-point one-tap), StreakDisplay (compassionate copy variants), SessionPlayer (audio w/ background + sleep timer), BreathingPacer, NatureBackdrop, PromptCard.
- **Motion language:** slow, breathing-tempo transitions (300–500ms, gentle easings); every animation respects `reduceMotion`; 60fps guaranteed by keeping all animation on the UI thread (Reanimated worklets/Skia) — JS-driven animation is banned in `ui`.
- **BreathingPacer (flagship component):** Skia-rendered expanding/contracting form driven by a Reanimated clock; haptics via `expo-haptics` synced to phase changes; optional voice guidance track; pattern-configurable (box / 4-7-8 / extended exhale from CMS config). FPS budget asserted in perf tests (doc 09).
- **Storybook (react-native)** + on-device component gallery in dev builds; visual regression via Chromatic or screenshot tests for tokens/primitives.
- Haptics, subtle gradients over nature imagery, skeletons-not-spinners, empty states with warmth — the "calm by default" principle is a UI-package concern, reviewed in design QA.

## 5. Studio-by-studio implementation notes

### Onboarding & check-in (P0)
- 4 screens max: intent picker → notification opt-in (with honest value copy; pre-permission prompt pattern) → optional account → done. Skippable to guest.
- Check-in: single tap + optional one-word tag; writes locally, syncs as metadata. Never blocks anything.

### Mind Workout (P0)
- Orchestrator in `features/workout`: composes warm-up (Calm's pacer, 60s) → recommended activity (rules from remote config: mood→studio mapping, editable server-side without release — CS-4) → cool-down (Gratitude 3-line over cached nature scene).
- Whole flow works offline (rules bundle cached; one nature scene and core audio pre-bundled/downloaded on first run).
- Streaks (CS-5): any completed activity counts; missed day → compassionate message + 1-tap "repair" micro-session (60s breathing). No loss-aversion copy — streak strings reviewed against the copy principles.

### Gratitude Studio (P0/P1)
- 3-line entry, autosave per line (debounced local writes), optional photo (compressed, encrypted at rest, E2EE-wrapped for sync).
- Prompts from CMS (≥100, localizable). Reminder at user-chosen time via **local scheduled notifications** (no server push needed — also satisfies "no background activity beyond scheduled local notifications").
- v1.0: Highlight Reel — generated **on-device** (content never leaves the privacy boundary) as a shareable image via Skia snapshot; share only by explicit action. Gratitude jar = archive view + on-this-day resurfacing (local query).

### Journal (P0/P1)
- Distraction-free editor (keyboard-aware, focus mode dims chrome); guided mode = prompt packs from CMS.
- E2EE at rest (doc 06); tags + calendar/tag views from local metadata index.
- App lock (JR-5): biometric/PIN gate independent of device lock — lock state on background/blur; privacy screen (blur app switcher snapshot).
- v1.0: voice journaling — record locally; transcription **on-device** (iOS Speech / Android SpeechRecognizer) with a private-server fallback only under explicit consent; audio deletable independently of transcript. Export (PDF/text, generated on-device) + permanent delete.

### Vent Space (P0/P1)
- "Vent now" ≤ 2 taps from anywhere (Today shortcut, quick action, widget).
- Burn-after-venting: recording buffered to an **encrypted temp file, excluded from backups**, wiped on session end; nothing enters SQLite or the sync queue unless "Save to Journal" is tapped.
- Post-vent cool-down offer (never forced). v1.0: rant timer, write-and-shred animation (Skia particle shred), void-scream mode with haptics.
- Every Vent screen shows the quiet "Get more support" affordance.

### Calm Room (P0/P1)
- Session catalog from CMS (≥30 at launch), filterable by duration/goal; audio via track-player: background playback, lock-screen controls, sleep timer.
- Breathing exercises use the shared pacer with per-pattern configs + optional voice layer.
- v1.0: soundscape mixer (layered loops, per-channel volume, sleep timer), offline downloads (premium): encrypted download store with license check on play, LRU eviction, and a downloads manager UI.

### Nature Escapes (P0)
- HLS playback with adaptive bitrate; battery-saver mode = audio-only rendition or still-image + audio (NE-2) — auto-suggested on low battery/data-saver OS flags.
- Scenes as live backgrounds for gratitude/journal/breathing (NE-3, v1.0) using paused-frame or low-res loop to protect battery.

### Focus Arena (P1)
- A small **game engine** package: scene loop on Skia/Reanimated, input sampling, adaptive difficulty controller (staircase method), round results schema. Games are data + components on top of the engine → supports FA-5 remote content packs later.
- 4 launch games: sustained attention, working memory, cognitive flexibility, breath-paced calm-under-pressure (reuses pacer). Personal bests local + synced. Honest framing copy from CMS with legal-review flag.

### AI Coach (P1) — client side
- Chat UI with streaming (SSE/WebSocket), session debrief cards, "What my Coach knows" screen (AC-7) with per-item delete.
- Per-feature opt-in toggles for journal/vent theme access (AC-2) — off by default, revocable, with plain-language explanation.
- Crisis-safe rendering: escalation responses render the crisis sheet component natively (not just text).

## 6. Accessibility (WCAG 2.1 AA) — built-in, not audited-in

- Every `ui` primitive: `accessibilityRole/Label/Hint/State`, 44pt targets, focus order; dynamic type up to XXL without truncation (test at 200%).
- `prefersReducedMotion` honored globally (pacer gets a non-animated alternative: numeric phase countdown + haptic).
- Captions on all guided audio (VTT from CMS, rendered in SessionPlayer); contrast-checked palette in tokens; screen-reader E2E passes in QA (doc 09).

## 7. i18n & RTL from day one

- **Zero hard-coded strings** — lint rule (`i18next/no-literal-string`). ICU plurals/genders. Pseudo-localization build variant to catch layout breaks early.
- RTL: logical layout properties only (`start`/`end`), `I18nManager` snapshot tests, RTL screenshot CI job — cheap now, a rebuild later (Arabic is localization #1).
- Locale-aware content: prompts/sessions/crisis directory requested with locale+region; en-only at launch but the pipes are live.

## 8. Notifications — "invitations, never alarms"

- Local scheduled notifications for reminders (user-chosen times, default evening for gratitude); server push reserved for genuinely useful moments (v1.0+, flag-gated).
- Quiet hours; frequency caps; every notification deep-links to a ≤ 1-tap start; copy from CMS (reviewable). Guardrail metric: post-notification uninstalls (doc 01 §3).

## 9. Widgets & quick actions (P1, CS-7)

- iOS WidgetKit (SwiftUI) + Android Glance widgets: 1-tap breathing / gratitude / streak status. Shared data via App Group / SharedPreferences bridge writing a tiny **metadata-only** snapshot (streak count, today-done flag — no content).
- Home-screen quick actions (long-press) at MVP: Vent now / Breathe — cheap, ships before widgets.

## 10. Mobile best-practice checklist

- [ ] TypeScript strict; no `any` in `packages/*`
- [ ] Hermes + New Architecture on; bundle analyzed per release (size budget: < 30MB initial download w/o media)
- [ ] All animation on UI thread; FPS assertions on pacer & game engine
- [ ] No blocking network before first frame; offline rendering from local DB
- [ ] Error boundaries per feature route; graceful offline/empty/error states designed, not defaulted
- [ ] Secrets never in JS bundle; API keys server-side; certificate pinning evaluated (doc 06)
- [ ] `__DEV__`-only logging; PII/content never logged (lint rule on logger)
- [ ] Deep links + notifications + widgets covered by E2E (Maestro)
- [ ] Device matrix includes a low-end Android (e.g., 3GB RAM) in every regression pass
