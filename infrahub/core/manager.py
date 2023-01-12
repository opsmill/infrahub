from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union
from uuid import UUID

from infrahub.core import get_branch, registry
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
)
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.schema import NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


class NodeManager:
    @classmethod
    async def query(
        cls,
        schema: Union[NodeSchema, str],
        filters: dict = None,
        fields: dict = None,
        limit: int = 100,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        session: Optional[AsyncSession] = None,
        account=None,
        *args,
        **kwargs,
    ) -> List[Node]:
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

        branch = await get_branch(branch, session=session)
        at = Timestamp(at)

        if isinstance(schema, str):
            schema = await registry.get_schema(session=session, name=schema, branch=branch.name)
        elif not isinstance(schema, NodeSchema):
            raise ValueError(f"Invalid schema provided {schema}")

        # Query the list of nodes matching this Query
        query = await NodeGetListQuery.init(
            session=session, schema=schema, branch=branch, limit=limit, filters=filters, at=at
        )
        await query.execute(session=session)
        node_ids = query.get_node_ids()

        response = await cls.get_many(
            ids=node_ids,
            fields=fields,
            branch=branch,
            account=account,
            at=at,
            include_source=include_source,
            session=session,
        )

        return list(response.values()) if node_ids else []

    @classmethod
    async def query_peers(
        cls,
        id: UUID,
        schema: RelationshipSchema,
        filters: dict,
        session: AsyncSession,
        fields: dict = None,
        limit: int = 100,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        account=None,
        *args,
        **kwargs,
    ) -> List[Relationship]:
        branch = await get_branch(branch, session=session)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id=id)

        query = await RelationshipGetPeerQuery.init(
            session=session, source_id=id, schema=schema, filters=filters, rel=rel, limit=limit, at=at
        )
        await query.execute(session=session)

        peers_info = list(query.get_peers())
        peer_ids = [peer.peer_id for peer in peers_info]

        if not peers_info:
            return []

        peers = await cls.get_many(
            ids=peer_ids, branch=branch, account=account, at=at, include_source=include_source, session=session
        )

        return [
            await Relationship(schema=schema, branch=branch, at=at, node_id=id).load(
                session=session,
                id=peer.rel_node_id,
                db_id=peer.rel_node_db_id,
                updated_at=peer.updated_at,
                data={"peer": peers[peer.peer_id]},
            )
            for peer in peers_info
        ]

    @classmethod
    async def get_one(
        cls,
        id: UUID,
        fields: dict = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        session: Optional[AsyncSession] = None,
        account=None,
        *args,
        **kwargs,
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
            session=session,
            *args,
            **kwargs,
        )

        if not result:
            return None

        return result[id]

    @classmethod
    async def get_many(
        cls,
        ids: List[UUID],
        fields: dict = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        session: Optional[AsyncSession] = None,
        account=None,
        *args,
        **kwargs,
    ) -> Dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        # Query all nodes
        query = await NodeListGetInfoQuery.init(session=session, ids=ids, branch=branch, account=account, at=at)
        await query.execute(session=session)
        nodes_info = query.get_nodes(session=session)

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

        # -----------------------------------------------
        # Query Source object
        # -----------------------------------------------
        # NOTE For now we assume that all source object are account objects but we'll need
        # to revisit that quickly
        # source_accounts = {}

        # if include_source:
        #     source_uuids = list(set([item.source_uuid for item in attrs_to_process.values() if item.source_uuid]))
        #     source_accounts = {id: get_account_by_id(id=id) for id in source_uuids}

        # -----------------------------------------------
        # Extract the ID from all LocalAttribute from all Nodes
        # -----------------------------------------------
        # local_attrs_ids = []
        # for attrs in node_attributes.values():
        #     for attr in attrs.get("attrs").values():
        #         if "AttributeLocal" in attr.attr_labels:
        #             local_attrs_ids.append(attr.attr_id)

        # query = NodeListGetLocalAttributeValueQuery(ids=local_attrs_ids, branch=branch, at=at).execute()
        # local_attributes = query.get_results_by_id()

        nodes = {}

        async for node in nodes_info:

            node_id = node.node_uuid
            attrs = {"db_id": node.node_id, "id": node_id, "updated_at": node.updated_at}

            if not node.schema:
                raise Exception(f"Unable to find the Schema associated with {node_id}, {node.labels}")

            # --------------------------------------------------------
            # Attributes
            # --------------------------------------------------------
            for attr_name, attr in node_attributes.get(node_id, {}).get("attrs", {}).items():

                # LOCAL ATTRIBUTE
                if "AttributeLocal" in attr.attr_labels:

                    # replace NULL with None
                    value = attr.value
                    value = None if value == "NULL" else value

                    attrs[attr_name] = dict(
                        db_id=attr.attr_id,
                        id=attr.attr_uuid,
                        name=attr_name,
                        value=value,
                        updated_at=attr.updated_at,
                    )

                    if attr.is_protected is not None:
                        attrs[attr_name]["is_protected"] = attr.is_protected

                    if attr.is_visible is not None:
                        attrs[attr_name]["is_visible"] = attr.is_visible

                    if attr.source_uuid:
                        attrs[attr_name]["source"] = attr.source_uuid

            # Identify the proper Class to use for this Node
            node_class = Node
            if node.schema.kind in registry.node:
                node_class = registry.node[node.schema.kind]

            item = await node_class.init(schema=node.schema, branch=branch, at=at, session=session)
            await item.load(**attrs, session=session)

            nodes[node_id] = item

        return nodes


