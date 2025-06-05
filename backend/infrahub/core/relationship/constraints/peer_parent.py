from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase

    from ..model import RelationshipManager


class RelationshipPeerParentConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    async def _check_relationship_peers_parent(
        self, relm: RelationshipManager, parent_rel_name: str, node: Node, peers: Mapping[str, Node]
    ) -> None:
        """Validate that all peers of a given `relm` have the same parent for the given `relationship_name`."""
        node_parent = await node.get_parent_relationship_peer(db=self.db, name=parent_rel_name)
        if not node_parent:
            # If the schema is properly validated we are not expecting this to happen
            raise ValidationError(f"Node {node.id} ({node.get_kind()}) does not have a parent peer")

        parents: set[str] = {node_parent.id}
        for peer in peers.values():
            parent = await peer.get_parent_relationship_peer(db=self.db, name=parent_rel_name)
            if not parent:
                # If the schema is properly validated we are not expecting this to happen
                raise ValidationError(f"Peer {peer.id} ({peer.get_kind()}) does not have a parent peer")
            parents.add(parent.id)

        if len(parents) != 1:
            raise ValidationError(
                f"All the elements of the '{relm.name}' relationship on node {node.id} ({node.get_kind()}) must have the same parent "
                "as the node"
            )

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:  # noqa: ARG002
        if not relm.schema.common_parent:
            return

        peers = await relm.get_peers(db=self.db)
        if not peers:
            return

        await self._check_relationship_peers_parent(
            relm=relm, parent_rel_name=relm.schema.common_parent, node=node, peers=peers
        )
