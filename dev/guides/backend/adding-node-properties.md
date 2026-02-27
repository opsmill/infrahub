# Adding a Property to an Existing Neo4j Node Type

> Part of: `dev/guides/backend/` | Related: [Database Schema](../../knowledge/backend/database-schema.md), [Writing Migrations](writing-migrations.md)

This checklist covers adding a new property to an existing Neo4j node label (e.g., adding `value_lower` to `AttributeValueIndexed`).

## Checklist

### 1. Find ALL Write Paths

The most critical step. Neo4j has no `NOT NULL` constraints — a node created without your property will exist silently with no error.

Search for every code path that creates or modifies the node type:

```bash
# Find all MERGE and CREATE for the node label
rg "MERGE.*YourLabel|CREATE.*YourLabel" backend/infrahub --type py
# Also search for the label in string literals
rg "YourLabel" backend/infrahub/core/query/ backend/infrahub/core/migrations/ --type py
```

Common write paths for `AttributeValueIndexed`:

| Path | File |
|------|------|
| Normal CRUD | `core/attribute.py` → `to_db()` |
| Batch node creation | `core/query/node.py` → `NodeCreateFullBatchQuery` |
| Resource pool allocation | `core/query/resource_manager.py` |
| Graph migrations | `core/migrations/graph/m0*.py` |
| Schema migrations | `core/migrations/schema/*.py` |
| Shared migration queries | `core/migrations/query/*.py` |

### 2. Write a Backfill Migration

Create a graph migration to populate the property on all existing nodes:

```python
# backend/infrahub/core/migrations/graph/m{NNN}_{description}.py
query = """
MATCH (av:AttributeValueIndexed)
WHERE av.value_lower IS NULL
CALL (av) {
    SET av.value_lower = toLower(toString(av.value))
} IN TRANSACTIONS
"""
```

- Use `IN TRANSACTIONS` for large dataset safety
- Use `WHERE ... IS NULL` for idempotency
- Register in `core/migrations/graph/__init__.py`

### 3. Update All Write Paths

Add the new property to every MERGE/CREATE pattern found in step 1. For MERGE patterns, the backfill migration (step 2) must run first to prevent duplicate node creation.

### 4. Add Index (if needed for queries)

If the property will be queried directly, add an index in `core/graph/index.py`:

```python
IndexItem(name="my_index", label="MyLabel", properties=["my_property"], type=IndexType.TEXT)
```

Index types:
- `RANGE` — equality and range comparisons
- `TEXT` — `CONTAINS`, `STARTS WITH`, `ENDS WITH`

### 5. Update Documentation

- Add the property to the node type table in `dev/knowledge/backend/database-schema.md`
- If the node type has a write path registry, update it

### 6. Write Tests

- Unit test: verify `to_db()` includes the new property
- Component test: verify queries that use the property return correct results
- Migration test: verify the backfill works on realistic data

## Common Mistakes

| Mistake | Consequence |
|---------|-------------|
| Only updating `to_db()` | Raw Cypher paths create nodes without the property |
| Adding property to MERGE without backfill | Existing nodes not found → duplicates created |
| Forgetting `IN TRANSACTIONS` in migration | OOM on large production databases |
| Not searching migration code paths | Schema/graph migrations bypass Python abstractions |

## See Also

- [Database Schema — Neo4j Gotchas](../../knowledge/backend/database-schema.md#neo4j-property-constraints-and-gotchas)
- [Writing Migrations](writing-migrations.md)
- [Query Pattern — MERGE vs CREATE](../../knowledge/backend/query-pattern.md#merge-vs-create-semantics)
