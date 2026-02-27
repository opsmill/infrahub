# Writing Graph Migrations

> Part of: `dev/guides/backend/` | Related: [Database Schema](../../knowledge/backend/database-schema.md), [Query Pattern](../../knowledge/backend/query-pattern.md)

Graph migrations modify Neo4j data to match new code expectations. They run during startup via `invoke db.migrate` and are ordered by filename number.

## File Location

```
backend/infrahub/core/migrations/graph/m{NNN}_{description}.py
```

Register in `backend/infrahub/core/migrations/graph/__init__.py`.

## Template

```python
from infrahub.core.migrations.shared import MigrationResult
from infrahub.database import InfrahubDatabase

async def migration(db: InfrahubDatabase) -> MigrationResult:
    query = """
    MATCH (n:SomeLabel)
    WHERE n.new_property IS NULL
    CALL (n) {
        SET n.new_property = <computed_value>
    } IN TRANSACTIONS
    """
    async with db.start_transaction() as dbt:
        await dbt.execute_query(query=query, params={})
    return MigrationResult()
```

## Rules

### Use IN TRANSACTIONS for Bulk Operations

Any migration that touches more than a few hundred nodes must use `IN TRANSACTIONS` to avoid exhausting Neo4j's transaction heap:

```cypher
-- Bad: single transaction for potentially millions of nodes
MATCH (av:AttributeValueIndexed)
SET av.new_prop = toLower(toString(av.value))

-- Good: batched transactions
MATCH (av:AttributeValueIndexed)
WHERE av.new_prop IS NULL
CALL (av) {
    SET av.new_prop = toLower(toString(av.value))
} IN TRANSACTIONS
```

### Guard with WHERE ... IS NULL

Always include a `WHERE property IS NULL` guard so the migration is idempotent and can be safely re-run:

```cypher
MATCH (av:AttributeValueIndexed)
WHERE av.value_lower IS NULL
CALL (av) {
    SET av.value_lower = toLower(toString(av.value))
} IN TRANSACTIONS
```

### Migration Must Run Before New Code Paths

If new code adds a property to a MERGE pattern (e.g., `MERGE (av {value: $v, value_lower: $vl})`), the backfill migration must run **before** any new code executes. Otherwise:

1. MERGE won't find existing nodes (they lack the new property)
2. MERGE creates duplicate nodes
3. Data integrity is silently corrupted

This is enforced by the migration ordering system — migrations run at startup before the app serves requests.

### Test with Realistic Volumes

Migration tests should create enough data to verify batching works. A migration that passes with 10 nodes but OOMs with 1M nodes is not correct.

### Avoid Modifying MERGE Keys

If you need to add a property that will be part of a MERGE pattern elsewhere, ensure the backfill migration runs first and populates the property on ALL existing nodes. See [Neo4j Property Constraints](../../knowledge/backend/database-schema.md#neo4j-property-constraints-and-gotchas).

## Schema Migrations vs Graph Migrations

| Type | Location | Trigger |
|------|----------|---------|
| Graph migrations | `core/migrations/graph/` | Run at startup, sequential by number |
| Schema migrations | `core/migrations/schema/` | Run when schema changes are detected (e.g., attribute kind change) |
| Shared migration queries | `core/migrations/query/` | Reusable query classes used by both graph and schema migrations |

Schema migrations in `core/migrations/schema/` and shared queries in `core/migrations/query/` also write to Neo4j directly with raw Cypher. They bypass `to_db()` and other Python-level abstractions. When adding properties to node types, these paths must be audited too.

## See Also

- [Database Schema](../../knowledge/backend/database-schema.md) - Node types and properties
- [Query Pattern](../../knowledge/backend/query-pattern.md) - MERGE vs CREATE semantics
