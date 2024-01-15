from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from infrahub_sdk.utils import duplicates, intersection
from pydantic import BaseModel, Field

import infrahub.config as config
from infrahub import lock
from infrahub.core import get_branch, get_branch_from_registry
from infrahub.core.constants import (
    RESERVED_ATTR_GEN_NAMES,
    RESERVED_ATTR_REL_NAMES,
    RESTRICTED_NAMESPACES,
    BranchSupportType,
    FilterSchemaKind,
    InfrahubKind,
    RelationshipCardinality,
    RelationshipDirection,
    RelationshipKind,
)
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaBranchDiff, SchemaBranchHash
from infrahub.core.node import Node
from infrahub.core.property import FlagPropertyMixin, NodePropertyMixin
from infrahub.core.schema import (
    AttributeSchema,
    FilterSchema,
    GenericSchema,
    GroupSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.utils import parse_node_kind
from infrahub.exceptions import SchemaNotFound
from infrahub.graphql import generate_graphql_schema
from infrahub.log import get_logger
from infrahub.utils import format_label
from infrahub.visuals import select_color

log = get_logger()


if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin,too-many-public-methods,too-many-lines

INTERNAL_SCHEMA_NODE_KINDS = [node["namespace"] + node["name"] for node in internal_schema["nodes"]]
SUPPORTED_SCHEMA_NODE_TYPE = [
    "SchemaGroup",
    "SchemaGeneric",
    "SchemaNode",
]
SUPPORTED_SCHEMA_EXTENSION_TYPE = ["NodeExtensionSchema"]

KIND_FILTER_MAP = {
    "Text": FilterSchemaKind.TEXT,
    "String": FilterSchemaKind.TEXT,
    "Number": FilterSchemaKind.NUMBER,
    "Integer": FilterSchemaKind.NUMBER,
    "Boolean": FilterSchemaKind.BOOLEAN,
    "Checkbox": FilterSchemaKind.BOOLEAN,
    "Dropdown": FilterSchemaKind.TEXT,
}


class SchemaDiff(BaseModel):
    added: List[str] = Field(default_factory=list)
    changed: List[str] = Field(default_factory=list)
    removed: List[str] = Field(default_factory=list)

    @property
    def all(self) -> List[str]:
        return self.changed + self.added + self.removed


class SchemaNamespace(BaseModel):
    name: str
    user_editable: bool


class SchemaBranch:
    def __init__(self, cache: Dict, name: Optional[str] = None, data: Optional[Dict[str, int]] = None):
        self._cache: Dict[str, Union[NodeSchema, GenericSchema, GroupSchema]] = cache
        self.name: Optional[str] = name
        self.nodes: Dict[str, str] = {}
        self.generics: Dict[str, str] = {}
        self.groups: Dict[str, str] = {}
        self._graphql_schema = None

        if data:
            self.nodes = data.get("nodes", {})
            self.generics = data.get("generics", {})
            self.groups = data.get("groups", {})

    def get_hash(self) -> str:
        """Calculate the hash for this objects based on the content of nodes, generics and groups.

        Since the object themselves are considered immuable we just need to use the hash from each object to calculate the global hash.
        """
        md5hash = hashlib.md5()
        for key, value in sorted(tuple(self.nodes.items()) + tuple(self.generics.items()) + tuple(self.groups.items())):
            md5hash.update(str(key).encode())
            md5hash.update(str(value).encode())

        return md5hash.hexdigest()

    def get_hash_full(self) -> SchemaBranchHash:
        return SchemaBranchHash(main=self.get_hash(), nodes=self.nodes, generics=self.generics, groups=self.groups)

    def to_dict(self) -> Dict[str, Any]:
        # TODO need to implement a flag to return the real objects if needed
        return {"nodes": self.nodes, "generics": self.generics, "groups": self.groups}

    async def get_graphql_schema(self, db: InfrahubDatabase) -> GraphQLSchema:
        if not self._graphql_schema:
            self._graphql_schema = await generate_graphql_schema(db=db, branch=self.name)

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

    def set(self, name: str, schema: Union[NodeSchema, GenericSchema, GroupSchema]) -> str:
        """Store a NodeSchema, GenericSchema or GroupSchema associated with a specific name.

        The object will be stored in the internal cache based on its hash value.
        If a schema with the same name already exist, it will be replaced
        """
        schema_hash = schema.get_hash()
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

    def has(self, name: str) -> bool:
        try:
            self.get(name=name)
            return True
        except SchemaNotFound:
            return False

    def get_all(self, include_internal: bool = False) -> Dict[str, Union[NodeSchema, GenericSchema, GroupSchema]]:
        """Retrive everything in a single dictionary."""

        return {
            name: self.get(name=name)
            for name in list(self.nodes.keys()) + list(self.generics.keys()) + list(self.groups.keys())
            if include_internal or name not in INTERNAL_SCHEMA_NODE_KINDS
        }

    def get_namespaces(self, include_internal: bool = False) -> List[SchemaNamespace]:
        all_schemas = self.get_all(include_internal=include_internal)
        namespaces: Dict[str, SchemaNamespace] = {}
        for schema in all_schemas.values():
            if isinstance(schema, GroupSchema):
                continue
            if schema.namespace in namespaces:
                continue
            namespaces[schema.namespace] = SchemaNamespace(
                name=schema.namespace, user_editable=schema.namespace not in RESTRICTED_NAMESPACES
            )

        return list(namespaces.values())

    def get_schemas_for_namespaces(
        self, namespaces: Optional[List[str]] = None, include_internal: bool = False
    ) -> List[Union[NodeSchema, GenericSchema]]:
        """Retrive everything in a single dictionary."""
        all_schemas = self.get_all(include_internal=include_internal)
        if namespaces:
            return [schema for schema in all_schemas.values() if schema.namespace in namespaces]
        return list(all_schemas.values())

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
            new_item = self.get(name=node_extension.kind)
            new_item.update(node_extension)
            self.set(name=node_extension.kind, schema=new_item)

    def process(self) -> None:
        self.process_pre_validation()
        self.process_validate()
        self.process_post_validation()

    def process_pre_validation(self) -> None:
        self.generate_identifiers()
        self.process_default_values()
        self.process_inheritance()
        self.process_hierarchy()
        self.process_branch_support()

    def process_validate(self) -> None:
        self.validate_names()
        self.validate_menu_placements()
        self.validate_kinds()
        self.validate_identifiers()

    def process_post_validation(self) -> None:
        self.add_groups()
        self.add_hierarchy()
        self.process_filters()
        self.generate_weight()
        self.process_labels()
        self.process_dropdowns()

    def generate_identifiers(self) -> None:
        """Generate the identifier for all relationships if it's not already present."""
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            for rel in node.relationships:
                if rel.identifier:
                    continue

                rel.identifier = str("__".join(sorted([node.kind, rel.peer]))).lower()

            self.set(name=name, schema=node)

    def validate_identifiers(self) -> None:
        """Validate that all relationships have a unique identifier for a given model."""
        # Organize all the relationships per identifier and node
        rels_per_identifier: Dict[str, Dict[str, List[RelationshipSchema]]] = defaultdict(lambda: defaultdict(list))
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            for rel in node.relationships:
                rels_per_identifier[rel.identifier][name].append(rel)

        valid_options = [
            [RelationshipDirection.BIDIR, RelationshipDirection.BIDIR],
            sorted([RelationshipDirection.INBOUND, RelationshipDirection.OUTBOUND]),
        ]

        for identifier, rels_per_kind in rels_per_identifier.items():
            # Per node kind, check if the directions are good
            for _, rels in rels_per_kind.items():
                directions = sorted([rel.direction.value for rel in rels])
                if not (len(rels) == 1 or (len(rels) == 2 and directions == ["inbound", "outbound"])):
                    names_directions = [(rel.name, rel.direction.value) for rel in rels]
                    raise ValueError(
                        f"{node.kind}: Identifier of relationships must be unique for a given direction > {identifier!r} : {names_directions}"
                    ) from None

                # Continue if no other model is using this identifier
                if len(rels_per_kind) == 1:
                    continue

                # If this node has 2 relationships, BIDIRECTIONAL is not a valid option on the remote node
                if len(rels) == 2:
                    for rel in rels:
                        if (
                            rel.peer in list(rels_per_kind.keys())
                            and len(rels_per_kind[rel.peer]) == 1
                            and rels_per_kind[rel.peer][0].direction == RelationshipDirection.BIDIR
                        ):
                            raise ValueError(
                                f"{node.kind}: Incompatible direction detected on Reverse Relationship for {rel.name!r} ({identifier!r}) "
                                f" > {RelationshipDirection.BIDIR.value} "
                            ) from None

                elif (
                    len(rels) == 1
                    and rels[0].peer in list(rels_per_kind.keys())
                    and len(rels_per_kind[rels[0].peer]) == 1
                ):
                    peer_direction = rels_per_kind[rels[0].peer][0].direction
                    if sorted([peer_direction, rels[0].direction]) not in valid_options:
                        raise ValueError(
                            f"{node.kind}: Incompatible direction detected on Reverse Relationship for {rels[0].name!r} ({identifier!r})"
                            f" {rels[0].direction.value} <> {peer_direction.value}"
                        ) from None

    def validate_names(self) -> None:
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            if names_dup := duplicates(node.attribute_names + node.relationship_names):
                raise ValueError(
                    f"{node.kind}: Names of attributes and relationships must be unique : {names_dup}"
                ) from None

            if node.kind in INTERNAL_SCHEMA_NODE_KINDS:
                continue

            for attr in node.attributes:
                if attr.name in RESERVED_ATTR_REL_NAMES or (
                    isinstance(node, GenericSchema) and attr.name in RESERVED_ATTR_GEN_NAMES
                ):
                    raise ValueError(f"{node.kind}: {attr.name} isn't allowed as an attribute name.")
            for rel in node.relationships:
                if rel.name in RESERVED_ATTR_REL_NAMES or (
                    isinstance(node, GenericSchema) and rel.name in RESERVED_ATTR_GEN_NAMES
                ):
                    raise ValueError(f"{node.kind}: {rel.name} isn't allowed as a relationship name.")

    def validate_menu_placements(self) -> None:
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)
            if node.menu_placement:
                try:
                    self.get(name=node.menu_placement)
                except SchemaNotFound:
                    raise ValueError(f"{node.kind}: {node.menu_placement} is not a valid menu placement") from None

    def validate_kinds(self) -> None:
        for name in list(self.nodes.keys()):
            node = self.get(name=name)

            for generic_kind in node.inherit_from:
                if self.has(name=generic_kind):
                    if not isinstance(self.get(name=generic_kind), GenericSchema):
                        raise ValueError(
                            f"{node.kind}: Only generic model can be used as part of inherit_from, {generic_kind!r} is not a valid entry."
                        ) from None
                else:
                    raise ValueError(
                        f"{node.kind}: {generic_kind!r} is not a invalid Generic to inherit from"
                    ) from None

            for rel in node.relationships:
                if rel.peer in [InfrahubKind.GENERICGROUP]:
                    continue
                if not self.has(rel.peer):
                    raise ValueError(
                        f"{node.kind}: Relationship {rel.name!r} is referencing an invalid peer {rel.peer!r}"
                    ) from None

    def process_dropdowns(self) -> None:
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            changed = False

            attributes = [attr for attr in node.attributes if attr.kind == "Dropdown"]
            for attr in attributes:
                if not attr.choices:
                    continue

                sorted_choices = sorted(attr.choices or [], key=lambda x: x.name, reverse=True)
                defined_colors = [choice.color for choice in sorted_choices if choice.color]
                for choice in sorted_choices:
                    if not choice.color:
                        choice.color = select_color(defined_colors)
                    if not choice.label:
                        choice.label = format_label(choice.name)
                    if not choice.description:
                        choice.description = ""

                if attr.choices != sorted_choices:
                    attr.choices = sorted_choices
                    changed = True

            if changed:
                self.set(name=name, schema=node)

    def process_labels(self) -> None:
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            changed = False

            if not node.label:
                node.label = format_label(node.name)
                changed = True

            for attr in node.attributes:
                if not attr.label:
                    attr.label = format_label(attr.name)
                    changed = True

            for rel in node.relationships:
                if not rel.label:
                    rel.label = format_label(rel.name)
                    changed = True

            if changed:
                self.set(name=name, schema=node)

    def process_hierarchy(self) -> None:
        for name in self.nodes.keys():
            node = self.get(name=name)

            if not node.hierarchy and not node.parent and not node.children:
                continue

            if not node.hierarchy and (node.parent is not None or node.children is not None):
                raise ValueError(f"{node.kind} Hierarchy must be provided if either parent or children is defined.")

            changed = False
            if node.hierarchy not in self.generics.keys():
                # TODO add a proper exception for all schema related issue
                raise ValueError(f"{node.kind} Unable to find the generic {node.hierarchy!r} provided in 'hierarchy'.")

            if node.hierarchy not in node.inherit_from:
                node.inherit_from.append(node.hierarchy)
                changed = True

            if node.parent is None:
                node.parent = node.hierarchy
                changed = True
            elif node.parent != "":
                if node.parent not in list(self.nodes.keys()) + list(self.generics.keys()):
                    raise ValueError(f"{node.kind} Unable to find the node {node.parent!r} provided in 'parent'.")

            if node.children is None:
                node.children = node.hierarchy
                changed = True
            elif node.children != "":
                if node.children not in list(self.nodes.keys()) + list(self.generics.keys()):
                    raise ValueError(f"{node.kind} Unable to find the node {node.children!r} provided in 'children'.")

            if changed:
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

            generics_used_by["CoreNode"].append(node.kind)

            generic_with_hierarchical_support = []
            for generic_kind in node.inherit_from:
                if generic_kind not in self.generics.keys():
                    # TODO add a proper exception for all schema related issue
                    raise ValueError(f"{node.kind} Unable to find the generic {generic_kind}")

                if self.get(generic_kind).hierarchical:
                    generic_with_hierarchical_support.append(generic_kind)

                # Store the list of node referencing a specific generics
                generics_used_by[generic_kind].append(node.kind)
                node.inherit_from_interface(interface=self.get(name=generic_kind))

            if len(generic_with_hierarchical_support) > 1:
                raise ValueError(
                    f"{node.kind} Only one generic with hierarchical support is allowed per node {generic_with_hierarchical_support}"
                )
            if len(generic_with_hierarchical_support) == 1 and node.hierarchy is None:
                node.hierarchy = generic_with_hierarchical_support[0]

            self.set(name=name, schema=node)

        # Update all generics with the list of nodes referrencing them.
        for generic_name in self.generics.keys():
            generic = self.get(name=generic_name)

            if generic.kind in generics_used_by:
                generic.used_by = sorted(generics_used_by[generic.kind])
            else:
                generic.used_by = []

            self.set(name=generic_name, schema=generic)

    def process_branch_support(self) -> None:
        """Set branch support flag on all attributes and relationships if not already defined.

        if either node on a relationship support branch, the relationship must be branch aware.
        """
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            for attr in node.attributes:
                if attr.branch is not None:
                    continue

                attr.branch = node.branch

            for rel in node.relationships:
                if rel.branch is not None:
                    continue

                peer_node = self.get(name=rel.peer)
                if isinstance(peer_node, GroupSchema) or node.branch == peer_node.branch:
                    rel.branch = node.branch
                elif BranchSupportType.LOCAL in (node.branch, peer_node.branch):
                    rel.branch = BranchSupportType.LOCAL
                else:
                    rel.branch = BranchSupportType.AWARE

            self.set(name=name, schema=node)

    def process_default_values(self) -> None:
        """Ensure that all attributes with a default value are flagged as optional: True."""
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            for attr in node.attributes:
                if attr.default_value is None:
                    continue

                if attr.default_value is not None and not attr.optional:
                    attr.optional = True

            self.set(name=name, schema=node)

    def process_filters(self) -> Node:
        # Generate the filters for all nodes and generics, at the NodeSchema and at the relationships level.
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)
            node.filters = self.generate_filters(schema=node, include_relationships=True)

            for rel in node.relationships:
                peer_schema = self.get(name=rel.peer)
                if not peer_schema or isinstance(peer_schema, GroupSchema):
                    continue

                rel.filters = self.generate_filters(schema=peer_schema, include_relationships=False)

            self.set(name=name, schema=node)

    def generate_weight(self):
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)
            current_weight = 0
            changed = False
            for item in node.attributes + node.relationships:
                current_weight += 1000
                if not item.order_weight:
                    item.order_weight = current_weight
                    changed = True

            if changed:
                self.set(name=name, schema=node)

    def add_groups(self):
        if not self.has(name=InfrahubKind.GENERICGROUP):
            return

        for node_name in list(self.nodes.keys()) + list(self.generics.keys()):
            schema: Union[NodeSchema, GenericSchema] = self.get(name=node_name)

            if isinstance(schema, NodeSchema) and InfrahubKind.GENERICGROUP in schema.inherit_from:
                continue

            if schema.kind in INTERNAL_SCHEMA_NODE_KINDS or schema.kind == InfrahubKind.GENERICGROUP:
                continue

            if "member_of_groups" not in schema.relationship_names:
                schema.relationships.append(
                    RelationshipSchema(
                        name="member_of_groups",
                        identifier="group_member",
                        peer=InfrahubKind.GENERICGROUP,
                        kind=RelationshipKind.GROUP,
                        cardinality=RelationshipCardinality.MANY,
                        branch=BranchSupportType.AWARE,
                    )
                )

            if "subscriber_of_groups" not in schema.relationship_names:
                schema.relationships.append(
                    RelationshipSchema(
                        name="subscriber_of_groups",
                        identifier="group_subscriber",
                        peer=InfrahubKind.GENERICGROUP,
                        kind=RelationshipKind.GROUP,
                        cardinality=RelationshipCardinality.MANY,
                        branch=BranchSupportType.AWARE,
                    )
                )

            self.set(name=node_name, schema=schema)

    def add_hierarchy(self):
        for node_name in self.nodes.keys():
            node: NodeSchema = self.get(name=node_name)

            if node.parent is None and node.children is None:
                continue

            if node.parent and "parent" not in node.relationship_names:
                node.relationships.append(
                    RelationshipSchema(
                        name="parent",
                        identifier="parent__child",
                        peer=node.parent,
                        kind=RelationshipKind.HIERARCHY,
                        cardinality=RelationshipCardinality.ONE,
                        branch=BranchSupportType.AWARE,
                        direction=RelationshipDirection.OUTBOUND,
                        hierarchical=node.hierarchy,
                    )
                )

            if node.children and "children" not in node.relationship_names:
                node.relationships.append(
                    RelationshipSchema(
                        name="children",
                        identifier="parent__child",
                        peer=node.children,
                        kind=RelationshipKind.HIERARCHY,
                        cardinality=RelationshipCardinality.MANY,
                        branch=BranchSupportType.AWARE,
                        direction=RelationshipDirection.INBOUND,
                        hierarchical=node.hierarchy,
                    )
                )

            self.set(name=node_name, schema=node)

    def generate_filters(
        self, schema: Union[NodeSchema, GenericSchema], include_relationships: bool = False
    ) -> List[FilterSchema]:
        """Generate the FilterSchema for a given NodeSchema or GenericSchema object."""
        # pylint: disable=too-many-branches
        filters = []

        filters.append(FilterSchema(name="ids", kind=FilterSchemaKind.LIST))

        for attr in schema.attributes:
            filter_kind = KIND_FILTER_MAP.get(attr.kind, None)
            if not filter_kind:
                continue

            filter = FilterSchema(name=f"{attr.name}__value", kind=filter_kind)

            if attr.enum:
                filter.enum = attr.enum

            filters.append(filter)
            filters.append(FilterSchema(name=f"{attr.name}__values", kind=FilterSchemaKind.LIST))

            for flag_prop in FlagPropertyMixin._flag_properties:
                filters.append(FilterSchema(name=f"{attr.name}__{flag_prop}", kind=FilterSchemaKind.BOOLEAN))
            for node_prop in NodePropertyMixin._node_properties:
                filters.append(FilterSchema(name=f"{attr.name}__{node_prop}__id", kind=FilterSchemaKind.TEXT))

        # Define generic filters, mainly used to query all nodes associated with a given account
        if include_relationships:
            filters.append(FilterSchema(name="any__value", kind=FilterSchemaKind.TEXT))
            for flag_prop in FlagPropertyMixin._flag_properties:
                filters.append(FilterSchema(name=f"any__{flag_prop}", kind=FilterSchemaKind.BOOLEAN))
            for node_prop in NodePropertyMixin._node_properties:
                filters.append(FilterSchema(name=f"any__{node_prop}__id", kind=FilterSchemaKind.TEXT))

        if not include_relationships:
            return filters

        for rel in schema.relationships:
            if rel.kind not in ["Attribute", "Parent"]:
                continue
            filters.append(FilterSchema(name=f"{rel.name}__ids", kind=FilterSchemaKind.LIST, object_kind=rel.peer))
            peer_schema = self.get(name=rel.peer)

            for attr in peer_schema.attributes:
                filter_kind = KIND_FILTER_MAP.get(attr.kind, None)
                if not filter_kind:
                    continue

                filter = FilterSchema(name=f"{rel.name}__{attr.name}__value", kind=filter_kind)

                if attr.enum:
                    filter.enum = attr.enum

                filters.append(filter)
                filters.append(FilterSchema(name=f"{rel.name}__{attr.name}__values", kind=FilterSchemaKind.LIST))

                for flag_prop in FlagPropertyMixin._flag_properties:
                    filters.append(
                        FilterSchema(name=f"{rel.name}__{attr.name}__{flag_prop}", kind=FilterSchemaKind.BOOLEAN)
                    )
                for node_prop in NodePropertyMixin._node_properties:
                    filters.append(
                        FilterSchema(name=f"{rel.name}__{attr.name}__{node_prop}__id", kind=FilterSchemaKind.TEXT)
                    )

        return filters


