from __future__ import annotations

import copy
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

from graphql import GraphQLSchema
from pydantic import BaseModel, Field

import infrahub.config as config
from infrahub.core import get_branch, get_branch_from_registry, registry
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
)
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.schema import (
    AttributeSchema,
    FilterSchema,
    FilterSchemaKind,
    GenericSchema,
    GroupSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import SchemaNotFound
from infrahub.lock import registry as lock_registry
from infrahub.utils import deep_merge_dict, intersection

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch

SUPPORTED_SCHEMA_NODE_TYPE = ["NodeSchema", "GenericSchema", "GroupSchema"]
SUPPORTED_SCHEMA_EXTENSION_TYPE = ["NodeExtensionSchema"]
INTERNAL_SCHEMA_NODE_KINDS = [node["kind"] for node in internal_schema["nodes"]]

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
        nodes_info = query.get_nodes()
        nodes_info_by_id = {node.node_uuid: node async for node in nodes_info}

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

        for node_id in ids:
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


class SchemaDiff(BaseModel):
    added: List[str] = Field(default_factory=list)
    changed: List[str] = Field(default_factory=list)
    removed: List[str] = Field(default_factory=list)

    @property
    def all(self) -> List[str]:
        return self.changed + self.added + self.removed


class SchemaBranch:
    def __init__(self, cache: Dict, name: Optional[str] = None, data: Optional[Dict[str, int]] = None):
        self._cache: Dict[int, Union[NodeSchema, GenericSchema, GroupSchema]] = cache
        self.name: Optional[str] = name
        self.nodes: Dict[str, int] = {}
        self.generics: Dict[str, int] = {}
        self.groups: Dict[str, int] = {}
        self._graphql_schema = None

        if data:
            self.nodes = data.get("nodes", {})
            self.generics = data.get("generics", {})
            self.groups = data.get("groups", {})

    def __hash__(self) -> int:
        """Calculate the hash for this objects based on the content of nodes, generics and groups.

        Since the object themselves are considered immuable we just need to use the has id from each object to calculate the global hash.
        """
        return hash(tuple(self.nodes.items()) + tuple(self.generics.items()) + tuple(self.groups.items()))

    def to_dict(self) -> Dict[str, Any]:
        # TODO need to implement a flag to return the real objects if needed
        return {"nodes": self.nodes, "generics": self.generics, "groups": self.groups}

    async def get_graphql_schema(self, session: AsyncSession) -> GraphQLSchema:
        from infrahub.graphql import (  # pylint: disable=import-outside-toplevel
            generate_graphql_paginated_schema,
            generate_graphql_schema,
        )

        schema_creator = generate_graphql_schema
        if config.SETTINGS.experimental_features.paginated:
            schema_creator = generate_graphql_paginated_schema

        if not self._graphql_schema:
            self._graphql_schema = await schema_creator(session=session, branch=self.name)

        return self._graphql_schema

    def diff(self, obj: SchemaBranch) -> SchemaDiff:
        local_keys = list(self.nodes.keys()) + list(self.generics.keys()) + list(self.groups.keys())
        other_keys = list(obj.nodes.keys()) + list(obj.generics.keys()) + list(obj.groups.keys())
        present_both = intersection(local_keys, other_keys)
        present_local_only = list(set(local_keys) - set(present_both))
        present_other_only = list(set(other_keys) - set(present_both))

        schema_diff = SchemaDiff(added=present_local_only, removed=present_other_only)
        for key in present_both:
            if key in self.nodes and key in obj.nodes and self.nodes[key] != obj.nodes[key]:
                schema_diff.changed.append(key)
            elif key in self.generics and key in obj.generics and self.generics[key] != obj.generics[key]:
                schema_diff.changed.append(key)
            elif key in self.groups and key in obj.groups and self.groups[key] != obj.groups[key]:
                schema_diff.changed.append(key)

        return schema_diff

    def duplicate(self, name: Optional[str] = None) -> SchemaBranch:
        """Duplicate the current object but conserve the same cache."""
        return self.__class__(name=name, data=copy.deepcopy(self.to_dict()), cache=self._cache)

    def set(self, name: str, schema: Union[NodeSchema, GenericSchema, GroupSchema]) -> int:
        """Store a NodeSchema, GenericSchema or GroupSchema associated with a specific name.

        The object will be stored in the internal cache based on its hash value.
        If a schema with the same name already exist, it will be replaced
        """
        schema_hash = hash(schema)
        if schema_hash not in self._cache:
            self._cache[schema_hash] = schema

        if "Node" in schema.__class__.__name__:
            self.nodes[name] = schema_hash
        elif "Generic" in schema.__class__.__name__:
            self.generics[name] = schema_hash
        elif "Group" in schema.__class__.__name__:
            self.groups[name] = schema_hash

        return schema_hash

    def get(self, name: str) -> Union[NodeSchema, GenericSchema, GroupSchema]:
        """Access a specific NodeSchema, GenericSchema or GroupSchema, defined by its kind.

        To ensure that no-one will ever change an object in the cache,
        the function always returns a copy of the object, not the object itself
        """
        key = None
        if name in self.nodes:
            key = self.nodes[name]
        elif name in self.generics:
            key = self.generics[name]
        elif name in self.groups:
            key = self.groups[name]

        if key:
            return self._cache[key].duplicate()

        raise SchemaNotFound(
            branch_name=self.name, identifier=name, message=f"Unable to find the schema '{name}' in the registry"
        )

    def get_all(self, include_internal: bool = False) -> Dict[str, Union[NodeSchema, GenericSchema, GroupSchema]]:
        """Retrive everything in a single dictionary."""

        return {
            name: self.get(name=name)
            for name in list(self.nodes.keys()) + list(self.generics.keys()) + list(self.groups.keys())
            if include_internal or name not in INTERNAL_SCHEMA_NODE_KINDS
        }

    def load_schema(self, schema: SchemaRoot) -> None:
        """Load a SchemaRoot object and store all NodeSchema, GenericSchema or GroupSchema.

        In the current implementation, if a schema object present in the SchemaRoot already exist, it will be overwritten.
        """
        for item in schema.nodes + schema.generics + schema.groups:
            try:
                existing_item = self.get(name=item.kind)
                new_item = existing_item.duplicate()
                new_item.update(item)
                self.set(name=item.kind, schema=new_item)
            except SchemaNotFound:
                self.set(name=item.kind, schema=item)

        for node_extension in schema.extensions.nodes:
            node = self.get(name=node_extension.kind)

            for item in node_extension.attributes:
                node.attributes.append(item)
            for item in node_extension.relationships:
                node.relationships.append(item)

            self.set(name=node.kind, schema=node)

    def process(self) -> None:
        self.generate_identifiers()
        self.process_inheritance()
        self.process_filters()
        # self.generate_weight()

    def generate_identifiers(self) -> None:
        """Generate the identifier for all relationships if it's not already present."""
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            for rel in node.relationships:
                if rel.identifier:
                    continue

                rel.identifier = str("__".join(sorted([node.kind, rel.peer]))).lower()

            self.set(name=name, schema=node)

    def process_inheritance(self) -> None:
        """Extend all the nodes with the attributes and relationships
        from the Interface objects defined in inherited_from.
        """

        generics_used_by = defaultdict(list)

        # For all node_schema, add the attributes & relationships from the generic / interface
        for name in self.nodes.keys():
            node = self.get(name=name)
            if not node.inherit_from:
                continue

            for generic_kind in node.inherit_from:
                if generic_kind not in self.generics.keys():
                    # TODO add a proper exception for all schema related issue
                    raise ValueError(f"{node.kind} Unable to find the generic {generic_kind}")

                # Store the list of node referencing a specific generics
                generics_used_by[generic_kind].append(node.kind)
                node.inherit_from_interface(interface=self.get(name=generic_kind))

            self.set(name=name, schema=node)

        # Update all generics with the list of nodes referrencing them.
        for generic_name in self.generics.keys():
            generic = self.get(name=generic_name)

            if generic.kind in generics_used_by:
                generic.used_by = sorted(generics_used_by[generic.kind])
            else:
                generic.used_by = []

            self.set(name=generic_name, schema=generic)

    def process_filters(self) -> Node:
        # Generate the filters for all nodes, at the NodeSchema and at the relationships level.
        for node_name in self.nodes:
            node_schema = self.get(name=node_name)
            new_node = node_schema.duplicate()
            new_node.filters = self.generate_filters(schema=new_node, top_level=True, include_relationships=True)

            for rel in new_node.relationships:
                peer_schema = self.get(name=rel.peer)
                if not peer_schema:
                    continue

                rel.filters = self.generate_filters(schema=peer_schema, top_level=False, include_relationships=False)

            self.set(name=node_name, schema=new_node)

    @staticmethod
    def generate_filters(
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


class SchemaManager(NodeManager):
    def __init__(self):
        self._cache: Dict[int, Any] = {}
        self._branches: Dict[str, SchemaBranch] = {}

    def _get_from_cache(self, key):
        return self._cache[key]

    def set(
        self, name: str, schema: Union[NodeSchema, GenericSchema, GroupSchema], branch: Optional[str] = None
    ) -> int:
        branch = branch or config.SETTINGS.main.default_branch

        if branch not in self._branches:
            self._branches[branch] = SchemaBranch(cache=self._cache, name=branch)

        return self._branches[branch].set(name=name, schema=schema)

    def has(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        try:
            self.get(name=name, branch=branch)
            return True
        except SchemaNotFound:
            return False

    def get(
        self, name: str, branch: Optional[Union[Branch, str]] = None
    ) -> Union[NodeSchema, GenericSchema, GroupSchema]:
        # For now we assume that all branches are present, will see how we need to pull new branches later.
        branch = get_branch_from_registry(branch=branch)

        if branch.name in self._branches:
            try:
                return self._branches[branch.name].get(name=name)
            except SchemaNotFound:
                pass

        default_branch = config.SETTINGS.main.default_branch
        return self._branches[default_branch].get(name=name)

    def get_full(
        self, branch: Optional[Union[Branch, str]] = None
    ) -> Dict[str, Union[NodeSchema, GenericSchema, GroupSchema]]:
        branch = get_branch_from_registry(branch=branch)

        branch_name = None
        if branch.name in self._branches:
            branch_name = branch.name
        else:
            branch_name = config.SETTINGS.main.default_branch

        return self._branches[branch_name].get_all()

    async def get_full_safe(
        self, branch: Optional[Union[Branch, str]] = None
    ) -> Dict[str, Union[NodeSchema, GenericSchema, GroupSchema]]:
        await lock_registry.wait_branch_schema_update_available()

        return self.get_full(branch=branch)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name in self._branches:
            return self._branches[name]

        self._branches[name] = SchemaBranch(cache=self._cache, name=name)
        return self._branches[name]

    def set_schema_branch(self, name: str, schema: SchemaBranch) -> None:
        self._branches[name] = schema

    async def update_schema_branch(
        self,
        schema: SchemaBranch,
        session: AsyncSession,
        branch: Optional[Union[Branch, str]] = None,
        limit: Optional[List[str]] = None,
        update_db: bool = True,
    ):
        branch = await get_branch(branch=branch, session=session)

        if update_db:
            await self.load_schema_to_db(schema=schema, session=session, branch=branch, limit=limit)
            # After updating the schema into the db
            # we need to pull a fresh version because some default value are managed/generated within the node object
            updated_schema = await self.load_schema_from_db(session=session, branch=branch)

        self._branches[branch.name] = updated_schema

    def register_schema(self, schema: SchemaRoot, branch: str = None) -> SchemaBranch:
        """Register all nodes, generics & groups from a SchemaRoot object into the registry."""

        branch = branch or config.SETTINGS.main.default_branch
        schema_branch = self.get_schema_branch(name=branch)
        schema_branch.load_schema(schema=schema)
        schema_branch.process()
        return schema_branch

    async def load_schema_to_db(
        self,
        schema: SchemaBranch,
        session: AsyncSession,
        branch: Union[str, Branch] = None,
        limit: Optional[List[str]] = None,
    ) -> None:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await get_branch(branch=branch, session=session)
        for item_kind in list(schema.generics.keys()) + list(schema.nodes.keys()) + list(schema.groups.keys()):
            if limit and item_kind not in limit:
                continue
            item = schema.get(name=item_kind)
            if not item.id:
                node = await self.load_node_to_db(node=item, branch=branch, session=session)
                schema.set(name=item_kind, schema=node)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, session=session)
                schema.set(name=item_kind, schema=node)

    async def load_node_to_db(
        self,
        session: AsyncSession,
        node: Union[NodeSchema, GenericSchema, GroupSchema],
        branch: Union[str, Branch] = None,
    ) -> None:
        """Load a Node with its attributes and its relationships to the database.

        FIXME Currently this function only support adding new node, we need to update it to update existing nodes as well.
        """
        branch = await get_branch(branch=branch, session=session)

        node_type = node.__class__.__name__

        if node_type not in SUPPORTED_SCHEMA_NODE_TYPE:
            raise ValueError(f"Only schema node of type {SUPPORTED_SCHEMA_NODE_TYPE} are supported")

        node_schema = self.get(name=node_type, branch=branch)
        attribute_schema = self.get(name="AttributeSchema", branch=branch)
        relationship_schema = self.get(name="RelationshipSchema", branch=branch)

        # Duplicate the node in order to store the IDs after inserting them in the database
        new_node = node.duplicate()

        # Create the node first
        schema_dict = node.dict(exclude={"id", "filters", "relationships", "attributes"})
        obj = await Node.init(schema=node_schema, branch=branch, session=session)
        await obj.new(**schema_dict, session=session)
        await obj.save(session=session)
        new_node.id = obj.id

        # Then create the Attributes and the relationships
        if isinstance(node, (NodeSchema, GenericSchema)):
            new_node.relationships = [item for item in new_node.relationships if item.inherited]
            new_node.attributes = [item for item in new_node.attributes if item.inherited]

            for item in node.local_attributes:
                new_attr = await self.create_attribute_in_db(
                    schema=attribute_schema, item=item, parent=obj, branch=branch, session=session
                )
                new_node.attributes.append(new_attr)

            for item in node.local_relationships:
                new_rel = await self.create_relationship_in_db(
                    schema=relationship_schema, item=item, parent=obj, branch=branch, session=session
                )
                new_node.relationships.append(new_rel)

        # Save back the node with the newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db(
        self,
        session: AsyncSession,
        node: Union[NodeSchema, GenericSchema, GroupSchema],
        branch: Union[str, Branch] = None,
    ) -> None:
        """Update a Node with its attributes and its relationships in the database."""
        branch = await get_branch(branch=branch, session=session)

        node_type = node.__class__.__name__

        if node_type not in SUPPORTED_SCHEMA_NODE_TYPE:
            raise ValueError(f"Only schema node of type {SUPPORTED_SCHEMA_NODE_TYPE} are supported")

        # Update the node First
        schema_dict = node.dict(exclude={"id", "filters", "relationships", "attributes"})
        obj = await self.get_one(id=node.id, branch=branch, session=session, include_owner=True, include_source=True)

        if not obj:
            raise SchemaNotFound(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        attribute_schema = self.get(name="AttributeSchema", branch=branch)
        relationship_schema = self.get(name="RelationshipSchema", branch=branch)

        # Update all direct attributes attributes
        for key, value in schema_dict.items():
            getattr(obj, key).value = value

        new_node = node.duplicate()

        # Update the attributes and the relationships nodes as well
        await obj.attributes.update(session=session, data=[item.id for item in node.local_attributes if item.id])
        await obj.relationships.update(session=session, data=[item.id for item in node.local_relationships if item.id])
        await obj.save(session=session)

        # Then Update the Attributes and the relationships
        if isinstance(node, (NodeSchema, GenericSchema)):
            items = await self.get_many(
                ids=[item.id for item in node.local_attributes + node.local_relationships if item.id],
                session=session,
                branch=branch,
                include_owner=True,
                include_source=True,
            )

            for item in node.local_attributes:
                if item.id and item.id in items:
                    await self.update_attribute_in_db(item=item, attr=items[item.id], session=session)
                elif not item.id:
                    new_attr = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, branch=branch, session=session, parent=obj
                    )
                    new_node.attributes.append(new_attr)

            for item in node.local_relationships:
                if item.id and item.id in items:
                    await self.update_relationship_in_db(item=item, rel=items[item.id], session=session)
                elif not item.id:
                    new_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, branch=branch, session=session, parent=obj
                    )
                    new_node.relationships.append(new_rel)

        # Save back the node with the (potnetially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    @staticmethod
    async def create_attribute_in_db(
        schema: NodeSchema, item: AttributeSchema, branch: Branch, session: AsyncSession, parent: Node
    ) -> AttributeSchema:
        obj = await Node.init(schema=schema, branch=branch, session=session)
        await obj.new(**item.dict(exclude={"id", "filters"}), node=parent, session=session)
        await obj.save(session=session)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def create_relationship_in_db(
        schema: NodeSchema, item: RelationshipSchema, branch: Branch, session: AsyncSession, parent: Node
    ) -> RelationshipSchema:
        obj = await Node.init(schema=schema, branch=branch, session=session)
        await obj.new(**item.dict(exclude={"id", "filters"}), node=parent, session=session)
        await obj.save(session=session)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_attribute_in_db(item: AttributeSchema, attr: Node, session: AsyncSession) -> None:
        item_dict = item.dict(exclude={"id", "filters"})
        for key, value in item_dict.items():
            getattr(attr, key).value = value
        await attr.save(session=session)

    @staticmethod
    async def update_relationship_in_db(item: RelationshipSchema, rel: Node, session: AsyncSession) -> None:
        item_dict = item.dict(exclude={"id", "filters"})
        for key, value in item_dict.items():
            getattr(rel, key).value = value
        await rel.save(session=session)

    async def load_schema_from_db(
        self,
        session: AsyncSession,
        branch: Union[str, Branch] = None,
    ) -> SchemaBranch:
        """Query all the node of type NodeSchema, GenericSchema and GroupSchema from the database and convert them to their respective type."""

        branch = await get_branch(branch=branch, session=session)
        schema = SchemaBranch(cache=self._cache, name=branch.name)

        group_schema = self.get(name="GroupSchema", branch=branch)
        for schema_node in await self.query(
            schema=group_schema, branch=branch, prefetch_relationships=True, session=session
        ):
            schema.set(
                name=schema_node.kind.value, schema=await self.convert_group_schema_to_schema(schema_node=schema_node)
            )

        generic_schema = self.get(name="GenericSchema", branch=branch)
        for schema_node in await self.query(
            schema=generic_schema, branch=branch, prefetch_relationships=True, session=session
        ):
            schema.set(
                name=schema_node.kind.value,
                schema=await self.convert_generic_schema_to_schema(schema_node=schema_node, session=session),
            )

        node_schema = self.get(name="NodeSchema", branch=branch)
        for schema_node in await self.query(
            schema=node_schema, branch=branch, prefetch_relationships=True, session=session
        ):
            schema.set(
                name=schema_node.kind.value,
                schema=await self.convert_node_schema_to_schema(schema_node=schema_node, session=session),
            )

        schema.process()
        self._branches[branch.name] = schema

        return schema

    @staticmethod
    async def convert_node_schema_to_schema(schema_node: Node, session: AsyncSession) -> NodeSchema:
        """Convert a schema_node object loaded from the database into NodeSchema object."""

        node_data = {"id": schema_node.id}

        # First pull all the local attributes at the top level, then convert all the local relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        for rel_name in schema_node._relationships:
            if rel_name not in node_data:
                node_data[rel_name] = []

            rm = getattr(schema_node, rel_name)
            for rel in await rm.get(session=session):
                item = await rel.get_peer(session=session)
                item_data = {"id": item.id}
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return NodeSchema(**node_data)

    @staticmethod
    async def convert_generic_schema_to_schema(schema_node: Node, session: AsyncSession) -> GenericSchema:
        """Convert a schema_node object loaded from the database into GenericSchema object."""

        node_data = {"id": schema_node.id}

        # First pull all the attributes at the top level, then convert all the relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        for rel_name in schema_node._relationships:
            if rel_name not in node_data:
                node_data[rel_name] = []

            rm = getattr(schema_node, rel_name)
            for rel in await rm.get(session=session):
                item = await rel.get_peer(session=session)
                item_data = {"id": item.id}
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return GenericSchema(**node_data)

    @staticmethod
    async def convert_group_schema_to_schema(schema_node: Node) -> GroupSchema:
        """Convert a schema_node object loaded from the database into GroupSchema object."""

        node_data = {"id": schema_node.id}

        # First pull all the attributes at the top level, then convert all the relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            node_data[attr_name] = getattr(schema_node, attr_name).value

        return GroupSchema(**node_data)
