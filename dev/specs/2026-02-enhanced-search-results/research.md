# Research: Enhanced Search Results

**Feature**: 2026-02-enhanced-search-results
**Date**: 2026-02-19
**Updated**: 2026-02-23

## Research Findings

### R1: Backend Search API — Current Capabilities

**Decision**: Extend the existing `InfrahubSearchAnywhere` GraphQL query with an `offset` parameter for pagination.

**Rationale**: The current resolver at `backend/infrahub/graphql/queries/search.py` already supports `q`, `limit`, `partial_match`, and `case_sensitive` params and returns `count` + `edges`. It lacks `offset` for pagination, which is needed by the full results page. Adding `offset` to the existing query is the minimal change — it maps directly to Cypher `SKIP` clause.

**Alternatives considered**:
- **New dedicated search endpoint**: Rejected — unnecessary complexity when existing endpoint can be extended with one parameter.
- **Cursor-based pagination**: Rejected — the search results are not ordered by a stable cursor; offset-based is simpler and sufficient for this use case where result sets are bounded.
- **Client-side pagination only**: Rejected — fetching all results at once would be expensive for large datasets on the full results page.

**Current backend code path** (post-US4 fix):
1. `search_resolver()` in `search.py` receives GraphQL params
2. For both case-sensitive and case-insensitive: uses `NodeGetListByAttributeValueQuery` with `case_insensitive` flag
3. Query uses native Cypher SKIP/LIMIT for pagination
4. `query.count()` returns true total (separate Cypher COUNT query without SKIP/LIMIT)
5. Results returned as `[{"id": uuid, "kind": kind}]`

**Key finding (fixed)**: The `count` field previously returned `len(results)` AFTER limit/offset were applied. The US4 fix uses `query.count()` which runs a separate Cypher query without SKIP/LIMIT, returning the true total.

### R2: Frontend Search Dropdown — Current Architecture

**Decision**: Modify the existing `search-anywhere` components to increase the result limit and add a scrollable container with footer.

**Rationale**: The search dropdown uses the `cmdk` library (Command palette pattern). The current limit of 4 results is hardcoded in `frontend/app/src/entities/navigation/api/search.ts`. The `Command.List` component from cmdk already supports scrolling — the constraint is the hardcoded limit, not the UI framework.

**Alternatives considered**:
- **Replace cmdk with custom dropdown**: Rejected — cmdk provides keyboard navigation, accessibility, and filtering for free. Modifying its container height is sufficient.
- **Virtual scrolling in dropdown**: Rejected — with a cap of 50 items, standard DOM rendering is performant; virtual scrolling adds complexity for no benefit.

**Current component tree**:
```
SearchAnywhere → SearchAnywhereDialog → Command → Command.List
  ├── SearchActions (Go to: max 3)
  ├── SearchNodes (Objects: max 4) ← change to 50
  └── SearchDocs (Docs: max 3)
```

**Changes needed**:
- `search.ts`: Change limit from 4 to 50
- `search-anywhere-dialog.tsx`: Set max-height on `Command.List` with overflow-y scroll
- New `search-anywhere-footer.tsx`: Shows "View all X results" with count, links to `/search?q=...`

### R3: Frontend Routing — Adding the Search Results Page

**Decision**: Add a new `/search` route with lazy-loaded page component following existing patterns.

**Rationale**: The router at `frontend/app/src/app/router.tsx` uses React Router with lazy imports. All pages follow the pattern: page component in `pages/`, entity logic in `entities/`, lazy loaded via `router.tsx`.

**Route pattern**:
```tsx
{ path: "/search", lazy: () => import("@/pages/search-results") }
```

**URL format**: `/search?q=<query>` — search term passed as URL query parameter via `nuqs` for URL state sync, enabling bookmarking and sharing.

### R4: Frontend Table Components — Reuse Strategy

**Decision**: Reuse the existing `DataTable` component from `shared/components/table/data-table.tsx` for node type group tables on the full results page.

**Rationale**: The `DataTable<T>` component already supports TanStack Table, sortable columns, pagination, loading states, and empty states. The full results page tables can use this component with dynamically generated columns based on each node type's schema (same pattern as `ObjectTable`).

**Alternatives considered**:
- **Custom table component**: Rejected — existing DataTable covers all requirements (sorting, pagination, links).
- **Single unified table for all types**: Rejected — different node types have different attributes, so grouping with separate tables per type (like NetBox) is the right UX.

**Reusable utilities**:
- `getObjectTableColumns()` from `entities/nodes/object/ui/object-table/utils/` — generates columns from schema
- `getObjectDetailsUrl()` — constructs detail page URLs
- `useSchema()` hook — fetches schema definition for a given kind

### R5: Backend Pagination Fix (US4) — Unified Query Path

**Decision**: Unify case-sensitive and case-insensitive search paths to use `NodeGetListByAttributeValueQuery` with a `case_insensitive` flag.

