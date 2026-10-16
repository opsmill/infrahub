# Neo4j Indexes and Constraints

## Why indexes are critical

Every `MATCH`, `MERGE`, or `WHERE` predicate on a node/relationship property requires an index on the **initial lookup property** (the anchor that starts traversal). Without one, Neo4j does a full AllNodesScan or AllRelationshipsScan.

**Index requires a label.** Without a label, Neo4j cannot identify which index to use and falls back to full scan even if an index exists.

```cypher
// IGNORED: no label → no index used, full scan
MATCH (n {email: $email}) RETURN n.name, n.email

// USED: label present → RANGE/UNIQUE index on Person.email
MATCH (n:Person {email: $email}) RETURN n.name, n.email

// IGNORED in MERGE too: label required
MERGE (n {email: $email})          // full scan, no lock
MERGE (n:Person {email: $email})   // index lookup + constraint lock
```

MERGE compounds this: `MERGE (n:Person {email: $email})` = `MATCH` + `CREATE IF NOT EXISTS`. MATCH phase scans without an index. With a constraint, MERGE also acquires a lock on the constraint entry, preventing concurrent duplicate creation.

**Single index per MATCH clause by default.** Planner picks one anchor index for multi-predicate queries. Use `USING INDEX` hints to force multiple indexes in the same MATCH.

---

## Index type decision table

| Query predicate | Index type | Notes |
|---|---|---|
| `prop = $val`, `prop > $val`, `prop < $val`, `prop >= $val`, `prop <= $val` | **RANGE** | Numbers, dates, booleans, strings |
| `prop STARTS WITH $val` | **RANGE** | Also supported by TEXT but RANGE is faster for prefix |
| `prop CONTAINS $val`, `prop ENDS WITH $val` | **TEXT** | Uses trigram (text-2.0); RANGE does NOT support these efficiently |
| `prop IN [$a, $b]` (string list) | **TEXT** | Faster than RANGE for string list membership |
| `prop IS NOT NULL` | **RANGE** | Existence check with range index |
| `point.distance(n.loc, $pt) < $r`, `point.withinBBox(...)` | **POINT** | Spatial queries |
| Full-text search, multiple labels/props, fuzzy, Lucene syntax | **FULLTEXT** | Returns score; not a filter index |
| `(n:Label)` or `()-[r:TYPE]-()` without property | **LOOKUP** | Always exists; covers label/type scans |
| `vector.similarity.*`, `SEARCH ... VECTOR INDEX` | **VECTOR** | See `neo4j-vector-index-skill` |
| Multiple props on same label in AND | **COMPOSITE** | All composite props must appear in WHERE |

---

## Index providers (internal implementations)

| Index type | Default provider | Notes |
|---|---|---|
| RANGE / UNIQUE / NODE KEY / COMPOSITE | `range-1.0` | B-tree variant; all scalar types |
| TEXT | `text-2.0` | Trigram-based — see section below |
| FULLTEXT | `fulltext-1.0` | Apache Lucene (`lucene+native-3.0`) |

LOOKUP indexes (auto-created, two per database) have no user-configurable provider.

---

## TEXT index — trigram internals

Default `text-2.0` indexes STRING values as overlapping **trigrams** (3-Unicode-codepoint windows). Example: `"developer"` → `["dev","eve","vel","elo","lop","ope","per"]`.

- `CONTAINS "vel"` / `ENDS WITH "per"` → direct trigram lookup, O(1) index probe.
- `STARTS WITH` works via trigram but RANGE is faster for prefix-only.
- When both RANGE and TEXT exist on the same STRING property, planner **auto-selects TEXT** for `CONTAINS`/`ENDS WITH`, RANGE for `STARTS WITH`/`=`/range predicates.
- TEXT takes **less storage** than RANGE for high-cardinality string data.
- TEXT may show **higher db-hits but lower elapsed time** vs RANGE for substring queries — measure elapsed ms, not db-hits.
- `text-1.0` (pre-5.1) does NOT use trigrams — deprecated.

---

## Create syntax

