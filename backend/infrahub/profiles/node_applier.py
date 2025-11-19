from typing import Any

from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.node import Node
from infrahub.core.relationship import RelationshipManager
from infrahub.core.relationship.model import Relationship
from infrahub.database import InfrahubDatabase

from .queries.get_profile_data import GetProfileDataQuery, ProfileData, RelationshipFilter


class NodeProfilesApplier:
    def __init__(self, db: InfrahubDatabase, branch: Branch):
        self.db = db
        self.branch = branch

    async def _get_profile_ids(self, node: Node) -> list[str]:
        try:
            profiles_rel = node.get_relationship("profiles")
        except ValueError:
            return []
        profile_rels = await profiles_rel.get_relationships(db=self.db)
        return [pr.peer_id for pr in profile_rels if pr.peer_id]

    async def _get_attr_names_for_profiles(self, node: Node) -> list[str]:
        node_schema = node.get_schema()

        # get the names of attributes that could be affected by profile changes
        attr_names_for_profiles: list[str] = []
        for attr_schema in node_schema.attributes:
            attr_name = attr_schema.name
            node_attr: BaseAttribute = getattr(node, attr_name)
            if node_attr.is_from_profile or node_attr.is_default:
                attr_names_for_profiles.append(attr_name)
        return attr_names_for_profiles

    async def _get_rel_names_for_profiles(self, node: Node) -> list[str]:
        node_schema = node.get_schema()

        rel_names_for_profiles: list[str] = []
        for rel_schema in node_schema.relationships:
            if rel_schema.kind not in [RelationshipKind.GENERIC, RelationshipKind.ATTRIBUTE]:
                continue

            rel_name = rel_schema.name
            node_rel = node.get_relationship(rel_name)

            current_rels = await node_rel.get_relationships(db=self.db)
            if node_rel.is_from_profile or len(current_rels) == 0:
                rel_names_for_profiles.append(rel_name)

        return rel_names_for_profiles

    async def _get_rel_filters_for_profiles(self, node: Node, rel_names: list[str]) -> list[RelationshipFilter]:
        node_schema = node.get_schema()

        identifiers: list[RelationshipFilter] = []
        for rel_name in rel_names:
            rel_schema = node_schema.get_relationship(name=rel_name)

            # We are past schema validation so we should have an identifier
            if not rel_schema.identifier:
                raise ValueError(f"Relationship {rel_name} has no identifier")

            identifiers.append(
                RelationshipFilter(
                    relationship_identifier=f"profile_{rel_schema.identifier}", direction=rel_schema.direction
                )
            )
        return identifiers

    async def _get_sorted_profile_data(
        self,
        profile_ids: list[str],
        attr_names_for_profiles: list[str],
        relationship_filters: list[RelationshipFilter] | None = None,
    ) -> list[ProfileData]:
        if not profile_ids:
            return []
        query = await GetProfileDataQuery.init(
            db=self.db,
            branch=self.branch,
            profile_ids=profile_ids,
            attr_names=attr_names_for_profiles,
            relationship_filters=relationship_filters,
        )
        await query.execute(db=self.db)
        profile_data_list = query.get_profile_data()
        return sorted(profile_data_list, key=lambda x: (x.priority, x.uuid))

    def _apply_profile_to_attribute(self, node_attr: BaseAttribute, profile_value: Any, profile_id: str) -> bool:
        is_changed = False
        if node_attr.value != profile_value:
            node_attr.value = profile_value
            is_changed = True
        if node_attr.is_default is not False:
            node_attr.is_default = False
            is_changed = True
        if node_attr.is_from_profile is not True:
            node_attr.is_from_profile = True
            is_changed = True
        if node_attr.source_id != profile_id:  # type: ignore[attr-defined]
            node_attr.set_source(value=profile_id)
            is_changed = True
        return is_changed

    def _remove_profile_from_attribute(self, node_attr: BaseAttribute) -> None:
        node_attr.clear_source()
        node_attr.value = node_attr.schema.default_value
        node_attr.is_default = True
        node_attr.is_from_profile = False

    async def _apply_profile_to_relationship(
        self, node: Node, node_rel: RelationshipManager, peer_ids: list[str], profile_id: str
    ) -> bool:
        """Apply profile relationship peers to a node relationship.

        Profile relationships are only applied if the node has no existing peers for this relationship.
        If any peers exist, profile relationships are not applied.
        """
        is_changed = False

        current_rels = await node_rel.get_relationships(db=self.db)
        current_peer_ids = {rel.peer_id for rel in current_rels if rel.peer_id}

        # We have peers to override the ones from the profile, so remove those ones
        if current_peer_ids and peer_ids:
            for peer_id in peer_ids:
                if peer_id in current_peer_ids:
                    await node_rel.remove_locally(db=self.db, peer_id=peer_id)
                    is_changed = True

            if is_changed:
                node_rel.is_from_profile = False
                await node_rel.save(db=self.db)
            return is_changed

        if node_rel.schema.cardinality == RelationshipCardinality.ONE:
            target_peer_ids = {peer_ids[0]} if peer_ids else set()
        else:
            target_peer_ids = set(peer_ids)

        # Remove relationships that are from this profile but not in target
        for rel in current_rels:
            source = await rel.get_source(db=self.db)
            if node_rel.is_from_profile and source and source.id == profile_id:
                if rel.peer_id and rel.peer_id not in target_peer_ids:
                    await node_rel.remove_locally(peer_id=rel.peer_id, db=self.db)
                    node_rel.is_from_profile = True
                    is_changed = True

        # Add relationships that are in target but not present
        for peer_id in target_peer_ids:
            if peer_id not in current_peer_ids:
                new_rel = Relationship(schema=node_rel.schema, branch=self.branch, node=node)
                await new_rel.new(db=self.db, data=peer_id)
                new_rel.set_source(value=profile_id)
                node_rel._relationships.append(new_rel)
            node_rel.is_from_profile = True
            is_changed = True

        await node_rel.save(db=self.db)

        return is_changed

    async def _remove_profile_from_relationship(self, relationship_manager: RelationshipManager) -> None:
        relationship_manager.is_from_profile = False
        await relationship_manager.delete(db=self.db)

    async def apply_profiles(self, node: Node) -> list[str]:
        profile_ids = await self._get_profile_ids(node=node)
        attr_names_for_profiles = await self._get_attr_names_for_profiles(node=node)
        rel_names_for_profiles = await self._get_rel_names_for_profiles(node=node)
        rel_filters_for_profiles = await self._get_rel_filters_for_profiles(node=node, rel_names=rel_names_for_profiles)
        if not attr_names_for_profiles and not rel_filters_for_profiles:
            return []

        # get profiles priorities, attribute values, and relationship peers on branch
        sorted_profile_data = await self._get_sorted_profile_data(
            profile_ids=profile_ids,
            attr_names_for_profiles=attr_names_for_profiles,
            relationship_filters=rel_filters_for_profiles,
        )

        updated_field_names: list[str] = []
        # set attribute values/is_default/is_from_profile on nodes
        for attr_name in attr_names_for_profiles:
            has_profile_attr_data = False
            node_attr = node.get_attribute(attr_name)
            for profile_data in sorted_profile_data:
                profile_value = profile_data.attribute_values.get(attr_name)
                if profile_value is not None:
                    has_profile_attr_data = True
                    is_changed = False
                    is_changed = self._apply_profile_to_attribute(
                        node_attr=node_attr, profile_value=profile_value, profile_id=profile_data.uuid
                    )
                    if is_changed:
                        updated_field_names.append(attr_name)
                    break
            if not has_profile_attr_data and node_attr.is_from_profile:
                self._remove_profile_from_attribute(node_attr=node_attr)
                updated_field_names.append(attr_name)

        for rel_filter in rel_filters_for_profiles:
            has_profile_rel_data = False
            node_rel = node.get_relationship_by_identifier(rel_filter.relationship_identifier.removeprefix("profile_"))

            for profile_data in sorted_profile_data:
                profile_peers = profile_data.relationship_peers.get(rel_filter)
                if profile_peers:
                    has_profile_rel_data = True
                    is_changed = await self._apply_profile_to_relationship(
                        node=node, node_rel=node_rel, peer_ids=profile_peers, profile_id=profile_data.uuid
                    )
                    if is_changed:
                        updated_field_names.append(node_rel.name)
                    break

            # Refresh the relationship manager to update the is_from_profile property
            await node_rel._fetch_relationships(db=self.db)
            if not has_profile_rel_data and node_rel.is_from_profile:
                await self._remove_profile_from_relationship(relationship_manager=node_rel)
                updated_field_names.append(node_rel.name)

        return updated_field_names
