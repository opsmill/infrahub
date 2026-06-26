# Cypher PROFILE anti-patterns

Reference checklist for reading the `PROFILE` plain-text output of a slow Cypher query against the Infrahub graph. Walk top-down through the plan, focus on the first operator with bad numbers — that is usually the planner's choice of entry point and where the biggest win is.

## What to look at, in order

1. **Total `db hits`** — order of magnitude only. 10s of millions for a query that returns a handful of rows = something wrong.
2. **Top-level operator (the entry point)** — the first thing the planner does. A bad choice here cascades into the rest.
3. **`db hits` ÷ `rows` per operator** — selectivity. A scan over 1M nodes returning 1M rows is fine; a scan over 1M returning 5 is a missed index.
4. **`Estimated rows` vs actual `rows`** — large estimation errors (off by 10×+) signal stale statistics or a query shape the planner can't reason about; rewrite or add hints.
5. **`page hits`** — high `page faults` mean cold cache; re-run before drawing conclusions.

## Anti-patterns

### 1. `AllNodesScan` near the top

```
+----------+----------------+------+---------+
| Operator | Details        | Rows | DB hits |
+----------+----------------+------+---------+
| AllNodes…|                |  9M  |  9M+1   |
```

The planner couldn't find a label or index to start from. Fix: add a label on the start vertex, or filter by an indexed property in the same `MATCH`.

### 2. `NodeByLabelScan` + downstream `Filter`

```
| NodeByLabelScan | Node     |  9M  |
| Filter          | n.uuid = …|  1  |
```

Label scan then post-filter on a property. Add a property index for that label (`backend/infrahub/core/graph/index.py`) so the planner uses `NodeIndexSeek` instead.

### 3. Function call defeating an indexed property

```
WHERE toString(n.uuid) = $id   -- ❌
WHERE n.uuid = $id             -- ✅
```

`toString`, `toInteger`, `toLower`, `apoc.text.…`, or any function wrapping an indexed property will fall back to a scan. This is the exact bug PR #9225 hit on `node_get_kind_query`. Strip the conversion; convert the param in Python before passing.

### 4. `Expand(All)` with high `db hits`

```
| Expand(All) | (n)-[:IS_RELATED]->(m) |  120k rows  |  4.5M db hits |
```

The expansion is reading many relationship properties to filter. If you're filtering `IS_RELATED` (or `IS_PART_OF`, `HAS_SOURCE`, `HAS_OWNER`, `IS_PROTECTED`) by `branch` / `from` / `status`, add a **relationship-property index** in `index.py`. PR #9225 added these specifically for the diff queries.

### 5. `$param IS NULL`-guarded `UNION`

```cypher
CALL {
  ...
  WHERE $node_ids IS NOT NULL AND n.uuid IN $node_ids
  ...
  UNION
  ...
  WHERE $node_ids IS NULL
  ...
}
```

The planner does **not** prune the dead `UNION` branch at runtime based on a `$param IS NULL` guard — it still plans and executes both, and the unguarded branch typically triggers a wide scan (catastrophic when the missing param means "all branches" or "all nodes"). Fix: build two queries in Python and pick which to run based on whether the list is set. PR #9225 fixes diff queries this way.

### 6. `CartesianProduct`

```
| CartesianProduct | (a) × (b) |  10M  |
```

Two `MATCH` patterns with no connecting relationship — the planner takes their cross product. Add a path between them or `WITH …` + reorder to gate the second match on the first.

### 7. `Eager` operator

```
| Eager | … | 9M |
```

An "Eager" forces the previous pipeline to fully materialise before the next can start — a sync point. Causes by:

- writes that depend on reads of the same labels/properties,
- aggregation that the planner thinks must be globally consistent,
- `DETACH DELETE` after a match it wrote into.

Move the read above the write, split into multiple statements, or push the filter earlier so less work is materialised.

### 8. `runtime=parallel` masking the plan

The OTel-traced Cypher may have a `CYPHER runtime=parallel\n` prefix when running on Neo4j Enterprise. Parallel runtime can hide serial inefficiencies and the plan text is harder to read (per-pipeline rows multiply across workers). Always strip it for the first analysis (`profile_slow_query.py profile … --no-parallel`). Re-introduce parallel only after the single-thread plan is clean.

### 9. `OrderedDistinct` or `Sort` over a huge intermediate

```
| Sort | n.name |  9M  |  9M |
```

Sorting/deduplicating before filtering. Push the `WHERE` above the `WITH … ORDER BY` so the sort runs on the small set.

### 10. Skewed `IN` list parameters

```
WHERE n.uuid IN $ids
```

with `$ids` containing 50k entries → may switch from index lookup to a hash join over a giant temp. If the list is large, consider batching in Python (UNWIND a few hundred at a time).

### 11. Planner picks the wrong start node

When two indexed nodes could serve as entry point and the planner picks the one with lower selectivity:

```cypher
MATCH (a:Foo {uuid: $a_uuid})-[…]-(b:Bar {uuid: $b_uuid})
```

Force the right side with a hint:

```cypher
USING INDEX b:Bar(uuid)
```

Only use hints when PROFILE proves the planner is wrong — hints calcify the plan and can rot when data shape changes.

## Operators that are usually fine

- `NodeIndexSeek`, `NodeUniqueIndexSeek`, `NodeByIdSeek` — the planner found an index. Good.
- `Expand(Into)` — both endpoints already pinned. Cheap.
- `Apply` / `Optional` with small inputs.
- `Distinct` with small input cardinality.

## When to add an index vs restructure the query

- **Add an index** when the same operator appears across multiple slow queries and the property/relationship has a clear access pattern (`branch`, `from`, `uuid`, `name`). Put it in `backend/infrahub/core/graph/index.py` so migrations carry it.
- **Restructure the query** when the planner has the right indexes but is still picking a bad entry point (often because of an `IS NULL` guard, function on indexed prop, or unnecessary `UNION`).

When in doubt: add the index, re-PROFILE, see if the planner uses it. If it does and the plan is clean, ship. If it doesn't, the issue is structural.

## Sanity check after a fix

- Re-run `profile_slow_query.py profile <span_id> --no-parallel` against the same scenario.
- Compare total `db hits` and the operator at the top of the plan.
- Run twice and ignore the first run's elapsed time (page-cache cold).
- If the user-visible API call doesn't get faster despite the plan being clean, the bottleneck is elsewhere (Python serialization, GraphQL resolver, multiple round-trips).
