# Cypher Execution Plan Operators — Full Reference

Read plans bottom-up: leaf operators at bottom, `ProduceResults` at top.

**Lazy vs Eager**: Most operators stream rows to parent as produced. Eager operators (marked ✗ below) must consume *all* input before emitting output — they materialise the full row set and can cause OOM on large inputs.

---

## Leaf Operators (data source)

| Operator | Signal | Notes |
|---|---|---|
| `AllNodesScan` | ✗✗ Bad | Scans entire node store. No label → no label index. Add label + property index. |
| `NodeByLabelScan` | ✗ Bad | Scans all nodes of a label. No property index. Add RANGE index. |
| `NodeByIdSeek` | ✓ | Lookup by internal node ID. Fast but fragile — IDs are not stable. Use `elementId()`. |
| `NodeIndexSeek` | ✓ | Equality/range predicate satisfied via RANGE or LOOKUP index. Optimal. |
| `NodeUniqueIndexSeek` | ✓ | Unique constraint index hit. Optimal. |
| `NodeIndexScan` | ~ | Full scan of an index (no predicate selectivity). Faster than label scan; still linear. |
| `NodeIndexContainsScan` | ✓ | TEXT index CONTAINS/STARTS WITH. Requires TEXT index on property. |
| `NodeIndexEndsWithScan` | ✓ | TEXT index ENDS WITH. Requires TEXT index on property. |
| `RelationshipIndexSeek` | ✓ | Relationship property index hit. |
| `RelationshipByIdSeek` | ✓ | Lookup by relationship ID. |
| `DirectedRelationshipByIdSeek` | ✓ | Directed rel by ID. |
| `UndirectedRelationshipByIdSeek` | ~ | Undirected rel scan — matches twice (both directions). |
| `NodeByElementIdSeek` | ✓ | Lookup by `elementId()` string. Preferred over `id()`. |
| `Argument` | — | Passes outer scope variables into subquery. |

---

## Traversal Operators

| Operator | Signal | Notes |
|---|---|---|
| `Expand(All)` | ~ | Traverses all incoming/outgoing rels from a node. Normal. Limit fanout with WHERE/LIMIT. |
| `Expand(Into)` | ~ | Finds rels between two already-matched nodes. Efficient for known endpoints. |
| `OptionalExpand(All)` | ~ | OPTIONAL MATCH equivalent. Returns null row if no match. |
| `OptionalExpand(Into)` | ~ | Optional expand between known endpoints. |
| `VarLengthExpand(All)` | ✗ | Variable-length `(a)-[*1..5]->(b)` — can be expensive. Use QPE patterns or bound depth. |
| `VarLengthExpand(Pruning)` | ~ | Pruned variable-length — avoids re-visiting nodes. Better than All. |
| `BFSPruningVarLengthExpand` | ✓ | BFS-based; used for `SHORTEST` paths. Preferred. |
| `ShortestPath` | ~ | Single shortest path. Replaced by QPE in Cypher 25. |

---

## Join Operators

| Operator | Signal | Notes |
|---|---|---|
| `CartesianProduct` | ✗ Bad | Two unconnected MATCH branches joined without predicate. O(m×n). Add WHERE join. |
| `NodeHashJoin` | ~ | Hash join on node IDs. Eager — builds hash table. Memory-intensive for large inputs. |
| `ValueHashJoin` | ~ | Hash join on arbitrary values (e.g. property equality). Eager. |
| `TriadicSelection` | ✓ | Optimised "friend-of-friend excluding already-known" pattern. |
| `TriadicBuild` / `TriadicFilter` | ✓ | Components of triadic optimisation. |

---

## Filter / Projection Operators

| Operator | Signal | Notes |
|---|---|---|
| `Filter` | ~ | Applies predicate after scan/expand. Non-index-backed predicate. Move to index if possible. |
| `CacheProperties` | ✓ | Caches property values from store to avoid re-reads downstream. |
| `Projection` | — | Evaluates expressions for output columns. |
| `DropResult` | — | Discards results (e.g., write queries where RETURN is absent). |
| `ProduceResults` | — | Root operator — emits final rows to client. |

