# Implementation Plan: Enhanced Search Results

**Branch**: `2026-02-enhanced-search-results` | **Date**: 2026-02-19 | **Updated**: 2026-02-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/2026-02-enhanced-search-results/spec.md`

## Summary

Enhance the Infrahub "search anywhere" UI to show up to 50 scrollable results in the dropdown (currently capped at 4), display total match count with a "View all X results" link, and provide a new dedicated full search results page that groups results by node type in sortable tables. Fix broken backend pagination for case-insensitive search by unifying both code paths into a single Cypher query with native SKIP/LIMIT. Add permission-aware filtering so search results respect model-level read permissions.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI, GraphQL (graphene), React 19.2, TanStack Table, TanStack React Query, cmdk, React Router, React Aria, nuqs
**Storage**: Neo4j 5.28 (graph database, existing search queries via Cypher)
**Testing**: pytest (backend unit/component), Vitest (frontend unit), Playwright (E2E)
**Target Platform**: Web application (browser)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Dropdown results within 1s of typing; full results page loads within 2s for up to 500 results; zero overhead for admin/unrestricted users after permission filtering is added
**Constraints**: Dropdown eagerly fetches up to 50 results; full page uses pagination (20 per group); must respect branch and time-machine context; permission filtering must be pre-query (Cypher-level) to maintain pagination correctness
**Scale/Scope**: Touches ~18-22 files across backend GraphQL/query layer and frontend search entity

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | No schema changes needed; search reads existing node data |
| II. Branch-Safe by Default | PASS | Existing search already includes branch/temporal filters; new pagination parameters don't affect branch safety |
| III. Type Safety & Explicit Contracts | PASS | Backend: typed resolver params and return types. Frontend: TypeScript strict, generated GraphQL types. New `case_insensitive` and `allowed_kinds` params are typed |
| IV. Test Discipline | PASS | Plan includes: backend component tests for pagination + permissions, frontend Vitest for new components, Playwright E2E for full flow |
| V. Query Performance & Efficiency | PASS | Unified Cypher query with native SKIP/LIMIT. No N+1 patterns. Admin fast-path skips permission filter entirely. `allowed_kinds` is a simple list membership check in Cypher |
| VI. Security & Input Boundaries | PASS | Search input already sanitized; offset/limit are integers validated by GraphQL type system. Permission filtering enforced pre-query at database level — no information leakage |
| VII. Simplicity & Maintainability | PASS | Reuses existing DataTable, ObjectTable patterns, and search query infrastructure. Permission filtering uses existing PermissionManager — no new abstractions. `NodeGetListByAttributeValueQuery` extended with minimal parameters |

**Gate result: PASS** — no violations detected.

### Post-Design Re-check

| Principle | Status | Notes |
|-----------|--------|-------|
| III. Type Safety | PASS | New GraphQL `offset` param is typed Int. Frontend uses generated types. `case_insensitive` is bool, `allowed_kinds` is `list[str] | None`. New `NodeGetListByAttributeValueQueryResult` is a frozen dataclass |
| V. Query Performance | PASS | Single Cypher query for both case paths. `WITH DISTINCT n` ensures count is correct without redundant DISTINCT in RETURN. `query.count()` runs a separate COUNT query without SKIP/LIMIT. Admin users: zero additional overhead. Restricted users: one-time permission resolution per request (PermissionManager already cached) |
| VI. Security | PASS | Permission-aware filtering applied as pre-query Cypher filter (`n.kind IN $allowed_kinds`). Super admin fast-path via `is_super_admin()`. Empty `allowed_kinds` returns zero results. No post-query information leakage possible |
| VII. Simplicity | PASS | Full results page reuses existing ObjectTable pattern. Permission filtering adds ~20 lines to search resolver — no new classes or abstractions. `NodeGetListByAttributeValueQuery` gains one optional parameter |

## Project Structure

### Documentation (this feature)

```text
specs/2026-02-enhanced-search-results/
├── plan.md              # This file
├── research.md          # Phase 0 output (updated 2026-02-23)
├── data-model.md        # Phase 1 output (updated 2026-02-23)
├── quickstart.md        # Phase 1 output (updated 2026-02-23)
├── contracts/           # Phase 1 output (updated 2026-02-23)
│   └── search-api.graphql
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/core/query/
│   └── node.py                                # MODIFIED: case_insensitive flag, WITH DISTINCT n
│                                              # TODO: add allowed_kinds parameter
├── infrahub/graphql/queries/
│   └── search.py                              # MODIFIED: unified query path, query.count()
│                                              # TODO: add permission resolution
└── tests/component/graphql/queries/
    └── test_search.py                         # MODIFIED: pagination + count tests
                                               # TODO: add permission filtering tests

