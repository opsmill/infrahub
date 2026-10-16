# Cypher Syntax Reference

Full syntax reference for clauses, patterns, and functions.
Version markers: `[2025.01]` = new/changed in Cypher 25 / Neo4j 2025.x — older models default to the pre-2025 form.
`[2026.01]` = requires Neo4j 2026.x. Unmarked = stable pre-2025, well-known priors.

---

## Index and Constraint Types

### Index decision table

| Index type | Best for | `CONTAINS`/`ENDS WITH` | Spatial | Fulltext |
|---|---|---|---|---|
| `RANGE` | `=`, `>`, `<`, `STARTS WITH`, `IS NOT NULL` | Slow (use TEXT instead) | ❌ | ❌ |
| `TEXT` | `CONTAINS`, `ENDS WITH`, `=` on strings, list `IN` with strings | ✅ | ❌ | ❌ |
| `POINT` | `point.distance()`, `point.withinBBox()` | ❌ | ✅ | ❌ |
| `FULLTEXT` | Lucene tokenized search; multiple labels/props | ❌ | ❌ | ✅ |
| `COMPOSITE` | Queries always testing 2+ properties together | — | ❌ | ❌ |

Create syntax:
```cypher
CREATE RANGE INDEX    name IF NOT EXISTS FOR (n:Label) ON (n.prop)
CREATE TEXT INDEX     name IF NOT EXISTS FOR (n:Label) ON (n.prop)
CREATE POINT INDEX    name IF NOT EXISTS FOR (n:Label) ON (n.prop)
CREATE COMPOSITE INDEX name IF NOT EXISTS FOR (n:Label) ON (n.p1, n.p2)
CREATE FULLTEXT INDEX  name IF NOT EXISTS FOR (n:Label|OtherLabel) ON EACH [n.p1, n.p2]
// Relationship index:
CREATE RANGE INDEX    name IF NOT EXISTS FOR ()-[r:TYPE]-() ON (r.prop)
```

### Constraint types

```cypher
// Uniqueness (+ implicitly creates RANGE index)
CREATE CONSTRAINT name IF NOT EXISTS FOR (n:Label) REQUIRE n.prop IS UNIQUE

// Existence (node property must not be null)
CREATE CONSTRAINT name IF NOT EXISTS FOR (n:Label) REQUIRE n.prop IS NOT NULL

// Relationship existence
CREATE CONSTRAINT name IF NOT EXISTS FOR ()-[r:TYPE]-() REQUIRE r.prop IS NOT NULL

// Node key = unique + existence (Enterprise only)
CREATE CONSTRAINT name IF NOT EXISTS FOR (n:Label) REQUIRE n.prop IS NODE KEY
// Multi-property node key:
CREATE CONSTRAINT name IF NOT EXISTS FOR (n:Label) REQUIRE (n.p1, n.p2) IS NODE KEY

// Relationship key (Enterprise only)
CREATE CONSTRAINT name IF NOT EXISTS FOR ()-[r:TYPE]-() REQUIRE r.prop IS RELATIONSHIP KEY
```

Rules:
- Add uniqueness constraint on MERGE key before loading data
- `IF NOT EXISTS` prevents error on re-run
- `SHOW CONSTRAINTS YIELD name, type` to inspect

---

## MERGE Safety

```cypher
// DO: MERGE on constrained key only; set other properties in ON CREATE / ON MATCH
CYPHER 25
MATCH (a:Person {id: $a}) MATCH (b:Person {id: $b})
MERGE (a)-[r:KNOWS]->(b)
  ON CREATE SET r.since = date()
  ON MATCH SET r.lastSeen = date()

// DON'T: MERGE on multiple non-constrained properties -- can create duplicates
// DON'T: MERGE a full path with unbound endpoints -- creates ghost nodes
// DON'T: MERGE key properties that are not in a constraint -- slow and creates duplicates
```

---

## Property Updates

`SET n = {}` **replaces all properties** (destructive). `SET n += {}` **merges** (additive — unmentioned properties are preserved).

