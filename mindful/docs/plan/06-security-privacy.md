# 06 — Security & Privacy Plan

The PRD's privacy promises (§8) are marketing claims **and** legal commitments. This doc makes them technically true.

## 1. Threat model (summary)

| Adversary | Mitigation |
|---|---|
| Server breach / insider reading journals | Client-side E2EE — server holds ciphertext only |
| Stolen/shared device | App lock (biometric/PIN) independent of device lock; keys in secure enclave; privacy screen |
| Network attacker | TLS 1.3, cert pinning (with remote kill-switch to avoid bricking on cert rotation) |
| Analytics leakage of content | Metadata-only typed catalog + ingest schema validation; no content code path |
| Subpoena/insider for vents | Burn-after-venting content never exists server-side |
| Account takeover | IdP MFA support, refresh-token rotation w/ reuse detection, device list + revocation |

## 2. Encryption architecture (journal, gratitude, coach content)

**Library:** libsodium (XChaCha20-Poly1305 AEAD, Argon2id KDF, crypto_box for wrapping).

```
Master Key (MK)           32B random, generated on device at first run
  ├─ stored in iOS Keychain / Android Keystore (StrongBox where available,
  │  accessible: afterFirstUnlockThisDeviceOnly, non-exportable wrapper)
  ├─ Data Keys (DK) per collection, wrapped by MK   → rotate without re-encrypting MK
  └─ entries encrypted with DK + per-entry nonce; key_id stored beside ciphertext
```

### Multi-device & recovery (the hard part — decided now, before beta)
- On account creation the user gets a **Recovery Kit**: MK wrapped by a key derived (Argon2id) from a generated 12-word recovery phrase; the wrapped MK is stored server-side, the phrase is shown once (with "save to password manager / print" flows) and never stored by us.
- New device sign-in: MK arrives via (a) recovery phrase, or (b) **device-to-device approval** — existing device encrypts MK to the new device's public key (QR/push approval), the friendlier default.
- **Honest trade-off surfaced in UX:** lose all devices *and* the phrase → encrypted content is unrecoverable. This is the correct privacy-first choice; copy must say it plainly at account creation.
- Guest → account link: same MK is retained; wrapped copies created for recovery at link time.

### What is *not* E2EE (by design, disclosed)
Activity metadata, check-in scores, streaks, Mind Score inputs, user-applied tags — these power sync/score/analytics and are protected by TLS + at-rest disk encryption + access controls. The privacy policy and in-app "How your data works" screen state this split in plain language.

## 3. Burn-after-venting — enforcement checklist

- [ ] Vent buffers live in an encrypted temp dir flagged `NSFileProtectionComplete` / EncryptedFile; excluded from iCloud/Google backup (`isExcludedFromBackup`, `android:allowBackup` rules)
- [ ] No vent-content type exists in the API client — unrepresentable, not just unused
- [ ] Files overwritten-then-unlinked on session end **and** on app crash recovery (startup sweep)
- [ ] "Save to Journal" is the only persistence path and runs the standard E2EE write
- [ ] E2E test: vent → force-kill app → relaunch → assert temp dir empty

## 4. Device security

- App lock (JR-5): PIN (Argon2id-hashed, Keystore-backed) or biometrics; auto-lock on background; blur/obscure app-switcher snapshot (`FLAG_SECURE` optional mode on Android — evaluate vs screenshot-sharing of highlight reels).
- Root/jailbreak: detect and warn (not block — the Carrier persona may only have one device).
- All local DBs: SQLCipher or content-column ciphertext (we do the latter — see doc 03 §3) + OS full-disk encryption; MMKV encrypted instance for prefs.

## 5. Metadata-only analytics — enforcement at every layer

1. **Type layer:** event catalog types admit no free-text (`packages/analytics`).
2. **Lint layer:** logger and analytics wrappers reject variables typed as user content (tagged template types); CI greps for direct PostHog imports outside the package.
3. **Ingest layer:** JSON-Schema validation server-side; unknown fields dropped + alerted.
4. **Review layer:** privacy owner sign-off required on catalog changes (CODEOWNERS on the events package).
5. **No third-party ad SDKs — ever:** dependency allow-list in CI; any new SDK requires privacy review.

## 6. GDPR / UK GDPR / CCPA program

| Requirement | Implementation |
|---|---|
| Lawful basis & consent | Consent ledger (versioned policy acceptances, per-feature Coach opt-ins AC-2, safety-scanning opt-in §6.2) |
| Access/portability | Self-serve export (doc 04 §3 privacy): ciphertext bundle + metadata JSON; decrypted rendering on-device |
| Erasure | Deletion orchestrator: fan-out to all modules (registry-tested), blobs + rows hard-deleted, analytics pseudonym unlinked, backups expire ≤ 30 days; user gets confirmation |
| Minimization | Metadata-only spine; no content server processing; 24-mo analytics window |
| DPIA | Required before beta (special-category-adjacent data); revisit for Coach (v1.0), safety-scanning opt-in, listener marketplace, Teams |
| Processors | DPA inventory: cloud, IdP, RevenueCat, PostHog, LLM provider (zero-retention / no-training terms required), push |
| Data residency | Region tag on users; EU pinning available at provider level; residency plan reviewed per expansion market |
| Age | Configurable age gate (13+ default, per-region override — PRD open Q6); no marketplace under 18 (Phase 3) |
| Children/teens | If 13–15 permitted: no Coach content opt-ins by default, stricter defaults; legal review pre-beta |

HIPAA explicitly out of scope (no PHI, no clinical services); revisit only for healthcare partnerships.

## 7. Application & infrastructure security baseline

- OWASP MASVS (mobile) + ASVS (API) as the audit checklists; external **pen test before public v1.0**, scoped test before beta.
- Secrets: cloud secret manager; no secrets in app bundle or repo (gitleaks in CI); API keys used by the app are proxied server-side (LLM, Mux keys never ship in the client).
- Supply chain: lockfiles + `pnpm audit`/OSV scanning + Renovate; pinned GitHub Actions; SBOM per release.
- Access: SSO + MFA for all internal tools; prod DB access break-glass only, audited; support tooling shows metadata only (support **cannot** read content — by construction).
- Vulnerability disclosure policy + security.txt at launch; incident-response runbook incl. 72-hour GDPR breach-notification path.

## 8. Trust-facing UX (privacy as a feature)

- "How your data works" screen: the E2EE split, what the Coach can/can't see, one screen, human language.
- "What my Coach knows" (AC-7) with per-item delete.
- Per-feature Coach opt-ins with revocation (AC-2); safety-scanning opt-in copy co-written with clinical/legal.
- Export & delete are discoverable in settings, not buried.
