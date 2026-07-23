# Implementation Report: Peer-derived parent/children relationship labels

## Header

- **Feature**: Hierarchical `parent`/`children` relationships render the peer kind's schema label instead of the generic "Parent"/"Children".
- **Spec dir**: `specs/003-parent-children-labels`
- **Branch**: `parent-children-labels-ifc-2930` (IFC-2930)
- **Base commit**: `069933be4ec697d0b56ef3f83aa0495f7d1ebe44`
- **Head commit**: `c9d13a658b`
- **Result**: **DONE** — all 16 tasks complete, full CI gate green, review finding fixed inline.

## Chunk-by-chunk ledger

| # | Chunk (tasks) | Tasks | Outcome | Commit(s) | Notes |
|---|---------------|-------|---------|-----------|-------|
| 1 | Setup + Foundational (T001–T003) | 3 | ✅✅✅ | `a457018b` | Discriminator confirmed: `hierarchical` truthy on **both** parent and children auto-rels → truthiness check alone suffices. Rule unit test red→green. |
| 2 | Call sites (T004–T012) | 9 | ✅×9 | `319160de` | All nine sites wired. Also fixed a latent chunk-1 type error (rule imported `RelationshipSchema` from the generated-types module, which has no top-level export → switched to the domain-model re-export). |
| 3 | E2E (T013) | 1 | ✅ | `afb52b872b` | Per user request, folded into the existing `object-hierarchy-navigation.spec.ts` (targets `LocationCountry` USA: parent peer Continent, children peer Site) instead of a new file. Surfaced + fixed a stale `getByText("Children5")` assertion the feature had broken. |
| 3b | Regression: object-relationships e2e | — | ✅ | `222a0d32` | `Children2`→`Country2`, `Children5`→`Site5` in the hierarchical-children test. |
| 3c | Regression: forms + IPAM e2e | — | ✅ | `d271860e` | 8 assertions across 5 files: form combobox `Parent *`→`Continent *` (×4); IPAM children tab `Children`→`IP Prefix` (×4, scoped to `main-panel`). `search-parent-prefixes` confirmed unaffected. |
| 4 | Polish (T014–T016) | 3 | ✅✅✅ | `86596bc9` | Changelog fragment (`changed`); full CI gate all-green; quickstart coverage confirmed via passing e2e. |
| 6 | Review fix | — | ✅ | `c9d13a658b` | Critical review finding fixed (see §5). |

**Decisions flagged upward during implementation** (both confirmed with the user mid-run):
- Apply the peer label in **create/edit forms** too (site T009), not only the 5 read surfaces.
- **Self-referential** hierarchies (IPAM prefixes) apply the peer label (accepted tradeoff — direction no longer distinguished by label text; documented in spec Edge Cases).

## Tasks not completed

None. All T001–T016 are `[X]` in `tasks.md`.

## Local-pass evidence

Environment for E2E: live local Infrahub stack (frontend :8080, API :8000, demo data), chromium, `--project=setup --project=e2e`. Unit: Vitest v4.1.9 browser mode (chromium).

| Test id | Type | Run command | Passed at | Env | Verbatim pass line |
|---------|------|-------------|-----------|-----|--------------------|
| `get-relationship-field-label.test.ts` (5 cases C1–C4) | unit | `pnpm test src/entities/schema/domain/rules/get-relationship-field-label.test.ts` | 2026-07-21T14:03:22Z (re-run w/ column-header 2026-07-21T17:07) | Vitest browser (chromium) | `Test Files 1 passed (1)` / `Tests 5 passed (5)` |
| `object-hierarchy-navigation.spec.ts:20` (new label step) | e2e | `pnpm exec playwright test tests/e2e/objects/hierarchy/object-hierarchy-navigation.spec.ts --project=setup --project=e2e` | 2026-07-21 16:21:12 CEST | live stack | `4 passed (20.2s)` |
| `object-relationships.spec.ts:120` (hierarchical children) | e2e | `pnpm exec playwright test tests/e2e/objects/object-relationships.spec.ts ... -g "hierarchical children"` | 2026-07-21T14:24:22Z | live stack | `✓ …hierarchical children (4.3s)` / `4 passed (15.9s)` |
| `object-hierarchy-crud.spec.ts` + `object-hierarchy-tree-list.spec.ts` (combobox label) | e2e | `pnpm exec playwright test <both specs> --project=setup --project=e2e` | 2026-07-21 16:42:55 CEST | live stack | `5 passed (41.0s)` |
| IPAM: `sub-ip-prefix-list-filters` + `ip-prefix-list-sort` + `ip-namespace` | e2e | `pnpm exec playwright test <three specs> --project=setup --project=e2e` | 2026-07-21 16:43:44 CEST | live stack | `15 passed (1.2m)` |
| `search-parent-prefixes.spec.ts` (regression check, unaffected) | e2e | `pnpm exec playwright test tests/e2e/search-parent-prefixes.spec.ts --project=setup --project=e2e` | 2026-07-21 16:45:05 CEST | live stack | `7 passed (18.8s)` |