```cypher
// SET = replaces -- wipes all other properties not in the map
CYPHER 25
MATCH (n:Person {id: $id})
SET n = {name: $name, age: $age}         // every other property is removed

// SET += merges -- safe partial update
CYPHER 25
MATCH (n:Person {id: $id})
SET n += {name: $name}                   // other properties preserved

// Bulk import with parameter map -- set all map keys onto node
CYPHER 25
UNWIND $rows AS row
MERGE (n:Person {id: row.id})
SET n += row
```

---

## DELETE and REMOVE

```cypher
// DETACH DELETE -- removes node AND all its relationships
CYPHER 25
MATCH (n:TempNode {id: $id})
DETACH DELETE n

// DELETE relationship only
CYPHER 25
MATCH (a:Person {id: $a})-[r:KNOWS]->(b:Person {id: $b})
DELETE r

// Plain DELETE on a node with relationships -> runtime error; always DETACH DELETE nodes

// REMOVE a property (sets it absent -- not null, absent)
CYPHER 25
MATCH (n:Person {id: $id})
REMOVE n.nickname

// REMOVE a label
CYPHER 25
MATCH (n:Person {id: $id})
REMOVE n:VIPMember

// Remove ALL properties -- SET to empty map (REMOVE cannot do this)
CYPHER 25
MATCH (n:Person {id: $id})
SET n = {}
```

---

## WITH Scope and Aggregation

`WITH` defines a new scope — every variable not listed is dropped. Use `WITH *` to carry all forward.

```cypher
// Variable 'b' dropped after WITH
CYPHER 25
MATCH (a:Person)-[:KNOWS]->(b:Person)
WITH a, count(*) AS friends         // 'b' is out of scope after this line
WHERE friends > 5
RETURN a.name, friends
ORDER BY friends DESC
```

`WITH` resets aggregation scope — filter on aggregates before further traversal:

```cypher
CYPHER 25
MATCH (p:Person)-[:ACTED_IN]->(m:Movie)
WITH p, count(m) AS movieCount
WHERE movieCount > 3
MATCH (p)-[:KNOWS]->(f:Person)       // second MATCH uses filtered 'p'
RETURN p.name, f.name
```

**`count(*)` vs `count(expr)`**: `count(*)` counts all rows including nulls; `count(n)` counts only non-null values. Use `count(DISTINCT n.prop)` to deduplicate.

**Aggregation grouping keys**: every non-aggregating expression in `RETURN`/`WITH` is implicitly a grouping key.

---

## ORDER BY

- No `AS alias` in ORDER BY items — `ORDER BY n.prop DESC` not `ORDER BY n.prop AS p DESC`
- No `NULLS LAST` / `NULLS FIRST` — SQL syntax; nulls sort last ascending / first descending by default
- After aggregation, sort by the RETURN alias, not the pre-aggregation variable

```cypher
// DO:
CYPHER 25
MATCH (p:Person)-[:ACTED_IN]->(m:Movie)
RETURN p.name, count(m) AS movies
ORDER BY movies DESC, p.name ASC
LIMIT 10
```

---

## Conditional Expressions

```cypher
// Generic CASE (if-elseif-else)
CYPHER 25
MATCH (n:Movie)
RETURN n.title,
  CASE
    WHEN n.rating >= 8 THEN 'great'
    WHEN n.rating >= 6 THEN 'good'
    ELSE 'skip'
  END AS verdict

// Simple CASE (switch on one expression)
RETURN n.status,
  CASE n.status
    WHEN 'A' THEN 'Active'
    WHEN 'I' THEN 'Inactive'
    ELSE 'Unknown'
  END AS label
```

No `least()` / `greatest()` — use `CASE WHEN a < b THEN a ELSE b END`.

Conditional counting — `count(x WHERE ...)` is SQL, not Cypher:
```cypher
// DO:
sum(CASE WHEN r.rating = 5 THEN 1 ELSE 0 END) AS fiveStarCount
COUNT { MATCH (r:Review) WHERE r.rating = 5 } AS fiveStarCount
```

---

## Null Handling

```cypher
WHERE n.email IS NOT NULL     // correct
WHERE n.email = null          // always null, never matches

// coalesce() -- returns first non-null argument
RETURN coalesce(n.nickname, n.name) AS displayName
```

`collect()` and aggregation functions ignore null values. `null = null` is `null` (not `true`). `WHERE` treats `null` as `false`.

---

## Type Coercion

