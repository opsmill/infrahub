from dataclasses import dataclass

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetInfoQuery
from infrahub.core.schema import MainSchemaTypes
from infrahub.core.schema.generic_schema import GenericSchema
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


class RelationshipPeerKindConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @staticmethod
    def _build_error(name: str, kind: str, peer_id: str, allowed_kinds: list[str]) -> ValidationError:
        return ValidationError(
            {name: f"{kind} - {peer_id} cannot be added to relationship, must be of type: {allowed_kinds}"}
        )

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:  # noqa: ARG002
        branch = await registry.get_branch(db=self.db) if not self.branch else self.branch
        peer_schema = registry.schema.get(name=relm.schema.peer, branch=branch, duplicate=False)
        if isinstance(peer_schema, GenericSchema):
            allowed_kinds = peer_schema.used_by
        else:
            allowed_kinds = [peer_schema.kind]
        relationships = await relm.get_relationships(db=self.db, force_refresh=False)
        if not relationships:
            return

        errors: list[ValidationError] = []
        # A peer that is already in hand states its own kind, only the ones named by an id are read.
        peer_ids_to_read: list[str] = []
        for relationship in relationships:
            peer_id = relationship.peer_id
            if peer_id is None:
                continue
            peer_kind = relationship.get_concrete_peer_kind()
            if peer_kind is None:
                peer_ids_to_read.append(peer_id)
            elif peer_kind not in allowed_kinds:
                errors.append(
                    self._build_error(name=relm.name, kind=peer_kind, peer_id=peer_id, allowed_kinds=allowed_kinds)
                )

        if peer_ids_to_read:
            peers_query = await NodeListGetInfoQuery.init(db=self.db, branch=branch, ids=peer_ids_to_read)
            await peers_query.execute(db=self.db)

            async for peer_node in peers_query.get_nodes(db=self.db, duplicate=False):
                if not peer_node.schema:
                    raise ValueError(f"Cannot identify schema for node {peer_node.node_uuid}")
                if peer_node.schema.kind not in allowed_kinds:
                    errors.append(
                        self._build_error(
                            name=relm.name,
                            kind=peer_node.schema.kind,
                            peer_id=peer_node.node_uuid,
                            allowed_kinds=allowed_kinds,
                        )
                    )

        if not errors:
            return

        raise ValidationError(errors)
