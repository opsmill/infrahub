# Data Model: Enhanced Search Results

**Feature**: 2026-02-enhanced-search-results
**Date**: 2026-02-19
**Updated**: 2026-02-23

## Overview

This feature does not introduce new database entities. It extends the existing search GraphQL API contract, fixes backend pagination, and adds permission-aware filtering plus client-side data structures for the new search results page.

## Existing Entities (No Changes)

### Node (Neo4j)
All searchable nodes in Infrahub. The search indexes across all `Attribute` → `AttributeValue` relationships.

- **id**: UUID (primary key)
- **kind**: String (node type identifier, e.g., "CoreDevice", "InfraInterface")
- **attributes**: Variable per schema definition

### AttributeValueIndexed (Neo4j)
Text-indexed attribute values used by the search query.

- **value**: String (TEXT indexed)

## Extended API Types

### SearchResult (GraphQL response)

**Current fields**:
- `id: String!` — Node UUID
- `kind: String!` — Node type

**No changes** — the existing response shape is sufficient. The `kind` field enables client-side grouping and is the key field for permission filtering.

### SearchResponse (GraphQL response — extended)

**Current fields**:
- `count: Int!` — Total matching results
- `edges: [NodeEdge!]!` — Result list

**Changes**:
- `count` semantics: NOW returns true total count of all matching results **independent of offset/limit** (was: count of results after limit). Uses `query.count()` which runs a separate Cypher COUNT query.
- For permission-restricted users: count reflects only results the user is authorized to see (because permission filtering is applied pre-query in Cypher).
- New `offset` parameter support for native database-level pagination (Cypher SKIP/LIMIT).

## Query Model Changes

### NodeGetListByAttributeValueQuery (extended)

**New parameters**:
- `case_insensitive: bool = False` — When true, uses `toLower(toString(av.value)) CONTAINS toLower(toString($search_value))` for matching. When false, uses 4-variation approach (original, lower, upper, title case) for TEXT index leverage.
- `allowed_kinds: list[str] | None = None` — When provided, adds `AND n.kind IN $allowed_kinds` filter to Cypher query. Used for permission-aware filtering. When None, no kind-specific filter is applied (existing behavior for admins).

**Query behavior**:
- `WITH DISTINCT n` added after main query body — ensures `get_count_query()` counts distinct nodes (not node/attr/rel tuples)
- `return_labels` no longer uses `DISTINCT` (redundant with `WITH DISTINCT n`)
- ORDER BY `n.uuid` for deterministic ordering across pages

## Permission Model (No Schema Changes)

### Permission Resolution for Search

The search resolver uses existing permission infrastructure — no new permission types or schemas are introduced.

**Resolution flow**:
1. Check `permission_manager.is_super_admin()` → if true, skip all filtering (fast-path)
2. Enumerate schemas via `registry.get_full_schema(branch=branch)`
3. For each schema, extract namespace/name from kind using `extract_camelcase_words()`
4. Check `permission_manager.resolve_object_permission()` with action="view"
5. Collect allowed kinds into a list for the Cypher filter

**Key entity**: `ObjectPermission(namespace, name, action="view", decision=PermissionDecision.ALLOW_ALL.value)`

## Client-Side Data Structures

### SearchResultsGroup (frontend only)

Groups search results by node type for the full results page.

- **kind**: String — node type identifier
- **label**: String — human-readable type name (from schema)
- **count**: Number — number of results in this group
- **results**: SearchResult[] — array of results for this type

### SearchResultsPageState (frontend only)

State for the full search results page.

- **query**: String — current search query (from URL param `q`)
- **totalCount**: Number — total results across all types
- **groups**: SearchResultsGroup[] — results grouped by kind, sorted by count descending

## Validation Rules

- `q` (search query): Non-empty string, trimmed of leading/trailing whitespace
- `limit`: Positive integer, default 10 for dropdown, 500 for full page
- `offset`: Non-negative integer, default 0
- `allowed_kinds`: List of valid schema kind strings, or None for unrestricted access
- Client-side grouping: Groups with 0 results are excluded from display

## State Transitions

No state machines or lifecycle transitions — search is a read-only operation. Results are ephemeral and not persisted.