Prefer **OrNull variants** — return `null` on unconvertible input instead of throwing [2025.01; pre-2025 base forms throw]:

```cypher
toIntegerOrNull(n.score)
toFloatOrNull(n.score)
toBooleanOrNull(n.flag)
toStringOrNull(n.value)
```

Type predicates for mixed-type properties: [2025.01]
```cypher
MATCH (n:Event)
WHERE n.value IS :: INTEGER NOT NULL  // true only for non-null INTEGER values
RETURN n.name, n.value
```

**DateTime vs date() mismatch**: `datetime_prop >= date('2025-01-01')` returns 0 rows — use `.year` accessor or `datetime()` literals for `ZONED DATETIME` properties.

**GQL compliance aliases [2026.02–04]** — valid syntax, but use the Cypher form in new code:
| GQL alias | Cypher equivalent |
|---|---|
| `FOR x IN list` | `UNWIND list AS x` |
| `PROPERTY_EXISTS(n, 'prop')` | `n.prop IS NOT NULL` |
| `n IS [NOT] LABELED Label` | `n:Label` / `NOT n:Label` |
| `FILTER` | `WHERE` |
| `LET x = expr` | `WITH expr AS x` |
| GQL function aliases `[2026.02]`: `ceiling`, `ln`, `local_time`, `local_datetime`, `zoned_time`, `zoned_datetime`, `duration_between`, `path_length`, `collect_list`, `percentile_cont`, `percentile_disc`, `stdev_samp`, `stdev_pop` | `ceil`, `log`, `localtime`, `localdatetime`, `time`, `datetime`, `duration.between`, `length`, `collect`, `percentileCont`, `percentileDisc`, `stDev`, `stDevP` |

---

## List Expressions

```cypher
[x IN list WHERE x > 0]                    // filter only
[x IN list | x * 2]                        // transform only
[x IN list WHERE x > 0 | x * 2]           // filter + transform

ANY(x IN list WHERE x > 0)
ALL(x IN list WHERE x > 0)
NONE(x IN list WHERE x > 0)
SINGLE(x IN list WHERE x > 0)

size(list)
head(list) / tail(list) / last(list)
list[0..3]                                  // slice
list + [newElement]
coll.sort(list)                             // [2025.01] native — replaces apoc.coll.sort()
```

`2 IN [1, null, 3]` returns `null` — guard with `IS NOT NULL` before membership tests.

**Pattern comprehension:**
```cypher
MATCH (n:Person {id: $id})
RETURN [(n)-[:KNOWS]->(f:Person) | f.name] AS friends,
       [(n)-[:ACTED_IN]->(m:Movie) WHERE m.year > 2020 | m.title] AS recentFilms
```

Use pattern comprehensions for simple one-hop inline collections; for multi-step traversals use `COLLECT { MATCH ... RETURN ... }`.

---

## String Functions

```cypher
toLower(s) / toUpper(s)                    // case conversion (lower/upper are GQL aliases) [2025.01: lower()/upper() added as aliases]
trim(s) / ltrim(s) / rtrim(s)             // strip whitespace; btrim(s, 'xy') strips custom chars [2025.01: btrim]
split(s, delimiter)                         // returns LIST<STRING>
substring(s, start, length)                // 0-indexed; length optional
left(s, n) / right(s, n)                   // first/last n characters
replace(s, search, replacement)            // replace all occurrences
size(s)                                     // character count (same as char_length)
reverse(s)                                  // reverse string
toString(x) / toStringOrNull(x)            // convert any type to STRING
string.indexOf(input, value)                // index of first match, -1 if absent [2026.05, Cypher 25]
string.join(list, delimiter)                // join LIST<STRING> with delimiter [2026.05, Cypher 25]
string.regexReplace(original, regex, repl)  // regex replace all matches [2026.05, Cypher 25]
```

All string functions return `null` when any argument is `null`.

---

## Introspection Functions

```cypher
labels(n)            // LIST<STRING> of all labels
type(r)              // STRING relationship type name
keys(n)              // LIST<STRING> of property keys
properties(n)        // MAP of all properties
elementId(n)         // STRING internal ID [replaces deprecated id(n) — pre-2025 models generate id()]
```

---

