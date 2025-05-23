from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from infrahub.core.constants import RelationshipCardinality
from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes, NonGenericSchemaTypes
    from infrahub.database import InfrahubDatabase

    from ..model import RelationshipManager


@dataclass
class NodeToValidate:
    uuid: str
    relative_uuids: list[str]
    schema: NonGenericSchemaTypes


class RelationshipPeerRelativesConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    async def _check_relationship_peers_relatives(
        self,
        relm: RelationshipManager,
        node_schema: MainSchemaTypes,
        peers: Mapping[str, Node],
        relationship_name: str,
    ) -> None:
        """Validate that all peers of a given `relm` have the same set of relatives (aka peers) for the given `relationship_name`."""
        nodes_to_validate: list[NodeToValidate] = []

        for peer in peers.values():
            peer_schema = peer.get_schema()

            # FIXME: this should be part of the schema validation process
            if relationship_name not in peer_schema.relationship_names:
                raise ValidationError(
                    f"Peer {peer.id} of '{relm.name}' does not have a '{relationship_name}' relationship"
                )

            peer_relm: RelationshipManager = getattr(peer, relationship_name)
            peer_relm_peers = await peer_relm.get_peers(db=self.db)

            nodes_to_validate.append(
                NodeToValidate(
                    uuid=peer.id, relative_uuids=[n.id for n in peer_relm_peers.values()], schema=peer_schema
                )
            )

        relative_uuids = nodes_to_validate[0].relative_uuids
        for node in nodes_to_validate[1:]:
            if node.relative_uuids != relative_uuids:
                raise ValidationError(
                    f"Node {node.uuid} of '{node_schema.kind}.{relm.name}' has different peers for its "
                    f"'{node.schema.kind}.{relationship_name}' relationship compared to other nodes"
                )

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes) -> None:
        if relm.schema.cardinality != RelationshipCardinality.MANY or not relm.schema.common_relatives:
            return

        peers = await relm.get_peers(db=self.db)
        if not peers:
            return

        for rel_name in relm.schema.common_relatives:
            await self._check_relationship_peers_relatives(
                relm=relm, node_schema=node_schema, peers=peers, relationship_name=rel_name
            )
