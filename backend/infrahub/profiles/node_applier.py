from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub_sdk.utils import is_valid_uuid

from infrahub.core.constants import InfrahubKind
from infrahub.core.relationship.model import Relationship

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship import RelationshipManager
    from infrahub.database import InfrahubDatabase

    from .data_reader import ProfileDataReader


@dataclass(frozen=True)
class ProfileFieldValues:
    """The values and the peers that a node's profiles give some of its fields."""

    attribute_values: dict[str, Any]
    """Attribute name mapped to the value the profiles give it."""

    relationship_peers: dict[str, list[str]]
    """Relationship name mapped to the ids of the peers the profiles give it."""


class NodeProfilesApplier:
    """Applies profile values to nodes and templates.

    Profile values take precedence over both default values and template-sourced values.
    When a template has profiles assigned:
    1. Profile values are applied to the template itself
    2. Nodes created from that template inherit the profile values (not the template's own values)
    3. Profile priority determines which profile wins when multiple profiles set the same attribute
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, profile_data_reader: ProfileDataReader) -> None:
        self.db = db
        self.branch = branch
        self.profile_data_reader = profile_data_reader

    async def _get_profile_ids(self, node: Node) -> list[str]:
        try:
            profiles_rel = node.get_relationship("profiles")
        except ValueError:
            return []
        profile_ids: list[str] = []
        for profile_rel in await profiles_rel.get_relationships(db=self.db):
            # A node not saved yet can name a profile by its human-friendly id.
            if not profile_rel.peer_id or not is_valid_uuid(profile_rel.peer_id):
                await profile_rel.resolve(db=self.db)
            if profile_rel.peer_id:
                profile_ids.append(profile_rel.peer_id)
        return profile_ids

    async def _get_attr_names_for_profiles(self, node: Node) -> list[str]:
        node_schema = node.get_schema()

        # get the names of attributes that could be affected by profile changes
        attr_names_for_profiles: list[str] = []
        for attr_schema in node_schema.attributes:
            attr_name = attr_schema.name
            node_attr: BaseAttribute = getattr(node, attr_name)
            if self._takes_profile_value(node_attr=node_attr):
                attr_names_for_profiles.append(attr_name)
        return attr_names_for_profiles

    @staticmethod
    def _takes_profile_value(node_attr: BaseAttribute) -> bool:
        return bool(node_attr.is_from_profile or node_attr.is_default)

    async def _get_rel_names_for_profiles(self, node: Node) -> list[str]:
        node_schema = node.get_schema()

        rel_names_for_profiles: list[str] = []
        for rel_schema in node_schema.relationships:
            if not rel_schema.support_profiles:
                continue

            rel_name = rel_schema.name
            node_rel = node.get_relationship(rel_name)

            current_rels = await node_rel.get_relationships(db=self.db)
            if node_rel.is_from_profile or len(current_rels) == 0:
                rel_names_for_profiles.append(rel_name)

        return rel_names_for_profiles

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
        if node_attr.source_id != profile_id:
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

        Profile relationships are only applied if the node has no user-set peers for this relationship.
        User-set peers (not from profile) take precedence over profile values.
        """
        is_changed = False

        current_rels = await node_rel.get_relationships(db=self.db)

        user_set_peer_ids: set[str] = set()
        profile_set_rels: list[Relationship] = []
        for rel in current_rels:
            if rel.peer_id:
                if rel.is_from_profile:
                    profile_set_rels.append(rel)
                else:
                    user_set_peer_ids.add(rel.peer_id)

        # If user has set any peers, they override profile values entirely
        if user_set_peer_ids:
            for rel in profile_set_rels:
                if rel.peer_id and rel.peer_id not in user_set_peer_ids:
                    await node_rel.remove_locally(peer_id=rel.peer_id, db=self.db)
                    is_changed = True
                elif rel.peer_id and rel.peer_id in user_set_peer_ids:
                    rel.clear_source()
                    is_changed = True

            if is_changed:
                node_rel.is_from_profile = False
                await node_rel.save(db=self.db)
            return is_changed

        is_changed = await self._replace_profile_peers(
            node=node, node_rel=node_rel, profile_set_rels=profile_set_rels, peer_ids=peer_ids, profile_id=profile_id
        )
        if is_changed:
            await node_rel.save(db=self.db)

        return is_changed

    async def _replace_profile_peers(
        self,
        node: Node,
        node_rel: RelationshipManager,
        profile_set_rels: list[Relationship],
        peer_ids: list[str],
        profile_id: str,
    ) -> bool:
        """Replace, in memory, the peers a profile set on the relationship with the profile's peers."""
        profile_peer_ids = set(peer_ids)
        profile_set_peer_ids = {rel.peer_id for rel in profile_set_rels if rel.peer_id}
        relationships_to_replace: dict[str, list[Relationship]] = {"insert": [], "remove": []}

        # Remove relationships that are from profile but not in the new profile value
        for rel in profile_set_rels:
            if rel.peer_id and rel.peer_id not in profile_peer_ids:
                relationships_to_replace["remove"].append(rel)

        # Add relationships that are in profile but not present
        for peer_id in profile_peer_ids:
            if peer_id not in profile_set_peer_ids:
                new_rel = Relationship(
                    schema=node_rel.schema,
                    branch=self.branch,
                    source_kind=InfrahubKind.PROFILE,
                    node=node,
                )
                await new_rel.new(db=self.db, data=peer_id)
                new_rel.set_source(value=profile_id)
                relationships_to_replace["insert"].append(new_rel)

        is_changed = await node_rel.update_relationships(
            db=self.db,
            relationships_to_remove=relationships_to_replace["remove"],
            relationships_to_insert=relationships_to_replace["insert"],
        )

        if profile_peer_ids:
            node_rel.is_from_profile = True

        return is_changed

    async def _remove_profile_from_relationship(self, relationship_manager: RelationshipManager) -> None:
        relationship_manager.is_from_profile = False
        await relationship_manager.delete(db=self.db)

    async def get_field_values(self, node: Node, attr_names: list[str], rel_names: list[str]) -> ProfileFieldValues:
        """Return the values and the peers the node's profiles give the named fields, leaving the node unchanged.

        A named attribute left at its default or set by a profile takes the value of the profile of highest priority
        that sets it, and a named relationship that profiles support and that holds no peer the writer set takes the
        peers of the profile of highest priority that sets it; a field no profile sets is left out. The profiles are
        read at most once, and not at all when no named field can take a profile value.
        """
        candidate_attr_names = [
            attr_name for attr_name in attr_names if self._takes_profile_value(node_attr=node.get_attribute(attr_name))
        ]
        candidate_rels = [
            node_rel
            for node_rel in (node.get_relationship(name=rel_name) for rel_name in rel_names)
            if await self._takes_profile_peers(node_rel=node_rel)
        ]
        field_values = ProfileFieldValues(attribute_values={}, relationship_peers={})
        if not candidate_attr_names and not candidate_rels:
            return field_values
        sorted_profile_data = await self.profile_data_reader.read(
            schema=node.get_schema(),
            profile_ids=await self._get_profile_ids(node=node),
            attr_names=candidate_attr_names,
            rel_names=[node_rel.name for node_rel in candidate_rels],
        )
        for attr_name in candidate_attr_names:
            profile_value = next(
                (
                    profile_data.attribute_values[attr_name]
                    for profile_data in sorted_profile_data
                    if profile_data.attribute_values.get(attr_name) is not None
                ),
                None,
            )
            if profile_value is not None:
                field_values.attribute_values[attr_name] = profile_value
        for node_rel in candidate_rels:
            profile_peers = next(
                (
                    profile_data.peers_of(relationship=node_rel.schema)
                    for profile_data in sorted_profile_data
                    if profile_data.peers_of(relationship=node_rel.schema)
                ),
                None,
            )
            if profile_peers is not None:
                field_values.relationship_peers[node_rel.name] = profile_peers
        return field_values

    async def _takes_profile_peers(self, node_rel: RelationshipManager) -> bool:
        """Whether profiles support the relationship and every peer it holds, if any, was set by a profile."""
        if not node_rel.schema.support_profiles:
            return False
        return all(rel.is_from_profile for rel in await node_rel.get_relationships(db=self.db))

    async def apply_profiles(self, node: Node) -> list[str]:
        """Reconcile a node's profile-sourced attributes and relationships with its assigned profiles.

        For each attribute and relationship that supports profiles, the highest-priority profile value
        is applied, or a previously profile-sourced value is reset when no assigned profile supplies
        one. Values the user has set directly are left untouched and take precedence over profiles.

        Returns the names of the attributes and relationships that this method modified. Fields the
        caller changed before calling this method are not reported unless applying profiles changed
        them further; an empty list means nothing was modified here.
        """
        profile_ids = await self._get_profile_ids(node=node)
        attr_names_for_profiles = await self._get_attr_names_for_profiles(node=node)
        rel_names_for_profiles = await self._get_rel_names_for_profiles(node=node)
        if not attr_names_for_profiles and not rel_names_for_profiles:
            return []

        # get profiles priorities, attribute values, and relationship peers on branch
        sorted_profile_data = await self.profile_data_reader.read(
            schema=node.get_schema(),
            profile_ids=profile_ids,
            attr_names=attr_names_for_profiles,
            rel_names=rel_names_for_profiles,
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
                    is_changed = self._apply_profile_to_attribute(
                        node_attr=node_attr, profile_value=profile_value, profile_id=profile_data.uuid
                    )
                    if is_changed:
                        updated_field_names.append(attr_name)
                    break
            if not has_profile_attr_data and node_attr.is_from_profile:
                self._remove_profile_from_attribute(node_attr=node_attr)
                updated_field_names.append(attr_name)

        for rel_name in rel_names_for_profiles:
            has_profile_rel_data = False
            node_rel = node.get_relationship(name=rel_name)

            for profile_data in sorted_profile_data:
                profile_peers = profile_data.peers_of(relationship=node_rel.schema)
                if profile_peers:
                    has_profile_rel_data = True
                    is_changed = await self._apply_profile_to_relationship(
                        node=node, node_rel=node_rel, peer_ids=profile_peers, profile_id=profile_data.uuid
                    )
                    if is_changed:
                        updated_field_names.append(node_rel.name)
                    break

            # Refresh the relationship manager to update the is_from_profile property
            await node_rel.refresh_update_details(db=self.db)
            if not has_profile_rel_data and node_rel.is_from_profile:
                await self._remove_profile_from_relationship(relationship_manager=node_rel)
                updated_field_names.append(node_rel.name)

        return updated_field_names
