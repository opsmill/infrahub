---
name: neo4j-cypher-skill
description: Generates, optimizes, and validates Cypher 25 queries for Neo4j 2025.x and 2026.x.
  Use when writing new Cypher queries, optimizing slow queries, graph pattern matching, vector
  or fulltext search, subqueries, or batch writes. Covers MATCH, MERGE, CREATE, WITH, RETURN,
  CALL, UNWIND, FOREACH, LOAD CSV, SEARCH, expressions, functions, indexes, and subqueries.
  Does NOT handle driver migration or API changes — use neo4j-migration-skill.
  Does NOT cover DB administration or server ops — use neo4j-cli-tools-skill.
compatibility: Neo4j >= 2025.01 (safe baseline); Cypher 25
version: 1.0.1
---

## When to Use
- Writing, optimizing, or debugging Cypher queries
- Graph pattern matching, QPEs, variable-length paths
- Vector/fulltext search, subqueries, batch writes, LOAD CSV

## When NOT to Use
- **Driver migration/API changes** → `neo4j-migration-skill`
- **DB admin** (users, config, backups) → `neo4j-cli-tools-skill`
- **Hybrid search that combines vector with fulltext or other ranked sources** → `neo4j-vector-index-skill`

GQL conformance note: `LET`, `FINISH`, `FILTER`, and `INSERT` are valid Cypher 25 clauses (introduced via GQL conformance, mostly in Neo4j 2025.06). On older versions, fall back to `WITH` / (omit RETURN) / `WHERE` / `CREATE`. `INSERT` requires `&`-separated multi-labels and does not support dynamic labels/types.

---

## Pre-flight

| ? | Known | Unknown |
|---|---|---|
| `<db-name>-schema.json` found in project | Use it directly — skip live inspection | — |
| Schema (from context or live DB) | Use directly | Run Schema-First Protocol |
| Neo4j version | Use version features | Default to 2025.01 safe set |
| Executing (not generating)? | Use EXPLAIN + write gate | State query is unvalidated |

Schema unknown + no tool → produce non-executable sketch outside a code block:
```
(<SOURCE_LABEL> {<KEY>: $value})-[:<REL_TYPE>]->(<TARGET_LABEL>)
```
Never fill guessed names — realistic guesses get copied blindly.

---

## Defaults — apply every query

1. `CYPHER 25` — first token; never repeat after `UNION` or inside subqueries
2. Schema first — inspect before writing; if schema in prompt, use it directly
3. `MERGE` on constrained key only; rel `MERGE` on already-bound endpoints only
4. Label-free `MATCH (n)` forbidden unless bound or followed by `WHERE n:$($label)`
5. `LIMIT 25` default on all exploratory reads; push `WITH n LIMIT` before high-cardinality operations (variable-length traversals, fan-out MATCH, Cartesian products)
6. Comments: `//` only — `--` is SQL, invalid
7. `REPEATABLE ELEMENTS` / `DIFFERENT RELATIONSHIPS` go after `MATCH`, not end of pattern
8. `SHOW` commands: `YIELD` before `WHERE`; combinable with general Cypher clauses incl. `UNION`/`RETURN` [2026.05] — `SHOW DATABASES` still requires system db (use `USE system`)
9. Inline node predicates `(:Label WHERE p=x)` — valid in `MATCH` only
10. `WHERE` cannot follow bare `UNWIND` — use `WITH x WHERE`
11. `(a)-[:R]-(b)` — undirected matches both directions, double-counts; use directed unless unknown
12. `DETACH DELETE` — plain `DELETE` throws if node has relationships

---

## Style

| Element | Convention |
|---|---|
| Node labels | PascalCase `:Person` |
| Rel types | SCREAMING_SNAKE_CASE `:KNOWS` |
| Properties/vars | camelCase `firstName` |
| Clauses | UPPERCASE `MATCH` |
| Booleans/null | lowercase `true false null` |
| Strings | single-quoted; double only if contains `'` |

> Schema is truth. `:Person`, `:KNOWS`, `name` in examples are illustrative — substitute real names from schema.

---

## Schema-First Protocol

