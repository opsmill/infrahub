from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Type, Union

from infrahub_sdk.utils import deep_merge_dict

from infrahub.core import get_branch, registry
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeGetHierarchyQuery,
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
    NodeToProcess,
)
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.schema import GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFound, SchemaNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.branch import Branch
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


class NodeManager:
    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
        schema: Union[NodeSchema, GenericSchema, str],
        filters: Optional[dict] = None,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
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

        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        if isinstance(schema, str):
            schema = registry.get_schema(name=schema, branch=branch.name)
        elif not isinstance(schema, (NodeSchema, GenericSchema)):
            raise ValueError(f"Invalid schema provided {schema}")

        # Query the list of nodes matching this Query
        query = await NodeGetListQuery.init(
            db=db, schema=schema, branch=branch, offset=offset, limit=limit, filters=filters, at=at
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

        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetListQuery.init(db=db, schema=schema, branch=branch, filters=filters, at=at)
        return await query.count(db=db)

    @classmethod
    async def count_peers(
        cls,
        ids: List[str],
        schema: RelationshipSchema,
        filters: dict,
        db: InfrahubDatabase,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> int:
        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id=ids[0])

        query = await RelationshipGetPeerQuery.init(
            db=db, source_ids=ids, schema=schema, filters=filters, rel=rel, at=at
        )
        return await query.count(db=db)

    @classmethod
    async def query_peers(
        cls,
        db: InfrahubDatabase,
        ids: List[str],
        schema: RelationshipSchema,
        filters: dict,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
    ) -> List[Relationship]:
        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id=id)

        query = await RelationshipGetPeerQuery.init(
            db=db,
            source_ids=ids,
            schema=schema,
            filters=filters,
            rel=rel,
            offset=offset,
            limit=limit,
            at=at,
        )
        await query.execute(db=db)

        peers_info = list(query.get_peers())

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            peer_schema = await schema.get_peer_schema(branch=branch)
            if peer_schema.display_labels:
                display_label_fields = peer_schema.generate_fields_for_display_label()
                fields = deep_merge_dict(fields, display_label_fields)

        if not peers_info:
            return []

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
        direction: Literal["ancestors", "descendants"],
        node_schema: NodeSchema,
        hierarchy_schema: GenericSchema,
        filters: dict,
        db: InfrahubDatabase,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> int:
        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=direction,
            node_id=id,
            node_schema=node_schema,
            hierarchy_schema=hierarchy_schema,
            filters=filters,
            at=at,
            branch=branch,
        )

        return await query.count(db=db)

    @classmethod
    async def query_hierarchy(
        cls,
        db: InfrahubDatabase,
        id: UUID,
        direction: Literal["ancestors", "descendants"],
        node_schema: NodeSchema,
        hierarchy_schema: GenericSchema,
        filters: dict,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
    ) -> Dict[str, Node]:
        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=direction,
            node_id=id,
            node_schema=node_schema,
            hierarchy_schema=hierarchy_schema,
            filters=filters,
            offset=offset,
            limit=limit,
            at=at,
            branch=branch,
        )
        await query.execute(db=db)

        peers_ids = list(query.get_peer_ids())

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            if hierarchy_schema.display_labels:
                display_label_fields = hierarchy_schema.generate_fields_for_display_label()
                fields = deep_merge_dict(fields, display_label_fields)

        if not peers_ids:
            return []

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
        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        node_schema = registry.get_node_schema(name=schema_name, branch=branch)
        if not node_schema.default_filter:
            raise NodeNotFound(branch_name=branch.name, node_type=schema_name, identifier=id)

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
            raise NodeNotFound(
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
        branch = await get_branch(branch=branch, db=db)
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
            raise NodeNotFound(branch_name=branch.name, node_type=schema_name, identifier=id)
        return node

    @classmethod
    async def get_one(
        cls,
        id: str,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
        kind: Optional[str] = None,
    ) -> Optional[Node]:
        """Return one node based on its ID."""
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
            raise NodeNotFound(
                branch_name=branch.name,
                node_type=kind,
                identifier=id,
                message=f"Node with id {id} exists, but it is a {node.get_kind()}, not {kind}",
            )

        return node

    @classmethod
    async def get_many(  # pylint: disable=too-many-branches
        cls,
        db: InfrahubDatabase,
        ids: List[str],
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        account=None,
    ) -> Dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = await get_branch(branch=branch, db=db)
        at = Timestamp(at)

        # Query all nodes
        query = await NodeListGetInfoQuery.init(db=db, ids=ids, branch=branch, account=account, at=at)
        await query.execute(db=db)
        nodes_info_by_id: Dict[str, NodeToProcess] = {node.node_uuid: node async for node in query.get_nodes()}

        # Query list of all Attributes
        query = await NodeListGetAttributeQuery.init(
            db=db,
            ids=list(nodes_info_by_id.keys()),
            fields=fields,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            account=account,
            at=at,
        )
        await query.execute(db=db)
        node_attributes = query.get_attributes_group_by_node()

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
            attrs = {"db_id": node.node_id, "id": node_id, "updated_at": node.updated_at}

            if not node.schema:
                raise SchemaNotFound(
                    branch_name=branch.name,
                    identifier=node_id,
                    message=f"Unable to find the Schema associated with {node_id}, {node.labels}",
                )

            # --------------------------------------------------------
            # Attributes
            # --------------------------------------------------------
            for attr_name, attr in node_attributes.get(node_id, {}).get("attrs", {}).items():
                if "AttributeLocal" in attr.attr_labels:
                    attrs[attr_name] = {
                        "db_id": attr.attr_id,
                        "id": attr.attr_uuid,
                        "name": attr_name,
                        "value": attr.value,
                        "updated_at": attr.updated_at,
                    }

                    if attr.is_protected is not None:
                        attrs[attr_name]["is_protected"] = attr.is_protected

                    if attr.is_visible is not None:
                        attrs[attr_name]["is_visible"] = attr.is_visible

                    if attr.source_uuid:
                        attrs[attr_name]["source"] = attr.source_uuid

                    if attr.owner_uuid:
                        attrs[attr_name]["owner"] = attr.owner_uuid

            # --------------------------------------------------------
            # Relationships
            # --------------------------------------------------------
            if prefetch_relationships and peers:
                for rel_schema in node.schema.relationships:
                    if node_id in peers_per_node and rel_schema.identifier in peers_per_node[node_id]:
                        rel_peers = [peers.get(id) for id in peers_per_node[node_id][rel_schema.identifier]]
                        if rel_schema.cardinality == "one":
                            if len(rel_peers) == 1:
                                attrs[rel_schema.name] = rel_peers[0]
                        elif rel_schema.cardinality == "many":
                            attrs[rel_schema.name] = rel_peers

            node_class = identify_node_class(node=node)
            item = await node_class.init(schema=node.schema, branch=branch, at=at, db=db)
            await item.load(**attrs, db=db)

            nodes[node_id] = item

        return nodes


registry.manager = NodeManager