class SchemaManager(NodeManager):
    @classmethod
    async def register_schema_to_registry(cls, schema: SchemaRoot, branch: Union[str, Branch] = None):
        """Register all nodes from a SchemaRoot object into the registry."""
        for node in schema.nodes:
            await registry.set_schema(node.kind, node, branch=branch)

        return True

    @classmethod
    async def load_schema_to_db(cls, schema: SchemaRoot, session: AsyncSession, branch: Union[str, Branch] = None):
        """Load all nodes from a SchemaRoot object into the database."""

        branch = await get_branch(branch, session=session)

        for node in schema.nodes:
            await cls.load_schema_node_to_db(schema_node=node, branch=branch, session=session)

        return True

    @classmethod
    async def load_schema_node_to_db(
        cls,
        session: AsyncSession,
        schema_node: NodeSchema,
        branch: Union[str, Branch] = None,
    ):

        branch = await get_branch(branch)

        node_schema = await registry.get_schema(session=session, name="NodeSchema", branch=branch)
        attribute_schema = await registry.get_schema(session=session, name="AttributeSchema", branch=branch)
        relationship_schema = await registry.get_schema(session=session, name="RelationshipSchema", branch=branch)

        attrs = []
        rels = []
        for item in schema_node.attributes:
            attr = await Node.init(schema=attribute_schema, branch=branch, session=session)
            await attr.new(**item.dict(), session=session)
            await attr.save(session=session)
            attrs.append(attr)

        for item in schema_node.relationships:
            rel = await Node.init(schema=relationship_schema, branch=branch, session=session)
            await rel.new(**item.dict(), session=session)
            await rel.save(session=session)
            rels.append(rel)

        attribute_ids = [attr.id for attr in attrs] or None
        relationship_ids = [rel.id for rel in rels] or None

        schema_dict = schema_node.dict()
        schema_dict["relationships"] = relationship_ids
        schema_dict["attributes"] = attribute_ids

        node = await Node.init(schema=node_schema, branch=branch, session=session)
        await node.new(**schema_dict, session=session)
        await node.save(session=session)

        return True

    @classmethod
    async def load_schema_from_db(
        self,
        session: AsyncSession,
        branch: Union[str, Branch] = None,
    ) -> SchemaRoot:
        """Query all the node of type node_schema from the database and convert them to NodeSchema."""

        branch = await get_branch(branch, session=session)

        schema = SchemaRoot(nodes=[])

        node_schema = await registry.get_schema(session=session, name="NodeSchema", branch=branch)
        for schema_node in await self.query(node_schema, branch=branch, session=session):
            schema.nodes.append(await self.convert_node_schema_to_schema(schema_node=schema_node, session=session))

        return schema

    @staticmethod
    async def convert_node_schema_to_schema(schema_node: Node, session: AsyncSession) -> NodeSchema:
        """Convert a schema_node object loaded from the database into NodeSchema object."""

        node_data = {}

        # First pull all the attributes at the top level, then convert all the relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        for rel_name in schema_node._relationships:

            if rel_name not in node_data:
                node_data[rel_name] = []

            for rel in getattr(schema_node, rel_name):
                item_data = {}
                item = await rel.get_peer(session=session)
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return NodeSchema(**node_data)
