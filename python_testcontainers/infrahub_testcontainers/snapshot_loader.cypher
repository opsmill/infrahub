// Seed an empty Neo4j with the committed Infrahub core-bootstrap snapshot so the booting server
// skips first-time initialization. Streamed from the gzip JSON artifact with apoc (no Cypher-literal
// parsing), replaying the same shape as the in-process restore: a temporary `_SnapshotNode` label +
// index lets edges be matched by list position, then the temporary label/property/index are dropped.
CREATE INDEX snapshot_restore_idx IF NOT EXISTS FOR (n:`_SnapshotNode`) ON (n._snapshot_idx);
CALL db.awaitIndexes(300);
CALL apoc.load.json('file:///core_bootstrap.json.gz', null, {compression: 'GZIP'}) YIELD value
UNWIND range(0, size(value.nodes) - 1) AS i
WITH value.nodes[i] AS node, i
CALL apoc.create.node(node.labels + ['_SnapshotNode'], apoc.map.setKey(node.properties, '_snapshot_idx', i)) YIELD node AS n
RETURN count(n);
CALL apoc.load.json('file:///core_bootstrap.json.gz', null, {compression: 'GZIP'}) YIELD value
UNWIND value.edges AS edge
MATCH (a:`_SnapshotNode` {_snapshot_idx: edge.from}), (b:`_SnapshotNode` {_snapshot_idx: edge.to})
CALL apoc.create.relationship(a, edge.type, edge.properties, b) YIELD rel
RETURN count(rel);
MATCH (n:`_SnapshotNode`) CALL (n) { REMOVE n:`_SnapshotNode` REMOVE n._snapshot_idx } IN TRANSACTIONS OF 10000 ROWS;
DROP INDEX snapshot_restore_idx IF EXISTS;
