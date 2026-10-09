---
name: neo4j-query-tuning-skill
description: Diagnoses and fixes slow Neo4j Cypher queries by reading execution plans, identifying
  bad operators (AllNodesScan, CartesianProduct, Eager, NodeByLabelScan), and prescribing fixes
  (indexes, hints, query rewrites, runtime selection). Use when a query is slow, when EXPLAIN
  or PROFILE output needs interpretation, when dbHits or pageCacheHitRatio are poor, when
  cardinality estimation diverges from actuals, or when deciding between slotted/pipelined/parallel
  runtimes. Covers USING INDEX / USING SCAN / USING JOIN hints, db.stats.retrieve, SHOW QUERIES,
  SHOW TRANSACTIONS, TERMINATE TRANSACTION.
  Does NOT write new Cypher from scratch — use neo4j-cypher-skill.
  Does NOT cover GDS algorithm tuning — use neo4j-gds-skill.
  Does NOT cover index/constraint creation syntax details — use neo4j-cypher-skill references/indexes.md.
allowed-tools: Bash WebFetch
version: 1.0.1
---

## When to Use
- Query takes unexpectedly long; need root-cause analysis
- EXPLAIN/PROFILE output in hand — needs interpretation
- Identifying which index is missing or unused
- Deciding between slotted / pipelined / parallel runtimes
- Monitoring live queries: SHOW QUERIES, SHOW TRANSACTIONS
- Cardinality estimates wrong (plan replanning needed)

## When NOT to Use
- **Writing Cypher from scratch** → `neo4j-cypher-skill`
- **GDS algorithm performance** → `neo4j-gds-skill`
- **Schema design / data modelling** → `neo4j-modeling-skill`

---

## EXPLAIN vs PROFILE

| | EXPLAIN | PROFILE |
|---|---|---|
| Executes query? | No | Yes |
| Returns data? | No | Yes |
| Shows `rows` (actual) | No | Yes |
| Shows `dbHits` (actual) | No | Yes |
| Shows `estimatedRows` | Yes | Yes |
| Cost | Zero | Full query cost |

Run `PROFILE` **twice** — first run warms page cache; second gives representative metrics.

```cypher
EXPLAIN MATCH (p:Person {email: $email}) RETURN p.name
PROFILE MATCH (p:Person {email: $email}) RETURN p.name
```

Query API alternative (no driver):
```bash
curl -X POST https://<host>/db/<db>/query/v2 \
  -u <user>:<pass> -H "Content-Type: application/json" \
  -d '{"statement": "EXPLAIN MATCH (p:Person {email: $email}) RETURN p.name", "parameters": {"email": "a@b.com"}}'
```

---

## Key Plan Metrics

| Metric | Good | Investigate if |
|---|---|---|
| `dbHits` | Low; drops after index added | High relative to `rows` |
| `rows` | Shrinks early in plan | Large until final operator |
| `estimatedRows` | Close to `rows` | >10× divergence from actual |
| `pageCacheHitRatio` | >0.99 | <0.90 (disk I/O bottleneck) |
| `pageCacheHits` | High | — |
| `pageCacheMisses` | Near 0 | Rising (page cache too small) |

Read plans **bottom-up** — leaf operators at bottom initiate data retrieval.

---

## Operator Reference