**Priority order:**

1. `<db-name>-schema.json` anywhere in project → read directly, state file name + `schema_retrieved_at`, skip live inspection. If significantly outdated and DB reachable, offer re-fetch. Full rules: [references/schema-guardrail.md](references/schema-guardrail.md).
   - **Existence** — labels/rel-types/properties must be in schema; try synonym resolution before asking
   - **Property type** — reason about intent first (e.g. string vs INTEGER may be null check); ask only if unclear
   - **Relationship direction** — wrong direction → correct silently and note
   - **Synonym mapping** — unambiguous → resolve silently; ambiguous → pick most likely, note; ask if unresolvable

   Scripts: `generate_schema.py` (live DB + APOC), `define_schema.py` (no DB), `import_neo4j_schema.py` (converts `neo4j-graphrag-python`, `graph-schema-introspector`, `graph-schema-json-js-utils`, `mcp-neo4j-data-modeling`).

2. Schema in context → use it, skip inspection.

3. Schema missing → run:
```cypher
CALL db.schema.visualization() YIELD nodes, relationships RETURN nodes, relationships;
SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state WHERE state = 'ONLINE';
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties;
SHOW PROCEDURES YIELD name RETURN split(name,'.')[0] AS namespace, count(*) AS procedures;
```

Property types per label — check APOC first:
```cypher
// If APOC available (preferred — use this):
CALL apoc.meta.schema() YIELD value RETURN value;

// No APOC AND database ≤ 100k nodes/rels only (expensive on large graphs):
CALL db.schema.nodeTypeProperties() YIELD nodeType, propertyName, propertyTypes, mandatory;
CALL db.schema.relTypeProperties() YIELD relType, propertyName, propertyTypes, mandatory;
```

Validate before returning any query: label exists · rel type+direction correct · property on that label · index ONLINE.

---

## Key Patterns

### MERGE
```cypher
// MERGE on constrained key; set extras in ON CREATE/ON MATCH
CYPHER 25
MATCH (a:Person {id: $a}) MATCH (b:Person {id: $b})
MERGE (a)-[r:KNOWS]->(b)
  ON CREATE SET r.since = date()
  ON MATCH  SET r.lastSeen = date()
```
`SET n = {}` replaces all props. `SET n += {}` merges (safe partial update). Use `+=` for updates.

### WITH scope
```cypher
CYPHER 25
MATCH (a:Person)-[:KNOWS]->(b:Person)
WITH a, count(*) AS friends   // b dropped here
WHERE friends > 5
RETURN a.name, friends ORDER BY friends DESC
```
Every var not listed in `WITH` is dropped. `WITH *` carries all forward.

### Subqueries — cheat sheet
```
EXISTS { (a)-[:R]->(b) }                           // boolean check
COUNT  { (a)-[:R]->(b) WHERE a.x > 0 }             // count
COLLECT { MATCH (a)-[:R]->(b) RETURN b.name }       // collect list (full MATCH+RETURN required)
CALL (p) { MATCH (p)-[:ACTED_IN]->(m) RETURN m }    // correlated subquery (explicit import)
OPTIONAL CALL (p) { ... }                           // nullable subquery
```
`CALL { WITH x ... }` deprecated → `CALL (x) { ... }`. `COLLECT {}` returns exactly one column.

### CALL IN TRANSACTIONS (bulk writes)
```cypher
CYPHER 25
LOAD CSV WITH HEADERS FROM 'file:///data.csv' AS row
CALL (row) {
  MERGE (p:Person {id: row.id}) SET p += row
} IN TRANSACTIONS OF 1000 ROWS ON ERROR CONTINUE REPORT STATUS AS s
```
Input stream must be outside subquery. Auto-commit only — never wrap in `beginTransaction()`. `PERIODIC COMMIT` deprecated.

