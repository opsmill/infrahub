from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema, ProfileSchema
from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import Relationship, RelationshipManager
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class RelationshipProfileRemovalConstraint(RelationshipManagerConstraintInterface):
    """Constraint that validates removing profiles from a node doesn't violate required relationships.

    This runs in two cases:
    1. When a node's `profiles` relationship is changed.
    2. When a profile's `related_nodes` relationship is changed.

    In both cases, it will perform checks only if peers are being removed from the relationship being changed.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch
        self.schema_branch = registry.schema.get_schema_branch(branch.name if branch else registry.default_branch)

    def _get_required_attributes_names(self, schema: NodeSchema) -> set[str]:
        attr_names: set[str] = set()
        for attr_schema in schema.attributes:
            if attr_schema.support_profiles and not attr_schema.optional:
                attr_names.add(attr_schema.name)
        return attr_names

    def _get_required_relationship_names(self, schema: NodeSchema) -> set[str]:
        rel_names: set[str] = set()
        for rel_schema in schema.relationships:
            if rel_schema.support_profiles and not rel_schema.optional:
                rel_names.add(rel_schema.name)
        return rel_names

    async def _validate_profile_removal(
        self, node: Node, profile_id: str, required_attr_names: set[str], required_rel_names: set[str]
    ) -> None:
        for attr_name in required_attr_names:
            attr = node.get_attribute(name=attr_name)
            if attr.is_from_profile:
                source = await attr.get_source(db=self.db)
                if source and source.id == profile_id:
                    node_display_label = await node.get_display_label(db=self.db)
                    node_reference = f"node '{node_display_label}' (ID: {node.get_id()})"
                    raise ValidationError(
                        f"Cannot remove profile '{profile_id}' because {node_reference} "
                        f"inherits required attribute '{attr_name}' from this profile."
                    )

        for rel_name in required_rel_names:
            rel_manager = node.get_relationship(name=rel_name)

            relationships: list[Relationship] = await rel_manager.get_relationships(db=self.db)
            for rel in relationships:
                if rel.is_from_profile:
                    source = await rel.get_source(db=self.db)
                    if source and source.id == profile_id:
                        node_display_label = await node.get_display_label(db=self.db)
                        node_reference = f"node '{node_display_label}' (ID: {node.get_id()})"
                        raise ValidationError(
                            f"Cannot remove profile '{profile_id}' because {node_reference} "
                            f"inherits required relationship '{rel_name}' from this profile."
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

        for profile_id in relm_update_details.peer_ids_present_database_only:
            await self._validate_profile_removal(
                node=node,
                profile_id=profile_id,
                required_attr_names=required_attr_names,
                required_rel_names=required_rel_names,
            )

    async def _check_profile_related_nodes_removal(
        self, relm: RelationshipManager, profile_schema: ProfileSchema, profile: Node
    ) -> None:
        relm_update_details = await relm.fetch_relationship_ids(db=self.db, force_refresh=False)
        if not relm_update_details.peer_ids_present_database_only:
            return

        target_kind = profile_schema.get_relationship(name="related_nodes").peer
        target_schema = self.schema_branch.get_node(name=target_kind, duplicate=False)

        required_attr_names = self._get_required_attributes_names(schema=target_schema)
        required_rel_names = self._get_required_relationship_names(schema=target_schema)
        if not required_attr_names and not required_rel_names:
            return

        nodes = await NodeManager.get_many(
            db=self.db,
            branch=self.branch,
            ids=relm_update_details.peer_ids_present_database_only,
            include_metadata=MetadataOptions.SOURCE,
        )
        for node in nodes.values():
            await self._validate_profile_removal(
                node=node,
                profile_id=profile.get_id(),
                required_attr_names=required_attr_names,
                required_rel_names=required_rel_names,
            )

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:
        if relm.name == "profiles" and isinstance(node_schema, NodeSchema):
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

        required_attr_names = self._get_required_attributes_names(schema=target_schema)
        required_rel_names = self._get_required_relationship_names(schema=target_schema)
        if not required_attr_names and not required_rel_names:
            return

        nodes = await NodeManager.get_many(
            db=self.db, branch=self.branch, ids=related_node_ids, include_metadata=MetadataOptions.SOURCE
        )
        for node in nodes.values():
            await self._validate_profile_removal(
                node=node,
                profile_id=profile.get_id(),
                required_attr_names=required_attr_names,
                required_rel_names=required_rel_names,
            )
