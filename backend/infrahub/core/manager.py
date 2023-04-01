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
from infrahub.core.schema import (
    FilterSchema,
    FilterSchemaKind,
    GenericSchema,
    GroupSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.exceptions import SchemaNotFound
from infrahub.utils import deep_merge_dict
from infrahub_client.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch

SUPPORTED_SCHEMA_NODE_TYPE = ["NodeSchema", "GenericSchema", "GroupSchema"]

# pylint: disable=redefined-builtin


class NodeManager:
    @classmethod
    async def query(
        cls,
        schema: Union[NodeSchema, str],
        filters: Optional[dict] = None,
        fields: Optional[dict] = None,
        limit: int = 100,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        session: Optional[AsyncSession] = None,
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
            session=session, schema=schema, branch=branch, limit=limit, filters=filters, at=at
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
        )

        return list(response.values()) if node_ids else []

    @classmethod
    async def query_peers(
        cls,
        id: UUID,
        schema: RelationshipSchema,
        filters: dict,
        session: AsyncSession,
        fields: Optional[dict] = None,
        limit: int = 100,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
    ) -> List[Relationship]:
        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        rel = Relationship(schema=schema, branch=branch, node_id=id)

        query = await RelationshipGetPeerQuery.init(
            session=session, source_id=id, schema=schema, filters=filters, rel=rel, limit=limit, at=at
        )
        await query.execute(session=session)

        peers_info = list(query.get_peers())

        # if display_label has been requested we need to ensure we are querying the right fields
        if fields and "display_label" in fields:
            peer_schema = await schema.get_peer_schema()
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
            session=session,
        )

        if not result:
            return None

        return result[id]

    @classmethod
    async def get_many(
        cls,
        ids: List[UUID],
        fields: Optional[dict] = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        include_owner: bool = False,
        session: Optional[AsyncSession] = None,
        account=None,
    ) -> Dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = await get_branch(branch=branch, session=session)
        at = Timestamp(at)

        # Query all nodes
        query = await NodeListGetInfoQuery.init(session=session, ids=ids, branch=branch, account=account, at=at)
        await query.execute(session=session)
        nodes_info = query.get_nodes()

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

        nodes = {}

        async for node in nodes_info:
            node_id = node.node_uuid
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
    async def register_schema_to_registry(cls, schema: SchemaRoot, branch: str = None):
        """Register all nodes & generics from a SchemaRoot object into the registry."""
        for item in schema.generics + schema.nodes + schema.groups:
            registry.set_schema(name=item.kind, schema=item, branch=branch)

        return True

    @classmethod
    async def load_schema_to_db(cls, schema: SchemaRoot, session: AsyncSession, branch: Union[str, Branch] = None):
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await get_branch(branch=branch, session=session)

        for item in schema.generics + schema.nodes + schema.groups:
            await cls.load_node_to_db(node=item, branch=branch, session=session)

        return True

    @staticmethod
    async def generate_filters(
        schema: NodeSchema, top_level: bool = False, include_relationships: bool = False
    ) -> List[FilterSchema]:
        """Generate the FilterSchema for a given NodeSchema object."""

        filters = []

        if top_level:
            filters.append(FilterSchema(name="ids", kind=FilterSchemaKind.LIST))

        else:
            filters.append(FilterSchema(name="id", kind=FilterSchemaKind.TEXT))

        for attr in schema.attributes:
            if attr.kind in ["Text", "String"]:
                filter = FilterSchema(name=f"{attr.name}__value", kind=FilterSchemaKind.TEXT)
            elif attr.kind in ["Number", "Integer"]:
                filter = FilterSchema(name=f"{attr.name}__value", kind=FilterSchemaKind.NUMBER)
            elif attr.kind in ["Boolean", "Checkbox"]:
                filter = FilterSchema(name=f"{attr.name}__value", kind=FilterSchemaKind.BOOLEAN)
            else:
                continue

            if attr.enum:
                filter.enum = attr.enum

            filters.append(filter)

        if not include_relationships:
            return filters

        for rel in schema.relationships:
            if rel.kind in ["Attribute", "Parent"]:
                filters.append(FilterSchema(name=f"{rel.name}__id", kind=FilterSchemaKind.OBJECT, object_kind=rel.peer))

        return filters

    @classmethod
    async def load_node_to_db(
        cls,
        session: AsyncSession,
        node: Union[NodeSchema, GenericSchema, GroupSchema],
        branch: Union[str, Branch] = None,
    ) -> None:
        """Load a Node with its attributes and its relationships to the database."""
        branch = await get_branch(branch=branch, session=session)

        node_type = node.__class__.__name__

        if node_type not in SUPPORTED_SCHEMA_NODE_TYPE:
            raise ValueError(f"Only schema node of type {SUPPORTED_SCHEMA_NODE_TYPE} are supported")

        node_schema = registry.get_schema(name=node_type, branch=branch)
        attribute_schema = registry.get_schema(name="AttributeSchema", branch=branch)
        relationship_schema = registry.get_schema(name="RelationshipSchema", branch=branch)

        # Create the node first
        schema_dict = node.dict(exclude={"filters", "relationships", "attributes"})
        obj = await Node.init(schema=node_schema, branch=branch, session=session)
        await obj.new(**schema_dict, session=session)
        await obj.save(session=session)

        # Then create the Attributes and the relationships
        if isinstance(node, (NodeSchema, GenericSchema)):
            for item in node.local_attributes:
                attr = await Node.init(schema=attribute_schema, branch=branch, session=session)
                await attr.new(**item.dict(exclude={"filters"}), node=obj, session=session)
                await attr.save(session=session)

            for item in node.local_relationships:
                rel = await Node.init(schema=relationship_schema, branch=branch, session=session)
                await rel.new(**item.dict(exclude={"filters"}), node=obj, session=session)
                await rel.save(session=session)

    @classmethod
    async def load_schema_from_db(
        cls,
        session: AsyncSession,
        branch: Union[str, Branch] = None,
    ) -> SchemaRoot:
        """Query all the node of type NodeSchema, GenericSchema and GroupSchema from the database and convert them to their respective type."""

        branch = await get_branch(branch=branch, session=session)

        schema = SchemaRoot()

        group_schema = registry.get_schema(name="GroupSchema", branch=branch)
        for schema_node in await cls.query(schema=group_schema, branch=branch, session=session):
            schema.groups.append(await cls.convert_group_schema_to_schema(schema_node=schema_node))

        generic_schema = registry.get_schema(name="GenericSchema", branch=branch)
        for schema_node in await cls.query(schema=generic_schema, branch=branch, session=session):
            schema.generics.append(await cls.convert_generic_schema_to_schema(schema_node=schema_node, session=session))

        node_schema = registry.get_schema(name="NodeSchema", branch=branch)
        for schema_node in await cls.query(schema=node_schema, branch=branch, session=session):
            schema.nodes.append(await cls.convert_node_schema_to_schema(schema_node=schema_node, session=session))

        schema.extend_nodes_with_interfaces()

        # Generate the filters for all nodes, at the NodeSchema and at the relationships level.
        for node in schema.nodes:
            node.filters = await SchemaManager.generate_filters(schema=node, top_level=True, include_relationships=True)

            for rel in node.relationships:
                peer_schema = [node for node in schema.nodes if node.kind == rel.peer]
                if not peer_schema:
                    continue

                rel.filters = await SchemaManager.generate_filters(
                    schema=peer_schema[0], top_level=False, include_relationships=False
                )

        return schema

    @staticmethod
    async def convert_node_schema_to_schema(schema_node: Node, session: AsyncSession) -> NodeSchema:
        """Convert a schema_node object loaded from the database into NodeSchema object."""

        node_data = {}

        # First pull all the local attributes at the top level, then convert all the local relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        for rel_name in schema_node._relationships:
            if rel_name not in node_data:
                node_data[rel_name] = []

            rm = getattr(schema_node, rel_name)
            for rel in await rm.get(session=session):
                item_data = {}
                item = await rel.get_peer(session=session)
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return NodeSchema(**node_data)

    @staticmethod
    async def convert_generic_schema_to_schema(schema_node: Node, session: AsyncSession) -> GenericSchema:
        """Convert a schema_node object loaded from the database into GenericSchema object."""

        node_data = {}

        # First pull all the attributes at the top level, then convert all the relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        for rel_name in schema_node._relationships:
            if rel_name not in node_data:
                node_data[rel_name] = []

            rm = getattr(schema_node, rel_name)
            for rel in await rm.get(session=session):
                item_data = {}
                item = await rel.get_peer(session=session)
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return GenericSchema(**node_data)

    @staticmethod
    async def convert_group_schema_to_schema(schema_node: Node) -> GroupSchema:
        """Convert a schema_node object loaded from the database into GroupSchema object."""

        node_data = {}

        # First pull all the attributes at the top level, then convert all the relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        # for rel_name in schema_node._relationships:

        #     if rel_name not in node_data:
        #         node_data[rel_name] = []

        #     for rel in getattr(schema_node, rel_name):
        #         item_data = {}
        #         item = await rel.get_peer(session=session)
        #         for item_name in item._attributes:
        #             item_data[item_name] = getattr(item, item_name).value

        #         node_data[rel_name].append(item_data)

        return GroupSchema(**node_data)