frontend/app/src/
├── entities/navigation/
│   ├── api/
│   │   └── search.ts                     # MODIFY: increase limit to 50, add offset param
│   ├── domain/
│   │   ├── search-anywhere.query.ts       # MODIFY: update hook for new params
│   │   └── search-anywhere.query-keys.ts  # MODIFY: add offset to cache keys
│   └── ui/search-anywhere/
│       ├── search-anywhere-dialog.tsx      # MODIFY: add scrollable container + footer
│       ├── search-nodes.tsx               # MODIFY: render up to 50 results in scrollable list
│       └── search-anywhere-footer.tsx     # NEW: "View all X results" link component
├── entities/search-results/               # NEW: full results page entity
│   ├── api/
│   │   └── search-results.ts             # NEW: GraphQL query with offset/pagination
│   ├── domain/
│   │   ├── search-results.query.ts        # NEW: React Query hook for paginated search
│   │   └── search-results.query-keys.ts   # NEW: cache key management
│   ├── ui/
│   │   ├── search-results-page.tsx        # NEW: main page component
│   │   ├── search-results-header.tsx      # NEW: editable search bar + total count
│   │   ├── search-results-group.tsx       # NEW: node type group with table
│   │   └── search-results-table.tsx       # NEW: sortable table per node type
│   └── types.ts                           # NEW: type definitions
├── pages/search-results/
│   └── index.tsx                          # NEW: route page component (lazy loaded)
└── app/
    └── router.tsx                         # MODIFY: add /search route
```

**Structure Decision**: Web application structure following Infrahub's existing Feature-Sliced Design pattern. New `entities/search-results/` entity for the full results page, modifications to existing `entities/navigation/` for dropdown enhancements.

## Implementation Status

### Completed (US4 — Backend Pagination Fix)

- ✅ `NodeGetListByAttributeValueQuery`: `case_insensitive` flag, `WITH DISTINCT n`, updated return_labels
- ✅ `search_resolver`: unified both paths, `query.count()` for true total, native offset/limit
- ✅ Tests: 42 passing (pagination consistency, true total count, case-insensitive parity)

### Completed (US1 — Scrollable Dropdown)

- ✅ Frontend dropdown limit increased to 10, scrollable container, keyboard nav preserved

### Completed (US2 — Total Count & "View All" Link)

- ✅ SearchAnywhereFooter component, "View all X results" link, dialog close on nav

### Completed (US3 — Full Results Page)

- ✅ `/search` route, page component, grouped tables, sortable columns, URL sync, pagination

### Remaining (US5 — Permission-Aware Filtering)

- 🔲 `NodeGetListByAttributeValueQuery`: add `allowed_kinds: list[str] | None = None` parameter
- 🔲 `search_resolver`: compute allowed kinds from PermissionManager, admin fast-path
- 🔲 Tests: permission-filtered search results, admin fast-path, empty permissions

## Permission Filtering Design (US5)

### Algorithm

```
1. IF permission_manager.is_super_admin():
     → skip kind filter (no Cypher clause, zero overhead)
2. ELSE:
     a. all_schemas = registry.get_full_schema(branch=branch)
     b. For each schema kind:
        - Extract namespace/name via extract_camelcase_words()
        - Check resolve_object_permission(ObjectPermission(namespace, name, "view", ALLOW_ALL))
        - If allowed: add to allowed_kinds list
     c. IF allowed_kinds is empty:
        → return empty results (count=0, edges=[])
     d. ELSE:
        → pass allowed_kinds to query as Cypher filter: AND n.kind IN $allowed_kinds
```

### Query Changes

In `NodeGetListByAttributeValueQuery.query_init()`:

```cypher
-- Existing kind filter (by Neo4j labels: Node, GenericGroup):
AND any(l IN labels(n) WHERE l in $kinds)

-- New permission filter (by specific schema kinds: InfraDevice, CoreIPAddress, etc.):
AND n.kind IN $allowed_kinds
```

Both filters are independent and both applied when present:
- `kinds` filters by Neo4j node labels (broad categories)
- `allowed_kinds` filters by specific schema kind (permission-level granularity)

### Key Imports

```python
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import PermissionDecision
from infrahub.utils import extract_camelcase_words
```

## Complexity Tracking

> No constitution violations to justify.
>
> Complexity note: The permission filtering adds ~20 lines to `search_resolver` and ~5 lines to `NodeGetListByAttributeValueQuery`. No new classes, no new abstractions, no new dependencies. This is within the simplicity bounds of Principle VII.
