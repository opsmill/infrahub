# Data Model: Optimize Automated Task Query Performance

**Feature**: infp-501-optimize-prefect-queries
**Date**: 2026-04-29

## Overview

This feature introduces no new persistent database entities. It replaces verbose SDK read calls inside Prefect tasks with targeted query models that fetch only the fields each task actually needs.

The key structural addition is a per-domain **query model** following the existing `HFIDGraphQL` pattern in `backend/infrahub/hfid/models.py`.

---

## Query Model Pattern

Each domain that requires optimized reads gets a typed query model. The model is a Pydantic class or frozen dataclass with:

```
QueryModel
├── render_query() -> str             # Returns a GraphQL query string fetching only required fields
└── parse_response(dict) -> list[T]   # Returns typed results from the raw execute_graphql() response
```

### Type `T` (per domain)

A frozen dataclass representing the minimal node data the task actually uses. At minimum:

```python
@dataclass(frozen=True)
class NodeID:
    id: str
```

For tasks that need additional fields (e.g., `display_label`, `hfid`), the dataclass grows accordingly but MUST NOT include fields the task does not use.

---

## Per-Domain Query Models

### display_labels domain

**File**: `backend/infrahub/display_labels/models.py`
**New model**: `DisplayLabelNodeQuery`

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `str` | The node kind to query |
| `branch` | `str` | Branch name for the query |

**Fetches**: `id` only (current `client.all()` with `exclude=` still returns HFID — this replaces it)
**Returns**: `list[NodeID]`

---

### hfid domain

**File**: `backend/infrahub/hfid/models.py`
**Existing model**: `HFIDGraphQL` (already uses custom query pattern — read queries to be aligned)

The existing `HFIDGraphQL` already builds custom queries for its lookup needs. Audit to confirm whether any remaining `client.all()` or `client.filters()` calls can be folded into this model.

---

### computed_attribute domain

**File**: `backend/infrahub/computed_attribute/tasks.py` (query model may go in a new `queries.py`)
**New model**: `ComputedAttributeNodeQuery`

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `str` | The computed attribute kind |
| `branch` | `str` | Branch name |

**Fetches**: `id` only
**Returns**: `list[NodeID]`

---

## No Schema Changes

- No new Neo4j nodes, relationships, or constraints.
- No changes to `backend/infrahub/core/schema/` or generated files.
- No GraphQL or REST API contract changes — this is an internal query layer change only.

---

## Relationships Between Concepts

```
Prefect Task
    │
    │ calls
    ▼
QueryModel.render_query()        ─── produces ───▶  GraphQL query string
    │
    │ passes to
    ▼
client.execute_graphql(query, branch_name=branch)
    │
    │ returns raw dict
    ▼
QueryModel.parse_response()      ─── returns ────▶  list[FrozenDataclass]
    │
    │ uses
    ▼
Task business logic (unchanged output)
```

---

## State Transitions

No state machine changes. Task inputs, outputs, and side effects are unchanged — only the internal data-fetching mechanism is replaced.
