# Frontend Direction — Continue on Refine + AntD, or Migrate to the Proposed Headless Stack

> **Status: ANALYSIS — decision pending (owner).**
> Produced 2026-07-14 from a full audit of `frontend/` (the Refine + AntD scaffold),
> `design-prototype/` (the custom HTML/CSS design system), AGENTS.md, and CLAUDE.md.
> This is the "migration analysis" task called for in CLAUDE.md's status banner.
> No code was modified.

---

## 1. What was audited

**`frontend/`** — npm-workspaces monorepo (`shared` / `tenant-portal` / `admin-portal`),
Vite + React 19 + TypeScript, Refine (`@refinedev/core@5`, `@refinedev/antd@6`,
`@refinedev/react-router@2`), AntD 5.29, axios, React Router 7. **~3,650 lines of
TS/TSX total** (shared 984, tenant 1,771, admin 902).

**`design-prototype/`** — 29 HTML files (27 distinct screens + hub + live component
catalog), one 842-line `theme.css` that is a complete, token-driven design system,
and a 382-line vanilla-JS chrome script. It covers essentially the whole tenant
product surface plus the admin dashboard and onboarding wizard, in light + dark,
with 7 switchable brand palettes, 6 sidebar themes, and RTL groundwork.

### 1.1 The scaffold today (facts)

| Area | State |
|---|---|
| Tenant resources | 6 fully working: customers, products, invoices (rich editor), credit notes, recurring invoices, e-invoice batches (polling 6-step status stepper). Excel import for customers/products/batches. |
| Admin portal | Organizations list + read-only detail + a substantial **6-step onboarding wizard** (449 lines, resumable-draft model, owner provisioning, imports). Everything else is "Coming soon" cards. |
| Refine depth | Deeply idiomatic: `useTable`/`useForm`/`useCustomMutation` throughout, `ThemedLayout`, resources array, auth/data providers. This is a genuinely Refine-native app, not a thin wrapper. |
| Styling | **~95% stock AntD.** Theme = default blue `#1677FF` + `borderRadius: 8`; `components: {}` empty. ~250 lines of dead prototype CSS sit unused in `tenant-portal/src/index.css`. |
| Auth | localStorage JWT (access + refresh, single-flight refresh interceptor). CLAUDE.md's target is httpOnly cookie sessions — a gap on *either* path. |
| Tenant switching | **Not implemented.** Org is silently locked to the first membership at login. |
| Missing screens | Printable invoice document (`invoices/{id}/document` — documented in AGENTS.md, never built), dashboard, reports, settings, customer statement, payment recording, all master–detail views. |
| Tests | **Zero.** No Vitest, no Playwright, no test script anywhere. Lint config exists only for tenant-portal; no lint script, no Prettier. |

### 1.2 The prototype today (facts)

The prototype is not a sketch — it is a **finished design system with a component
registry** (`COMPONENTS.md` assigns stable codes like `PIL-01`, `TBL-01`, `MDL-01`
to copyable markup) and a screen for nearly every backend capability, including the
ones the scaffold never built (dashboard with hand-built SVG charts, reports, settings
shell, import wizard, customer statement, invoice document with status ribbon,
master–detail record layouts, error/auth pages, command palette).

Its design language, precisely:

- **Brand-derived neutral system.** One `--brand` token; all surfaces, borders and
  secondary text tints derive from it at runtime via CSS `color-mix()`. Switch
  `data-palette` and the entire chrome re-tints — no rebuild.
- **Signature dark sidebar shell** (always dark, independent of light/dark content
  theme, 6 selectable sidebar themes, gradient logo tile, "Getting Started" progress
  widget, 64px icon-rail collapse, off-canvas mobile drawer).
- **Fintech-ledger typography**: system sans, weights 500–760, negative tracking on
  headings, monospace + `tabular-nums` for TRNs/money/codes.
- Uppercase 11.5px table headers on a brand-tinted row, hover-revealed row actions,
  pill status badges with a colored dot, 8px controls / 14px cards / 999px pills,
  very shallow shadows, 3px `brand-weak` focus rings.
- Distinctive custom surfaces: FTA validation-code chips, compliance rail in the
  invoice editor, 6-step batch workflow, invoice sheet with corner ribbon, ⌘K
  command palette, notification center, bulk-action bar.

---

## 2. Can AntD faithfully reproduce the prototype's design language?

**Short answer: it can approximate it well (~85–90%), but it cannot adopt it — and
the approximation carries a permanent maintenance tax.** The honest breakdown is in
three tiers:

### Tier 1 — Achievable with AntD theme tokens (clean)

