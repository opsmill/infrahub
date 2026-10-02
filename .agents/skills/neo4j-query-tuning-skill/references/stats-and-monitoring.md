# Stats and Monitoring — Reference

## SHOW QUERIES

Lists currently running queries across all databases (admin required for other users' queries).

```cypher
SHOW QUERIES
YIELD query, queryId, database, username, elapsedTimeMillis, allocatedBytes,
      status, activeLockCount, pageHits, pageFaults, protocol, connectionId
WHERE elapsedTimeMillis > 5000
RETURN queryId, username, elapsedTimeMillis, allocatedBytes, query
ORDER BY elapsedTimeMillis DESC
```

Key fields:
- `queryId` — use with `TERMINATE QUERY`
- `elapsedTimeMillis` — wall time since query started
- `allocatedBytes` — heap allocated; high = memory pressure
- `status` — `running`, `planning`, `waiting`, `closing`
- `activeLockCount` — >0 means write transaction holding locks
- `pageHits` / `pageFaults` — cache hit/miss counts for this query

Kill a single query:
```cypher
TERMINATE QUERY "query-id-string"
YIELD queryId, username, message
```

---

## SHOW TRANSACTIONS

Lists all currently open transactions.

```cypher
SHOW TRANSACTIONS
YIELD transactionId, database, username, currentQuery, elapsedTime,
      status, cpuTime, waitTime, idleTime, activeLockCount,
      pageHits, pageFaults, currentQueryId
WHERE status <> 'Terminated'
RETURN transactionId, username, status, elapsedTime, activeLockCount, currentQuery
ORDER BY elapsedTime DESC
```

Key fields:
- `transactionId` — use with `TERMINATE TRANSACTION`
- `status` — `Running`, `Blocked`, `Closing`, `Terminated`
- `activeLockCount` — transactions blocking others will have high counts
- `currentQuery` — the Cypher string currently executing (or last executed)
- `elapsedTime` — duration since transaction opened

Terminate a transaction:
```cypher
TERMINATE TRANSACTION "neo4j-transaction-123"
YIELD transactionId, username, message
```

Terminate multiple:
```cypher
TERMINATE TRANSACTIONS "tx-1", "tx-2"
YIELD transactionId, message
```

---

## Database Statistics

### Graph Counts
Node/relationship counts by label and type — the data the planner uses for cardinality estimation.

```cypher
CALL db.stats.retrieve('GRAPH COUNTS')
YIELD section, data
RETURN section, data
```

`data` map includes keys like:
- `nodes` — total node count
- `relationships` — total rel count
- `nodesByLabel` — map of `{label: count}`
- `relsByType` — map of `{type: count}`
- `relsByTypeStartingLabel` / `relsByTypeEndingLabel` — selectivity data

### Token Stats
```cypher
CALL db.stats.retrieve('TOKENS')
YIELD section, data
RETURN section, data
```

Returns internal token ID mappings for labels, property keys, and relationship types.

### Retrieve All Stats
```cypher
CALL db.stats.retrieveAllAnonymized('GRAPH COUNTS')
YIELD section, data
RETURN section, data
```
Anonymized version for sharing without exposing property names.

---

## Statistics and Replanning

### Config
`dbms.cypher.statistics_divergence_threshold` (default: `0.75`)

Formula: `abs(a - b) / max(a, b)`. At 0.75, plan invalidated when statistics change by 75% (~4× growth/shrink). Lower to replan more aggressively on growing databases.

### Force Replanning
```cypher
// Recalculate all statistics immediately (blocks until complete):
CALL db.prepareForReplanning()

// Resample a specific index asynchronously:
CALL db.resampleIndex("index-name")

// Resample all outdated indexes asynchronously:
CALL db.resampleOutdatedIndexes()
```

Force replanning of a single query without changing stats:
```cypher
CYPHER replan=force
MATCH (p:Person {email: $email}) RETURN p.name
```

Skip replanning (use cached plan even if stale — useful during high-load bursts):
```cypher
CYPHER replan=skip
MATCH (p:Person {email: $email}) RETURN p.name
```

---

## Index Health Check

```cypher
// Indexes not yet ONLINE (still populating or failed):
SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state
WHERE state <> 'ONLINE'
RETURN name, type, labelsOrTypes, properties, state

// All online indexes:
SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state, populationPercent
WHERE state = 'ONLINE'
RETURN name, type, labelsOrTypes, properties
ORDER BY type, labelsOrTypes
```

Index types and supported predicates:
| Type | `=` | `<>` | `<` `>` | `IN` | `STARTS WITH` | `CONTAINS` | `ENDS WITH` | `POINT` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| RANGE | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| TEXT | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ |
| POINT | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| FULLTEXT | — | — | — | — | — | ✓ | — | — |
| LOOKUP | node/rel by ID | — | — | — | — | — | — | — |

---

## Query Log (server-side)

On self-managed Neo4j, slow queries log to `neo4j.log` and `query.log`:

Config options (`neo4j.conf`):
```
db.logs.query.enabled=INFO          # Log all queries (verbose) or WARN (slow only)
db.logs.query.threshold=2s          # Log queries taking longer than this
db.logs.query.parameter_logging_enabled=true
db.logs.query.allocation_logging_enabled=true
db.logs.query.page_logging_enabled=true
```

Each log entry includes: `{elapsedMs} ms: {query}` with optional params, allocated bytes, page hits/misses.

---

## Page Cache Sizing

Small page cache → high `pageFaults` → disk I/O → slow queries.

```cypher
// Current page cache stats:
CALL dbms.queryJmx("org.neo4j:instance=kernel#0,name=Page cache")
YIELD attributes
RETURN attributes
```

Or from SHOW TRANSACTIONS/QUERIES:
- `pageHits` high, `pageFaults` low → cache is sufficient
- `pageFaults` > 1% of pageHits → increase `server.memory.pagecache.size` in `neo4j.conf`

Set page cache to hold the entire graph store (`graph.db/` directory size).
