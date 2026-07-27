# 08 — DevOps, CI/CD & Operations

## 1. Environments

| Env | Purpose | Data |
|---|---|---|
| `local` | Dev machines; docker-compose (Postgres, Redis, CMS, PostHog dev key); Expo dev client | Seeded fixtures |
| `staging` | Every merge to `main`; full stack incl. CMS staging content; TestFlight/Internal-track builds point here | Synthetic only — never prod data |
| `production` | Tagged releases | Real |

- Config via environment (12-factor); app build profiles (EAS: `development`, `preview`, `production`) select API base + keys.
- **No prod data in lower envs, ever** (content is E2EE anyway, but metadata counts too).

## 2. Source control & workflow

- Trunk-based: short-lived branches → PR → squash-merge to `main`. Feature flags decouple merge from release (unfinished studios ship dark).
- Conventional Commits → changelogs + semantic versions; CODEOWNERS: privacy owner on `packages/analytics` + `privacy` module, safety owner on `coach/` + `safety/`, design owner on `packages/ui` tokens.
- PR gates: typecheck, lint (incl. boundary + i18n-literal + logger rules), unit tests, OpenAPI breaking-change check, bundle-size diff (mobile), gitleaks, dependency/OSV scan.

## 3. CI/CD pipelines (GitHub Actions + Turborepo remote cache)

### Backend
```
PR:    lint → typecheck → unit → integration (Testcontainers: PG+Redis) → contract tests
main:  build image → deploy staging (migration job first: expand-only) → smoke + API E2E → ready
prod:  manual promote (release tag) → canary 10% → auto-rollback on SLO burn → 100%
```

### Mobile
```
PR:      lint → typecheck → unit/component tests → (label-triggered) Maestro E2E on emulator/simulator
main:    EAS preview build → internal distribution (QA + stakeholders) + Maestro cloud run
release: EAS production build → TestFlight / Play internal → staged rollout
         iOS phased release · Android staged 5% → 20% → 50% → 100%, halt on crash-rate regression
OTA:     EAS Update for JS-only fixes — channel per release; runtime-version discipline;
         never OTA anything requiring native changes; OTA changes go through the same PR gates
```

- Store automation: EAS Submit + store metadata as code (fastlane deliver/supply style) — screenshots, descriptions, and **age-rating answers** versioned in-repo (they're safety-reviewed artifacts here).
- Release cadence: weekly mobile release train from `main`; hotfix path via OTA or expedited build.

## 4. Infrastructure as code

- Terraform for everything (VPC, ECS/Cloud Run, RDS multi-AZ, Redis, S3+CDN, WAF, secret manager, alerting); reviewed via PR; `staging` and `prod` from the same modules with different vars.
- Migrations: expand → deploy → migrate data → contract (separate PRs); `atlas`/`drizzle-kit` diff checked in CI; rollback = redeploy previous image (schema stays compatible one version back).

## 5. Feature flags & remote config (Unleash)

| Use | Examples |
|---|---|
| Dark-ship & staged rollout | Coach tab hidden pre-v1.0; Focus Arena per-cohort |
| Kill switches | Coach hard-off, notifications off, cert-pinning off |
| Remote config | Recommendation rules (CS-4), Mind Score weights (CS-6), free-tier caps |
| Experiments | Onboarding variants, paywall placements — always with guardrail metrics attached |

Flag hygiene: owner + expiry date per flag; stale-flag report monthly.

## 6. Observability & SLOs

| Signal | Tooling |
|---|---|
| Traces/metrics/logs | OpenTelemetry → Grafana stack (or Datadog); trace IDs from app → API → jobs |
| Mobile | Sentry: crashes, ANRs, release health, cold-start TTI, pacer FPS custom metric |
| Product | PostHog dashboards: north star, habit funnel, guardrail metrics (weekly review ritual) |
| Cost | LLM spend per conversation; media CDN egress; per-env budgets + alerts |

**SLOs:** API availability 99.9% (30-day) · p95 core API < 300ms · crisis-directory fetch success (incl. cache fallback) 100% — synthetic-checked from multiple regions · Coach first-token p95 < 2s (chat), < 1.5s (voice, P2). Error budgets gate risky deploys.

**Alerting:** page on SLO burn + crash-rate spikes + queue depth + webhook failures (RevenueCat); guardrail-metric anomalies (uninstall spike after a notification send) alert product, not just eng.

## 7. Operations

- Runbooks (repo `runbooks/`): DB failover, CDN purge, crisis-directory emergency update (**< 1 hour path**, quarterly drill), store-review rejection response, LLM provider outage (fallback flip), OTA rollback, security incident + 72h breach notification.
- On-call: lightweight rotation from beta; escalation policy; status page.
- Backups: PITR + nightly snapshots, 30-day retention (aligned with erasure promise), quarterly restore test.
- DR: cross-region snapshot copies; RTO 4h / RPO 1h documented and tested pre-v1.0.

## 8. Developer experience

- `pnpm i && pnpm dev` boots API + CMS + app (Expo) against local docker-compose in < 10 min from clean clone (measured).
- Seed script: demo users, content fixtures, flag defaults. `.env.example` maintained; direnv.
- ADRs (`docs/adr/`) for every load-bearing decision (this plan seeds the first ~10).
- CLAUDE.md / AGENTS.md kept current for AI-assisted development: architecture map, commands, conventions, module boundaries.
