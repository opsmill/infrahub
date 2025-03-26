from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.lock import initialize_lock
from infrahub.log import get_logger

from ... import registry
from ...constants import RelationshipCardinality, RelationshipDirection
from ...initialization import initialization
from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DedupCardinalityOneRelsQuery(Query):
    name = "dedup_cardinality_one_rels"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        """
        Nodes having cardinality one relationship might end up with more than one relationship due to some concurrency
        issue. In that case, this query keeps only the most recent relationship.
        """

        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        rel_one_identifiers_inbound = defaultdict(list)
        rel_one_identifiers_outbound = defaultdict(list)
        for schema_branch in registry.schema._branches.values():
            all_nodes = schema_branch.get_all()
            for node in all_nodes.values():
                for rel in node.relationships:
                    if rel.cardinality == RelationshipCardinality.ONE:
                        if rel.direction == RelationshipDirection.INBOUND:
                            rel_one_identifiers_inbound[node.kind].append(rel.identifier)
                        else:
                            # Outbound or BIDIR. In BIDIR case, we have node1 -> rel_node <- node2,
                            # so an outbound arrow leaves the node.
                            rel_one_identifiers_outbound[node.kind].append(rel.identifier)

        # Two matches: One for outbound, the other for inbound
        # We need to check for node kind otherwise we would not be able to differentiate the `many` side
        # of a one-to-many BIDIR relationship.
        query = """

        CALL {
            MATCH (rel_node: Relationship)-[edge:IS_RELATED]->(n: Node)<-[edge_2:IS_RELATED]-(rel_node_2: Relationship {name: rel_node.name})
            WHERE rel_node.name in $rel_one_identifiers_inbound[n.kind]
                AND edge.branch = edge_2.branch
                and edge.status = "active"
                and edge_2.status = "active"
                and edge.to is NULL
                and edge_2.to is null
                and edge_2.from >= edge.from  // delete the oldest one
            DETACH DELETE rel_node
        }

        CALL {
            MATCH (rel_node_3: Relationship)<-[edge_3:IS_RELATED]-(n: Node)-[edge_4:IS_RELATED]->(rel_node_4: Relationship {name: rel_node_3.name})
            WHERE rel_node_3.name in $rel_one_identifiers_outbound[n.kind]
                AND edge_3.branch = edge_4.branch
                and edge_3.status = "active"
                and edge_4.status = "active"
                and edge_3.to is NULL
                and edge_4.to is null
                and edge_4.from >= edge_3.from  // delete the oldest one
            DETACH DELETE rel_node_3
        }
        """

        params = {
            "rel_one_identifiers_inbound": rel_one_identifiers_inbound,
            "rel_one_identifiers_outbound": rel_one_identifiers_outbound,
        }

        self.params.update(params)
        self.add_to_query(query)


class Migration023(GraphMigration):
    name: str = "dedup_cardinality_one_rels"
    minimum_version: int = 22
    queries: Sequence[type[Query]] = [DedupCardinalityOneRelsQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