`DISJOINT BY` [2026.06, Cypher 25] on `IN CONCURRENT TRANSACTIONS` prevents deadlocks by scheduling batches that share lock-prone resources sequentially — use when importing relationships:
```cypher
CYPHER 25
LOAD CSV WITH HEADERS FROM 'file:///rels.csv' AS line
CALL (line) {
  MATCH (a:Movie {id: line.movieId}), (b:Person {id: line.personId})
  MERGE (b)-[:ACTED_IN]->(a)
} IN CONCURRENT TRANSACTIONS OF 1000 ROWS DISJOINT BY (line.movieId, line.personId)
```
`DISJOINT BY (expr,...)` declares lock keys (outer-query variables only); `DISJOINT BY AUTO` infers them via static analysis; `DISJOINT BY NONE` disables. Overrides `dbms.cypher.transactions.default_subquery_batch_strategy`. `EXPLAIN`/`PROFILE` shows keys in `DISJOINT BY (...)` on `TransactionForeach`.

### QPE basics
```cypher
CYPHER 25
MATCH SHORTEST 1 (a:Person {name:'Alice'})(()-[:KNOWS]->()){1,}(b:Person {name:'Bob'})
RETURN b.name

// ACYCLIC [2026.03] — no repeated nodes within a path (prevents cycles)
CYPHER 25
MATCH p = ACYCLIC (start:Router {name: $from})-[:LINK]-+(end:Router {name: $to})
RETURN [n IN nodes(p) | n.name] AS route
ORDER BY length(p) LIMIT 5
```
Quantifier outside group: `(pattern){N,M}`. Groups start+end with node. `REPEATABLE ELEMENTS` needs bounded `{m,n}`. `ACYCLIC` implies nodes cannot repeat within a path (stronger than default `DIFFERENT RELATIONSHIPS`).

Match mode — add after `MATCH`:
- `DIFFERENT RELATIONSHIPS` (default) — each rel traversed once per path
- `REPEATABLE ELEMENTS` [2025.x] — nodes/rels revisitable; use for circular routes, weight-optimized paths, constrained backtracking; requires bounded `{m,n}`

### Conditional CALL subqueries [2025.06]
```cypher
CYPHER 25
MATCH (move:Item {id: $id})
OPTIONAL MATCH (insertBefore:Item {id: $before})
OPTIONAL MATCH (insertAfter:Item  {id: $after})
CALL (move, insertBefore, insertAfter) {
  WHEN insertBefore IS NULL THEN {
    MATCH (last:Item) WHERE NOT (last)-[:NEXT]->() AND last <> move
    CREATE (last)-[:NEXT]->(move)
  }
  WHEN insertAfter IS NULL THEN {
    CREATE (move)-[:NEXT]->(insertBefore)
  }
  ELSE {
    CREATE (insertAfter)-[:NEXT]->(move)
    CREATE (move)-[:NEXT]->(insertBefore)
  }
}
```
Use WHEN…THEN…ELSE for if-else-if write logic; mutually exclusive (first match wins). Not available pre-2025.06.

### Dynamic relationship types [2025.x]
```cypher
// Create/match/merge with dynamic rel type (must resolve to exactly one STRING)
CYPHER 25 CREATE (a:Node)-[:$($relType)]->(b:Node)
CYPHER 25 MATCH  (a:Node)-[:$($relType)]->(b:Node) RETURN a.name, b.name
```

### Spatial / Point
```cypher
// WGS84 geographic point
SET n.coords = point({longitude: $lon, latitude: $lat})

// Distance in metres; requires POINT index for performance
MATCH (a:Place {name: $origin}) MATCH (b:Place)
RETURN b.name, point.distance(a.coords, b.coords) AS distM
ORDER BY distM LIMIT 10

// Bounding-box pre-filter (uses POINT index) then distance
MATCH (b:Place)
WHERE point.withinBBox(b.coords,
        point({longitude: $west, latitude: $south}),
        point({longitude: $east, latitude: $north}))
RETURN b.name, point.distance(b.coords, $origin) AS distM
```
Create POINT index: `CREATE POINT INDEX name IF NOT EXISTS FOR (n:Place) ON (n.coords)`

