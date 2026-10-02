# Advanced Graph Patterns

Load when solving path-finding, fraud detection, DAG traversal, temporal graphs, or stateful QPE problems.

Version markers: `[Neo4j 5]` = Neo4j 5.x, `[2025.x]` = Neo4j 2025.x / Cypher 25, `[2025.06]` = 2025.06+.

---

## REPEATABLE ELEMENTS — When to Use [2025.x]

Default: `DIFFERENT RELATIONSHIPS` — each relationship traversed at most once per path.
Use `REPEATABLE ELEMENTS` when:
- Nodes have limited connectivity (single in/out relationship) and weight-optimized paths are needed
- Problem requires backtracking through already-visited nodes (circular routes, constrained path search)
- Path must revisit waypoints (multi-stop routes, recurring visits)

```cypher
// Find circular routes from CPH using same connections multiple times
CYPHER 25
MATCH (cph:Airport {iata: 'CPH'})
MATCH REPEATABLE ELEMENTS p=(cph)(()-[c:CONNECTION]-() WHERE c.km < 548){2,6}(cph)
WITH p, reduce(d=0, c IN relationships(p) | d + c.km) AS distance
WHERE distance >= 805
ORDER BY distance LIMIT 1
RETURN p, distance
```

`REPEATABLE ELEMENTS` requires bounded quantifier `{m,n}` — do not use `{1,}` (unbounded).

---

## Multi-Stop Shortest Path [2025.x]

Multiple waypoints in one query via chained QPE groups:

```cypher
CYPHER 25
MATCH REPEATABLE ELEMENTS p =
  ALL SHORTEST (:Airport {iata:'CPH'})--{,10}
               (:Airport {iata:'IFJ'})--{,10}
               (:Airport {iata:'DFW'})
WITH p, reduce(d=0, c IN relationships(p) | d + c.km) AS distance
ORDER BY distance LIMIT 1
RETURN p, distance
```

---

## Stateful Route Planning with allReduce [2025.x]

`allReduce` for simulation-style traversal where path validity depends on accumulated state (energy, time, cost):

```cypher
CYPHER 25 runtime=parallel
MATCH (src:Geo {name: $source}), (dst:Geo {name: $target})
MATCH REPEATABLE ELEMENTS p=(src)(()-[r:ROAD|CHARGE]-(x:Geo)){1,12}(dst)
WHERE allReduce(
  curr = {soc: $initial_soc_pct, mins: 0.0},
  r IN relationships(p) |
    CASE
      WHEN r:ROAD   THEN {soc: curr.soc - r.drain_pct,   mins: curr.mins + r.drive_mins}
      WHEN r:CHARGE THEN {soc: curr.soc + r.charge_pct,  mins: curr.mins + r.charge_mins}
    END,
  $min_soc <= curr.soc <= $max_soc AND curr.mins <= $max_mins
)
// Spatial pre-filter: skip detours > 1.3x direct distance
AND ALL(x IN nodes(p) WHERE
  point.distance(x.geo, dst.geo) < 1.3 * point.distance(src.geo, dst.geo))
RETURN p, reduce(d=0, r IN relationships(p) | d + r.drive_mins) AS total_mins
ORDER BY total_mins ASC LIMIT 1
```

`allReduce(accumulator = initial, item IN list | updateExpr, predicate)` — returns `true` only if predicate holds at every step. Prunes invalid paths inline during expansion.

---

## DAG Traversal and Critical Path [Neo4j 5]

Model: ActivityStart/ActivityEnd nodes connected by weighted `:ACTIVITY` edges; zero-weight `:DEPENDS_ON` edges for sequencing.

```cypher
// Longest path (critical path) — small graphs only
// For large graphs use gds.dag.longestPath instead
CYPHER 25
MATCH p=(a:ActivityStart)-[:ACTIVITY|DEPENDS_ON]*->(b:ActivityEnd)
WITH b.name AS task,
     reduce(t=0, r IN [x IN relationships(p) WHERE type(x)='ACTIVITY' | x] |
            t + r.expectedTime) AS totalTime
RETURN task, max(totalTime) AS criticalPathTime
ORDER BY criticalPathTime DESC

// GDS alternative for large DAGs (much faster):
// CALL gds.dag.longestPath.stream('dag_graph') YIELD nodeId, distance
```

Limitation: Cypher QPE for longest path fails on large graphs; use `gds.dag.longestPath` for production.

---

## Fraud Detection — Temporal Component Graph [2025.x]

Pattern: User-Event-Thing model where fraud rings = connected components sharing resources (IPs, devices, emails).

**Problem**: Standard WCC includes future events → "future leakage" in ML features.
**Solution**: Chronological `:SAME_CC_AS` forest — each event links only to components existing at its timestamp.

