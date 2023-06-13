from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from infrahub.core import get_branch, registry
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
)
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.schema import NodeSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import SchemaNotFound
from infrahub.utils import deep_merge_dict

if TYPE_CHECKING:
    from uuid import UUID

    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


# pylint: disable=redefined-builtin


class NodeManager:
    @classmethod
    async def query(
        cls,
        schema: Union[NodeSchema, str],
        filters: Optional[dict] = None,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        session: Optional[AsyncSession] = None,
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

        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        if isinstance(schema, str):
            schema = registry.get_schema(name=schema, branch=branch.name)
        elif not isinstance(schema, NodeSchema):
            raise ValueError(f"Invalid schema provided {schema}")

        # Query the list of nodes matching this Query
        query = await NodeGetListQuery.init(
            session=session, schema=schema, branch=branch, offset=offset, limit=limit, filters=filters, at=at
        )
        await query.execute(session=session)
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
            session=session,
            prefetch_relationships=prefetch_relationships,
        )

        return list(response.values()) if node_ids else []

    @classmethod
    async def count(
        cls,
        session: AsyncSession,
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

        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        query = await NodeGetListQuery.init(session=session, schema=schema, branch=branch, filters=filters, at=at)
        return await query.count(session=session)

    @classmethod
    async def count_peers(
        cls,
        id: str,
        schema: RelationshipSchema,
        filters: dict,
        session: AsyncSession,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Union[Branch, str]] = None,
    ) -> int:
        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id=id)

        query = await RelationshipGetPeerQuery.init(
            session=session, source_id=id, schema=schema, filters=filters, rel=rel, at=at
        )
        return await query.count(session=session)

    @classmethod
    async def query_peers(
        cls,
        id: UUID,
        schema: RelationshipSchema,
        filters: dict,
        session: AsyncSession,
        fields: Optional[dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
    ) -> List[Relationship]:
        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id=id)

        query = await RelationshipGetPeerQuery.init(
            session=session, source_id=id, schema=schema, filters=filters, rel=rel, offset=offset, limit=limit, at=at
        )
        await query.execute(session=session)

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
            await Relationship(schema=schema, branch=branch, at=at, node_id=id).load(
                session=session,
                id=peer.rel_node_id,
                db_id=peer.rel_node_db_id,
                updated_at=peer.updated_at,
                data=peer,
            )
            for peer in peers_info
        ]

    @classmethod
    async def get_one(
        cls,
        id: UUID,
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        session: Optional[AsyncSession] = None,
        prefetch_relationships: bool = False,
        account=None,
    ) -> Node:
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
            session=session,
        )

        if not result:
            return None

        return result[id]

    @classmethod
    async def get_many(  # pylint: disable=too-many-branches
        cls,
        ids: List[UUID],
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        prefetch_relationships: bool = False,
        session: Optional[AsyncSession] = None,
        account=None,
    ) -> Dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        # Query all nodes
        query = await NodeListGetInfoQuery.init(session=session, ids=ids, branch=branch, account=account, at=at)
        await query.execute(session=session)
        nodes_info_by_id = {node.node_uuid: node async for node in query.get_nodes()}

        # Query list of all Attributes
        query = await NodeListGetAttributeQuery.init(
            session=session,
            ids=ids,
            fields=fields,
            branch=branch,
            include_source=include_source,
            include_owner=include_owner,
            account=account,
            at=at,
        )
        await query.execute(session=session)
        node_attributes = query.get_attributes_group_by_node()

        # if prefetch_relationships is enabled
        # Query all the peers associated with all nodes at once.
        peers_per_node = None
        peers = None
        if prefetch_relationships:
            query = await NodeListGetRelationshipsQuery.init(session=session, ids=ids, branch=branch, at=at)
            await query.execute(session=session)
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
                session=session,
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

            # Identify the proper Class to use for this Node
            node_class = Node
            if node.schema.kind in registry.node:
                node_class = registry.node[node.schema.kind]

            item = await node_class.init(schema=node.schema, branch=branch, at=at, session=session)
            await item.load(**attrs, session=session)

            nodes[node_id] = item

        return nodes
