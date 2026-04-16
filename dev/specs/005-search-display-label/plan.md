# Implementation Plan: Search Anywhere Display Label Enrichment

**Branch**: `005-search-display-label` | **Date**: 2026-04-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-search-display-label/spec.md`

## Summary

Enrich the InfrahubSearchAnywhere GraphQL API with a `display_label` field so that Schema and Internal namespace nodes can be searched by UUID and rendered in the frontend with human-readable labels. The frontend renders a simplified result for unknown schema kinds and links to the schema page.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: Graphene (GraphQL), React 19, gql.tada, TanStack Query
**Storage**: Neo4j (no changes needed)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Web application
**Project Type**: Web (backend + frontend)
**Performance Goals**: No additional network requests for Schema/Internal node results
**Constraints**: Backward-compatible GraphQL schema change (additive nullable field)
**Scale/Scope**: 3 backend files, 4 frontend files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is uninitialized (template only). No project-specific gates to evaluate. Proceeding.

## Project Structure

### Documentation (this feature)

```text
specs/005-search-display-label/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: technical research
├── data-model.md        # Phase 1: entity changes
├── quickstart.md        # Phase 1: implementation guide
├── contracts/
│   └── search-graphql.md  # Phase 1: GraphQL API contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
backend/
├── infrahub/graphql/queries/search.py          # GraphQL type + resolver changes
└── tests/component/graphql/queries/test_search.py  # Backend test updates

frontend/app/src/
├── entities/navigation/api/search.ts           # GraphQL query update
├── entities/navigation/domain/search-anywhere.ts  # Domain type update
└── entities/navigation/ui/search-anywhere/
    ├── search-nodes.tsx                        # Component rendering changes
    └── search-nodes.test.tsx                   # New test file

schema/schema.graphql                           # Auto-regenerated
```

**Structure Decision**: Modifications to existing files in the established backend/frontend structure. One new test file for frontend component coverage.

## Implementation Steps

### Step 1: Backend — Add display_label to GraphQL type and resolver

**File**: `backend/infrahub/graphql/queries/search.py`

Changes:
- Add `display_label = Field(String, required=False)` to the `Node` ObjectType (line 23)
- Remove the `namespace not in ("Schema", "Internal")` filter (line 119)
- After `NodeManager.get_one()`, compute `display_label` via `await matching.get_display_label(db=graphql_context.db)`
- Include `display_label` in the result dict for UUID matches

**Spec coverage**: FR-001, FR-002, FR-003, FR-004

### Step 2: Backend — Update tests

**File**: `backend/tests/component/graphql/queries/test_search.py`

Changes:
- Rename `test_search_anywhere_by_uuid_excludes_internal_nodes` to `test_search_anywhere_by_uuid_includes_schema_internal_nodes`
- Update assertions: Schema/Internal UUID search now returns results with display_label
- Add assertions for the `display_label` field value
- Add test that text-based search still excludes Schema/Internal nodes (no regression)
- Update the SEARCH_QUERY constant to include `display_label`

**Spec coverage**: FR-001, FR-002, FR-008

### Step 3: Regenerate GraphQL schema

**Command**: `uv run invoke backend.generate`

This updates `schema/schema.graphql` to include the new `display_label` field in the search node type.

### Step 4: Frontend — Update API query and domain type

**File**: `frontend/app/src/entities/navigation/api/search.ts`
- Add `display_label` to the SEARCH GraphQL query selection set

**File**: `frontend/app/src/entities/navigation/domain/search-anywhere.ts`
- Add `display_label?: string | null` to the `ObjectResult` type
- Map `display_label` through in the `searchAnywhere` function

**Spec coverage**: FR-002, FR-004

### Step 5: Frontend — Simplified rendering for Schema/Internal nodes

**File**: `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.tsx`

Changes to `NodesOptions` component:
- When `useSchema(node.kind)` returns null (Schema/Internal kinds), render a new `SchemaNodeResult` component instead of returning null
- `SchemaNodeResult` displays:
  - Display label from search result (fallback to kind if null)
  - Kind badge (e.g., "SchemaNode")
  - Links to `/schema?kind={kind}`
- Does NOT call `useGetObject` — all data comes from the search result

**Spec coverage**: FR-005, FR-006, FR-007

### Step 6: Frontend — Add component tests

**File**: `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx` (new)

Tests:
- Schema kind result renders simplified view with display_label
- Schema kind result links to `/schema?kind=...`
- Regular kind result still renders via full detail path
- Missing display_label falls back to kind

**Spec coverage**: FR-005, FR-006, FR-007, FR-008

### Step 7: Lint, format, betterer

```bash
uv run invoke format && uv run invoke lint
cd frontend/app && npm run biome:fix && npx betterer
```

Update `.betterer.results` if needed.
