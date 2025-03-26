from dataclasses import dataclass

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.query.relationship import RelationshipCountPerNodeQuery
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError

from ..model import RelationshipManager
from .interface import RelationshipManagerConstraintInterface


@dataclass
class NodeToValidate:
    uuid: str
    cardinality: RelationshipCardinality
    min_count: int | None = None
    max_count: int | None = None


class RelationshipCountConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes) -> None:  # noqa: ARG002
        branch = await registry.get_branch(db=self.db) if not self.branch else self.branch

        # NOTE adding resolve here because we need to retrieve the real ID
        # but if the validation fails we'll end up with some allocated resources that are not being used
        await relm.resolve(db=self.db)

        nodes_to_validate: list[NodeToValidate] = []

        # peer_ids_present_local_only:
        #    new relationship, need to check if the schema on the other side has a max_count defined
        # peer_ids_present_database_only:
        #    relationship to be deleted, need to check if the schema on the other side has a min_count defined
        # TODO see how to manage Generic node
        peer_schema = registry.schema.get(name=relm.schema.peer, branch=branch)
        peer_rels = peer_schema.get_relationships_by_identifier(id=relm.schema.get_identifier())
        if not peer_rels:
            return

        update_details = await relm.fetch_relationship_ids(db=self.db, force_refresh=False)
        for peer_rel in peer_rels:
            # If a relationship is directional and both have the same direction they can't work together
            if relm.schema.direction == peer_rel.direction and peer_rel.direction != RelationshipDirection.BIDIR:
                continue

            for peer_id in update_details.peer_ids_present_local_only + update_details.peer_ids_present_database_only:
                if peer_rel.max_count and peer_id in update_details.peer_ids_present_local_only:
                    nodes_to_validate.append(
                        NodeToValidate(uuid=peer_id, max_count=peer_rel.max_count, cardinality=peer_rel.cardinality)
                    )

                if peer_rel.min_count and peer_id in update_details.peer_ids_present_database_only:
                    nodes_to_validate.append(
                        NodeToValidate(uuid=peer_id, min_count=peer_rel.min_count, cardinality=peer_rel.cardinality)
                    )

        query = await RelationshipCountPerNodeQuery.init(
            db=self.db,
            node_ids=[node.uuid for node in nodes_to_validate],
            identifier=relm.schema.identifier,
            direction=relm.schema.direction.neighbor_direction,
            branch=branch,
        )
        await query.execute(db=self.db)
        count_per_peer = await query.get_count_per_peer()

        # Need to adjust the number based on what we will add / remove
        #  +1 for max_count
        #  -1 for min_count
        for node in nodes_to_validate:
            if node.max_count and count_per_peer[node.uuid] + 1 > node.max_count:
                raise ValidationError(
                    f"Node {node.uuid} has {count_per_peer[node.uuid] + 1} peers "
                    f"for {relm.schema.identifier}, maximum of {node.max_count} allowed",
                )
            if node.min_count and count_per_peer[node.uuid] - 1 < node.min_count:
                raise ValidationError(
                    f"Node {node.uuid} has {count_per_peer[node.uuid] - 1} peers "
                    f"for {relm.schema.identifier}, no fewer than {node.min_count} allowed",
                )
