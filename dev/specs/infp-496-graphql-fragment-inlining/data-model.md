# Data Model: GraphQL Fragment Inlining

**Feature**: `infp-496-graphql-fragment-inlining`
**Date**: 2026-03-18

---

## Summary

No new database entities or schema migrations are introduced. This feature operates entirely at
import time: the rendered query string is stored in the existing `CoreGraphQLQuery.query` field.

---

## Existing Entity: CoreGraphQLQuery (unchanged)

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique name of the query within the repository |
| `query` | `str` | **After this feature**: stores the fully-rendered, self-contained GraphQL document (operation + inlined fragment definitions). Before this feature, stored only the operation. |
| `description` | `str \| None` | Optional description |

The stored `query` string remains a valid GraphQL document in both cases (with and without
fragments). No migration is needed because the column type and semantics are unchanged — only the
content grows when fragment spreads are resolved.

---

## New SDK Config Entities (Pydantic models, no DB persistence)

### `InfrahubRepositoryFragmentConfig`

**Location**: `python_sdk/infrahub_sdk/schema/repository.py`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `name` | `str` | required | Logical name for this fragment source entry |
| `file_path` | `Path` | required | Path to a `.gql` file or directory, relative to repo root |

**Validation rules**:
- `file_path` is not validated to exist at parse time; existence is checked at import time via
  `load_fragments()` which raises `FragmentFileNotFoundError` if the path is absent.

**Methods**:
- `load_fragments(relative_path: str = ".") -> list[str]` — reads and returns raw content of all
  `.gql` files at `file_path`. Returns a list with one element for a file, or one element per
  `.gql` file for a directory (sorted alphabetically). Raises `FragmentFileNotFoundError` if
  `file_path` does not exist.

### `InfrahubRepositoryConfig` (modified)

Adds one new field:

| Field | Type | Default | Description |
|---|---|---|---|
| `graphql_fragments` | `list[InfrahubRepositoryFragmentConfig]` | `[]` | Declared fragment sources for this repository |

---

## Fragment Resolution (In-Memory, No Persistence)

Fragment definitions are parsed from declared files at import time, held in memory during the
import of a single repository commit, and discarded after all queries are rendered. They are never
written to the database.

The in-memory structure during resolution:

```python
fragment_index: dict[str, FragmentDefinitionNode]
# key: fragment name (e.g., "interfaceFragment")
# value: graphql-core AST node
```

---

## State Transitions

```text
Repository sync triggered
  │
  ├─ Load graphql_fragments from .infrahub.yml
  │    └─ Call load_fragments() per entry → list[str] (raw content)
  │
  ├─ Build fragment_index from all content strings
  │    ├─ DuplicateFragmentError → abort fragment loading for this sync
  │    └─ Success → fragment_index: dict[str, FragmentDefinitionNode]
  │
  └─ For each query in graphql_queries:
       ├─ render_query_with_fragments(query_str, fragment_files)
       │    ├─ No spreads → return query_str unchanged
       │    ├─ FragmentNotFoundError → log error, skip this query (FR-009)
       │    ├─ CircularFragmentError → log error, skip this query (FR-009)
       │    └─ Success → rendered_query: str
       │
       └─ Store rendered_query in CoreGraphQLQuery.query (create/update/delete as before)
```

---

## Constraints

- Fragment files are **not** stored in the database (spec requirement).
- No new database node types or relationship types.
- No schema migration or `backend.generate` invocation needed.
- `CoreGraphQLQuery` uniqueness key (`name` per branch) is unchanged.
