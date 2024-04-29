from __future__ import annotations

from functools import reduce
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union

from infrahub_sdk.utils import deep_merge_dict

from infrahub.core.node import Node
from infrahub.core.node.delete_validator import NodeDeleteValidator
from infrahub.core.query.node import (
    AttributeFromDB,
    AttributeNodePropertyFromDB,
    NodeGetHierarchyQuery,
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
    NodeToProcess,
)
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from infrahub.core.relationship import Relationship
from infrahub.core.schema import GenericSchema, NodeSchema, ProfileSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import NodeNotFoundError, SchemaNotFoundError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.constants import RelationshipHierarchyDirection
    from infrahub.database import InfrahubDatabase


# pylint: disable=redefined-builtin


def identify_node_class(node: NodeToProcess) -> Type[Node]:
    """Identify the proper class to use to create the NodeObject.

    If there is a class in the registry matching the name Kind, use it
    If there is a class in the registry matching one of the node Parent, use it
    Otherwise use Node
    """
    if node.schema.kind in registry.node:
        return registry.node[node.schema.kind]

    if node.schema.inherit_from:
        for parent in node.schema.inherit_from:
            if parent in registry.node:
                return registry.node[parent]

    return Node


class ProfileAttributeIndex:
    def __init__(
        self,
        profile_attributes_id_map: dict[str, dict[str, AttributeFromDB]],
        profile_ids_by_node_id: dict[str, list[str]],
    ):
        self._profile_attributes_id_map = profile_attributes_id_map
        self._profile_ids_by_node_id = profile_ids_by_node_id

    def apply_profiles(self, node_data_dict: dict[str, Any]) -> dict[str, Any]:
        updated_data: dict[str, Any] = {**node_data_dict}
        node_id = node_data_dict.get("id")
        profile_ids = self._profile_ids_by_node_id.get(node_id, [])
        if not profile_ids:
            return updated_data
        profiles = [
            self._profile_attributes_id_map[p_id] for p_id in profile_ids if p_id in self._profile_attributes_id_map
        ]
        profiles.sort(key=lambda p: str(p.attrs.get("profile_priority").value))

        for attr_name, attr_data in updated_data.items():
            if not isinstance(attr_data, AttributeFromDB):
                continue
            if not attr_data.is_default:
                continue
            profile_value, profile_uuid = None, None
            index = 0

            while profile_value is None and index <= (len(profiles) - 1):
                try:
                    profile_value = profiles[index].attrs[attr_name].value
                    if profile_value != "NULL":
                        profile_uuid = profiles[index].node["uuid"]
                        break
                    profile_value = None
                except (IndexError, KeyError, AttributeError):
                    ...
                index += 1

            if profile_value is not None:
                attr_data.value = profile_value
                attr_data.is_from_profile = True
                attr_data.is_default = False
                attr_data.node_properties["source"] = AttributeNodePropertyFromDB(uuid=profile_uuid, labels=[])
        return updated_data


