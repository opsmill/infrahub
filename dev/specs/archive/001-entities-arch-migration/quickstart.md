# Quickstart: Migrating One Entity

The repeatable recipe for each per-entity PR. Do exactly one entity per PR.

## Prerequisites

- On a fresh branch off trunk (`stable`/`develop` per team convention) — **not** the planning branch.
- `cd frontend/app`.

## Steps

1. **Survey the entity.**
   ```bash
   find src/entities/<entity> -type f | sort
   ls src/entities/<entity>/domain
   ```
   Count `domain/` files → decide split (>4 = split; ≤4 = stay flat).

2. **Classify each `domain/` file** using the heuristic in `data-model.md`:
   - type declarations → `domain/model/`
   - pure functions (no I-O) → `domain/rules/`
   - orchestration / calls `api/` → `domain/use-cases/`
   - generated↔domain mapping → **move to `api/`**

3. **Split mixed files (Option A).** If a file co-locates domain types + mapping (e.g. `*.mappers.ts`):
   - move the exported domain types to `domain/model/`
   - move the mapping functions to `api/`, retyped to return the domain types
   - `api/` fetchers now return domain types (not raw generated shapes)

4. **Move files & rewrite imports.** Prefer `git mv` to preserve history. Update every import site
   across the repo (not just within the entity).

5. **Purge generated types from `domain/`.** Ensure no `domain/**` file imports `**/graphql/generated`
   or `shared/api/rest/types.generated`. They belong in `api/` now.

6. **Add the Tier-1 guard glob.** Append `src/entities/<entity>/domain/**` to the `overrides.includes`
   list in `biome.jsonc` (see `contracts/biome-guard.md`).

7. **Verify — all four MUST be green:**
   ```bash
   pnpm tsc
   pnpm build
   pnpm test
   pnpm biome
   ```

8. **Open the PR.** Diff should touch only this entity + the one lint-config line. Confirm no Towncrier
   fragment is needed (internal refactor).

## Entity-specific notes

- **`role-manager`** (first, mechanics): 2 files, stays flat. Also do the one-time guard liveness check
  from `contracts/biome-guard.md` (add a forbidden import, confirm `pnpm biome` fails, revert).
- **`branches`** (second, canonical): split `branch.mappers.ts` three ways; fix the generated-type leak;
  then **update `dev/knowledge/frontend/entities-structure.md`** to document the reconciled structure
  using `branches` as the worked example. Leave the `store`/`branchesState` read as-is (deferred, FR-016)
  and record it in `contracts/dependency-rules.md`.
- **`nodes/`** (last): treat each sub-module as its own PR. Do **not** disturb in-flight sort work in
  `nodes/object` — verify its tests stay green.

## Definition of done (per entity)

- [ ] Layout matches `data-model.md` (flat/split per policy; no <2-file folders).
- [ ] `domain/` imports zero generated types; `domain/model` is a pure leaf.
- [ ] Mappers live in `api/`; `api/` returns domain types.
- [ ] Tier-1 glob added; `pnpm biome` passes.
- [ ] `pnpm tsc && pnpm build && pnpm test` all green.
- [ ] PR touches exactly one entity + the lint-config line.
- [ ] Public behavior unchanged; tests moved with subjects.