## FOREACH vs UNWIND

| Use | When |
|---|---|
| `FOREACH (x IN list \| write-clause)` | Side-effect writes only — no RETURN needed |
| `UNWIND list AS x` | Need to read, filter, or return list items |

`FOREACH` cannot be followed by `RETURN` or `WITH`. When in doubt, use `UNWIND`.

```cypher
// FOREACH -- side-effect only
CYPHER 25
MATCH p = (a:Person {name:'Alice'})-[:KNOWS*1..3]->(b:Person)
FOREACH (n IN nodes(p) | SET n.visited = true)

// UNWIND -- when you need to process and return
CYPHER 25
UNWIND $items AS item
WITH item WHERE item.active = true
MERGE (n:Item {id: item.id})
  ON CREATE SET n.name = item.name
RETURN count(n) AS created
```

---

## OPTIONAL MATCH

Returns `null` for the optional pattern rather than eliminating the row.

```cypher
CYPHER 25
MATCH (p:Person {id: $id})
OPTIONAL MATCH (p)-[:MANAGES]->(d:Department)
RETURN p.name, d.name AS department    // d.name is null when no match

// Boolean check -- use EXISTS instead of OPTIONAL MATCH
RETURN p.name, EXISTS { (p)-[:MANAGES]->() } AS isManager
```

Do NOT chain multiple `OPTIONAL MATCH` for nested optional data — each fan-out multiplies row count. Use `COLLECT {}` instead.

---

## UNION and UNION ALL

`UNION` deduplicates (slow). `UNION ALL` keeps all rows (fast). Both branches must return identical column names and count.

```cypher
CYPHER 25                              // prefix only on first branch
MATCH (n:Employee) RETURN n.name AS name, n.email AS email
UNION ALL
MATCH (n:Contractor) RETURN n.name AS name, n.email AS email
```

`SHOW` commands cannot be combined with `UNION`. Never repeat `CYPHER 25` on subsequent branches.

---

## Spatial / Point

```cypher
// Create a point (WGS84 geographic)
point({longitude: -122.4194, latitude: 37.7749})               // 2D
point({longitude: -122.4194, latitude: 37.7749, height: 100})  // 3D

// Create a point (Cartesian)
point({x: 1.5, y: 2.3})             // 2D cartesian
point({x: 1.5, y: 2.3, z: 4.0})    // 3D cartesian

// Store on node
MATCH (p:Location {id: $id})
SET p.coords = point({longitude: $lon, latitude: $lat})

// Distance in metres
MATCH (a:Location) WHERE a.name = 'HQ'
MATCH (b:Location)
RETURN b.name, point.distance(a.coords, b.coords) AS distM
ORDER BY distM LIMIT 10

// Bounding-box filter before distance (uses POINT index)
MATCH (b:Location)
WHERE point.withinBBox(b.coords,
        point({longitude: -123.0, latitude: 37.0}),
        point({longitude: -122.0, latitude: 38.0}))
RETURN b.name, point.distance(b.coords, $origin) AS distM
```

POINT index (required for fast spatial queries):
```cypher
CREATE POINT INDEX location_coords IF NOT EXISTS
FOR (n:Location) ON (n.coords)
```

Point components: `.x` / `.y` / `.z` (Cartesian) and `.longitude` / `.latitude` / `.height` (WGS84).

---

## Date and Time

```cypher
date()                               // DATE
datetime()                           // ZONED DATETIME
localdatetime()                      // LOCAL DATETIME
localtime()                          // LOCAL TIME

date('2025-01-15')
datetime('2025-01-15T10:30:00+02:00')
duration({days: 7, hours: 2})

n.birthDate.year / .month / .day
n.createdAt.hour / .minute / .second / .timezone

date() + duration({months: 3})
duration.between(date1, date2)
date.truncate('month', date())        // first day of current month
```

Type rule: `ZONED DATETIME` properties must be compared with `datetime()` literals, not `date()` — mixing types returns 0 rows.

Duration components: `.years`, `.months`, `.days`, `.hours`, `.minutes`, `.seconds` — `.inDays` / `.inMonths` / `.inSeconds` do NOT exist.

---

## LOAD CSV

