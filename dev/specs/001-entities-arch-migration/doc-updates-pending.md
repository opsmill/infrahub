# Pending doc updates for `dev/knowledge/frontend/entities-structure.md`

Accumulated during the migration (2026-07-02). Apply at the end, once all entities are done.

## 1. Type-placement heuristic (model vs. colocate)

Add a rule that resolves where a type lives:

> **Move a type to `domain/model/` when it is shared domain vocabulary** — an entity, value object, ID, filter, or union that multiple call-sites import as a concept (e.g. `FilterDefinition`, `NumberPool`, `BranchListItem`).
> **Keep a type colocated with its function when it is that function's own contract** — a `Params` / `Result` / function-signature alias used only to type one use-case or rule (e.g. `GetBranchesParams`, `GetBranchesResult`, `SchemaResult` on `resolveSchema`).

Litmus test applied during migration:
- `FilterDefinition` (discriminated union, ~12 importers, functions were incidental accessors) → **model**.
- `NumberPool` (domain entity, 5 importers) → **model**.
- `SchemaResult` (the return type of the `resolveSchema` rule, 3 importers, function is primary) → **stays colocated** in `rules/resolve-schema.ts`.
- `GetBranchesParams/Result/GetBranches` → **stay colocated** in the use-case.

Value-object *data* (predefined constant instances of domain types, e.g. `ALL_METADATA_FILTERS`, `METADATA_CREATED_AT`) → **model** (vocabulary values), not `rules/`.

## 2. Reconciled decisions to reflect (already in tasks.md decision log)

- **Enforcement is review-only** — the Tier-1 Biome guard was dropped; there is no lint guard. (entities-structure.md already updated to say this.)
- **Generated enums / node value-types** (`BranchStatus`, `CheckType`, `Branch`) and the **schema `components` contract** are allowed in `domain/model`; only **wire response DTOs** move to `api/`. (Already in the doc's "DTOs vs enums" section — confirm wording covers node value-types + the schema-contract exception.)
- **Option-b mappers**: mappers live in `api/` but are *called by* use-cases; fetchers still return `{data,errors}`. The doc's "Mappers" section says mapping lives in api/ — confirm it doesn't over-promise "fetchers return domain types" (that stronger form, FR-002, was not implemented).
- **`betterer`, not `pnpm tsc`, is the TS gate** (repo carries 208 tracked tsc errors). Worth a one-line note in the verification guidance so future migrators refresh `.betterer.results` for moved files rather than chasing the pre-existing 208.

## 3. The 1-file-folder nuance

`data-model.md` says "never create a folder for <2 files," but split reference entities (branches, nodes/object) legitimately end up with a 1-file `model/` or `rules/`. Clarify: **once an entity is split (>4 files), create whichever of model/rules/use-cases a file belongs in — even at 1 file** — rather than leaving a stray typed file flat at `domain/` root. (This is what the resource-manager `type.ts` fix corrected.)

## 4. Relative-import gotcha (for the migration guide / quickstart)

Moving a `domain/*.ts` into `domain/use-cases|rules/` adds one directory level, so **relative** imports (e.g. test fixtures `../../../../tests/fake/schema`) break — the `@/` alias sed does not catch them. `betterer` (full tsc) is what surfaces these; add `+1 ../` per level moved. Bit us in schema (11) and nodes/object (1).

## 6. `utils.ts` is banned — content fans out by responsibility

All entity `*/utils.ts` grab-bags were eliminated. The rule for the doc: **there is no `utils.ts`**; classify each function/type into a layered home:
- URL/path builders + tab-segment types + outlet/param hooks → `ui/routing/<noun>-urls.ts` (+ `ui/routing/` for the cluster). Updated `url-construction.md` accordingly.
- Pure domain logic → `domain/rules/`; domain types → `domain/model/`.
- Presentation/view-model helpers (colors, select-options) → `ui/`.
- Browser-storage / token persistence → **`api/`** (external I/O), so domain reaches it via `domain → api` (this fixed the auth `domain → storage` leak — `authentication/api/token-storage.ts`).
- Namespace-shared helpers with no single owner (e.g. `ipam`) → namespace-level `ui/routing/` + `domain/rules/`.

Worked examples committed: branches, proposed-changes, nodes/object, ipam, permission, authentication, path-traversal.

Still to do (separate from `utils.ts` files): the remaining `utils/` **directories** (`resource-manager/utils`, `ipam/*/utils`, `nodes/{object,relationships,convert}/utils`, `nodes/object/ui/object-table/utils`) — same fan-out treatment.

## 7. Backend-authoritative violation to fix

`path-traversal/domain/rules/visible-namespace.ts` (`HIDDEN_NAMESPACES`) is a **client-side mirror of the backend `DEFAULT_EXCLUDED_NAMESPACES`** — exactly the anti-pattern `entities-structure.md`'s "Backend is authoritative" section calls out. It's only relocated, not fixed. Proper fix: surface excluded namespaces via the API rather than hardcoding the set client-side.

## 5. Deferred follow-ups (tracked in tasks.md T053/T054/T050)

- Lift storage/global-state reads out of `domain/` into `ui/` (branches `store`/`branchesState`, schema jotai `store`, auth `localStorage`/`window`).
- Propose dependency-cruiser (Tier-2 directional enforcement) — new-dependency decision.
- `nodes/` namespace-level loose files (`types.ts`, `utils.ts`, `getObjectItemDisplayValue.tsx`, `stores/`) left in place.
- **Pre-existing boundary smell** (surfaced by the boundary audit, not introduced by the migration): `nodes/relationships/api/get-default-parent-from-api.ts` imports `getSchema` (schema's `domain/use-cases`) — an `api/` file calling another entity's use-case, which the layer rules forbid (`api/` → shared + own `domain/model` only). The migration only repointed its path. Fix by lifting the `getSchema` call out of the fetcher into a `relationships` use-case. Tracked for when `relationships` is properly migrated.
- **`shared → entity` inversion**: `shared/components/form/object-form.tsx` imports `object-template-form` (now `nodes/object/ui/object-template/`). `shared/` is the base layer and should not import from `entities/`. Pre-existing; persists after relocating object-template. Fix by inverting the dependency (object-form takes the template UI as a prop / slot, or the template feature composes object-form rather than the reverse).
- **Flat `nodes/` UI-only sub-modules — RESOLVED** (and then corrected for existing-home fit + honest names): `object-template` → `object/ui/object-template/`; `getSchemaObjectColumns` (view-model builder) → existing `object/ui/object-table/`; `object-item-meta-edit` and the `action-buttons` (detail-header buttons) → nested under the existing `object/ui/object-details/` (their caller lives there), not new top-level siblings; `edit-form-hook` was misnamed (no hook — just dynamic form-field types) and schema-coupled, used only by `object-item-edit` → merged (`form.tsx` inlined), renamed to `object-item-edit/form-field-types.ts`, and moved to its sole consumer. **Lesson for the migration guide: when folding a folder in, check for an existing subfolder that already fits and sanity-check the folder/file name before creating a new one.**
- **Remaining `nodes/` structure questions** (optional, not done): (a) namespace loose files `types.ts`/`utils.ts`/`getObjectItemDisplayValue.tsx`/`stores/` (T050); (b) the *structured* object-facet sub-modules `object-item-edit`, `convert`, `hierarchy`, `profiles`, `relationships` are legitimately separate (they have their own `api/domain/ui`), but several are conceptually object facets — a possible future consolidation into `nodes/object`, to decide deliberately rather than mechanically.
