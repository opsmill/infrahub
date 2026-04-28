# Creating Graph Migrations

> Part of: `dev/guides/backend/` | Related: [Database Schema](../../knowledge/backend/database-schema.md), [Query Pattern](../../knowledge/backend/query-pattern.md), [Backend Checklist](../../guidelines/backend/checklist.md)

Step-by-step guide for adding a new graph migration that transforms existing Neo4j data during upgrade.

## When to Create a Migration

Create a migration when you need to:

- Modify node/relationship properties or labels
- Add or remove indexes / constraints
- Normalize stored values to a new format
- Backfill data after a schema change
- Clean up orphaned or malformed data

Schema definition changes that can be resolved by normal schema migrations (renames, type changes) do not need a graph migration.

## Migration Types

Choose the right base class in `backend/infrahub/core/migrations/shared.py`:

- **`GraphMigration`** — Runs a fixed list of `Query` classes in sequence. Use when transformations can be expressed purely in Cypher.
- **`ArbitraryMigration`** — Implements a custom `execute()` method. Use when you need Python logic (e.g., JSON parsing, conditional branching, batching decisions driven by fetched data).
- **`InternalSchemaMigration`** — Modifies internal schema definitions. Rarely used directly.

## Steps

### Step 1: Create the Migration File

Place the file at `backend/infrahub/core/migrations/graph/m{NNN}_{descriptive_name}.py` where `{NNN}` is the next sequential number (check existing files for the highest).

The file **must** contain a class named `Migration{NNN}` matching the number — `discovery.py` auto-registers it via naming convention.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult, get_migration_console

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

console = get_migration_console()


class Migration070(ArbitraryMigration):
    """Short description of what this migration does."""

    name: str = "070_index_hfid_values"
    minimum_version: int = 69

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        try:
            # migration logic
            ...
        except Exception as exc:
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
```

Set `minimum_version` to the current `GRAPH_VERSION` (the migration runs when upgrading from that version).

### Step 2: Bump `GRAPH_VERSION`

Update `backend/infrahub/core/graph/__init__.py`:

```python
GRAPH_VERSION = 70  # Match the new migration number
```

### Step 3: Batching Large Datasets

Migrations can touch millions of nodes. Always batch to avoid memory exhaustion and long-held transactions.

**Python-side batching** (when transformations require Python logic):

```python
update_batch_size: int = 1000

async def _transform(self, db: InfrahubDatabase) -> None:
    offset = 0
    while True:
        results = await db.execute_query(
            query=FETCH_QUERY, params={"offset": offset, "limit": self.update_batch_size}
        )
        if not results:
            break

        updates = [build_update(r) for r in results if needs_update(r)]
        if updates:
            await db.execute_query(query=APPLY_QUERY, params={"updates": updates})

        offset += self.update_batch_size
```

**Cypher-side batching** (when the whole transformation is expressible in Cypher):

```cypher
MATCH (n:SomeNode)
WHERE <filter>
CALL (n) {
    SET n.new_prop = value
} IN TRANSACTIONS OF 1000 ROWS
```

`CALL ... IN TRANSACTIONS` requires the `MATCH` to be outside the subquery — move all matching up front.

### Step 4: Beware of Shared Nodes

Some nodes in the graph are de-duplicated via `MERGE` (e.g., `AttributeValue` on `value` + `is_default`). Multiple relationships from different parents can point to the same node. Before modifying a node's properties or labels, verify it isn't shared — or create a new node and transfer the relevant edges. See [Database Schema — AttributeValue](../../knowledge/backend/database-schema.md) for details.

### Step 5: Idempotency

Every migration must be safe to run twice. After a successful run, a second run should be a no-op.

- Check preconditions inside the query (e.g., `WHERE NOT n:AlreadyProcessed`)
- Skip Python transformations when `new_value == raw_value`

### Step 6: Write a Component Test

Create `backend/tests/component/core/migrations/graph/test_{NNN}_{name}.py`.

Prefer inserting test data with `Node.init()` / `Node.new()` / `Node.save()` so the graph state matches what production code produces. Use raw Cypher only when you need to set up intentionally malformed or legacy data that the normal API wouldn't create.

Run the migration, verify the post-state, and include an idempotency check (run the migration twice and verify the result is unchanged).

### Step 7: Verify the Build

Run the graph version test:

```bash
uv run pytest backend/tests/unit/core/graph/test_graph_version.py
```

This verifies `GRAPH_VERSION` matches the last migration number and that `minimum_version` is set correctly.

## See Also

- [Database Schema](../../knowledge/backend/database-schema.md) — Graph structure, edge properties, temporal/branch rules
- [Query Pattern](../../knowledge/backend/query-pattern.md) — Branch-aware edge resolution, Cypher shadowing rules
- [Backend Checklist](../../guidelines/backend/checklist.md) — Pre-merge checks for backend features