```cypher
// With headers
CYPHER 25
LOAD CSV WITH HEADERS FROM 'file:///persons.csv' AS row
MERGE (p:Person {id: toInteger(row.id)})
SET p.name = row.name, p.score = toFloat(row.score)

// Large files -- always wrap in CALL IN TRANSACTIONS
CYPHER 25
LOAD CSV WITH HEADERS FROM 'file:///large.csv' AS row
CALL (row) {
  MERGE (p:Person {id: row.id})
  SET p += row
} IN TRANSACTIONS OF 1000 ROWS ON ERROR CONTINUE
```

All CSV fields are `STRING` — coerce explicitly. `PERIODIC COMMIT` deprecated; use `CALL IN TRANSACTIONS`.

---

## Subqueries [2025.01]

**Expression subqueries** (auto-import outer variables — no `WITH` needed):

```cypher
EXISTS { (a)-[:R]->(b) }
EXISTS { MATCH (a)-[:R]->(b) WHERE a.x > 0 }
NOT EXISTS { (a)-[:R]->(b) }
COUNT  { (a)-[:R]->(b) WHERE a.x > 0 }
COLLECT { MATCH (a)-[:R]->(b) RETURN b.name }   // COLLECT: full MATCH+RETURN required
// COLLECT { (a)-[:R]->(b) }                    // SYNTAX ERROR -- bare pattern invalid
```

`COLLECT {}` returns exactly one column.

**`CALL` subqueries** — outer variables NOT auto-imported; declare explicitly in `CALL (x) { ... }`:

```cypher
CYPHER 25
MATCH (p:Person)
CALL (p) {
  MATCH (p)-[:ACTED_IN]->(m:Movie)
  RETURN count(m) AS movieCount
}
RETURN p.name, movieCount
// CALL (*) imports all outer variables; CALL () imports nothing
// CALL { WITH x ... } deprecated [pre-2025 form] -- use CALL (x) { ... } [2025.01]
```

| Goal | Use |
|---|---|
| Boolean existence check | `EXISTS { (a)-[:R]->(b) }` |
| Count matching subgraph | `COUNT { (a)-[:R]->(b) }` |
| Collect related items into a list | `COLLECT { MATCH (a)-[:R]->(b) RETURN b.name }` |
| Nullable join | `OPTIONAL MATCH` (simple) or `OPTIONAL CALL` (complex) |
| Subquery with own aggregation or writes | `CALL (x) { ... }` |

---

## Quantified Path Expressions (QPEs) [2025.01 — replaces shortestPath()/allShortestPaths() and `[:R*m..n]` syntax]

```cypher
// Reachability: 1-3 hops with relationship predicate
CYPHER 25
MATCH (start:Person {name: 'Alice'})
      (()-[rel:KNOWS WHERE rel.since > date('2024-01-01')]->(:Person)){1,3}
      (end)
WITH DISTINCT end
RETURN end.name

// Inner variables become lists -- access with list comprehension
CYPHER 25
MATCH (src:Person {name: 'Alice'})
      ((n:Person)-[:KNOWS]->()){1,3}(dst:Person)
RETURN [x IN n | x.name] AS via, dst.name AS reached
```

Syntax rules:
- Prefer `{1,}` over `+`, `{0,}` over `*`
- Quantifier goes **outside** the group: `(pattern){N,M}`
- Groups must start AND end with a node

Match modes [2025.01] (immediately after `MATCH`):

| Mode | Semantics |
|---|---|
| `DIFFERENT RELATIONSHIPS` | Default — each relationship traversed at most once per path |
| `REPEATABLE ELEMENTS` | Nodes AND relationships may be revisited; requires bounded `{m,n}` |
| `ACYCLIC` [2026.03] | No repeated nodes within a path; GQL path mode — prevents cycles |

`ACYCLIC` is placed before the path pattern: `MATCH p = ACYCLIC (a)-[:R]-+(b)`.  
Nodes cannot repeat within a path; may still repeat across paths (equijoins work).

Path selectors (immediately after `MATCH`, before the pattern):

| Selector | Semantics |
|---|---|
| `SHORTEST 1` | One shortest path |
| `ALL SHORTEST` | All shortest paths of equal minimum length |
| `ANY` | Any single path (no length guarantee) |
| `SHORTEST k GROUPS` | All paths grouped by length up to k distinct lengths |