```cypher
// Step 1: Build temporal connected components (process events in timestamp order)
CYPHER 25
MATCH (e:Event&!ConnectedComponent)
WITH e ORDER BY e.timestamp
CALL (e) {
  MATCH (e)(()-[:WITH]->(entity)<-[:WITH]-(:ConnectedComponent)){0,1}()<-[:COMMITS]-(u)
  WITH DISTINCT e, u
  MATCH (u)-[:SAME_CC_AS]->*(cc WHERE NOT EXISTS {(cc)-[:SAME_CC_AS]->()})
  MERGE (cc)-[:SAME_CC_AS]->(e)
  SET e:ConnectedComponent
} IN TRANSACTIONS OF 100 ROWS

// Step 2: Point-in-time component snapshot (features as of $asOfDate)
CYPHER 25
MATCH (cc:Event)
WHERE cc.timestamp <= $asOfDate
  AND NOT EXISTS {(cc)-[:SAME_CC_AS]->(x:Event WHERE x.timestamp <= $asOfDate)}
RETURN cc

// Step 3: Retrieve component membership for an event
CYPHER 25
MATCH p=(u:User)(()-[:SAME_CC_AS]->(ev))*(e:Event {event_id: $event_id})
UNWIND ev + [e] AS event
RETURN p, [(event)-[r:WITH]->(x) | [r, x]] AS with_things
```

**Scaling with GDS WCC** — process independent components in parallel:
```cypher
CYPHER 25
CALL gds.wcc.stream('wcc_graph') YIELD nodeId, componentId
WITH gds.util.asNode(nodeId) AS event, componentId
WITH componentId, collect(event) AS events
ORDER BY rand()
CALL (events) {
  UNWIND events AS e
  WHERE NOT e:ConnectedComponent
  ORDER BY e.timestamp ASC
  CALL (e) {
    MATCH (e)(()-[:WITH]->(entity)<-[:WITH]-(:ConnectedComponent)){0,1}()<-[:COMMITS]-(p)
    WITH DISTINCT e, p
    MATCH (p)-[:SAME_CC_AS]->*(cc WHERE NOT EXISTS {(cc)-[:SAME_CC_AS]->()})
    MERGE (cc)-[:SAME_CC_AS]->(e)
    SET e:ConnectedComponent
  }
} IN CONCURRENT TRANSACTIONS OF 100 ROWS
```

**Avoid O(n²) clique projection** — use linear path through shared entity instead:
```cypher
CYPHER 25
MATCH (thing:Thing|User)
CALL (thing) {
  MATCH (e:Event)-[:WITH|COMMITS]-(thing)
  WITH DISTINCT e
  WITH collect(e) AS events
  WITH CASE size(events) WHEN 1 THEN [events[0], null] ELSE events END AS events
  UNWIND range(0, size(events)-2) AS ix
  RETURN events[ix] AS source, events[ix+1] AS target
}
RETURN gds.graph.project('wcc_graph', source, target, {})
```

---

## Cycle Detection with QPE [Neo4j 5]

Detect non-repeating cycles without artificial length limits:

```cypher
// All cycles through a node (bounded for safety)
CYPHER 25
MATCH (start:Account {id: $id})
MATCH DIFFERENT RELATIONSHIPS p=(start)(()-[:TRANSFERS_TO]->()){2,10}(start)
RETURN p, length(p) AS cycleLength
ORDER BY cycleLength LIMIT 20

// Count paths through complex small-graph traversal
CYPHER 25 runtime=parallel
MATCH REPEATABLE ELEMENTS path=(:Start)((xs:!End)--(:!Start)){0,100}(e:End)
WHERE allReduce(
  visited = [],
  x IN xs | CASE WHEN x:Big THEN visited ELSE visited + [x] END,
  size(visited) <= size(apoc.coll.toSet(visited)) + 1
)
RETURN count(path) AS validPaths
```

---

## Path Selector Reference [2025.x]

| Selector | Returns | Use case |
|---|---|---|
| `SHORTEST 1` | One shortest path | Existence + distance |
| `ALL SHORTEST` | All equal-minimum-length paths | Parallel routing |
| `ANY` | Any path (no length guarantee) | Fast existence check |
| `SHORTEST k` | k shortest paths | Top-k routing |
| `SHORTEST k GROUPS` | All paths grouped by length up to k distinct lengths | Tier-based routing |

```cypher
// k-shortest paths with cost
CYPHER 25
MATCH SHORTEST 3 (a:City {name: $from})(()-[r:ROAD]->()){1,}(b:City {name: $to})
WITH *, reduce(c=0, r IN relationships(*) | c + r.cost) AS totalCost
ORDER BY totalCost
RETURN totalCost, [n IN nodes(*) | n.name] AS route
```

---

## Type Predicate for Schema Discovery [Neo4j 5]

Identifies properties by runtime type — useful in GraphRAG pipelines to auto-detect text fields:

```cypher
// Find all STRING properties on nodes in a label
CYPHER 25
MATCH (n:Article)
WITH keys(n) AS props, n LIMIT 1
UNWIND props AS p
WHERE n[p] IS :: STRING NOT NULL
RETURN p AS textProperty
```

---

## OPTIONAL CALL [Neo4j 5]

Left-outer join for procedures — row kept even if procedure returns no results:

```cypher
CYPHER 25
MATCH (m:Movie)
OPTIONAL CALL apoc.algo.dijkstra(m, $target, 'ROAD', 'distance') YIELD path, weight
RETURN m.title, weight    // weight is null when no path found
```
