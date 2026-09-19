# Performance Anti-Patterns

Load this when optimizing a slow query or reviewing a query before production use.

## Anti-Patterns

Severity: **[ALWAYS]** fix unconditionally. **[USUALLY]** fix unless confirmed reason not to. **[SITUATIONAL]** profile first.

| Anti-Pattern | Severity | Problem | Fix |
|---|---|---|---|
| `MATCH (n)` label-free | [ALWAYS] | AllNodesScan | Add label: `MATCH (n:Person)` — indexes require a label |
| `MATCH ()-[r]->()` label-free rel | [ALWAYS] | Full rel scan | `MATCH (n:User)-[r:POSTS]->()` |
| Assumed stored GDS props (`n.pageRank`) | [ALWAYS] | Property doesn't exist unless `.write` ran | Stream via `.stream` procedure |
| `CONTAINS`/`ENDS WITH` without a text index | [ALWAYS] | Range index does not support these; causes full label scan | `CREATE TEXT INDEX idx FOR (n:Label) ON (n.prop)` |
| `MATCH (u)-[:R]->(t1), (u)-[:R]->(t2) WHERE t1 <> t2` | [USUALLY] | O(n²) pairs | `collect(t) AS items WHERE size(items) >= 2` |
| `UNWIND list AS a UNWIND list AS b WHERE a <> b` | [USUALLY] | O(n²) pairs | `LIMIT` before pairing, or sample `list[0..10]` |
| Chained `OPTIONAL MATCH` for nested optional data | [USUALLY] | Fan-out multiplies row count | `COLLECT { MATCH (a)-[:R]->(b) RETURN b }` |
| `LIMIT` only at final `RETURN` | [USUALLY] | Full traversal runs before limit | Push `WITH n LIMIT 100` before expensive joins |
| Cartesian product (two MATCHes, no join) | [USUALLY] | Multiplies all rows | Add join predicate in `WHERE` |

→ See [indexes.md](indexes.md) for index type selection, MERGE lock semantics, hints, and `SHOW INDEXES YIELD *`.

## Text indexes vs fulltext indexes

| Index type | Supports | Created with | Queried with |
|---|---|---|---|
| Text index | `CONTAINS`, `ENDS WITH` | `CREATE TEXT INDEX idx FOR (n:Label) ON (n.prop)` | Standard `WHERE` + optional hint |
| Fulltext index | Lucene tokenized search with scoring | `CREATE FULLTEXT INDEX idx FOR (n:Label1\|Label2) ON EACH [n.prop1, n.prop2]` | `CALL db.index.fulltext.queryNodes('idx', $query)` |

```cypher
// Text index
CREATE TEXT INDEX person_bio FOR (n:Person) ON (n.bio)
MATCH (n:Person) USING TEXT INDEX n:Person(bio) WHERE n.bio CONTAINS $s RETURN n

// Fulltext index
CREATE FULLTEXT INDEX entity FOR (n:Person|Company) ON EACH [n.name, n.description]
CALL db.index.fulltext.queryNodes('entity', $query) YIELD node, score
RETURN node.name, score ORDER BY score DESC LIMIT 20
```

EXPLAIN / PROFILE red flags: `AllNodesScan`, `CartesianProduct`, `NodeByLabelScan`, `Eager`.

For analytics over large sets:
```cypher
CYPHER 25 runtime=parallel
MATCH (n:Article)
RETURN count(n), avg(n.sentiment)
```

Confirm with EXPLAIN — header must show `Runtime PARALLEL`. Only for large analytical scans; adds overhead for OLTP short-hop lookups.

## Eager Operator

`Eager` materializes entire intermediate result in memory. Blocks streaming; causes heap pressure at scale.

**Common triggers:**

| Pattern | Why Eager appears | Fix |
|---|---|---|
| `MATCH (n:A) ... MERGE (:A {...})` | MERGE on same label as MATCH | collect first, then UNWIND+write |
| `UNWIND list MERGE (a:X) MERGE (b:X)` | Two MERGEs on same label in one row | `CALL IN TRANSACTIONS` |
| `MATCH (n:A) CREATE (m:A)` | CREATE on same label as MATCH | collect first |
| `FOREACH (x IN list \| CREATE (:A))` | Write inside FOREACH visible to outer read | `UNWIND` + write |
| `MATCH (n:A)-[]-(m) MERGE (:A {name:'London'})` | Ambiguous label scope | Add specific label to MATCH nodes |