Path modes combine with shortest selectors [2026.05]: `MATCH ANY SHORTEST ACYCLIC (a)-[:R]-+(b)` — `ACYCLIC` valid with `ANY SHORTEST`, `SHORTEST k`, `ALL SHORTEST`, `SHORTEST k GROUPS`.

```cypher
CYPHER 25 MATCH SHORTEST 1 (a:Person {name:'Alice'})(()-[:KNOWS]->()){1,}(b:Person {name:'Bob'})
RETURN b.name
```

---

## Dynamic Labels and Properties [2025.01]

```cypher
// Filter by dynamic label
CYPHER 25
MATCH (n)
WHERE n:$($label)
RETURN n

// Set label dynamically
CYPHER 25
MATCH (n:Pending)
SET n:$(n.category)

// Dynamic property key -- bracket notation required
CYPHER 25
MATCH (n:Config)
RETURN n[$key]

MATCH (n:Config {id: $id})
SET n[$key] = $value
// DON'T: SET n.$key = $value     // SyntaxError

// Copy properties between elements
SET n = properties(r)
// DON'T: SET n = r               // TypeError -- assigns reference, not properties
```

---

## SEARCH Clause (Vector/Fulltext Search) [2026.01]

```cypher
// Node vector index
CYPHER 25
MATCH (c:Chunk)
SEARCH c IN (VECTOR INDEX news FOR $embedding LIMIT 10)
SCORE AS score
WHERE score > 0.8
RETURN c.text, score
ORDER BY score DESC

// Procedure fallback (pre-2026.01):
CYPHER 25 CALL db.index.vector.queryNodes('news', 10, $embedding) YIELD node AS c, score RETURN c.text, score

// Fulltext -- always use procedure regardless of version:
CYPHER 25 CALL db.index.fulltext.queryNodes('entity', $query) YIELD node, score RETURN node.name, score LIMIT 20
```

SEARCH syntax: binding variable only (not `(c)`); `LIMIT` inside parens; `SCORE AS` after closing paren.

---

## CALL IN TRANSACTIONS (write batching only) [2025.01: CONCURRENT, REPORT STATUS added; PERIODIC COMMIT removed]

Input stream must be **outside** the subquery — filtering inside collapses everything into one transaction.

```cypher
// Basic batch update
CYPHER 25
MATCH (c:Customer)
CALL (c) {
  SET c.flag = 'done'
} IN TRANSACTIONS OF 1000 ROWS
RETURN count(c)

// With error handling and status reporting
CYPHER 25
LOAD CSV WITH HEADERS FROM 'file:///data.csv' AS row
CALL (row) {
  MERGE (p:Person {id: row.id})
    ON CREATE SET p.name = row.name
} IN TRANSACTIONS OF 500 ROWS
  ON ERROR CONTINUE
  REPORT STATUS AS s
WITH s WHERE s.errorMessage IS NOT NULL
RETURN s.transactionId, s.errorMessage

// Parallel batches
CYPHER 25
UNWIND $rows AS row
CALL (row) {
  MERGE (:Movie {id: row.id})
} IN 4 CONCURRENT TRANSACTIONS OF 10 ROWS
  ON ERROR CONTINUE
```

`IN TRANSACTIONS` comes **after** the `{ }` block. Read-only use prohibited. Requires auto-commit — do not wrap in `beginTransaction()`.

**ON ERROR options**: `FAIL` (default) | `CONTINUE` (skip failed batch) | `BREAK` (stop after first error) | `RETRY FOR N SECS` [2025.03+]

---

## Conditional CALL Subqueries (WHEN…THEN…ELSE) [2025.06 / Neo4j 2025.06+]

If-else-if semantics in a single subquery block. Replaces multiple independent `CALL` blocks or complex `CASE` with side effects.

```cypher
// Move a linked-list item: insert before/after depending on context
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

Rules:
- Branches receive only params declared in `CALL(params)`
- Mutually exclusive — first matching WHEN wins
- Each branch can contain full write clauses; `ELSE` is optional
- Cannot mix `WHEN...THEN` and regular subquery body in same `CALL`

---

## Label Pattern Expressions [Neo4j 5+]

Boolean logic on labels using `|` (OR), `&` (AND), `!` (NOT):

```cypher
// Nodes with label A OR B
MATCH (n:Person|Organization) RETURN n

