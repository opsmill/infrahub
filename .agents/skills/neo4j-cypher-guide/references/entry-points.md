# Branch-Scoped Query Entry Points Reference

## Why the Planner Prefers a Label Scan

Index statistics record how many distinct values the `branch` property has, not how many edges
carry each value. The planner therefore estimates a `{branch: $branch_name}` seek as the edges of
that type divided by the number of `branch` values, even when the branch holds a small fraction of
them. A label scan followed by an expand can then come out cheaper:

- A kind label with few vertices starts the plan on any instance.
- `:Root` on `IS_PART_OF` starts the plan on an instance with few branches, where each `branch`
  value accounts for a large share of the edges. With more branches, the same pattern starts with
  the seek.
- `:Node` starts the plan when the edge type has only two `branch` values, such as `main` and one
  feature branch. With three or more values, `:Node` and `:Attribute` did not start the plan in
  testing.

Neo4j reuses the plan for every value of `$branch_name`. With a small kind label in the pattern,
forcing the seek cut database hits by over 100x on a branch with 25 changed edges, and multiplied
them by about 70x on the default branch. Use the label-free entry for a query that runs on a branch
with few changes, and the `Node(uuid)` entry for a query that can run on the default branch.

## Plan Operators to Check

Run `EXPLAIN`, or `PROFILE` on a realistic dataset, on each query text and read the first operator:

- Only the branch is known: `DirectedRelationshipIndexSeek` or `UndirectedRelationshipIndexSeek`.
  A type union plans one seek per type under a `Union`, followed by a `Distinct`.
- The node uuids are known: `NodeIndexSeek` on `Node(uuid)`.
- `NodeByLabelScan`, or `UnionNodeByLabelsScan` for a label union such as `Attribute|Relationship`,
  means a label replaced the index seek.

## Rules for the Label-Free Entry

- Leave every node in the first `MATCH` unlabelled, including nodes that are not endpoints of the
  indexed edge: a small label on any node of a multi-hop pattern can start the plan.
- Check the labels in a step that the planner does not merge back into the first `MATCH`:
  - `CALL () { ... }` when that step only checks labels. It holds no rows.
  - `WITH DISTINCT` on the start node when a second `MATCH` expands from it, so each start node is
    expanded once.
  - A label check on the first `MATCH`, or after a plain `WITH`, is merged back and brings the
    scan back.
- Put `DISTINCT` on the start node only. `DISTINCT` holds every row it has seen, and over every
  matched edge it held about 13 times the memory of `DISTINCT` on the start node.
- Repeat the indexed edge in the second `MATCH`, so the query returns the same rows as the original
  single `MATCH`.
- Leave out a label that the edge type already implies: `IS_PART_OF` always runs from a `Node` to
  `Root` (`dev/knowledge/backend/database-schema.md`).

## Indexed Edge That Is Not the First Hop

```cypher
MATCH (n)-[:HAS_ATTRIBUTE]->(a)-[:HAS_VALUE {branch: $branch_name}]->()
WITH DISTINCT n
MATCH (root:Root)<-[r_root:IS_PART_OF]-(n)-[:HAS_ATTRIBUTE]->(a:Attribute)
    -[r_value:HAS_VALUE {branch: $branch_name}]->(v:AttributeValue)
```

## Worked Example

The node, field and property path queries of the diff calculation in
`backend/infrahub/core/query/diff.py` build one entry clause per case and follow these rules.

## Adding a `branch` Index

Add a `branch` index for a new edge type to `rel_indexes` in `backend/infrahub/core/graph/index.py`.
New database indexes are on the "Ask First" list in `backend/AGENTS.md`.