class NodeManager:
    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
        schema: Union[NodeSchema, GenericSchema, ProfileSchema, str],
        filters: Optional[dict] = None,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        partial_match: bool = False,
    ) -> List[Node]:  # pylint: disable=unused-argument
        """Query one or multiple nodes of a given type based on filter arguments.

        Args:
            schema (NodeSchema or Str): Infrahub Schema or Name of a schema present in the registry.
            filters (dict, optional): filters provided in a dictionary
            fields (dict, optional): List of fields to include in the response.
            limit (int, optional): Maximum numbers of nodes to return. Defaults to 100.
            at (Timestamp or Str, optional): Timestamp for the query. Defaults to None.
            branch (Branch or Str, optional): Branch to query. Defaults to None.

        Returns:
            List[Node]: List of Node object
        """

        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        if isinstance(schema, str):
            schema = registry.schema.get(name=schema, branch=branch.name)
        elif not isinstance(schema, (NodeSchema, GenericSchema, ProfileSchema)):
            raise ValueError(f"Invalid schema provided {schema}")

        # Query the list of nodes matching this Query
        query = await NodeGetListQuery.init(
            db=db,
            schema=schema,
            branch=branch,
            offset=offset,
            limit=limit,
            filters=filters,
            at=at,
            partial_match=partial_match,
        )
        await query.execute(db=db)
        node_ids = query.get_node_ids()

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields and schema.display_labels:
            display_label_fields = schema.generate_fields_for_display_label()
            fields = deep_merge_dict(fields, display_label_fields)

        response = await cls.get_many(
            ids=node_ids,
            fields=fields,
            branch=branch,
            account=account,
            at=at,
            include_source=include_source,
            include_owner=include_owner,
            db=db,
            prefetch_relationships=prefetch_relationships,
        )

        return list(response.values()) if node_ids else []

    @classmethod
    async def count(
        cls,
        db: InfrahubDatabase,
        schema: NodeSchema,
        filters: Optional[dict] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        account=None,  # pylint: disable=unused-argument
        partial_match: bool = False,
    ) -> int:
        """Return the total number of nodes using a given filter

        Args:
            schema (NodeSchema): Infrahub Schema or Name of a schema present in the registry.
            filters (dict, optional): filters provided in a dictionary
            at (Timestamp or Str, optional): Timestamp for the query. Defaults to None.
            branch (Branch or Str, optional): Branch to query. Defaults to None.

        Returns:
            int: The number of responses found
        """

        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetListQuery.init(
            db=db, schema=schema, branch=branch, filters=filters, at=at, partial_match=partial_match
        )
        return await query.count(db=db)

    @classmethod
    async def count_peers(
        cls,
        ids: List[str],
        source_kind: str,
        schema: RelationshipSchema,
        filters: dict,
        db: InfrahubDatabase,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> int:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id="PLACEHOLDER")

        query = await RelationshipGetPeerQuery.init(
            db=db, source_ids=ids, source_kind=source_kind, schema=schema, filters=filters, rel=rel, at=at
        )
        return await query.count(db=db)

    @classmethod
    async def query_peers(
        cls,
        db: InfrahubDatabase,
        ids: List[str],
        source_kind: str,
        schema: RelationshipSchema,
        filters: dict,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
    ) -> List[Relationship]:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id="PLACEHOLDER")

        query = await RelationshipGetPeerQuery.init(
            db=db,
            source_ids=ids,
            source_kind=source_kind,
            schema=schema,
            filters=filters,
            rel=rel,
            offset=offset,
            limit=limit,
            at=at,
        )
        await query.execute(db=db)

        peers_info = list(query.get_peers())
        if not peers_info:
            return []

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            peer_schema = schema.get_peer_schema(branch=branch)
            if peer_schema.display_labels:
                display_label_fields = peer_schema.generate_fields_for_display_label()
                fields = deep_merge_dict(fields, display_label_fields)

        return [
            await Relationship(schema=schema, branch=branch, at=at, node_id=peer.source_id).load(
                db=db,
                id=peer.rel_node_id,
                db_id=peer.rel_node_db_id,
                updated_at=peer.updated_at,
                data=peer,
            )
            for peer in peers_info
        ]

    @classmethod
    async def count_hierarchy(
        cls,
        id: str,
        direction: RelationshipHierarchyDirection,
        node_schema: NodeSchema,
        filters: dict,
        db: InfrahubDatabase,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> int:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=direction,
            node_id=id,
            node_schema=node_schema,
            filters=filters,
            at=at,
            branch=branch,
        )

        return await query.count(db=db)

    @classmethod
    async def query_hierarchy(
        cls,
        db: InfrahubDatabase,
        id: str,
        direction: RelationshipHierarchyDirection,
        node_schema: NodeSchema,
        filters: dict,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
    ) -> Dict[str, Node]:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=direction,
            node_id=id,
            node_schema=node_schema,
            filters=filters,
            offset=offset,
            limit=limit,
            at=at,
            branch=branch,
        )
        await query.execute(db=db)

        peers_ids = list(query.get_peer_ids())

        if not peers_ids:
            return []

        hierarchy_schema = node_schema.get_hierarchy_schema()

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            if hierarchy_schema.display_labels:
                display_label_fields = hierarchy_schema.generate_fields_for_display_label()
                fields = deep_merge_dict(fields, display_label_fields)

        return await cls.get_many(
            db=db, ids=peers_ids, fields=fields, at=at, branch=branch, include_owner=True, include_source=True
        )

    @classmethod
    async def get_one_by_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        schema_name: str,
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
    ) -> Node:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node_schema = registry.schema.get(name=schema_name, branch=branch)
        if not node_schema.default_filter:
            raise NodeNotFoundError(branch_name=branch.name, node_type=schema_name, identifier=id)

        items = await NodeManager.query(
            db=db,
            schema=node_schema,
            fields=fields,
            limit=2,
            filters={node_schema.default_filter: id},
            branch=branch,
            at=at,
            include_owner=include_owner,
            include_source=include_source,
            prefetch_relationships=prefetch_relationships,
            account=account,
        )

        if len(items) > 1:
            raise NodeNotFoundError(
                branch_name=branch.name,
                node_type=schema_name,
                identifier=id,
                message=f"Unable to find node {id!r}, {len(items)} nodes returned, expected 1",
            )

        return items[0] if items else None

    @classmethod
    async def get_one_by_id_or_default_filter(
        cls,
        db: InfrahubDatabase,
        id: str,
        schema_name: str,
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
    ) -> Node:
        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node = await cls.get_one(
            id=id,
            fields=fields,
            at=at,
            branch=branch,
            include_owner=include_owner,
            include_source=include_source,
            db=db,
            prefetch_relationships=prefetch_relationships,
            account=account,
        )
        if node:
            return node

        node = await cls.get_one_by_default_filter(
            db=db,
            id=id,
            schema_name=schema_name,
            fields=fields,
            at=at,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            prefetch_relationships=prefetch_relationships,
            account=account,
        )
        if not node:
            raise NodeNotFoundError(branch_name=branch.name, node_type=schema_name, identifier=id)
        return node

    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        kind: Optional[str] = None,
    ) -> Optional[Node]:
        """Return one node based on its ID."""
        branch = await registry.get_branch(branch=branch, db=db)

        result = await cls.get_many(
            ids=[id],
            fields=fields,
            at=at,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            account=account,
            prefetch_relationships=prefetch_relationships,
            db=db,
        )

        if not result:
            return None

        node = result[id]

        if kind and node.get_kind() != kind:
            raise NodeNotFoundError(
                branch_name=branch.name,
                node_type=kind,
                identifier=id,
                message=f"Node with id {id} exists, but it is a {node.get_kind()}, not {kind}",
            )

        return node

    @classmethod
    async def get_many(  # pylint: disable=too-many-branches,too-many-statements
        cls,
        db: InfrahubDatabase,
        ids: List[str],
        fields: Optional[dict] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
    ) -> Dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = await registry.get_branch(branch=branch, db=db)
        at = Timestamp(at)

        # Query all nodes
        query = await NodeListGetInfoQuery.init(db=db, ids=ids, branch=branch, account=account, at=at)
        await query.execute(db=db)
        nodes_info_by_id: Dict[str, NodeToProcess] = {
            node.node_uuid: node async for node in query.get_nodes(duplicate=False)
        }
        profile_ids_by_node_id = query.get_profile_ids_by_node_id()
        all_profile_ids = reduce(
            lambda all_ids, these_ids: all_ids | set(these_ids), profile_ids_by_node_id.values(), set()
        )

        if fields and all_profile_ids:
            if "profile_priority" not in fields:
                fields["profile_priority"] = {}
            if "value" not in fields["profile_priority"]:
                fields["profile_priority"]["value"] = None

        # Query list of all Attributes
        query = await NodeListGetAttributeQuery.init(
            db=db,
            ids=list(nodes_info_by_id.keys()) + list(all_profile_ids),
            fields=fields,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            account=account,
            at=at,
        )
        await query.execute(db=db)
        all_node_attributes = query.get_attributes_group_by_node()
        profile_attributes: Dict[str, Dict[str, AttributeFromDB]] = {}
        node_attributes: Dict[str, Dict[str, AttributeFromDB]] = {}
        for node_id, attribute_dict in all_node_attributes.items():
            if node_id in all_profile_ids:
                profile_attributes[node_id] = attribute_dict
            else:
                node_attributes[node_id] = attribute_dict
        profile_index = ProfileAttributeIndex(
            profile_attributes_id_map=profile_attributes, profile_ids_by_node_id=profile_ids_by_node_id
        )

        # if prefetch_relationships is enabled
        # Query all the peers associated with all nodes at once.
        peers_per_node = None
        peers = None
        if prefetch_relationships:
            query = await NodeListGetRelationshipsQuery.init(db=db, ids=ids, branch=branch, at=at)
            await query.execute(db=db)
            peers_per_node = query.get_peers_group_by_node()
            peer_ids = []

            for _, node_data in peers_per_node.items():
                for _, node_peers in node_data.items():
                    peer_ids.extend(node_peers)

            peer_ids = list(set(peer_ids))
            peers = await cls.get_many(
                ids=peer_ids,
                branch=branch,
                at=at,
                db=db,
                include_owner=include_owner,
                include_source=include_source,
            )

        nodes = {}

        for node_id in ids:  # pylint: disable=too-many-nested-blocks
            if node_id not in nodes_info_by_id:
                continue

            node = nodes_info_by_id[node_id]
            new_node_data: Dict[str, Union[str, AttributeFromDB]] = {
                "db_id": node.node_id,
                "id": node_id,
                "updated_at": node.updated_at,
            }

            if not node.schema:
                raise SchemaNotFoundError(
                    branch_name=branch.name,
                    identifier=node_id,
                    message=f"Unable to find the Schema associated with {node_id}, {node.labels}",
                )

            # --------------------------------------------------------
            # Attributes
            # --------------------------------------------------------
            if node_id in node_attributes:
                for attr_name, attr in node_attributes[node_id].attrs.items():
                    new_node_data[attr_name] = attr

            # --------------------------------------------------------
            # Relationships
            # --------------------------------------------------------
            if prefetch_relationships and peers:
                for rel_schema in node.schema.relationships:
                    if node_id in peers_per_node and rel_schema.identifier in peers_per_node[node_id]:
                        rel_peers = [peers.get(id) for id in peers_per_node[node_id][rel_schema.identifier]]
                        if rel_schema.cardinality == "one":
                            if len(rel_peers) == 1:
                                new_node_data[rel_schema.name] = rel_peers[0]
                        elif rel_schema.cardinality == "many":
                            new_node_data[rel_schema.name] = rel_peers

            new_node_data_with_profile_overrides = profile_index.apply_profiles(new_node_data)
            node_class = identify_node_class(node=node)
            item = await node_class.init(schema=node.schema, branch=branch, at=at, db=db)
            await item.load(**new_node_data_with_profile_overrides, db=db)

            nodes[node_id] = item

        return nodes

    @classmethod
    async def delete(
        cls,
        db: InfrahubDatabase,
        nodes: List[Node],
        branch: Optional[Union[Branch, str]] = None,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> list[Node]:
        """Returns list of deleted nodes because of cascading deletes"""
        branch = await registry.get_branch(branch=branch, db=db)
        component_registry = get_component_registry()
        node_delete_validator = await component_registry.get_component(NodeDeleteValidator, db=db, branch=branch)
        ids_to_delete = await node_delete_validator.get_ids_to_delete(nodes=nodes, at=at)
        node_ids = {node.get_id() for node in nodes}
        missing_ids_to_delete = ids_to_delete - node_ids
        if missing_ids_to_delete:
            node_map = await cls.get_many(db=db, ids=list(missing_ids_to_delete), branch=branch, at=at)
            nodes += list(node_map.values())
        deleted_nodes = []
        for node in nodes:
            await node.delete(db=db, at=at)
            deleted_nodes.append(node)

        return deleted_nodes


registry.manager = NodeManager