// Nodes with label A AND B
MATCH (n:Employee&Manager) RETURN n

// Nodes with label A but NOT B
MATCH (n:Person&!VIP) RETURN n

// Complex expression
MATCH (n:Marvel|(DCComics&!Batman)) RETURN n
```

Dynamic label quantifiers in MATCH (require `$()` wrapper) [2025.01]:
```cypher
// Node must have ALL labels in the list
MATCH (n:$all($labelList)) RETURN n

// Node must have ANY label in the list
MATCH (n:$any($labelList)) RETURN n
```

---

## Compact CASE WHEN [Neo4j 5+]

Multiple values and comparison operators in a single WHEN branch.

```cypher
// Multiple values in WHEN (simple CASE)
MATCH (n:Event)
RETURN CASE n.dayOfWeek
  WHEN 1, 7 THEN 'weekend'
  WHEN 2, 3, 4, 5, 6 THEN 'weekday'
  ELSE 'unknown'
END AS dayType

// Comparison operators in WHEN (generic CASE)
RETURN CASE n.age
  WHEN > 65 THEN 'senior'
  WHEN > 18 THEN 'adult'
  WHEN < 0  THEN 'invalid'
  ELSE 'minor'
END AS ageGroup
```

---

## String Normalization [Neo4j 5+]

`normalize(s)` converts to NFC Unicode — solves accented character comparison where identical glyphs have different code points:

```cypher
// Match regardless of Unicode encoding differences (e.g., 'ö' as U+00F6 vs o + combining diacritic)
MATCH (c:City)
WHERE normalize(c.name) = normalize($cityName)
RETURN c

// Index on normalized form for consistent lookups
CREATE RANGE INDEX city_name IF NOT EXISTS FOR (c:City) ON (c.normalizedName)
MATCH (c:City) SET c.normalizedName = normalize(c.name)
```

---

## allReduce Function (Traversal State) [CYPHER 25]

Accumulates state during QPE traversal — mid-traversal filtering and stateful path constraints. Prunes invalid paths inline instead of post-filtering.

```cypher
// Syntax: allReduce(accumulator = initial, var IN list | updateExpr, predicate)
// Returns true only if predicate holds for every intermediate accumulator value

// Example: track visited small nodes, require no revisits
CYPHER 25
MATCH REPEATABLE ELEMENTS path = (:Start)((xs:!End)--(:!Start)){0,100}(e:End)
WHERE allReduce(
  visited = [],
  x IN xs | CASE WHEN x:Big THEN visited ELSE visited + [x] END,
  size(visited) <= size(apoc.coll.toSet(visited)) + 1
)
RETURN count(path)

// Example: stateful battery charge simulation during route traversal
CYPHER 25 runtime=parallel
MATCH REPEATABLE ELEMENTS p=(a:Geo {name: $src})(()-[r:ROAD|CHARGE]-(x:Geo)){1,12}(b:Geo {name: $dst})
WHERE allReduce(
  curr = {soc: $initial_soc, mins: 0.0},
  r IN relationships(p) |
    CASE
      WHEN r:ROAD   THEN {soc: curr.soc - r.drain,   mins: curr.mins + r.drive_mins}
      WHEN r:CHARGE THEN {soc: curr.soc + r.charge,  mins: curr.mins + r.charge_mins}
    END,
  $min_soc <= curr.soc <= $max_soc AND curr.mins <= $max_mins
)
RETURN p, reduce(d=0, r IN relationships(p) | d + r.drive_mins) AS total_mins
ORDER BY total_mins LIMIT 1
```

`allReduce` is evaluated inline during path expansion — prunes branches early rather than filtering after full traversal.

---

## NEXT Clause [CYPHER 25]

Chains query blocks without re-traversal; each block adds computed columns:

```cypher
CYPHER 25
MATCH (a:Airport {iata: $src})-[r:FLIGHT]->(b:Airport {iata: $dst})
RETURN a, b, r
NEXT
RETURN a, b, r, r.duration + r.layover AS totalTime
ORDER BY totalTime ASC LIMIT 5
```
