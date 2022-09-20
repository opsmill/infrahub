from __future__ import annotations

from typing import Dict, List, Union, TYPE_CHECKING

from infrahub.core import get_branch, registry
from infrahub.core.node import Node
from infrahub.core.node.query import (
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetLocalAttributeValueQuery,
)
from infrahub.core.relationship import Relationship
from infrahub.core.relationship.query import RelationshipGetPeerQuery
from infrahub.core.schema import NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


class NodeManager:
    @classmethod
    def query(
        cls,
        schema: Union[NodeSchema, str],
        filters: dict = None,
        fields: dict = None,
        limit: int = 100,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
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

        branch = get_branch(branch)
        at = Timestamp(at)

        if isinstance(schema, str):
            schema = registry.get_schema(schema, branch=branch.name)
        elif not isinstance(schema, NodeSchema):
            raise ValueError(f"Invalid schema provided {schema}")

        # Query the list of nodes matching this Query
        query = NodeGetListQuery(schema=schema, branch=branch, limit=limit, filters=filters, at=at).execute()
        node_ids = query.get_node_ids()

        return (
            list(
                cls.get_many(
                    ids=node_ids, fields=fields, branch=branch, account=account, at=at, include_source=include_source
                ).values()
            )
            if node_ids
            else []
        )

    @classmethod
    def query_peers(
        cls,
        id: str,
        schema: RelationshipSchema,
        filters: dict,
        fields: dict = None,
        limit: int = 100,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        account=None,
        *args,
        **kwargs,
    ) -> List[Relationship]:
        branch = get_branch(branch)
        at = Timestamp(at)

        query = RelationshipGetPeerQuery(
            source_id=id, schema=schema, filters=filters, rel=Relationship, limit=limit, branch=branch, at=at
        ).execute()
        peers_info = list(query.get_peers())
        peer_ids = [peer.peer_id for peer in peers_info]

        if not peers_info:
            return []

        peers = cls.get_many(ids=peer_ids, branch=branch, account=account, at=at, include_source=include_source)

        return [
            Relationship(schema=schema, branch=branch, at=at, node_id=id).load(
                id=peer.rel_uuid, db_id=peer.rel_id, updated_at=peer.updated_at, data={"peer": peers[peer.peer_id]}
            )
            for peer in peers_info
        ]

    @classmethod
    def get_one(
        cls,
        id: str,
        fields: dict = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        account=None,
        *args,
        **kwargs,
    ) -> Node:
        """Return one node based on its ID."""
        result = cls.get_many(
            ids=[id],
            fields=fields,
            at=at,
            branch=branch,
            include_source=include_source,
            account=account,
            *args,
            **kwargs,
        )

        if not result:
            return None

        return result[id]

    @classmethod
    def get_many(
        cls,
        ids: List[str],
        fields: dict = None,
        at: Union[Timestamp, str] = None,
        branch: Union[Branch, str] = None,
        include_source: bool = False,
        account=None,
        *args,
        **kwargs,
    ) -> Dict[str, Node]:
        """Return a list of nodes based on their IDs."""

        branch = get_branch(branch)
        at = Timestamp(at)

        # Query all nodes
        query = NodeListGetInfoQuery(ids=ids, branch=branch, account=account, at=at).execute()
        nodes_info = query.get_nodes()

        # Query list of all Attributes
        query = NodeListGetAttributeQuery(ids=ids, fields=fields, branch=branch, account=account, at=at).execute()
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

        for node in nodes_info:

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
                    # item = local_attributes[attr.attr_uuid]

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

            item = node_class(schema=node.schema, branch=branch, at=at).load(**attrs)

            nodes[node_id] = item

        return nodes


class SchemaManager(NodeManager):
    @classmethod
    def register_schema_to_registry(cls, schema: SchemaRoot, branch=None):
        """Register all nodes from a SchemaRoot object into the registry."""
        for node in schema.nodes:
            registry.set_schema(node.kind, node)

        return True

    @classmethod
    def load_schema_to_db(cls, schema: SchemaRoot, branch=None):
        """Load all nodes from a SchemaRoot object into the database."""

        branch = get_branch(branch)

        for node in schema.nodes:
            cls.load_schema_node_to_db(node, branch=branch)

        return True

    @classmethod
    def load_schema_node_to_db(cls, schema_node: NodeSchema, branch=None):

        branch = get_branch(branch)

        node_schema = registry.get_schema("NodeSchema")
        attribute_schema = registry.get_schema("AttributeSchema")
        relationship_schema = registry.get_schema("RelationshipSchema")

        attrs = []
        rels = []
        for item in schema_node.attributes:
            attr = Node(attribute_schema, branch=branch).new(**item.dict())
            attr.save()
            attrs.append(attr)

        for item in schema_node.relationships:
            rel = Node(relationship_schema, branch=branch).new(**item.dict())
            rel.save()
            rels.append(rel)

        attribute_ids = [attr.id for attr in attrs] or None
        relationship_ids = [rel.id for rel in rels] or None

        schema_dict = schema_node.dict()
        schema_dict["relationships"] = relationship_ids
        schema_dict["attributes"] = attribute_ids

        node = Node(schema=node_schema, branch=branch).new(**schema_dict)
        node.save()

        return True

    @classmethod
    def load_schema_from_db(self, branch=None) -> SchemaRoot:
        """Query all the node of type node_schema from the database and convert them to NodeSchema."""

        branch = get_branch(branch)

        schema = SchemaRoot(nodes=[])

        node_schema = registry.get_schema("NodeSchema")
        for schema_node in self.query(node_schema, branch=branch):
            schema.nodes.append(self.convert_node_schema_to_schema(schema_node))

        return schema

    @staticmethod
    def convert_node_schema_to_schema(schema_node: Node) -> NodeSchema:
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
                item = rel.peer
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return NodeSchema(**node_data)
