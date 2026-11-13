# Database Indexes

> Part of: `dev/knowledge/backend/` | Related: [Query Pattern](query-pattern.md), [Database Schema](database-schema.md), [Creating Migrations](../../guides/backend/creating-migrations.md)

When a query selects vertices or edges by a property, check that an index on that property exists for every label or edge type the query reads, and add the missing ones in the same change. A value, a name, and a range such as a time window on `from` or `to` are all selections by a property. Without the index the query reads every vertex of the label or every edge of the type, so its cost grows with the graph and not with what it returns.

## Check which indexes exist

`node_indexes` and `rel_indexes` in `backend/infrahub/core/graph/index.py` hold every index Infrahub declares. The API server creates the indexes of both lists when it starts, and does not wait for them to be online.

An index belongs to one label or one edge type. An index on `HAS_ATTRIBUTE(from)` does not serve a read of `IS_RELATED` edges, so a query that reads several edge types needs the index on each of them.

## Add a missing index

1. Declare the index in `node_indexes` or `rel_indexes`.
2. Add a graph migration that creates the same index and waits until it is online, so that an upgraded database does not answer queries while the index builds. See [Creating Migrations](../../guides/backend/creating-migrations.md).
3. Ask the maintainers before you add it: new database indexes are listed under "Ask First" in `backend/AGENTS.md`. Every write to that label or edge type updates the index, so an index is worth its cost only for a read that runs often.

## Write the query so that it uses the index

```cypher
// ❌ No edge type: no relationship index can serve the pattern, so every edge is read
MATCH ()-[r]->()
WHERE r.from >= $from_time AND r.from < $to_time
RETURN count(*) AS num_edges

// ✅ One read per edge type and property, each with a seek hint
CALL () {
    MATCH ()-[r:HAS_ATTRIBUTE]->()
    USING INDEX SEEK r:HAS_ATTRIBUTE(from)
    WHERE r.from >= $from_time AND r.from < $to_time
    RETURN count(*) AS num_edges
    UNION ALL
    MATCH ()-[r:HAS_ATTRIBUTE]->()
    USING INDEX SEEK r:HAS_ATTRIBUTE(to)
    WHERE r.to >= $from_time AND r.to < $to_time
    AND NOT coalesce(r.from >= $from_time AND r.from < $to_time, false)
    RETURN count(*) AS num_edges
}
RETURN sum(num_edges) AS num_edges
```

- Name the label or the edge type in the pattern. A pattern that names none cannot use any index.
- Write one `MATCH` per edge type and per property, joined with `UNION ALL`, and put `USING INDEX SEEK` on each. One `MATCH` over several types, or two properties joined with `OR`, leaves the choice to the planner: a seek is not guaranteed, and with `OR` a seek can be bounded on one side of the range only.
- Hint the index of the predicate that keeps the fewest rows. An index on `branch` keeps nearly every edge when the branch is the default branch.
- Aggregate, or return `DISTINCT` rows, inside each read, and combine the results after the `UNION ALL`. Each read then returns a few rows instead of one row per edge.
- When one edge can match two reads, exclude it from one of them. In the example, the read on `to` leaves out an edge that was opened and closed inside the window, because the read on `from` already counts it.

`DiffCountChanges` and `DiffFieldNodesQuery` (`backend/infrahub/core/query/diff.py`) are the queries to read alongside a new instance. [Query Pattern — Query performance](query-pattern.md#query-performance) holds the rules for the indexes on node `uuid`, node `kind` and attribute values.

## Check that the index is used

- Run the query with `EXPLAIN` or `PROFILE` on a graph much larger than what the query returns. Each read shows an index seek, and none starts from `AllNodesScan` or from a scan of a whole label or relationship type.
- Check that the required indexes exist and are online, then inspect the execution plan. A passing result test does not prove that an index was used: Neo4j can ignore an unfulfillable index hint and emit a warning, or fail the query when `dbms.cypher.hints_error` is enabled.
- A range that covers most of the graph costs more through the index than one scan of the edges. Use this shape for reads whose range is small against the graph.

## See Also

- [Query Pattern](query-pattern.md) - Query classes, parameter binding and the other performance rules
- [Database Schema](database-schema.md) - Vertex labels, edge types and their properties
- [Creating Migrations](../../guides/backend/creating-migrations.md) - Migration base classes and `GRAPH_VERSION`