Primary color, border radius (8 control / 14 card via `borderRadius`/`borderRadiusLG`),
font stack, base size, dark mode (`darkAlgorithm`), focus outline (`controlOutline`
tokens), many per-component tokens (Table `headerBg`, Menu colors, etc.). AntD v5's
token system is genuinely good at this level.

One concrete limitation: **the `color-mix()` neutral derivation cannot be expressed
in AntD tokens.** AntD's theme is a JavaScript-computed object — you cannot pass
`color-mix(in srgb, var(--brand) 6%, #fff)` as a token, because AntD derives hover/
active/disabled variants from concrete color values in JS. Runtime palette switching
is possible (recompute the ConfigProvider theme object), but the elegant one-token
derivation must be reimplemented as a JS color-math module producing ~25 precomputed
hex values per palette × light/dark. Doable; not hard; but it is a parallel
reimplementation of what the prototype does in 15 lines of CSS.

### Tier 2 — Achievable only with `.ant-*` CSS overrides (the fighting)

AntD v5 wraps its styles in `:where()` (low specificity), so plain CSS overrides do
win — this is easier than AntD v4. But you are styling **DOM you don't own**, and the
prototype diverges from AntD's structure, not just its colors:

- Table: uppercase/letter-spaced headers, hover-revealed fade-in row actions, footer
  layout (count + pager + page-size), no sticky header, exact cell padding.
- Status pills: AntD `Tag` has no leading dot and different metrics — the existing
  `StatusTag` would be rewritten as a custom span anyway.
- Inline line-item editor: the prototype's borderless `.li-input` cells inside a
  compact table ≠ AntD `Form.List` + `Input` visuals; heavy restyling of nested
  `.ant-form-item` internals.
- Select/date/dropdown popups, Modal chrome, toast anatomy (the rich TST-02 toast),
  Steps → the prototype's numbered-dot stepper with connector lines and error state.
- Every override is written against AntD's *internal* DOM, which can change on any
  minor release. This isn't a one-time cost; it's a tax on all future UI work
  (realistically 10–20% overhead per screen, plus breakage risk on upgrades).

### Tier 3 — Custom code on either path (AntD gives you nothing)

The most distinctive parts of the design have **no AntD counterpart at all**: the
dark sidebar shell (Refine's `ThemedLayout`/`ThemedSider` cannot be bent into it —
you would discard them and hand-build the shell), the topbar with global search /
quick-create / notification panel, the command palette, the invoice document sheet
with ribbon, the master–detail record layout, the compliance rail, the settings
shell, SVG dashboard charts, the bulk-action bar, error pages. **This tier is the
majority of the remaining product surface** — which means AntD's core value
("looks finished out of the box") is largely nullified by this design.

### The asymmetry that decides the question

The prototype's 842-line `theme.css` **is already the implementation** of the design
system — classes, tokens, states, dark mode, RTL, reduced-motion, responsive
behavior. On the proposed stack (Tailwind v4 + shadcn copy-in components whose
markup you own), that CSS ports **almost wholesale**: Tailwind v4 is CSS-variable
native, and shadcn components are unstyled Radix primitives wearing classes you
control. On AntD, that CSS ports **almost not at all** — none of its selectors match
AntD's DOM, and its token model conflicts with AntD's JS pipeline. Choosing AntD
means paying to *re-derive* a design system that already exists; choosing the
headless stack means *transplanting* it.

**Verdict:** faithful-enough reproduction on AntD is possible but is a permanent
uphill fight (Tier 2 forever) for a payoff (Tier 1 + prebuilt behaviors) that this
particular design mostly doesn't use. A tokens-only reskin (cheap) would produce an
app that is recognizably *not* the prototype — greenish AntD, not the envisioned
design.

---

## 3. Effort comparison, itemized

Assumptions: Claude Code writes the code; the owner reviews behavior. Estimates are
in **focused working days** and deliberately given as ranges. Backend changes (cookie
sessions + CSRF) are excluded — they are the same on both paths.

### 3.0 Work that is identical on both paths (~60–70% of remaining frontend work)

Listed once so neither path gets falsely charged for it. All of this is Tier 3
custom build (design exists in the prototype; no framework shortcut):

