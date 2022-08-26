from __future__ import annotations

from typing import List

from infrahub.core import get_branch, registry
from infrahub.core.node import Node
from infrahub.core.node.query import (
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetLocalAttributeValueQuery,
)
from infrahub.core.relationship.query import RelationshipGetPeerQuery
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp


class NodeManager:
    @classmethod
    def query(
        cls,
        schema,
        filters: dict = None,
        limit=100,
        at=None,
        branch=None,
        include_source=False,
        account=None,
        *args,
        **kwargs,
    ) -> List[Node]:
        """Query one or multiple nodes of a given type based on filter arguments.

        Args:
            schema (NodeSchema or Str): Infrahub Schema or Name of a schema present in the registry.
            filters (dict, optional): filters provided in a dictionary
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

        query = NodeGetListQuery(schema=schema, branch=branch, limit=limit, filters=filters, at=at).execute()

        node_ids = query.get_node_ids()

        return (
            list(
                cls.get_many(
                    ids=node_ids, branch=branch, account=account, at=at, include_source=include_source
                ).values()
            )
            if node_ids
            else []
        )

    @classmethod
    def query_peers(
        cls,
        id,
        schema,
        filters,
        limit=100,
        at=None,
        branch=None,
        include_source=False,
        account=None,
        *args,
        **kwargs,
    ):
        branch = get_branch(branch)
        at = Timestamp(at)

        query = RelationshipGetPeerQuery(
            source_id=id, schema=schema, filters=filters, limit=limit, branch=branch, at=at
        ).execute()
        peer_ids = query.get_peer_ids()

        return (
            list(
                cls.get_many(
                    ids=peer_ids, branch=branch, account=account, at=at, include_source=include_source
                ).values()
            )
            if peer_ids
            else []
        )

    @classmethod
    def get_one(cls, id: str, at=None, branch=None, include_source=False, account=None, *args, **kwargs) -> Node:

        result = cls.get_many(
            ids=[id], at=at, branch=branch, include_source=include_source, account=account, *args, **kwargs
        )

        if not result:
            return None

        return result[id]

    @classmethod
    def get_many(
        cls, ids: List[str], at=None, branch=None, include_source=False, account=None, *args, **kwargs
    ) -> List[Node]:

        branch = get_branch(branch)
        at = Timestamp(at)

        # Query list of all Attributes
        query = NodeListGetAttributeQuery(ids=ids, branch=branch, account=account, at=at).execute()
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
        # Pre-Query remote_node for all remote Attributes
        # -----------------------------------------------
        # TODO need to re-enable
        # remote_node_ids = []
        # remote_nodes = {}
        # for attrs in node_attributes.values():
        #     for attr in attrs.get("attrs").values():
        #         if "AttributeRemote" in attr.attr_labels:
        #             remote_node_ids.append(attr.attr_value_uuid)

        # if remote_node_ids:
        #     remote_nodes = cls.get_many(ids=list(set(remote_node_ids)), branch=branch, account=account, at=at)

        # -----------------------------------------------
        # Extract the ID from all LocalAttribute from all Nodes
        # -----------------------------------------------
        local_attrs_ids = []
        for attrs in node_attributes.values():
            for attr in attrs.get("attrs").values():
                if "AttributeLocal" in attr.attr_labels:
                    local_attrs_ids.append(attr.attr_id)

        query = NodeListGetLocalAttributeValueQuery(ids=local_attrs_ids, branch=branch, at=at).execute()

        local_attributes = query.get_results_by_id()

        nodes = {}
        for node_id, node in node_attributes.items():

            attrs = {"db_id": node["node"].id, "id": node_id}

            # Identify the type of the node and find its associated Class
            node_schema = None
            for label in node["node"].labels:
                if registry.has_schema(label):
                    node_schema = registry.get_schema(label)
                    break

            if not node_schema:
                raise Exception(f"Unable to find the Schema associated with {node_id}, {node['node'].labels}")

            # --------------------------------------------------------
            # Attributes
            # --------------------------------------------------------
            for attr_name, attr in node.get("attrs").items():

                # LOCAL ATTRIBUTE
                if "AttributeLocal" in attr.attr_labels:
                    item = local_attributes[attr.attr_uuid]

                    # replace NULL with None
                    value = item.get("av").get("value")
                    value = None if value == "NULL" else value

                    attrs[attr_name] = dict(
                        db_id=item.get("a").id,
                        id=item.get("a").get("uuid"),
                        # is_inherited=attr.is_inherited,
                        name=attr_name,
                        # permission=attr.permission,
                        value=value,
                        # source=source_accounts.get(attr.source_uuid, None),
                    )

            if not attrs:
                return None

            node_class = Node
            if node_schema.kind in registry.node:
                node_class = registry.node[node_schema.kind]

            item = node_class(schema=node_schema, branch=branch, at=at).load(**attrs)

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