```cypher
// RANGE (numbers, dates, booleans, strings: =, >, <, STARTS WITH, IS NOT NULL)
CREATE RANGE INDEX person_email IF NOT EXISTS FOR (n:Person) ON (n.email)

// RANGE on relationship
CREATE RANGE INDEX event_date IF NOT EXISTS FOR ()-[r:OCCURRED_ON]-() ON (r.date)

// RANGE composite (all listed props must appear in WHERE for planner to use it)
CREATE INDEX person_name_age IF NOT EXISTS FOR (n:Person) ON (n.name, n.age)

// RANGE composite on relationship
CREATE INDEX purchased_date_amount IF NOT EXISTS FOR ()-[r:PURCHASED]-() ON (r.date, r.amount)

// TEXT (string CONTAINS, ENDS WITH, IN list — trigram internally)
CREATE TEXT INDEX person_name_text IF NOT EXISTS FOR (n:Person) ON (n.name)

// TEXT on relationship
CREATE TEXT INDEX rates_interest IF NOT EXISTS FOR ()-[r:KNOWS]-() ON (r.interest)

// POINT (spatial)
CREATE POINT INDEX place_location IF NOT EXISTS FOR (n:Place) ON (n.location)

// POINT with spatial bounding box config (WGS-84 geographic CRS)
CREATE POINT INDEX place_wgs IF NOT EXISTS FOR (n:Place) ON (n.location)
OPTIONS {
  indexConfig: {
    `spatial.wgs-84.min`: [-180.0, -90.0],
    `spatial.wgs-84.max`: [180.0, 90.0]
  }
}
// Other spatial CRS config keys: spatial.cartesian.min/max, spatial.cartesian-3d.min/max, spatial.wgs-84-3d.min/max

// FULLTEXT (Lucene; multi-label, multi-prop, scored)
CREATE FULLTEXT INDEX search_articles IF NOT EXISTS
  FOR (n:Article|BlogPost) ON EACH [n.title, n.body]

// FULLTEXT with analyzer + eventually-consistent background updates
CREATE FULLTEXT INDEX search_articles IF NOT EXISTS
  FOR (n:Article|BlogPost) ON EACH [n.title, n.body]
OPTIONS {
  indexConfig: {
    `fulltext.analyzer`: 'english',
    `fulltext.eventually_consistent`: true
  }
}

// LOOKUP (auto-created per database — shown for reference only; do NOT drop or recreate)
CREATE LOOKUP INDEX node_label_lookup FOR (n) ON EACH labels(n)
CREATE LOOKUP INDEX rel_type_lookup  FOR ()-[r]-() ON EACH type(r)
```

### FULLTEXT analyzer options

| Analyzer | Use case |
|---|---|
| `standard-no-stop-words` | Default — general purpose, removes stop words |
| `english` | English stemming (run/runs/running → same token) |
| `simple` | Lowercase only, no stemming |
| Custom (Java SPI) | Implement `AnalyzerProvider` interface |

`fulltext.eventually_consistent: true` — index updated in background. Improves write throughput at cost of slight search lag.

---

## Constraints

Enforce data integrity AND create an implicit **RANGE index** (UNIQUE, NODE KEY). Prefer constraint over bare index when uniqueness is required.

**Edition notes**: UNIQUE and NOT NULL available in all editions. NODE KEY, RELATIONSHIP KEY, RELATIONSHIP UNIQUE, property type (`IS ::`) require **Enterprise Edition**.