| Item | Est. |
|---|---|
| Dashboard (KPIs, SVG/chart components, recent list) + Reports (VAT return, aging, sales trend) | 5–8 d |
| Settings shell + panels (company, numbering, tax, terms, users, FTA connection, notifications, billing) | 4–6 d |
| Import wizard (upload → map → review → commit) as designed | 3–4 d |
| Invoice document view + credit-note view (printable sheet, ribbon, FTA strip) | 2–3 d |
| Customer statement, record-payment modal, master–detail detail screens | 4–6 d |
| Command palette, notification center, bulk-action bar, error pages, auth screens to design | 4–6 d |
| **Tenant switcher** (missing today; required for a multi-tenant product) | 1–2 d |
| Playwright + Vitest setup, first E2E suite incl. RBAC/tenant-isolation negatives (CLAUDE.md quality gate) | 4–6 d |
| Lint/Prettier/Husky hardening across all workspaces | 1 d |

### 3.A Path A — stay on Refine + AntD, restyle to the prototype

| # | Item | Est. |
|---|---|---|
| A1 | Token bridge: JS color-derivation module replicating the `color-mix` neutral system; palette × light/dark precomputation; wire into `buildThemeConfig`; per-component token pass | 2–3 d |
| A2 | Discard `ThemedLayout`/`ThemedSider`/`AppHeader`; hand-build the prototype shell (dark sidebar, rail collapse, topbar, crumb bar, footer, account menu) inside the Refine app | 3–5 d |
| A3 | `.ant-*` override stylesheet: Table, Tabs, Pagination, Form/Input/Select, Modal, Steps, Tag→pill replacement, toasts, popovers | 4–6 d |
| A4 | Restyle the 7 existing screens against the new shell + overrides; rework `LineItemsField` to the borderless inline-editor look; rework `StatusTag` | 3–4 d |
| A5 | Ongoing override maintenance | +10–20% on every future screen; re-verify on each antd minor |
| | **Path A subtotal (to restyled parity of what exists)** | **12–18 d** |

End state: a hybrid — AntD engines wearing a hand-built skin. Fidelity ceiling
~85–90%; some idioms stay visibly AntD (popup animations, select internals, form
error choreography). The app keeps working throughout, which is Path A's main
advantage. Also note: the localStorage-JWT auth, no-tests, and Refine-magic gaps
against CLAUDE.md remain and would need their own work items on this path too.