**Rationale**: The case-insensitive path (default) previously looped over two kinds (`InfrahubKind.NODE`, `InfrahubKind.GENERICGROUP`), calling `NodeManager.query()` per kind with `db_limit = offset + limit`. This broke pagination: counts were unstable across pages, results shifted/duplicated, and `count` was neither page count nor true total. The case-sensitive path already used `NodeGetListByAttributeValueQuery` with native Cypher SKIP/LIMIT which worked correctly.

**Approach**:
- Added `case_insensitive: bool = False` to `NodeGetListByAttributeValueQuery.__init__`
- When `case_insensitive=True`: uses `toLower(toString(av.value)) CONTAINS toLower(toString($search_value))` for true case-insensitive matching
- When `case_insensitive=False`: keeps existing 4-variation approach (original, lower, upper, title case) for TEXT index usage
- Added `WITH DISTINCT n` after main query body to ensure `get_count_query()` counts distinct nodes
- Removed `DISTINCT` from `return_labels` (now redundant)
- Both paths use the same single Cypher query with native SKIP/LIMIT

**Alternatives considered**:
- **Keep separate paths, fix each independently**: Rejected — duplicated logic, harder to maintain, same bug could reoccur.
- **Use NodeManager.query() for both**: Rejected — NodeManager doesn't support cross-kind queries efficiently, and it introduces the per-kind loop problem.

**Status**: Implemented and tested (42 tests passing).

### R6: Client-Side Grouping by Node Type

**Decision**: Group search results by `kind` field on the client side for the full results page.

**Rationale**: The backend returns a flat list of `{id, kind}` pairs. Adding server-side grouping would require significant backend changes (multiple queries per kind, or aggregation). Since the full results page fetches paginated results and each result already includes `kind`, client-side grouping via a simple `reduce()` is efficient and avoids backend complexity.

**Approach for full page**: The full results page will:
1. Fetch search results with a higher limit (e.g., 100 per page)
2. Group results by `kind` on the client
3. Sort groups by count descending
4. Render a `DataTable` per group
5. Per-group pagination handled client-side within each table

**Note**: This means the initial page load fetches a batch of all-type results. If a specific type has many results, the user may need to load more. This is acceptable for MVP — a future enhancement could add per-type backend queries.

### R7: Permission-Aware Search Filtering (US5) — Architecture

**Decision**: Use a hybrid pre-query/post-query approach — compute allowed schema kinds from PermissionManager before the query, pass as Cypher-level filter (`n.kind IN $allowed_kinds`). Skip the filter entirely for super admin users (fast-path).

**Rationale**: Post-query filtering would break pagination correctness: if Cypher returns L results via SKIP/LIMIT and some are filtered out by permissions, the page shows fewer than L results, and `query.count()` returns the unfiltered total. Pre-query filtering keeps SKIP/LIMIT and count inherently correct.

**Permission infrastructure available**:
- `graphql_context.active_permissions` — PermissionManager instance
- `permission_manager.is_super_admin()` — fast-path detection (returns bool)
- `extract_camelcase_words(kind)` — splits "InfraDevice" into ["Infra", "Device"] for namespace/name
- `ObjectPermission(namespace, name, action="view", decision=PermissionDecision.ALLOW_ALL.value)` — permission object
- `permission_manager.resolve_object_permission(permission_to_check)` — check single kind (returns bool)
- `report_schema_permissions(branch, permission_manager, schemas)` — batch check all schemas

**Approach**:
1. Check `permission_manager.is_super_admin()` — if true, skip kind filter entirely (existing behavior)
2. Otherwise, enumerate all schemas via `registry.get_full_schema(branch=branch)`
3. For each schema kind, check if user has "view" permission using `resolve_object_permission()`
4. Collect allowed kinds into a list
5. Pass `allowed_kinds` to `NodeGetListByAttributeValueQuery` as an additional Cypher filter: `AND n.kind IN $allowed_kinds`
6. If `allowed_kinds` is empty, short-circuit and return 0 results

**Key imports**:
```python
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import PermissionDecision
from infrahub.utils import extract_camelcase_words
```

**Alternatives considered**:
- **Post-query Python filtering**: Rejected — breaks pagination (fewer results per page, count mismatch).
- **Per-kind separate queries**: Rejected — N+1 pattern, complex result merging.
- **New permission-aware query class**: Rejected — `NodeGetListByAttributeValueQuery` already supports `kinds` and can be extended with `allowed_kinds`. No new abstraction needed (Principle VII).

**Performance considerations**:
- Super admin fast-path: zero overhead (no schema enumeration, no permission checks, no Cypher clause)
- Restricted users: one-time per-request permission resolution (already computed and cached in `PermissionManager`)
- Schema enumeration: `registry.get_full_schema()` is cached; cost is iterating the list and checking permissions
- Cypher `n.kind IN $allowed_kinds`: adds a simple list membership check to the existing query, minimal DB impact