---

## Aggregation Operators

| Operator | Signal | Notes |
|---|---|---|
| `Aggregation` | ✓ | Streaming aggregation; no full materialisation needed. |
| `EagerAggregation` | ~ | Eager; must see all rows before emitting. Required for ORDER BY + aggregation. |
| `Distinct` | ~ | Deduplication. Eager on large inputs. Use `WITH DISTINCT` to push earlier. |
| `OrderedAggregation` | ✓ | Streaming aggregation when input is pre-sorted. |
| `OrderedDistinct` | ✓ | Streaming dedup when input is pre-sorted. |

---

## Sort / Limit Operators

| Operator | Signal | Notes |
|---|---|---|
| `Sort` | ✗ | Eager full sort — O(n log n). Materialises all rows. Add LIMIT to convert to Top. |
| `Top` | ✓ | Sort+Limit combined — O(n log k). Preferred; only keeps top k in memory. |
| `Top1` | ✓ | Single min/max — O(n). |
| `Limit` | ✓ | Truncates rows non-eagerly. Push as early as possible in the plan. |
| `Skip` | ~ | Offset pagination. Linear scan to skip position. Use keyset pagination for large offsets. |
| `PartialSort` | ~ | Sort within already-grouped prefix. More efficient than full Sort. |
| `PartialTop` | ✓ | Top within grouped prefix. |

---

## Write Operators

| Operator | Notes |
|---|---|
| `Create` | Creates nodes/rels. |
| `Merge` | Merge with lock semantics. Requires constraint for atomicity. |
| `SetProperty` / `SetProperties` | Sets properties. `SetProperties` batch-sets from map. |
| `SetLabels` / `RemoveLabels` | Label mutation. |
| `Delete` | Deletes node (fails if has rels). Use DetachDelete. |
| `DetachDelete` | Deletes node + all its rels. |
| `DeleteRelationship` | Deletes a relationship. |

---

## Control / Subquery Operators

| Operator | Notes |
|---|---|
| `Eager` | ✗✗ — Read/write conflict; materialises all upstream rows. Fix: add labels, collect-then-write, or CALL IN TRANSACTIONS. |
| `Apply` | Correlated subquery execution (CALL (x) { }). One inner execution per outer row. |
| `SemiApply` / `AntiSemiApply` | EXISTS { } / NOT EXISTS { } |
| `Optional` | OPTIONAL MATCH — passes null row if no match. |
| `ConditionalApply` | Subquery executed only if condition holds. |
| `AssertSameNode` | Verifies MERGE did not create duplicate (unique constraint enforcement). |
| `TransactionForeach` | CALL IN TRANSACTIONS outer loop. |
| `TransactionApply` | CALL IN TRANSACTIONS inner execution. |
| `Union` | Combines UNION branches. |
| `LoadCSV` | LOAD CSV row reader. |
| `Foreach` | FOREACH loop (write only, no RETURN). |

---

## Reading the Plan: Worked Example

```
ProduceResults         ← root; read last
  |
  Filter               ← predicate not index-backed
    |
    Expand(All)        ← traversal from matched node
      |
      NodeIndexSeek    ← leaf; read first; index used ✓
```

Index seek is efficient, expand is normal, filter applied after expand (not index-backed). If filter is selective, add a composite index or move the WHERE earlier.

---

## Operator Hints

```cypher
// Force index:
MATCH (p:Person {email: $email})
USING INDEX p:Person(email)
RETURN p

// Force label scan (ignore index):
MATCH (p:Person {active: true})
USING SCAN p:Person
RETURN p

// Force hash join at specific node:
MATCH (a:Author)-[:WROTE]->(b:Book)<-[:REVIEWED]-(r:Reviewer)
USING JOIN ON b
RETURN a.name, r.name

// Force index for relationship property:
MATCH ()-[t:TRANSFER {txId: $id}]->()
USING INDEX t:TRANSFER(txId)
RETURN t
```

Multiple hints can be combined in one query.
