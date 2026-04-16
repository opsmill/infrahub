# Quickstart: Search Anywhere Display Label Enrichment

## Files to Modify

### Backend (3 files)

1. **`backend/infrahub/graphql/queries/search.py`**
   - Add `display_label` field to `Node` ObjectType
   - Remove Schema/Internal namespace filter in `search_resolver`
   - Compute `display_label` via `node.get_display_label(db)` for UUID matches

2. **`backend/tests/component/graphql/queries/test_search.py`**
   - Update existing test `test_search_anywhere_by_uuid_excludes_internal_nodes` to verify Schema/Internal nodes ARE returned with display_label
   - Add test for display_label field presence in UUID search results

3. **`schema/schema.graphql`** (auto-generated)
   - Regenerate after backend changes: `uv run invoke backend.generate`

### Frontend (3 files)

4. **`frontend/app/src/entities/navigation/api/search.ts`**
   - Add `display_label` to the SEARCH GraphQL query selection set

5. **`frontend/app/src/entities/navigation/domain/search-anywhere.ts`**
   - Add `display_label` to `ObjectResult` type

6. **`frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.tsx`**
   - In `NodesOptions`: when `useSchema(node.kind)` returns null, render a simplified result component instead of returning null
   - Simplified result shows: display_label (or kind as fallback), kind badge, links to `/schema?kind={kind}`

### Frontend Tests (1 file)

7. **`frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx`** (new)
   - Test that Schema/Internal kind results render simplified view
   - Test that regular kind results still render full detail view
   - Test navigation URL construction for Schema/Internal kinds

## Implementation Order

1. Backend: modify search.py (GraphQL type + resolver)
2. Backend: update tests
3. Regenerate schema: `uv run invoke backend.generate`
4. Frontend: update API query + domain type
5. Frontend: update search-nodes component
6. Frontend: add tests
7. Run biome fix + betterer: `cd frontend/app && npm run biome:fix && npx betterer`

## Verification

```bash
# Backend tests
uv run invoke backend.test-unit

# Frontend tests
cd frontend/app && npm run test

# Lint
uv run invoke format && uv run invoke lint
cd frontend/app && npm run biome:fix
```