| Operator | Good/Bad | Meaning | Fix |
|---|---|---|---|
| `NodeIndexSeek` | ✓ | Exact match via RANGE/LOOKUP index | — |
| `NodeUniqueIndexSeek` | ✓ | Unique constraint index hit | — |
| `NodeIndexContainsScan` | ✓ | TEXT index CONTAINS / STARTS WITH | — |
| `NodeIndexScan` | ~ | Full index scan (no predicate) | Add WHERE predicate or composite index |
| `NodeByLabelScan` | ✗ | Scans all nodes of label | Add RANGE index on lookup property |
| `AllNodesScan` | ✗✗ | Scans entire node store | Add label + index to MATCH |
| `Expand(All)` | ~ | Traverse relationships from node | Normal; limit with LIMIT or WHERE |
| `Expand(Into)` | ~ | Find rels between two matched nodes | Normal for known-endpoint joins |
| `Filter` | ~ | Predicate applied after scan | Move predicate into WHERE with index |
| `CartesianProduct` | ✗ | No join predicate between two MATCH | Add WHERE join or use WITH between MATCHes |
| `NodeHashJoin` | ~ | Hash join on node IDs | Normal; planner chose hash join |
| `ValueHashJoin` | ~ | Hash join on values | Normal; watch memory for large inputs |
| `EagerAggregation` | ~ | Full aggregation (ORDER BY, count(*)) | Normal for aggregates |
| `Aggregation` | ✓ | Streaming aggregation | — |
| `Eager` | ✗ | Read/write conflict; materialises all rows | See Eager fix strategies below |
| `Sort` | ~ | Full sort — O(n log n) | Add `LIMIT` before Sort; push LIMIT earlier |
| `Top` | ✓ | Sort+Limit combined — O(n log k) | Preferred over Sort+Limit |
| `Limit` | ✓ | Truncates rows early | Push as early as possible |
| `Skip` | ~ | Offset pagination | Use keyset pagination on large graphs |
| `ProduceResults` | — | Final output operator | Root of tree |
| `UndirectedRelationshipByIdSeekPipe` | ~ | Lookup by relationship ID | Avoid `id(r)` — use `elementId(r)` |

Full operator reference → [references/plan-operators.md](references/plan-operators.md)

---

## Diagnostic Workflow (Agent Runbook)

### Step 1 — Baseline Plan
```cypher
EXPLAIN <query>
```
Scan output for `AllNodesScan`, `NodeByLabelScan`, `CartesianProduct`, `Eager`.

### Step 2 — Check Indexes
```cypher
SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state
WHERE state = 'ONLINE'
```
Find whether the label/property from the bad operator has an index.

### Step 3 — Create Missing Index
```cypher
// RANGE index for equality/range predicates:
CREATE INDEX person_email IF NOT EXISTS FOR (n:Person) ON (n.email)
// TEXT index for CONTAINS/ENDS WITH:
CREATE TEXT INDEX person_bio IF NOT EXISTS FOR (n:Person) ON (n.bio)
// Composite for multi-property lookup:
CREATE INDEX order_status_date IF NOT EXISTS FOR (n:Order) ON (n.status, n.createdAt)
```
Wait for `state = 'ONLINE'` before measuring.

### Step 4 — Profile After Fix
```cypher
PROFILE <query>
```
Compare `dbHits` and elapsed ms before/after. Target: `NodeIndexSeek` replaces scan operators.

### Step 5 — Stale Statistics (if estimatedRows wildly off)
```cypher
CALL db.prepareForReplanning()
// or resample a specific index:
CALL db.resampleIndex("person_email")
// or resample all outdated:
CALL db.resampleOutdatedIndexes()
```
Config: `dbms.cypher.statistics_divergence_threshold` (default `0.75` — plan expires when stat changes >75%).

---

## Fixing Common Plan Problems

### Missing Index → NodeByLabelScan / AllNodesScan
```cypher
// Force index hint when planner ignores it:
MATCH (p:Person {email: $email})
USING INDEX p:Person(email)
RETURN p.name
// Force label scan (sometimes faster for high selectivity):
MATCH (p:Person {email: $email})
USING SCAN p:Person
RETURN p.name
```

### Wrong Anchor — Planner Picks Wrong Starting Node
Reorder MATCH or use hints:
```cypher
// Force join at specific node:
MATCH (a:Author)-[:WROTE]->(b:Book)-[:IN_CATEGORY]->(c:Category {name: $cat})
USING JOIN ON b
RETURN a.name, b.title
```

### CartesianProduct — Two Unconnected MATCHes
```cypher
// Bad (Cartesian product):
MATCH (a:Author {id: $aid})
MATCH (b:Book  {id: $bid})
RETURN a.name, b.title

// Good (explicit join or WITH):
MATCH (a:Author {id: $aid})-[:WROTE]->(b:Book {id: $bid})
RETURN a.name, b.title
// Or: WITH between them to reset planning context
```