**Full CI gate (final, post review-fix):** `biome ci .` → `Checked 1491 files. No fixes applied.` · `knip` → clean (1 pre-existing advisory hint) · `betterer ci` → `201 issues` (unchanged, no regression) · `pnpm test` → `Test Files 149 passed (149) / Tests 1051 passed (1051)`.

## Review findings

| Severity | File | Finding | Status |
|----------|------|---------|--------|
| **Critical** | `object-table/cells/table-column-header.tsx:214` | Peer label computed only for the sort-submenu aria-label; the **visible** header text (in `ColumnHeaderMenu`) recomputed `label ?? name`, so column headers still showed "Parent"/"Children" — and the `children` cardinality-many path never resolved the peer at all. | **Fixed inline** (`c9d13a658b`) — resolve the peer label inside `ColumnHeaderMenu`, covering all paths. |
| Low | `get-relationship-field-label.test.ts` | Empty-string peer `label` edge (truthiness fall-through) not covered. | Deferred — peer labels are always populated in practice. |
| Medium | sort picker (`add-sort-picker.tsx`) & filter heading (`relationship-filter-form.tsx`) | No e2e asserts the peer label on a hierarchical relationship in these two surfaces (unit + other e2e cover the rest). | Deferred — behavior verified by the rule unit test; surfaces wired identically. |
| Low | `object-hierarchy-navigation.spec.ts:57` | `childrenTab` locator (`a[href*="/children"]`) unscoped; relies on a single match. | Deferred — passes today; could scope to the tab bar for robustness. |
| Low | `table-column-header.test.tsx` | No component test exercises a hierarchical relationship column header (the exact path the review fix touched). | Deferred — fix verified via rule unit test + type gate; worth a regression test later. |

## Autonomous decisions

1. **Chunking**: merged Phase 1 (T001) into Phase 2 (T002–T003) because the discriminator finding is a direct input to the rule implementation — splitting across clean-context subagents would lose it.
2. **E2E approach change (user-directed)**: switched from a standalone spec to extending existing hierarchy specs; this surfaced real regressions the standalone file would have hidden.
3. **Two mid-run product decisions** put to the user (forms + self-referential IPAM) — both resolved as "apply peer label everywhere"; test assertions updated to match.
4. **Redundant-agent cleanup**: an E2E redo agent and the original (which had processed the redirect) briefly overlapped; stopped the redundant one before it caused conflicts (no leftover changes).
5. **Review fix applied inline** by the orchestrator (single file, ~4 lines) rather than dispatched, per Phase 6 guidance for small localized high-severity fixes.

## Suggested next steps

1. **Open a PR** for `parent-children-labels-ifc-2930` → base branch (nothing pushed yet). CI will re-run the same gate.
2. Optionally address the deferred low/medium items — most valuable: a component regression test for the hierarchical column header (the review-fix path), and e2e assertions for the sort-picker / filter-heading surfaces.
3. Run `/speckit.opsmill.extract` if you want to capture any durable knowledge from this feature (not run automatically).

## Addendum — generic-peer refinement (2026-07-22)

Post-review, a behavior refinement was requested: **when the hierarchical peer resolves to a generic, keep "Parent"/"Children"** rather than showing the (too-broad) generic label. Only concrete node peers get the swap.

- Rule updated to guard on `!isGenericSchema(peerSchema)` (`177cbc47`); unit test gains case **C5** (generic peer → keep "Parent"/"Children"). Vitest now 1052/1052.
- Empirically reconciled against the live app (`f289fdea`): **IPAM** prefixes resolve their peer to the generic `BuiltinIPPrefix`, so IPAM parent/children now correctly read **"Parent"/"Children"** — the 4 IPAM e2e assertions were reverted from "IP Prefix" back to "Children". **Location** peers (`LocationContinent`, `LocationSite`) are concrete nodes, so they keep **"Continent"/"Site"** — Location specs unchanged.
- Final label behavior: **concrete-node peer → peer label** (Location: "Continent"/"Site"); **generic peer → "Parent"/"Children"** (IPAM prefixes). Full gate re-verified green (biome, betterer 201, vitest 1052/1052, 28 e2e passing).
- Spec/contract/data-model docs updated to match (the earlier "show the generic's label" decision is reversed).