**Fix 1: Add specific labels to disambiguate** [official — LP Eagerness planner]
```cypher
// BEFORE -- Eager: planner can't tell if new :City hits :LondonGroup MATCH
MATCH (station:LondonGroup)<-[:CALLS_AT]-(london_calling)
MERGE (london_calling)-[:CALLS_AT_CITY]->(city:City {name: 'London'})

// AFTER -- label :CallingPoint eliminates ambiguity; Eager removed
MATCH (station:LondonGroup)<-[:CALLS_AT]-(london_calling:CallingPoint)
MERGE (london_calling)-[:CALLS_AT_CITY]->(city:City {name: 'London'})
```

**Fix 2: collect first, then write**
```cypher
// BEFORE -- triggers Eager
MATCH (u:User {status: 'active'})
MERGE (u)-[:HAS_SESSION]->(s:Session {id: randomUUID()})

// AFTER
CYPHER 25
MATCH (u:User {status: 'active'})
WITH collect(u) AS users
UNWIND users AS u
MERGE (u)-[:HAS_SESSION]->(s:Session {id: randomUUID()})
```

**Fix 3: CALL IN TRANSACTIONS** — isolates each batch; each transaction is independent
```cypher
// BEFORE -- double Eager from two MERGEs on same label
CYPHER 25
UNWIND $pairs AS pair
MERGE (a:Person {id: pair.a})
MERGE (b:Person {id: pair.b})
MERGE (a)-[:KNOWS]->(b)

// AFTER
CYPHER 25
UNWIND $pairs AS pair
CALL (pair) {
  MERGE (a:Person {id: pair.a})
  MERGE (b:Person {id: pair.b})
  MERGE (a)-[:KNOWS]->(b)
} IN TRANSACTIONS OF 500 ROWS
```

---

## Label Inference [Neo4j 5 / 2025.x]

When the planner underestimates selectivity on multi-label queries:

```cypher
// Per-query hint
CYPHER inferSchemaParts = most_selective_label
MATCH (admin:Administrator {name: $adminName}),
      (resource:Resource {name: $resourceName})
MATCH p=(admin)-[:MEMBER_OF]->()-[:ALLOWED_INHERIT]->(company)
          -[:WORKS_FOR|HAS_ACCOUNT]-()-[:WORKS_FOR|HAS_ACCOUNT]-(resource)
RETURN count(p) AS accessCount
```

Instance-wide config: `dbms.cypher.infer_schema_parts = MOST_SELECTIVE_LABEL`

Impact: uses existing statistics + advanced deduction; can improve OLTP plans from ~13ms → ~80µs on complex multi-hop patterns. Verify with `EXPLAIN` — plan should show index seeks, not NodeByLabelScan.

---

## Batching Best Practices [Neo4j 5 / 2025.x]

Prefer native `CALL IN TRANSACTIONS` over `apoc.periodic.iterate` (APOC Core is maintenance-mode).

```cypher
// Modern pattern — full planner visibility, accurate stats, memory tracking
CYPHER 25
MATCH (n:Person)
CALL (n) {
  SET n.score = toInteger(rand() * 20 + 1)
} IN TRANSACTIONS OF 1000 ROWS
  ON ERROR CONTINUE
  REPORT STATUS AS s
WITH s WHERE s.errorMessage IS NOT NULL
RETURN s.transactionId, s.errorMessage

// Parallel batches [2025.01]
CYPHER 25
LOAD CSV WITH HEADERS FROM 'file:///data.csv' AS row
CALL (row) {
  MERGE (:Movie {id: row.id})
} IN 4 CONCURRENT TRANSACTIONS OF 500 ROWS
  ON ERROR RETRY FOR 30 SECS
```

`ON ERROR` options: `FAIL` (default) | `CONTINUE` | `BREAK` | `RETRY FOR N SECS` [2025.03+]

Advantages over `apoc.periodic.iterate`: memory tracking prevents OOM, planner shows execution plan, accurate query statistics, no double entity ID fetch.
