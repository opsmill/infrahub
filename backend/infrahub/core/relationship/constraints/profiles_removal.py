from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import PROFILES_RELATIONSHIP_NAME, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship.model import Relationship
from infrahub.core.schema import NodeSchema, ProfileSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class RelationshipProfileRemovalConstraint(RelationshipManagerConstraintInterface):
    """Constraint that validates removing profiles from a node doesn't violate required relationships.

    This runs in two cases:
    1. When a node's `profiles` relationship is changed.
    2. When a profile's `related_nodes` relationship is changed.

    In both cases, it will perform checks only if peers are being removed from the relationship being changed.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch
        self.schema_branch = registry.schema.get_schema_branch(branch.name if branch else registry.default_branch)

    def _get_required_attributes_names(self, schema: NodeSchema) -> set[str]:
        attr_names: set[str] = set()
        for attr_schema in schema.attributes:
            if not attr_schema.optional and schema.check_if_attr_supports_profiles(attribute_schema=attr_schema):
                attr_names.add(attr_schema.name)
        return attr_names

    def _get_required_relationship_names(self, schema: NodeSchema) -> set[str]:
        rel_names: set[str] = set()
        for rel_schema in schema.relationships:
            if rel_schema.support_profiles and not rel_schema.optional:
                rel_names.add(rel_schema.name)
        return rel_names

    async def _validate_profile_removal(
        self,
        node: Node,
        profile_id: str,
        required_attr_names: set[str],
        required_rel_names: set[str],
        peer_profile_ids_by_rel_name: dict[str, set[str]],
    ) -> None:
        for attr_name in required_attr_names:
            attr = node.get_attribute(name=attr_name)
            if attr.is_from_profile and attr.source_id == profile_id:
                node_display_label = await node.get_display_label(db=self.db)
                node_reference = f"node '{node_display_label}' (ID: {node.get_id()})"
                raise ValidationError(
                    f"Cannot remove profile '{profile_id}' because {node_reference} "
                    f"inherits required attribute '{attr_name}' from this profile."
                )

        for rel_name in required_rel_names:
            if profile_id in peer_profile_ids_by_rel_name.get(rel_name, set()):
                node_display_label = await node.get_display_label(db=self.db)
                node_reference = f"node '{node_display_label}' (ID: {node.get_id()})"
                raise ValidationError(
                    f"Cannot remove profile '{profile_id}' because {node_reference} "
                    f"inherits required relationship '{rel_name}' from this profile."
                )

    async def _get_peer_profile_ids(self, node: Node, rel_names: set[str]) -> dict[str, set[str]]:
        peer_profile_ids: dict[str, set[str]] = {}
        for rel_name in rel_names:
            relationships = await node.get_relationship(name=rel_name).get_relationships(db=self.db)
            peer_profile_ids[rel_name] = {str(rel.profile_id) for rel in relationships if rel.is_from_profile}
        return peer_profile_ids

    async def _get_peer_profile_ids_by_node(
        self, schema: NodeSchema, node_ids: list[str], rel_names: set[str], at: Timestamp
    ) -> dict[str, dict[str, set[str]]]:
        branch = await registry.get_branch(db=self.db, branch=self.branch)
        peer_profile_ids: dict[str, dict[str, set[str]]] = defaultdict(dict)
        for rel_name in rel_names:
            query = await RelationshipGetPeerQuery.init(
                db=self.db,
                branch=branch,
                at=at,
                source_ids=node_ids,
                source_kind=schema.kind,
                schema=schema.get_relationship(name=rel_name),
                rel=Relationship,
                include_metadata=MetadataOptions.SOURCE,
            )
            await query.execute(db=self.db)
            for peer in query.get_peers():
                if peer.is_from_profile:
                    peer_profile_ids[str(peer.source_id)].setdefault(rel_name, set()).add(str(peer.profile_id))
        return peer_profile_ids

    async def _validate_nodes_profile_removal(self, node_ids: list[str], profile_id: str, schema: NodeSchema) -> None:
        required_attr_names = self._get_required_attributes_names(schema=schema)
        required_rel_names = self._get_required_relationship_names(schema=schema)
        if not required_attr_names and not required_rel_names:
            return

        at = Timestamp()
        nodes = await NodeManager.get_many(
            db=self.db, branch=self.branch, ids=node_ids, at=at, include_metadata=MetadataOptions.SOURCE
        )
        peer_profile_ids = await self._get_peer_profile_ids_by_node(
            schema=schema, node_ids=list(nodes), rel_names=required_rel_names, at=at
        )
        for node in nodes.values():
            await self._validate_profile_removal(
                node=node,
                profile_id=profile_id,
                required_attr_names=required_attr_names,
                required_rel_names=required_rel_names,
                peer_profile_ids_by_rel_name=peer_profile_ids.get(node.get_id(), {}),
            )

    async def _check_node_profiles_removal(
        self, relm: RelationshipManager, node_schema: NodeSchema, node: Node
    ) -> None:
        required_attr_names = self._get_required_attributes_names(schema=node_schema)
        required_rel_names = self._get_required_relationship_names(schema=node_schema)
        if not required_attr_names and not required_rel_names:
            return

        relm_update_details = await relm.fetch_relationship_ids(db=self.db, force_refresh=False)
        if not relm_update_details.peer_ids_present_database_only:
            return

        if required_attr_names:
            # Required to get source for attributes
            node = await NodeManager.get_one(
                db=self.db, branch=self.branch, id=node.get_id(), include_metadata=MetadataOptions.SOURCE
            )

        peer_profile_ids = await self._get_peer_profile_ids(node=node, rel_names=required_rel_names)
        for profile_id in relm_update_details.peer_ids_present_database_only:
            await self._validate_profile_removal(
                node=node,
                profile_id=profile_id,
                required_attr_names=required_attr_names,
                required_rel_names=required_rel_names,
                peer_profile_ids_by_rel_name=peer_profile_ids,
            )

    async def _check_profile_related_nodes_removal(
        self, relm: RelationshipManager, profile_schema: ProfileSchema, profile: Node
    ) -> None:
        relm_update_details = await relm.fetch_relationship_ids(db=self.db, force_refresh=False)
        if not relm_update_details.peer_ids_present_database_only:
            return

        target_kind = profile_schema.get_relationship(name="related_nodes").peer
        target_schema = self.schema_branch.get_node(name=target_kind, duplicate=False)
        await self._validate_nodes_profile_removal(
            node_ids=relm_update_details.peer_ids_present_database_only,
            profile_id=profile.get_id(),
            schema=target_schema,
        )

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:
        if relm.name == PROFILES_RELATIONSHIP_NAME and isinstance(node_schema, NodeSchema):
            await self._check_node_profiles_removal(relm=relm, node_schema=node_schema, node=node)
            return

        if relm.name == "related_nodes" and isinstance(node_schema, ProfileSchema):
            await self._check_profile_related_nodes_removal(relm=relm, profile_schema=node_schema, profile=node)
            return

    async def validate_profile_deletion(self, profile: Node, profile_schema: ProfileSchema) -> None:
        related_nodes_rels = await profile.related_nodes.get_relationships(db=self.db)  # type: ignore[attr-defined]
        related_node_ids = [rel.peer_id for rel in related_nodes_rels if rel.peer_id]

        if not related_node_ids:
            return

        target_kind = profile_schema.get_relationship(name="related_nodes").peer
        target_schema = self.schema_branch.get_node(name=target_kind, duplicate=False)
        await self._validate_nodes_profile_removal(
            node_ids=related_node_ids, profile_id=profile.get_id(), schema=target_schema
        )
