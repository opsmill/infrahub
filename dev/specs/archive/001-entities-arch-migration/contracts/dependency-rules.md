# Contract: Entity Dependency Rules

The "interface" this feature exposes is the set of import edges permitted between layers. Every
migrated entity MUST satisfy this contract. It is the acceptance oracle for each PR.

## Allowed edges

```text
ui            → domain (same entity)
ui            → shared
ui            → other-entity domain
ui            → other-entity ui
domain/use-cases → own api/
domain/use-cases → domain/model
domain/use-cases → domain/rules
domain/rules  → domain/model
api           → domain/model      (TYPE-ONLY imports)
api           → shared
domain/*      → other-entity domain/model  (types only, no cycle)
```

## Forbidden edges

```text
domain/*      → ui
domain/*      → routing
domain/*      → @tanstack/react-query
domain/*      → @apollo/client
domain/*      → browser storage (localStorage/sessionStorage, jotai/zustand stores)
domain/*      → notification/toast libraries
domain/*      → **/graphql/generated/**  and  shared/api/rest/types.generated
api           → domain/rules
api           → domain/use-cases
api           → ui
domain/model  → api | domain/rules | domain/use-cases | ui   (model is a pure leaf)
ui            → another entity's api/
ANY           → import that forms a dependency cycle
```

## Enforcement mapping

| Rule | Tier 1 (Biome, now) | Tier 2 (dependency-cruiser, deferred) |
|------|---------------------|----------------------------------------|
| `domain/*` no React/TanStack/Apollo/storage/toast/generated | ✅ `noRestrictedImports` on `domain/**` glob | — |
| `domain/model` is a pure leaf | — | ✅ folder-directional rule |
| `api → domain/model` only (not rules/use-cases) | — | ✅ folder-directional rule |
| `ui` never imports another entity's `api/` | — | ✅ cross-entity folder rule |
| no cycles | (tsc/build surfaces most) | ✅ `no-circular` |

Until Tier 2 lands, the folder-directional rules are enforced by code review against this contract.

## Known accepted deviations

- `branches/domain/get-branches.ts` reads `store`/`branchesState` (browser state in domain). Deferred
  per FR-016; either the Tier-1 storage pattern excludes this file or the file is annotated until the
  follow-up lifts the read to `ui/`. Any such deviation MUST be recorded here when introduced.