### Eager — Read/Write Conflict
Three strategies (pick simplest):
1. **Add specific labels** to MATCH nodes so planner distinguishes read/write sets
2. **Collect-then-write**: `WITH collect(n) AS nodes UNWIND nodes AS n SET n.x = 1`
3. **CALL IN TRANSACTIONS**: isolates each batch in its own transaction
```cypher
CYPHER 25
MATCH (p:Person) WHERE p.score > 100
CALL (p) { SET p.tier = 'gold' } IN TRANSACTIONS OF 1000 ROWS
```

### Expensive CONTAINS / ENDS WITH
```cypher
// Needs TEXT index (RANGE does NOT support these):
CREATE TEXT INDEX person_bio IF NOT EXISTS FOR (n:Person) ON (n.bio)
MATCH (p:Person) WHERE p.bio CONTAINS $keyword RETURN p.name
```

### Over-Traversal — Push LIMIT Early
```cypher
// Bad: LIMIT after expensive join
MATCH (a:Author)-[:WROTE]->(b:Book)-[:REVIEWED_BY]->(r:Review)
RETURN a.name, b.title, r.text LIMIT 10

// Good: anchor limit before fan-out
MATCH (a:Author)-[:WROTE]->(b:Book)
WITH a, b LIMIT 10
MATCH (b)-[:REVIEWED_BY]->(r:Review)
RETURN a.name, b.title, r.text
```

---

## Cypher Runtime Selection

| Runtime | Select | Best For | Avoid When |
|---|---|---|---|
| `pipelined` | `CYPHER runtime=pipelined` | Default OLTP; streaming, low memory | Unsupported operators fall back to slotted |
| `slotted` | `CYPHER runtime=slotted` | Guaranteed stable behavior; debug | Performance-critical OLTP |
| `parallel` | `CYPHER 25 runtime=parallel` | Large analytical scans; aggregations | OLTP, writes, short queries, Aura Free |

Pipelined is default for most queries. Parallel requires `dbms.cypher.parallel.worker_limit` configured; available on Enterprise and Aura Pro 2025+.

```cypher
// Force parallel for large aggregation:
CYPHER 25 runtime=parallel
MATCH (n:Transaction) WHERE n.amount > 1000
RETURN n.currency, count(*), sum(n.amount)
```

---

## Query Monitoring Commands

```cypher
// Live queries + resource usage:
SHOW QUERIES YIELD query, queryId, elapsedTimeMillis, allocatedBytes, status, username

// Running transactions:
SHOW TRANSACTIONS YIELD transactionId, currentQuery, currentQueryProgress, elapsedTime, status, username, cpuTime, activeLockCount  // currentQueryProgress added [2026.03]

// Kill a specific transaction:
TERMINATE TRANSACTION $transactionId

// Kill a query:
TERMINATE QUERY $queryId

// Graph count stats (node/rel counts by label/type — feed into planner):
CALL db.stats.retrieve('GRAPH COUNTS') YIELD section, data RETURN section, data

// Token stats (label/property/rel-type IDs):
CALL db.stats.retrieve('TOKENS') YIELD section, data RETURN section, data
```

Full monitoring reference → [references/stats-and-monitoring.md](references/stats-and-monitoring.md)

---

## Checklist

- [ ] Run `EXPLAIN` first — identifies plan problems without execution cost
- [ ] Check for `AllNodesScan` / `NodeByLabelScan` — missing index
- [ ] Check for `CartesianProduct` — missing join predicate
- [ ] Check for `Eager` — read/write conflict
- [ ] `SHOW INDEXES` — confirm relevant index exists and `state = 'ONLINE'`
- [ ] Create missing index; wait for ONLINE
- [ ] Run `PROFILE` twice — first warms cache, second is representative
- [ ] Compare `dbHits` before/after fix
- [ ] If `estimatedRows` wildly off → `CALL db.prepareForReplanning()`
- [ ] Push `LIMIT` / `WITH n LIMIT k` before high-fanout operations
- [ ] For CONTAINS/ENDS WITH — TEXT index, not RANGE
- [ ] For large analytical queries — consider `runtime=parallel`
- [ ] Kill long-running queries with `TERMINATE TRANSACTION`