```cypher
// UNIQUE node — creates implicit RANGE index; MERGE acquires lock
CREATE CONSTRAINT person_email_unique IF NOT EXISTS
  FOR (n:Person) REQUIRE n.email IS UNIQUE

// UNIQUE composite node
CREATE CONSTRAINT book_title_year IF NOT EXISTS
  FOR (n:Book) REQUIRE (n.title, n.publicationYear) IS UNIQUE

// UNIQUE relationship (Enterprise)
CREATE CONSTRAINT sequel_order IF NOT EXISTS
  FOR ()-[r:SEQUEL_OF]-() REQUIRE r.order IS UNIQUE

// NODE KEY — composite uniqueness + existence; creates composite RANGE index (Enterprise)
CREATE CONSTRAINT person_key IF NOT EXISTS
  FOR (n:Person) REQUIRE (n.firstName, n.lastName) IS NODE KEY

// RELATIONSHIP KEY (Enterprise)
CREATE CONSTRAINT owns_key IF NOT EXISTS
  FOR ()-[r:OWNS]-() REQUIRE r.ownershipId IS RELATIONSHIP KEY

// NOT NULL node (existence only — no index created)
CREATE CONSTRAINT person_name_exists IF NOT EXISTS
  FOR (n:Person) REQUIRE n.name IS NOT NULL

// NOT NULL relationship
CREATE CONSTRAINT wrote_year_exists IF NOT EXISTS
  FOR ()-[r:WROTE]-() REQUIRE r.year IS NOT NULL

// PROPERTY TYPE node (Enterprise) — IS ::, IS TYPED, and :: are synonyms; IS :: is preferred
CREATE CONSTRAINT movie_title_type IF NOT EXISTS
  FOR (n:Movie) REQUIRE n.title IS :: STRING

// PROPERTY TYPE relationship (Enterprise)
CREATE CONSTRAINT rating_type IF NOT EXISTS
  FOR ()-[r:RATED]-() REQUIRE r.rating IS :: INTEGER
```

Supported types for `IS ::`: `BOOLEAN`, `STRING`, `INTEGER`, `FLOAT`, `DATE`, `LOCAL TIME`, `ZONED TIME`, `LOCAL DATETIME`, `ZONED DATETIME`, `DURATION`, `POINT`, `LIST<type>`.

---

## MERGE and constraints

`MERGE` = `MATCH` + conditional `CREATE`. Without an index/constraint on the merge property, MATCH scans all nodes of that label.

```cypher
// Without constraint: full scan + no atomicity guarantee
MERGE (p:Person {email: $email})

// With UNIQUE constraint:
//   1. O(log n) lookup via implicit RANGE index
//   2. Lock on constraint entry → prevents concurrent duplicate creation
//   3. Atomic: two concurrent MERGEs cannot both create the same node
CREATE CONSTRAINT person_email_unique IF NOT EXISTS
  FOR (n:Person) REQUIRE n.email IS UNIQUE

MERGE (p:Person {email: $email})
  ON CREATE SET p.createdAt = datetime()
  ON MATCH  SET p.lastSeenAt = datetime()
```

Merge on multiple properties without NODE KEY: planner may not use index.
Merge only on the indexed property, set others after: `MERGE (n:Label {keyProp: $val}) SET n.otherProp = $other`

---

## Fulltext search

Lucene — tokenized, scored, not a filter index. Result nodes must be joined back to the graph. Supports `LIST<STRING>` properties — each element analyzed independently.

```cypher
// Create (multi-label, multi-prop)
CREATE FULLTEXT INDEX article_search IF NOT EXISTS
  FOR (n:Article|BlogPost) ON EACH [n.title, n.body]

// Query nodes — returns node + score (descending)
CALL db.index.fulltext.queryNodes('article_search', 'graph database')
YIELD node, score
WHERE score > 0.5
RETURN node.title, score
ORDER BY score DESC LIMIT 10

// Query relationships
CALL db.index.fulltext.queryRelationships('rel_search', 'query string')
YIELD relationship, score
RETURN relationship, score

// Lucene query syntax:
//   'graph database'         token AND (default)
//   '"graph database"'       exact phrase
//   'graph OR database'      OR
//   'graph -relational'      NOT
//   'graph~'                 fuzzy
//   'graph*'                 wildcard prefix
//   'title:graph'            field-scoped search
//   'team:"Operations"'      field + exact phrase
```

Fulltext index does NOT participate in WHERE predicate planning. Use `CALL db.index.fulltext.queryNodes` / `queryRelationships` explicitly.

---

## Index hints (USING INDEX)

Force a specific index when the planner chooses a suboptimal plan. Use `EXPLAIN` first to confirm the issue.

