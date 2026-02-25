# Quickstart: Enhanced Search Results

**Feature**: 2026-02-enhanced-search-results
**Date**: 2026-02-19
**Updated**: 2026-02-23

## Prerequisites

- Infrahub dev environment running (backend + frontend)
- Neo4j database with test data (multiple node types with searchable attributes)

## Development Setup

```bash
# Backend
cd /path/to/infrahub
uv sync --all-groups

# Frontend
cd frontend/app
npm install
```

## Key Files to Modify

### Backend — Pagination Fix & Permissions (US4, US5)

1. **`backend/infrahub/core/query/node.py`** — `NodeGetListByAttributeValueQuery`
   - Add `case_insensitive: bool = False` parameter
   - Add `allowed_kinds: list[str] | None = None` parameter for permission filtering
   - When `case_insensitive=True`: use `toLower(toString(...))` matching
   - When `allowed_kinds` provided: add `AND n.kind IN $allowed_kinds` Cypher filter
   - Add `WITH DISTINCT n` for correct count queries
   - **Status**: `case_insensitive` implemented; `allowed_kinds` pending

2. **`backend/infrahub/graphql/queries/search.py`** — `search_resolver`
   - Unified both paths to use `NodeGetListByAttributeValueQuery`
   - Uses `query.count()` for true total count
   - Add permission resolution: compute allowed kinds from PermissionManager
   - Skip kind filter for super admin (fast-path)
   - **Status**: Unified query done; permission filtering pending

3. **`backend/tests/component/graphql/queries/test_search.py`**
   - Tests for offset, pagination consistency, true total count
   - Add tests for permission-filtered search results
   - **Status**: Pagination tests done; permission tests pending

### Frontend — Dropdown Enhancement (US1, US2)

4. **`frontend/app/src/entities/navigation/api/search.ts`**
   - Change limit from 4 to 10

5. **`frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-dialog.tsx`**
   - Add max-height + overflow-y-auto to Command.List
   - Add footer section below results

6. **`frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-footer.tsx`** (NEW)
   - "View all X results" link component
   - Links to `/search?q=<query>`

### Frontend — Full Results Page (US3)

7. **`frontend/app/src/app/router.tsx`**
   - Add route: `{ path: "/search", lazy: () => import("@/pages/search-results") }`

8. **`frontend/app/src/pages/search-results/index.tsx`** (NEW)
   - Page component exported as `Component`

9. **`frontend/app/src/entities/search-results/`** (NEW entity)
   - `api/search-results.ts` — GraphQL query with offset
   - `domain/search-results.query.ts` — React Query hook
   - `domain/search-results.query-keys.ts` — Cache keys
   - `ui/search-results-page.tsx` — Main page layout
   - `ui/search-results-header.tsx` — Search bar + total count
   - `ui/search-results-group.tsx` — Node type group wrapper
   - `ui/search-results-table.tsx` — Sortable DataTable per type
   - `types.ts` — TypeScript types

## Running Tests

```bash
# Backend search tests (component level)
uv run pytest backend/tests/component/graphql/queries/test_search.py -v

# Backend unit tests
uv run invoke backend.test-unit

# Backend lint
uv run invoke lint

# Frontend unit tests
cd frontend/app && npm run test

# Frontend E2E tests
cd frontend/app && npm run test:e2e
```

## Verification Checklist

### Backend Pagination (US4) ✅
1. Run search component tests — all 42 tests pass
2. Verify `query.count()` returns true total regardless of offset/limit
3. Verify page 1 + page 2 results have no duplicates and cover all matches
4. Verify case-insensitive search returns same pagination behavior as case-sensitive

### Permission Filtering (US5) 🔲
5. Create a user with restricted model-level read permissions
6. Search as restricted user — verify only permitted node types appear
7. Verify count reflects only permitted results
8. Search as admin — verify zero overhead (same results as before)

### Frontend Dropdown (US1, US2)
9. Type a search query in the search anywhere dialog (Cmd+K) — see up to 10 scrollable results
10. Verify the footer shows "View all X results" with correct total count
11. Click "View all {N} result(s)" — navigate to `/search?q=<query>`

### Full Results Page (US3)
12. Verify results are grouped by node type, sorted by count descending
13. Verify each group has a sortable table with node name, description, and link
14. Modify the search query on the results page — results update, URL changes
15. Share/bookmark the URL — reloading preserves the search
16. Navigate back — return to previous page