A structural cost with no line item: **version coupling.** `@refinedev/antd@6`
requires antd v5 (antd v6 causes the dual-package/ConfigProvider trap already
documented in AGENTS.md Gotcha #4). Staying means AntD majors arrive on Refine's
schedule, and every Refine upgrade re-tests the override layer.

### 3.B Path B — migrate to the proposed stack (TanStack Query/Table + RHF/Zod + Radix/shadcn + Tailwind v4 + react-router-dom v7)

| # | Item | Est. |
|---|---|---|
| B1 | New app scaffold + glue layer: `request.ts` fetch wrapper (credentials, tenant header, Zod parse, `ApiError`), `keys.ts` factory, query client presets, `useResourceMutation`, route guards | 3–5 d |
| B2 | Port `theme.css` → Tailwind v4 `@theme` + CSS variables (largely mechanical — tokens, palettes, dark mode, sidebar themes carry over) | 1–2 d |
| B3 | Component kit: app shell (port prototype markup), generic `<DataTable>` (TanStack Table + URL-synced state + loading/empty/error), form kit (`useResourceForm`, field components, 422 mapping), ~10 shadcn/Radix primitives (Dialog, Select, Dropdown, Tabs, Popover, Switch, Checkbox, Tooltip, Toast) restyled to the prototype | 6–9 d |
| B4 | Rebuild the 6 tenant resources on the golden-exemplar pattern (list + form + lifecycle actions), incl. invoice editor w/ compliance rail and the polling batch stepper | 6–9 d |
| B5 | Rebuild admin portal: org list/detail + 6-step onboarding wizard + imports | 3–5 d |
| B6 | Excel import/upload plumbing (multipart + blob downloads through the fetch wrapper), Zod schemas for the full API surface | 2–3 d |
| B7 | Decommission `frontend/` scaffold after parity sign-off | 0.5 d |
| | **Path B subtotal (to functional + visual parity)** | **21–33 d** |

End state: exactly the target architecture in CLAUDE.md — explicit glue, no
framework internals, the prototype's design system adopted nearly verbatim, and the
codebase the Playwright-as-reviewer strategy was designed for. The old app keeps
running untouched during the build (parallel workspace), so there is no dark period.

### 3.C What migration actually discards

Honest accounting of the sunk cost: of ~3,650 lines, the reusable parts port over
(`types/enums.ts` + `types/api.ts` ≈ 275 lines become Zod schemas; API-surface
knowledge, unwrap conventions, and lifecycle-action semantics carry as specs). What
is genuinely discarded is ~2,800 lines of Refine-idiom page code and providers —
working, but stock-looking, untested, and written quickly by AI against a foundation
that is itself being questioned. The onboarding wizard and batch stepper are the two
pieces with real embedded thought; both are well understood and re-specifiable.

### 3.D The real delta

**Migration costs roughly 8–15 more working days than restyling in place**, before
the shared work (§3.0) that dominates either way. In exchange it removes the
permanent override tax (A5), the Refine/antd version coupling, and every deviation
from the CLAUDE.md architecture, and it makes the prototype's CSS an asset instead
of a reference to imitate.

---

## 4. Risks on each path

**Path A risks**
- Override brittleness: every antd/Refine upgrade can silently shift styled DOM. With
  no human frontend reviewer, visual regressions ride on Playwright screenshots only.
- Fidelity ceiling: the last 10–15% of the design language never lands; the owner's
  envisioned product is permanently approximated.
- Compounding divergence from CLAUDE.md: Refine magic (`useTable`/providers) stays
  the thing the owner can't debug from first principles — the very constraint that
  motivated the proposed architecture.

**Path B risks**
- Rebuild scope discipline: 6 resources must be re-proven against the real backend;
  mitigated by the vertical-slice build order and E2E-first gate in CLAUDE.md.
- Behaviors AntD gave for free must come from somewhere: date picker (the prototype
  ships **no date-picker design** — decision needed; the standard shadcn answer is
  `react-day-picker`), searchable select/combobox (`cmdk` or Radix + filter), Excel
  drag-drop upload (small custom dropzone). Each is an explicit new-dependency
  decision per CLAUDE.md's rules.
- Temporary double surface: two frontends exist in the repo until decommission —
  needs a clear "no new features on the old scaffold" freeze to avoid split effort.

---

## 5. Recommendation

**Migrate (Path B).** The deciding facts, in order of weight:

1. **The design is already built — for the other stack.** The prototype is a complete
   component library whose CSS transplants nearly verbatim into Tailwind + shadcn
   copy-in components, and transplants essentially 0% into AntD. On AntD you pay
   12–18 days to *imitate* it and then a tax forever; on the headless stack you
   *adopt* it in 1–2 days (B2) plus component wiring you'd largely need anyway.
2. **AntD's value proposition doesn't apply here.** Its payoff is finished-looking
   components out of the box; the majority of this product's remaining surface is
   Tier-3 custom regardless. You'd keep AntD's constraints while doing custom work.
3. **The sunk cost is small and weak.** ~2,800 discardable lines, zero tests, no
   custom styling, no tenant switcher, missing the flagship document view. This is
   the cheapest moment the migration will ever have — every additional Refine screen
   raises the price.
4. **Architecture alignment.** CLAUDE.md's constraints (solo backend owner, no human
   frontend reviewer, behavior-verified correctness, explicit code over framework
   magic) were the rationale for the proposed stack; Path A keeps the frontend in
   permanent tension with its own charter, including the localStorage-JWT model that
   CLAUDE.md explicitly forbids.

**Stay on Path A only if** shipping features in the next few weeks matters more than
the design language and architecture — i.e. the owner would accept a tokens-only
AntD reskin (green primary + radius, visibly not the prototype) as the lasting look.
That is a legitimate business call, but it should be made knowingly, not by default.

### Suggested migration sequence (per CLAUDE.md build order)

1. Freeze `frontend/` (bugfixes only). Keep it running as the reference implementation.
2. Backend: cookie-session + CSRF endpoints (prerequisite for the target auth model).
3. New workspace: glue layer (B1) + tokens (B2) + shell and DataTable/form kit (B3).
4. **Vertical slice:** login → tenant switcher → invoices list → invoice create →
   one Playwright E2E against the real backend. Owner sign-off gates everything else.
5. Fan out the remaining resources from the golden exemplar (B4), then admin (B5).
6. Parity review against the old scaffold screen-by-screen → decommission (B7).

---

## 6. Open decisions for the owner

1. **The call itself:** Path A or Path B (this doc recommends B).
2. Date picker: adopt `react-day-picker` (shadcn Calendar) — the prototype has no
   design for it; one needs to be added to `design-prototype/` either way.
3. Combobox/command-palette engine: `cmdk` (also powers the ⌘K palette) — one new
   dependency covering two designed features.
4. Cookie-session backend work: schedule before or in parallel with B1 (the fetch
   wrapper's shape depends on it).
5. Chart approach for dashboard/reports: port the prototype's hand-built SVG charts
   (zero deps, exact look) vs. a library — recommendation: port the SVG components.
6. Scope of first parity release: does admin onboarding need to be in the initial
   migration, or can it trail (the old admin portal keeps working meanwhile)?