```cypher
// Generic hint — planner uses any available index on the property
MATCH (p:Person)
USING INDEX p:Person(email)
WHERE p.email = $email
RETURN p.name, p.email

// Force RANGE index specifically
MATCH (s:Scientist {born: 1850})
USING RANGE INDEX s:Scientist(born)
RETURN s.name, s.born

// Force TEXT index specifically
MATCH (c:Country)
USING TEXT INDEX c:Country(name)
WHERE c.name = 'Country7'
RETURN c.name, c.population

// Two hints in one query — forces both path ends to use their index (enables index join)
MATCH (p:Person)-[:ACTED_IN]->(m:Movie)<-[:DIRECTED]-(p2:Person)
USING INDEX p:Person(name)
USING INDEX p2:Person(name)
WHERE p.name CONTAINS 'John' AND p2.name CONTAINS 'George'
RETURN p.name, p2.name, m.title

// Relationship index hint
MATCH (u:User)-[r:RATED]->(m:Movie)
USING INDEX r:RATED(rating)
WHERE r.rating = 5
RETURN u.name, r.rating, m.title

// Relationship TEXT index hint
MATCH (n:Inventor)-[i:INVENTED_BY]->(inv:Invention)
USING TEXT INDEX i:INVENTED_BY(location)
WHERE i.location = 'Location7'
RETURN n.name, inv.name, i.location
```

Rules:
- Typed hints (`USING RANGE INDEX`, `USING TEXT INDEX`) only valid when the planner can guarantee the type doesn't change results.
- Hints do NOT guarantee improvement — PROFILE before/after; measure elapsed ms (not db-hits for TEXT).
- Index **not used** when predicate compares two node properties (`WHERE p.name = p2.name`) — no anchor.
- FULLTEXT has no `USING INDEX` hint — call `db.index.fulltext.queryNodes` explicitly.
- Check query stats first (`CALL db.stats.retrieve('GRAPH COUNTS')`) before adding hints.

---

## Inspect indexes and constraints

```cypher
// All indexes — core fields
SHOW INDEXES YIELD name, type, state, labelsOrTypes, properties, populationPercent
  WHERE state <> 'ONLINE' OR populationPercent < 100   // building or not ready

// Full details (includes: indexSize, lastRead, readCount, lastWrite, writeCount, indexConfig)
SHOW INDEXES YIELD *

// Filter by type
SHOW RANGE INDEXES    YIELD name, state, labelsOrTypes, properties
SHOW TEXT INDEXES     YIELD name, state, labelsOrTypes, properties
SHOW FULLTEXT INDEXES YIELD name, state, indexConfig
SHOW VECTOR INDEXES   YIELD name, state, populationPercent, indexConfig
SHOW LOOKUP INDEXES   YIELD name, state

// Unused index candidates (never read — review for removal)
SHOW INDEXES YIELD name, type, readCount, lastRead
  WHERE readCount = 0 AND type <> 'LOOKUP'
  RETURN name, type, lastRead
  ORDER BY lastRead

// Constraints
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties

// Check index used in query plan
EXPLAIN MATCH (p:Person {email: $email}) RETURN p
// 'NodeIndexSeek' or 'NodeUniqueIndexSeek' — index used ✓
// 'NodeIndexContainsScan' — TEXT index via CONTAINS ✓
// 'NodeByLabelScan' or 'AllNodesScan' — no index, add one

// PROFILE for timing (run twice; second run = true cost)
PROFILE MATCH (p:Person) WHERE p.name CONTAINS 'Robert' RETURN p.name
```

---

## Import pre-flight — create before loading

Create constraints and indexes **before** bulk import — MERGE during load uses the index for every row.

```cypher
// 1. Uniqueness constraints first (implicit RANGE index)
CREATE CONSTRAINT person_id    IF NOT EXISTS FOR (n:Person)  REQUIRE n.id    IS UNIQUE;
CREATE CONSTRAINT movie_id     IF NOT EXISTS FOR (n:Movie)   REQUIRE n.id    IS UNIQUE;
CREATE CONSTRAINT org_name     IF NOT EXISTS FOR (n:Org)     REQUIRE n.name  IS UNIQUE;

// 2. Additional lookup indexes (non-unique properties used in MATCH/WHERE)
CREATE RANGE INDEX person_email IF NOT EXISTS FOR (n:Person) ON (n.email);
CREATE TEXT  INDEX movie_title  IF NOT EXISTS FOR (n:Movie)  ON (n.title);

// 3. Wait for all to be ONLINE before loading
SHOW INDEXES YIELD name, state WHERE state <> 'ONLINE' RETURN name, state;
```