# pylint: disable=too-many-public-methods
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

        self._branches[branch].set(name=name, schema=schema)

        return hash(self._branches[branch])

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
        await lock.registry.local_schema_wait()

        return self.get_full(branch=branch)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name in self._branches:
            return self._branches[name]

        self._branches[name] = SchemaBranch(cache=self._cache, name=name)
        return self._branches[name]

    def set_schema_branch(self, name: str, schema: SchemaBranch) -> None:
        self._branches[name] = schema

    def process_schema_branch(self, name: str):
        schema_branch = self.get_schema_branch(name=name)
        schema_branch.process()

    async def update_schema_branch(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = None,
        limit: Optional[List[str]] = None,
        update_db: bool = True,
    ):
        branch = await get_branch(branch=branch, db=db)

        if update_db:
            await self.load_schema_to_db(schema=schema, db=db, branch=branch, limit=limit)
            # After updating the schema into the db
            # we need to pull a fresh version because some default value are managed/generated within the node object
            schema_diff = None
            if limit:
                schema_diff = SchemaBranchDiff(
                    nodes=[name for name in list(schema.nodes.keys()) if name in limit],
                    generics=[name for name in list(schema.generics.keys()) if name in limit],
                    groups=[name for name in list(schema.groups.keys()) if name in limit],
                )

            updated_schema = await self.load_schema_from_db(
                db=db, branch=branch, schema=schema, schema_diff=schema_diff
            )

        self._branches[branch.name] = updated_schema

    def register_schema(self, schema: SchemaRoot, branch: Optional[str] = None) -> SchemaBranch:
        """Register all nodes, generics & groups from a SchemaRoot object into the registry."""

        branch = branch or config.SETTINGS.main.default_branch
        schema_branch = self.get_schema_branch(name=branch)
        schema_branch.load_schema(schema=schema)
        schema_branch.process()
        return schema_branch

    async def load_schema_to_db(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Union[str, Branch] = None,
        limit: Optional[List[str]] = None,
    ) -> None:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await get_branch(branch=branch, db=db)

        for item_kind in list(schema.generics.keys()) + list(schema.nodes.keys()) + list(schema.groups.keys()):
            if limit and item_kind not in limit:
                continue
            item = schema.get(name=item_kind)
            if not item.id:
                node = await self.load_node_to_db(node=item, branch=branch, db=db)
                schema.set(name=item_kind, schema=node)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, db=db)
                schema.set(name=item_kind, schema=node)

    async def load_node_to_db(
        self,
        node: Union[NodeSchema, GenericSchema, GroupSchema],
        db: InfrahubDatabase,
        branch: Union[str, Branch] = None,
    ) -> None:
        """Load a Node with its attributes and its relationships to the database.

        FIXME Currently this function only support adding new node, we need to update it to update existing nodes as well.
        """
        branch = await get_branch(branch=branch, db=db)

        node_type = "SchemaGroup"
        if isinstance(node, GenericSchema):
            node_type = "SchemaGeneric"
        elif isinstance(node, NodeSchema):
            node_type = "SchemaNode"

        if node_type not in SUPPORTED_SCHEMA_NODE_TYPE:
            raise ValueError(f"Only schema node of type {SUPPORTED_SCHEMA_NODE_TYPE} are supported: {node_type}")

        node_schema = self.get(name=node_type, branch=branch)
        attribute_schema = self.get(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get(name="SchemaRelationship", branch=branch)

        # Duplicate the node in order to store the IDs after inserting them in the database
        new_node = node.duplicate()

        # Create the node first
        schema_dict = node.model_dump(exclude={"id", "filters", "relationships", "attributes"})
        obj = await Node.init(schema=node_schema, branch=branch, db=db)
        await obj.new(**schema_dict, db=db)
        await obj.save(db=db)
        new_node.id = obj.id

        # Then create the Attributes and the relationships
        if isinstance(node, (NodeSchema, GenericSchema)):
            new_node.relationships = []
            new_node.attributes = []

            for item in node.attributes:
                new_attr = await self.create_attribute_in_db(
                    schema=attribute_schema, item=item, parent=obj, branch=branch, db=db
                )
                new_node.attributes.append(new_attr)

            for item in node.relationships:
                new_rel = await self.create_relationship_in_db(
                    schema=relationship_schema, item=item, parent=obj, branch=branch, db=db
                )
                new_node.relationships.append(new_rel)

        # Save back the node with the newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db(
        self,
        db: InfrahubDatabase,
        node: Union[NodeSchema, GenericSchema, GroupSchema],
        branch: Union[str, Branch] = None,
    ) -> None:
        """Update a Node with its attributes and its relationships in the database."""
        branch = await get_branch(branch=branch, db=db)

        if isinstance(node, GenericSchema):
            node_type = "SchemaGeneric"
        elif isinstance(node, NodeSchema):
            node_type = "SchemaNode"

        if node_type not in SUPPORTED_SCHEMA_NODE_TYPE:
            raise ValueError(f"Only schema node of type {SUPPORTED_SCHEMA_NODE_TYPE} are supported: {node_type}")

        # Update the node First
        schema_dict = node.model_dump(exclude={"id", "filters", "relationships", "attributes"})
        obj = await self.get_one(id=node.id, branch=branch, db=db, include_owner=True, include_source=True)

        if not obj:
            raise SchemaNotFound(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        attribute_schema = self.get(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get(name="SchemaRelationship", branch=branch)

        # Update all direct attributes attributes
        for key, value in schema_dict.items():
            getattr(obj, key).value = value

        new_node = node.duplicate()

        # Update the attributes and the relationships nodes as well
        await obj.attributes.update(db=db, data=[item.id for item in node.local_attributes if item.id])
        await obj.relationships.update(db=db, data=[item.id for item in node.local_relationships if item.id])
        await obj.save(db=db)

        # Then Update the Attributes and the relationships
        if isinstance(node, (NodeSchema, GenericSchema)):
            items = await self.get_many(
                ids=[item.id for item in node.local_attributes + node.local_relationships if item.id],
                db=db,
                branch=branch,
                include_owner=True,
                include_source=True,
            )

            for item in node.local_attributes:
                if item.id and item.id in items:
                    await self.update_attribute_in_db(item=item, attr=items[item.id], db=db)
                elif not item.id:
                    new_attr = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_node.attributes.append(new_attr)

            for item in node.local_relationships:
                if item.id and item.id in items:
                    await self.update_relationship_in_db(item=item, rel=items[item.id], db=db)
                elif not item.id:
                    new_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_node.relationships.append(new_rel)

        # Save back the node with the (potnetially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    @staticmethod
    async def create_attribute_in_db(
        schema: NodeSchema, item: AttributeSchema, branch: Branch, parent: Node, db: InfrahubDatabase
    ) -> AttributeSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.model_dump(exclude={"id", "filters"}), node=parent, db=db)
        await obj.save(db=db)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def create_relationship_in_db(
        schema: NodeSchema, item: RelationshipSchema, branch: Branch, parent: Node, db: InfrahubDatabase
    ) -> RelationshipSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.model_dump(exclude={"id", "filters"}), node=parent, db=db)
        await obj.save(db=db)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_attribute_in_db(item: AttributeSchema, attr: Node, db: InfrahubDatabase) -> None:
        item_dict = item.model_dump(exclude={"id", "filters"})
        for key, value in item_dict.items():
            getattr(attr, key).value = value
        await attr.save(db=db)

    @staticmethod
    async def update_relationship_in_db(item: RelationshipSchema, rel: Node, db: InfrahubDatabase) -> None:
        item_dict = item.model_dump(exclude={"id", "filters"})
        for key, value in item_dict.items():
            getattr(rel, key).value = value
        await rel.save(db=db)

    async def load_schema(
        self,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
    ) -> SchemaBranch:
        """Load the schema either from the cache or from the database"""
        branch = await get_branch(branch=branch, db=db)

        if not branch.is_default and branch.origin_branch:
            origin_branch: Branch = await get_branch(branch=branch.origin_branch, db=db)

            if origin_branch.schema_hash.main == branch.schema_hash.main:
                origin_schema = self.get_schema_branch(name=origin_branch.name)
                new_branch_schema = origin_schema.duplicate()
                self.set_schema_branch(name=branch.name, schema=new_branch_schema)
                log.info("Loading schema from cache")
                return new_branch_schema

        current_schema = self.get_schema_branch(name=branch.name)
        schema_diff = current_schema.get_hash_full().compare(branch.schema_hash)
        return await self.load_schema_from_db(db=db, branch=branch, schema=current_schema, schema_diff=schema_diff)

    async def load_schema_from_db(
        self,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
        schema: Optional[SchemaBranch] = None,
        schema_diff: Optional[SchemaBranchDiff] = None,
    ) -> SchemaBranch:
        """Query all the node of type NodeSchema, GenericSchema and GroupSchema from the database and convert them to their respective type.

        Args:
            db: Database Driver
            branch: Name of the branch to load the schema from. Defaults to None.
            schema: (Optional) If a schema is provided, it will be updated with the latest value, if not a new one will be created.
            schema_diff: (Optional). List of nodes, generics & groups to query

        Returns:
            SchemaBranch
        """

        branch = await get_branch(branch=branch, db=db)
        schema = schema or SchemaBranch(cache=self._cache, name=branch.name)

        # If schema_diff has been provided, we need to build the proper filters for the queries based on the namespace and the name of the object.
        # the namespace and the name will be extracted from the kind with the function `parse_node_kind`
        filters = {"generics": {}, "groups": {}, "nodes": {}}
        has_filters = False
        if schema_diff:
            log.info("Loading schema from DB", schema_to_update=schema_diff.to_list())

            for node_type in list(filters.keys()):
                filter_value = {
                    "namespace__values": list(
                        {parse_node_kind(item).namespace for item in getattr(schema_diff, node_type)}
                    ),
                    "name__values": list({parse_node_kind(item).name for item in getattr(schema_diff, node_type)}),
                }

                if filter_value["namespace__values"]:
                    filters[node_type] = filter_value
                    has_filters = True

        if not has_filters or filters["groups"]:
            group_schema = self.get(name="SchemaGroup", branch=branch)
            for schema_node in await self.query(
                schema=group_schema, branch=branch, filters=filters["groups"], prefetch_relationships=True, db=db
            ):
                schema.set(
                    name=schema_node.kind.value,
                    schema=await self.convert_group_schema_to_schema(schema_node=schema_node),
                )

        if not has_filters or filters["generics"]:
            generic_schema = self.get(name="SchemaGeneric", branch=branch)
            for schema_node in await self.query(
                schema=generic_schema, branch=branch, filters=filters["generics"], prefetch_relationships=True, db=db
            ):
                kind = f"{schema_node.namespace.value}{schema_node.name.value}"
                schema.set(
                    name=kind,
                    schema=await self.convert_generic_schema_to_schema(schema_node=schema_node, db=db),
                )

        if not has_filters or filters["nodes"]:
            node_schema = self.get(name="SchemaNode", branch=branch)
            for schema_node in await self.query(
                schema=node_schema, branch=branch, filters=filters["nodes"], prefetch_relationships=True, db=db
            ):
                kind = f"{schema_node.namespace.value}{schema_node.name.value}"
                schema.set(
                    name=kind,
                    schema=await self.convert_node_schema_to_schema(schema_node=schema_node, db=db),
                )

        schema.process()
        self._branches[branch.name] = schema

        return schema

    @staticmethod
    async def convert_node_schema_to_schema(schema_node: Node, db: InfrahubDatabase) -> NodeSchema:
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
            for rel in await rm.get(db=db):
                item = await rel.get_peer(db=db)
                item_data = {"id": item.id}
                for item_name in item._attributes:
                    item_data[item_name] = getattr(item, item_name).value

                node_data[rel_name].append(item_data)

        return NodeSchema(**node_data)

    @staticmethod
    async def convert_generic_schema_to_schema(schema_node: Node, db: InfrahubDatabase) -> GenericSchema:
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
            for rel in await rm.get(db=db):
                item = await rel.get_peer(db=db)
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
