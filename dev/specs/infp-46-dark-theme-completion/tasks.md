# Tasks: Dark Theme Completion

**Input**: Design documents in `dev/specs/infp-46-dark-theme-completion/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. Constitution principle IV (Test Discipline) and `AGENTS.md` both require tests
for new functionality. Pure-function tasks are written test-first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on another incomplete task
- **[Story]**: the user story the task serves

## ⚠ Before starting

Two governance approvals are **required** before Phase 3 (see [plan.md](./plan.md#open-governance-points)).
`AGENTS.md` lists both as Ask First:

1. **GraphQL schema modification** — new `Theme` enum, `EffectiveTheme` type, field on two types, new
   mutation argument. Additive and non-breaking, but public schema.
2. **Persisted model change** — nullable `theme` on the `Preference` `StandardNode`. Expected additive
   with no data migration; confirm with an owner of the `StandardNode` persistence path.

Phases 1, 2 and 7–9 need neither approval and can proceed meanwhile.

Verification uses the binaries directly — `pnpm` scripts abort in this environment:

```bash
cd frontend/app && node_modules/.bin/vitest run && node_modules/.bin/biome ci . && node_modules/.bin/tsc --noEmit
```

---

## Phase 1: Setup

**Purpose**: make the worktree able to build and give the light theme a reference to be compared against.

- [x] T001 Initialise the visualizer submodule: `git submodule update --init frontend/packages/schema-visualizer`. Required for US7, and it clears the two phantom `betterer` findings an uninitialised submodule produces.
- [x] T002 [P] Install the editable SDK: `uv pip install -e python_sdk`. Fresh worktrees skip this and `infrahub_sdk` imports fail.
- [x] T003 Base the branch on `origin/bab-dark-theme-app` and open the pull request **against that branch**, not `develop` — this is a stacked PR on #10284. It supplies the surfaces US5 migrates and keeps this review free of #10284's 151 files. Re-target `develop` once #10284 merges; rebase if it is revised. ⚠ #10284's failing e2e checks are inherited and will show on this PR — say so in the description so they are not read as caused by this work.
- [ ] T004 ⏸ **Deferred to just before Phase 7** (needs a running stack; only US5/US6 depend on it). Capture light-theme reference screenshots of every page US5/US6 touch (proposed changes, a diff view, checks, path traversal, data viewer). FR-020/SC-005 make "light is unchanged" a hard constraint, and it is unprovable later without a baseline taken now.

**Checkpoint**: builds clean; light-theme baseline exists.

---

## Phase 2: Foundational (blocking)

**Purpose**: the theme value every other story consumes. Nothing here needs the backend, so it can
start immediately and in parallel with governance approval.

⚠ The context lives in `shared/`, the provider in the entity. `shared/` may not import an entity
(`dev/knowledge/frontend/entities-structure.md`), and there is **no lint guard** — layer rules are
review-enforced only.

- [x] T005 Create `frontend/app/src/shared/context/theme-context.ts` exporting the `ResolvedTheme` type (`"light" | "dark"`). It must import nothing from `entities/`. ⚠ **Scope corrected during implementation**: the React context const itself moved to Phase 3 (T021a). `knip` runs in CI and fails on any export without a consumer, so a context with neither a producer nor a reader cannot land green on its own — it must arrive with its provider. The *type* lands here because the pure resolver consumes it immediately.
- [x] T006 [P] Write failing tests for stage-2 resolution in `frontend/app/src/entities/preferences/domain/rules/theme.test.ts`: table-driven over `(choice, systemPrefersDark)` → `"light" | "dark"`, covering all three choices and both system states.
- [x] T007 Implement `frontend/app/src/entities/preferences/domain/rules/resolve-theme.ts` to pass T006 (named for the house `resolve-*` convention). ⚠ Pure only — `domain/rules` may not touch browser storage or React.

**Checkpoint**: a resolved theme can be held and read; consumers can be written against it.

---

## Phase 3: User Story 1 — Choose a theme (P1) 🎯 MVP

**Goal**: a user picks light / dark / match-system; it applies immediately, persists to their account,
and paints correctly on first frame.

**Independent Test**: change the setting, watch it apply without reload; reload under heavy network
throttling and confirm no flash; sign in from a second browser and see the same choice.

### Backend

- [ ] T008 [US1] Add `Theme` StrEnum (`LIGHT`, `DARK`, `SYSTEM`) to `backend/infrahub/core/preferences/constants.py`, beside `DateFormat`.
- [ ] T009 [US1] Add `theme: Optional[Theme] = None` to `Preference` in `backend/infrahub/core/preferences/models.py`. ⚠ `Optional[Theme]`, never `Theme | None` — `StandardNode.guess_field_type` requires it, as the file's own comment records.
- [ ] T010 [US1] Add `Theme` and `EffectiveTheme` to `backend/infrahub/graphql/types/preferences.py`; add `theme` to `EffectivePreferencesType` and `RawPreferencesType` per [contracts/graphql-preferences.md](./contracts/graphql-preferences.md). ⚠ Enum descriptions stay on **one line** — the SDL printer dedents multi-line descriptions inconsistently and makes the generated schema environment-dependent.
- [ ] T011 [US1] Resolve `theme` through the existing user → global → default chain in `backend/infrahub/graphql/queries/preferences.py`.
- [ ] T012 [US1] Write failing tests for the mutation's three-state argument in `backend/tests/unit/graphql/test_preferences.py`: omitted leaves unchanged, explicit `null` clears, a value sets. ⚠ This is the single easiest thing to get wrong — collapsing "omitted" and "null" makes an override impossible to clear.
- [ ] T013 [US1] Add the `theme` argument and payload field to `backend/infrahub/graphql/mutations/preferences.py`, honouring `_UNSET` exactly as `date_format` does. Passes T012.
- [ ] T014 [P] [US1] Test the resolution chain: nothing set → `DEFAULT`/null; user set → `USER`; clearing the user layer returns to `DEFAULT`. The global layer is exercised too — the mutation's `scope` argument reaches it and the chain must keep working — even though no interface writes it in this version.
- [ ] T015 [P] [US1] Test that a non-`Theme` value is rejected on construction, including on load from the database.
- [ ] T016 [US1] Regenerate and commit: `uv run invoke schema.generate-graphqlschema`. CI fails on a stale `schema/schema.graphql`.

### Frontend

- [ ] T017 [US1] Add `theme` to `PreferenceValues` and `EffectivePreferences` in `frontend/app/src/entities/preferences/domain/model/preference.ts`.
- [ ] T018 [US1] Add `theme` to the effective-preferences query and the **user** upsert mutation under `frontend/app/src/entities/preferences/ui/queries/`. ⚠ Not `update-global-preferences.mutation.ts` — leaving `theme` out of that document is what keeps the organisation scope unreachable from the interface without needing backend changes.
- [ ] T019 [US1] Regenerate frontend types: `cd frontend/app && pnpm codegen`.
- [ ] T020 [US1] Write failing tests for `frontend/app/src/entities/preferences/ui/theme-provider.test.tsx`: fills the shared context from the effective preference; falls back to the flag's default when the query fails; reacts to a `prefers-color-scheme` change while mounted.
- [ ] T021a [US1] Add the `ThemeContext` const and its reader hook to `frontend/app/src/shared/context/theme-context.ts` (moved from T005 — see the note there). Model it on the sibling `shared/context/date-preferences-context.tsx`. Land it in the same commit as T021 so no export exists without a consumer.
- [ ] T021 [US1] Implement `frontend/app/src/entities/preferences/ui/theme-provider.tsx` — fills `shared/context/theme-context`, applies the class to `document.documentElement`, writes the `localStorage` mirror, subscribes to `prefers-color-scheme`. Mirror `DatePreferencesProvider`'s shape. Passes T020. No `storage` listener — cross-tab sync is out of scope.
- [ ] T022 [US1] Mount the provider in `frontend/app/src/app/app.tsx` alongside `DatePreferencesProvider`.
- [ ] T023 [US1] Add the inline pre-paint script to `frontend/app/index.html` `<head>`, **before** the module script. Precedence: mirrored resolved theme → mirrored `system` choice resolved against `prefers-color-scheme` → light. ⚠ The empty-cache fallback is **light**, not `prefers-color-scheme` — consulting the system there would put a dark-OS user into the alpha palette before any preference has been read. `prefers-color-scheme` is read only when the *user* has chosen match-system. ⚠ It blocks rendering and runs before everything: wrap storage access in `try`/`catch` (`localStorage` throws when storage is disabled, e.g. Safari private browsing) and validate the stored string against the known set before using it as a class name.
- [ ] T024 [US1] Add the theme field to `frontend/app/src/entities/preferences/ui/preference-fields.tsx` as a `Combobox` matching the existing fields, keeping `"Automatic (inherited)"` as the empty label. Dark carries a visible **"alpha"** tag — the handover named that word specifically, so render it rather than a synonym; "match system" says it can resolve to the alpha palette (FR-008).
- [ ] T025 [P] [US1] Surface the field in `preferences-form.tsx` and `user-preferences-card.tsx`, updating their existing tests. ⚠ **Not** `global-preferences-form.tsx` — theme is user-scoped only in this version. The backend gains the global scope for free (the mutation's `scope` argument is shared), so this defers only the interface.
- [ ] T026 [US1] End-to-end test for first-paint correctness (FR-006 / SC-002): with a stored dark preference and the preference request delayed, assert the document element carries the dark class before the app has hydrated. Add a cold-cache case — no mirror, emulated **dark** browser preference — asserting the first paint is **light**, since a defaulted user must not reach the alpha palette by inference. ⚠ The pre-paint script sits outside the module graph so Vitest cannot reach it; this is its **only** automated coverage.
- [ ] T027 [US1] Remove `@custom-variant dark` and its `TODO: DELETE` from `frontend/packages/ui/src/styles/theme.css` (FR-019). ⚠ **Last task in this phase** — it is what all current dark rendering depends on; removing it earlier leaves the tree with no way to reach dark at all.

**Checkpoint**: US1 ships standalone. Dark is reachable, persistent and flash-free.

---

## Phase 4: User Story 2 — Non-production default (P1)

**Goal**: non-production deployments default to dark so the team dogfoods it without per-engineer setup.

**Independent Test**: load as a user with no stored preference on a pre-release build → dark; on a
release build → light; a personal choice beats both and is never overwritten.

- [ ] T028 [US2] Add `dark_theme: bool = False` to `ExperimentalFeaturesSettings` in `backend/infrahub/config.py`, beside `graphql_enums`. A plain bool — no tri-state is needed, since the flag carries no derived value. ⚠ Not `installation_type`, which is community-vs-enterprise and a tempting false lead on the same payload.
- [ ] T029 [US2] Regenerate and commit: `uv run invoke schema.generate-jsonschema`, then `cd frontend/app && pnpm codegen`. No new endpoint or payload field — `experimental_features` is already on the unauthenticated `/api/config`.
- [ ] T030 [US2] Enable it in `development/docker-compose.yml`: `INFRAHUB_EXPERIMENTAL_DARK_THEME: ${INFRAHUB_EXPERIMENTAL_DARK_THEME:-true}`. ⚠ Defaulting to `true` — unlike its two neighbours — is precisely what delivers SC-008. The env var still overrides for an engineer who wants light.
- [x] T031 [US2] Add the flag to `development/docker-compose.yml`, defaulted `true`. **Reversed during implementation:** the root `docker-compose.yml` gets the flag too, defaulted `false`, matching its two experimental siblings there. The original plan was to withhold it from the root file, but that file's env block is *generated* from `Settings` by `release.gen-config-env`, and CI's `validate-docker-compose-env-vars` fails on any drift. The generator's only per-setting exclusion is the `INFRAHUB_DEV` prefix skip, which would mean moving `dark_theme` into `DevelopmentSettings` — a class `/api/config` does not publish, so the gating rule could only read it by widening an unauthenticated endpoint to expose development-only settings. Not worth it. What the original decision protected is unaffected: production stays light because the default is `false` and the frontend gates on the flag. The only thing given up is that an operator *can* opt in from the root compose file — the same posture as `INFRAHUB_EXPERIMENTAL_GRAPHQL_ENUMS` and `INFRAHUB_EXPERIMENTAL_VALUE_DB_INDEX`.
- [ ] T032 [US2] Gate the theme field on the flag: with it off, render light and **omit the field entirely**. ⚠ Not a light-only picker — offering match-system would let a dark-OS user reach the alpha palette straight through the gate.
- [ ] T033 [US2] Default a user with no stored preference to dark when the flag is on, **ignoring the operating system**. Extend T020's tests to assert a defaulted user's theme does not change when the emulated system appearance flips.
- [ ] T034 [P] [US2] Test that turning the flag off **retains** a stored `DARK` preference — renders light, leaves the stored value intact, and honours it again when the flag returns. ⚠ A config change must never destroy user data (FR-013).
- [ ] T035 [US2] Pin the theme explicitly in both end-to-end suites (`frontend/app` Playwright and `tests/e2e` pytest) so they stop inheriting the flag's value. ⚠ #10284's e2e checks are already failing and are out of scope — baseline only from a green run after it lands, or its failures will be misread as fallout from this change.

**Checkpoint**: the dogfooding loop is live.

---

## Phase 5: User Story 3 — GraphQL sandbox (P2)

- [x] T036 [US3] Replace `forcedTheme="light"` in `frontend/app/src/pages/graphql/index.tsx` with the resolved theme from the shared context. ⚠ Pass `"light"`/`"dark"` only — never `"system"`, or GraphiQL runs its own `prefers-color-scheme` detection and can disagree with the application.
- [ ] T037 [US3] Test that the sandbox receives the resolved value and follows a theme change. ⚠ The relied-upon behaviour (reactive `forcedTheme`, and picker-hiding when set) is not documented public API — it was verified against `graphiql@5.2.4`'s bundled source, so a test is what protects the binding across upgrades. *Partially covered*: `use-resolved-theme.test.tsx` now guards the hook the page reads from; the GraphiQL binding itself (that `forcedTheme` reaches the sandbox and reacts) remains untested — GraphiQL is too heavy for the browser-mode suite, so this wants an e2e assertion on the sandbox page.

---

## Phase 6: User Story 4 — Mermaid diagrams (P2)

- [x] T038 [US4] Derive `mermaidConfig.theme` from the resolved theme in `frontend/app/src/shared/components/editor/markdown/markdown-with-mermaid.tsx`, mapping to Mermaid's `"dark"` / `"default"`. ⚠ `rehypePlugins` is currently a module-level constant; making it theme-dependent **must** memoise on the resolved theme alone. A new array identity per render re-runs the rehype pipeline continuously — the diagram flickers and a CPU core pins.
- [x] T039 [US4] Replace the hardcoded `bg-white` on the pan/zoom container in `frontend/app/src/shared/components/editor/markdown/mermaid-diagram.tsx` with a surface token. This is the bright panel behind an otherwise-correct dark diagram.
- [x] T040 [P] [US4] Tokenise the `mermaid-error` fallback styling so the parse-error state is legible in both themes (FR-015).
- [x] T041 [US4] Test that a theme change re-renders the diagram, and that the plugin array is stable across renders at a fixed theme.

---

## Phase 7: User Story 5 — Legacy pages onto tokens (P2)

**Goal**: no application component carries per-theme overrides or raw color literals.

⚠ Verify the light theme against the T004 baseline after **every batch**, not once at the end. This
is the constraint a token swap breaks most easily and the most expensive to bisect late.

- [ ] T042 [P] [US5] Migrate `entities/diff/ui/` — `node-diff/utils.tsx`, `node-diff/node.tsx`, `checks/validator.tsx`, `checks/check.tsx`, `checks/data-conflict.tsx`, `diff-badge.tsx`.
- [ ] T043 [P] [US5] Migrate `entities/path-traversal/ui/` — `path-results-list.tsx`, `infra-node.tsx`, `path-traversal-page.tsx`.
- [ ] T044 [P] [US5] Migrate `entities/proposed-changes/ui/diff-summary/diff-summary-tag-group.tsx`, `entities/tasks/ui/task-display.tsx`, `entities/branches/ui/branch-working-notice.tsx`, `entities/schema/ui/styled.tsx`, `entities/user-profile/ui/account-token-create-action.tsx`.
- [ ] T045 [P] [US5] Migrate `shared/components/` — `modals/modal-confirm.tsx`, `table/style.tsx`, `table/sticky-cell-shadow.tsx`, `ui/infrahub-logo.tsx`, `ui/link-pill.tsx`.
- [x] T046 [US5] ✅ **No work needed.** Migrate `shared/components/ui/badge.tsx` **separately and last**. ⚠ Verified during implementation: all twelve occurrences are semantic colours, which are out of scope. The file needs no change. Redesigning semantic palettes is **out of scope** (tracked separately); the rule is do not *degrade* them. Where a mechanical swap would flatten two currently-distinct severities into one, keep the distinction and note it for that separate effort.
- [ ] T047 [US5] Add the automated guard that makes SC-004 a standing property rather than a one-time cleanup. `betterer` is already wired into CI and is the lower-friction option; a lint rule is stricter. Without a guard the debt returns with the next feature branch.
- [ ] T048 [US5] Verify: `git grep -c "dark:" -- 'frontend/app/src/**/*.tsx'` returns nothing. ⚠ Use plain `git grep` — `rtk` reformats output and an empty piped result is not proof.

---

## Phase 8: User Story 6 — Data viewer (P3)

- [x] T049 [US6] Replace `bg-neutral-800 text-neutral-200` (line 29) and `border-neutral-700` (line 77) in `frontend/app/src/shared/components/data-viewer/data-viewer.tsx` with palette tokens. `neutral` is Tailwind's cold grey; the theme is built on warm `stone` — that difference is the reported tone mismatch.
- [ ] T050 [US6] Replace the two `bg-white` containers (lines 58, 89) with tokens — a fixed light background in dark mode, which FR-018 forbids.
- [ ] T051 [P] [US6] Walk every content type the viewer handles and confirm none retains a fixed light background.

---

## Phase 9: User Story 7 — Schema visualizer (P3)

⚠ Completes on the upstream repository's timeline. Tracked separately so it does not gate the other
six; the work stays in scope.

- [ ] T052 [US7] Open a pull request on `opsmill/infrahub-schema-visualizer` adding dark support: canvas, nodes, edges, labels and controls, with the theme accepted from the embedding application rather than detected independently.
- [ ] T053 [US7] Get it merged and released upstream.
- [ ] T054 [US7] Bump the submodule pointer here and pass the resolved theme into the visualizer. ⚠ Never point at an unpushed commit — it breaks every other checkout.
- [ ] T055 [US7] Confirm no visualizer styling code landed in this repository (FR-016).

---

## Phase 10: Cross-cutting

- [x] T056 Contrast audit (FR-021 / SC-009) across the pages walked for SC-006, not a sample — text and essential interface elements against their surfaces. ⚠ Scope boundary: this is legibility against a background, **not** semantic palettes (diagram, syntax-highlighting, status and severity colors), which are tracked separately. Record anything noticed there for that effort rather than fixing it here.
- [x] T057 [P] Add a changelog fragment under `changelog/`. This series used `ci/skip-changelog` for pure restyling, but a user-facing theme setting is a genuine feature and warrants an entry.
- [x] T058 [P] Document the theme preference in the user-facing docs under `docs/`, including that dark is pre-release.
- [ ] T059 Run `/pre-ci` before pushing — it runs the locally-executable CI checks including generated-file and generated-doc validation, which this feature touches in three places.

---

## Dependencies

```text
Phase 1 (setup)
   └─▶ Phase 2 (shared context + resolution)      ← blocks every consumer
          ├─▶ Phase 3 (US1)  ← governance approval required
          │      └─▶ Phase 4 (US2)
          ├─▶ Phase 5 (US3)     ┐
          ├─▶ Phase 6 (US4)     ├─ independent of each other
          └─▶ Phase 8 (US6)     ┘

Phase 7 (US5) ── needs PR #10284 merged (or T003's rebase)
Phase 9 (US7) ── independent; gated on the upstream repository
Phase 10      ── after the phases it audits
```

**Critical path**: T001 → T005/T007 → T008–T027 (US1) → T028–T035 (US2).

**Parallelisable once Phase 2 lands**: US3, US4, US6 and the US5 migration batches are all
independent of one another. US7 can start at any time.

## Task count

59 tasks: 4 setup, 3 foundational, 20 US1, 8 US2, 2 US3, 4 US4, 7 US5, 3 US6, 4 US7, 4 cross-cutting.

The US2 count is unchanged but its content is not: the version-derived resolver, its tests and the
config field were replaced by the flag, its compose wiring, and the flag-off behaviour.