### Aggregation grouping keys
Non-aggregating expressions in `RETURN`/`WITH` are implicit grouping keys — no `GROUP BY` needed:
```cypher
// actor + director are grouping keys; count(*) is the aggregate
MATCH (a:Person)-[:ACTED_IN]->(m:Movie)<-[:DIRECTED]-(d:Person)
RETURN a.name, d.name, count(*) AS collaborations
ORDER BY collaborations DESC
```
`count(n)` counts non-null; `count(*)` counts rows including nulls. `collect(DISTINCT expr)` deduplicates.
`count()` is faster than `size(collect())` — count() reads the internal store; collect() builds a list first.

---

## Common Syntax Traps (top causes of broken queries)

| Wrong | Right |
|---|---|
| `ORDER BY n.prop AS x DESC` | `ORDER BY n.prop DESC` |
| `ORDER BY preAggVar` after agg RETURN | Use RETURN alias |
| `count(r WHERE r.x=5)` | `sum(CASE WHEN r.x=5 THEN 1 ELSE 0 END)` |
| `UNWIND list AS x WHERE x>5` | `UNWIND list AS x WITH x WHERE x>5` |
| `least(a,b)` / `greatest(a,b)` | `CASE WHEN a<b THEN a ELSE b END` |
| `-- comment` | `// comment` |
| `shortestPath((a)-[*]->(b))` | `SHORTEST 1 (a)(()-[]->()){1,}(b)` |
| `id(n)` | `elementId(n)` |
| `[:REL*1..5]` | `(()-[:REL]->()){1,5}` |
| `CALL { WITH x ... }` | `CALL (x) { ... }` |
| `COLLECT { (a)-[:R]->(b) }` | `COLLECT { MATCH ... RETURN b }` |
| `SET n = {k:v}` partial update | `SET n += {k:v}` |
| `DELETE n` with relationships | `DETACH DELETE n` |
| `WHERE n.x = null` | `WHERE n.x IS NULL` |
| `toInteger(null)` throws | `toIntegerOrNull(null)` |
| `n.$key` dynamic property | `n[$key]` |
| `SET n:$label` | `SET n:$($label)` |
| `ZONED DATETIME >= date(...)` → 0 rows | Use `datetime(...)` or `.year` accessor |
| ISO string with `Z` suffix stored/compared as UTC | **`Z` ≠ UTC in Neo4j** — `Z` is parsed as an offset, not the UTC timezone; planner and range indexes treat them differently. Explicitly coerce: `datetime({datetime: datetime('2025-09-10T03:43:00Z'), timezone: 'UTC'})` ([neo4j#13519](https://github.com/neo4j/neo4j/issues/13519)) |
| `FOREACH ... RETURN` | `UNWIND ... RETURN` |

Full trap table → [references/syntax-traps.md](references/syntax-traps.md)

---

## Output Mode and Write Gate

Default: parameterized queries. **Return named properties, not full nodes or `RETURN *`.**
```cypher
// RIGHT: agent gets named fields it can reason over
CYPHER 25 MATCH (n:Organization {name: $name}) RETURN n.name, n.founded, n.industry LIMIT 10

// WRONG: full node object wastes tokens, leaks all properties, agent can't extract fields cleanly
CYPHER 25 MATCH (n:Organization {name: $name}) RETURN n LIMIT 10
```
Exception: schema/diagnostic queries (`CALL db.schema.visualization()`, `SHOW INDEXES YIELD *`, `EXPLAIN`) where the object is the point.

**Validation workflow:**
1. `EXPLAIN` before any write — catches syntax errors, missing indexes
2. New read: test with `LIMIT 1` first
3. Write: verify read half as `RETURN` before replacing with `SET`/`CREATE`/`DELETE`
4. `PROFILE` to measure db hits; check for `AllNodesScan`, `CartesianProduct`, `Eager`

**Query API v2** (no driver needed — works for schema inspection, EXPLAIN, reads, writes):
```bash
curl -X POST https://<instance>.databases.neo4j.io/db/<database>/query/v2 \
  -u <user>:<password> -H "Content-Type: application/json" \
  -d '{"statement": "EXPLAIN MATCH (n:Person {name: $name}) RETURN n", "parameters": {"name": "Alice"}}'
# Local: http://localhost:7474/db/<database>/query/v2
# Response: {"data": {"fields": [...], "values": [...]}}  — prefix EXPLAIN to plan without executing
```

**Write execution gate** — only when agent executes (MCP/cypher-shell/HTTP), NOT when generating for code/scripts/user to run:
1. Run `EXPLAIN` → report estimated rows affected
2. Wait for user confirmation before executing

---

## Version Gates

Default to 2025.01-safe features when version unknown.

| Feature | Min version | Fallback |
|---|---|---|
| `CYPHER 25`, QPEs, `CALL (x) {}` | 2025.01 | require 2025+ |
| Match modes (`DIFFERENT RELATIONSHIPS`, `REPEATABLE ELEMENTS`) | 2025.01 | require 2025+ |
| Dynamic labels `$($expr)`, `coll.sort()` | 2025.01 | APOC or app-side |
| `CONCURRENT TRANSACTIONS`, `REPORT STATUS` | 2025.01 | drop / omit |
| `SEARCH` clause (vector/fulltext) | 2026.01 | `CALL db.index.vector.queryNodes(...)` (deprecated 2026.04) |
| `ACYCLIC` path mode (no repeated nodes in path) | 2026.03 | post-filter with `size(nodes(p)) = size(apoc.coll.toSet(nodes(p)))` |
| `string.indexOf()`, `string.join()`, `string.regexReplace()` | 2026.05 | `apoc.text.*` or app-side |
| GQL aliases: `FOR`=`UNWIND`, `PROPERTY_EXISTS`=`IS NOT NULL`, `IS [NOT] LABELED`=`n:Label`; function aliases (`local_time`, `zoned_datetime`, `duration_between`, `collect_list`, etc.) | 2026.02–04 | GQL compliance only — use Cypher equivalents; full list → [references/cypher-syntax.md](references/cypher-syntax.md) |
| **GRAPH TYPE** schema DDL (`ALTER CURRENT GRAPH TYPE SET`, `EXTEND GRAPH TYPE WITH`, `DROP GRAPH TYPE ELEMENTS`, `SHOW CURRENT GRAPH TYPE`) | **2026.02 — PREVIEW** | Use individual `CREATE CONSTRAINT` / `CREATE INDEX` |

---

## Performance

EXPLAIN/PROFILE red flags: `AllNodesScan` `CartesianProduct` `NodeByLabelScan` `Eager`

Fix Eager — three approaches (choose simplest that works):
1. **Add specific labels** to MATCH nodes to eliminate read/write ambiguity:
   `MATCH (x:CallingPoint)` instead of bare `MATCH (x)` when writing `:City` nodes
2. **Collect first, then write**: `WITH collect(u) AS users UNWIND users AS u ...`
3. **CALL IN TRANSACTIONS**: isolates each batch in its own transaction

Label inference — when planner underestimates selectivity on multi-label queries: [Neo4j 5]
```cypher
CYPHER inferSchemaParts = most_selective_label
MATCH (admin:Administrator {name: $name}), (resource:Resource {name: $res})
MATCH p=(admin)-[:MEMBER_OF]->()-[:ALLOWED_INHERIT]->(company)
RETURN count(p)
```

Index anchors: every MATCH/MERGE/WHERE on a property needs an index on the lookup property or Neo4j scans all nodes. **Index only activates when the node has a label** — `MATCH (n {prop: $v})` never uses an index; `MATCH (n:Label {prop: $v})` does. MERGE without a constraint has no atomicity guarantee (two concurrent MERGEs can create duplicates). `CONTAINS`/`ENDS WITH` → TEXT index (RANGE does not support them). Force a plan with `USING INDEX n:Label(prop)` when EXPLAIN shows a scan.
Chained `OPTIONAL MATCH` for nested data → replace with `COLLECT { MATCH ... RETURN }`.
Dynamic labels (`$($label)`) → `AllNodesScan`+Filter; use static labels when possible.

Full anti-patterns → [references/performance.md](references/performance.md)

---

## Failure Recovery

- 0 results: check param types, remove WHERE predicates one-by-one, EXPLAIN for index use
- TypeErrors: use `toIntegerOrNull()`/`toFloatOrNull()`; guard with `IS NOT NULL`
- Variable out of scope: not listed in `WITH` → use `count(*)` not `count(droppedVar)`
- Timeouts: fix AllNodesScan → add early `LIMIT` → `CALL IN TRANSACTIONS OF 1000 ROWS`
- Long-running query progress [2026.03]: `SHOW TRANSACTIONS YIELD currentQuery, status, currentQueryProgress`
- DateTime mismatch: `ZONED DATETIME >= date(...)` → 0 rows; use `datetime()` or `.year`
- `Z` suffix ≠ UTC timezone: ISO strings with `Z` are stored as a UTC-offset, not the UTC zone — range queries across `Z` and `UTC` stored values return 0 rows. Coerce on write: `datetime({datetime: datetime($isoStr), timezone: 'UTC'})`
- Duration: `.inDays`/`.inMonths` don't exist; use `.days`/`.months`
- `Cannot merge node using null property value`: MERGE key resolved to null — validate params first
- `IndexNotFoundError`: `SHOW INDEXES YIELD name, state WHERE state <> 'ONLINE'`

---

## References

Load on demand:
- [references/indexes.md](references/indexes.md) — index types (RANGE/TEXT/FULLTEXT/POINT/COMPOSITE/LOOKUP), constraints, MERGE lock semantics, fulltext Lucene syntax, import pre-flight
- [references/cypher-syntax.md](references/cypher-syntax.md) — full syntax reference: WITH, DELETE, ORDER BY, CASE, null, lists, strings, dates, spatial/point, LOAD CSV, subqueries, QPEs, dynamic labels, SEARCH; conditional CALL (WHEN/THEN/ELSE); label pattern expressions; allReduce; NEXT clause; compact CASE WHEN; normalize(); index/constraint types table; functions annotated with version introduced
- [references/syntax-traps.md](references/syntax-traps.md) — 40+ syntax trap table
- [references/performance.md](references/performance.md) — anti-patterns, text vs fulltext indexes, Eager (3 fix strategies), label inference, batching best practices, parallel runtime
- [references/advanced-patterns.md](references/advanced-patterns.md) — REPEATABLE ELEMENTS patterns, allReduce stateful traversal, multi-stop QPE, route planning simulation, DAG critical path, temporal fraud detection component graph, cycle detection, OPTIONAL CALL
- [references/apoc.md](references/apoc.md) — APOC Core: refactoring, virtual graph, merge helpers, path expanders, triggers, collections, conditional execution
- [references/graph-type.md](references/graph-type.md) — **PREVIEW (2026.02+)** GRAPH TYPE DDL: `ALTER CURRENT GRAPH TYPE SET`, `EXTEND GRAPH TYPE WITH`, `DROP GRAPH TYPE ELEMENTS`, property types, constraints, label implications, relationship type enforcement

## WebFetch

| Need | URL |
|---|---|
| Clause semantics | `https://neo4j.com/docs/cypher-manual/25/clauses/{clause}/` |
| Function signatures | `https://neo4j.com/docs/cypher-manual/25/functions/{type}/` |
| QPE / paths | `https://neo4j.com/docs/cypher-manual/25/patterns/` |
| Spatial/point functions | `https://neo4j.com/docs/cypher-manual/25/functions/spatial/` |
| Index/constraint reference | `https://neo4j.com/docs/cypher-manual/25/indexes/` |
| Full cheat sheet | `https://neo4j.com/docs/cypher-cheat-sheet/25/all/` |

---

## Checklist
- [ ] Schema inspected or confirmed in context
- [ ] `CYPHER 25` prefix on every top-level query
- [ ] `$parameters` used (not literals)
- [ ] `LIMIT` on exploratory reads (default 25)
- [ ] `EXPLAIN` run; red flags resolved
- [ ] Write half verified as `RETURN` before executing
- [ ] Write execution gate applied if agent is executing (not generating)
- [ ] `MERGE` on constrained key only
- [ ] No label-free `MATCH (n)`
- [ ] Schema ops not inside explicit transaction
