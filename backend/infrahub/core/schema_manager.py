from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from infrahub_sdk.topological_sort import DependencyCycleExistsError, topological_sort
from infrahub_sdk.utils import compare_lists, duplicates, intersection
from pydantic import BaseModel

from infrahub import lock
from infrahub.core.constants import (
    RESERVED_ATTR_GEN_NAMES,
    RESERVED_ATTR_REL_NAMES,
    RESTRICTED_NAMESPACES,
    BranchSupportType,
    FilterSchemaKind,
    HashableModelState,
    InfrahubKind,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipDirection,
    RelationshipKind,
)
from infrahub.core.manager import NodeManager
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.models import (
    HashableModelDiff,
    SchemaBranchDiff,
    SchemaBranchHash,
    SchemaDiff,
    SchemaUpdateValidationResult,
)
from infrahub.core.node import Node
from infrahub.core.property import FlagPropertyMixin, NodePropertyMixin
from infrahub.core.registry import registry
from infrahub.core.schema import (
    AttributePathParsingError,
    AttributeSchema,
    BaseNodeSchema,
    FilterSchema,
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
    RelationshipSchema,
    SchemaAttributePath,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.utils import parse_node_kind
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.log import get_logger
from infrahub.utils import format_label
from infrahub.visuals import select_color

log = get_logger()

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin,too-many-public-methods,too-many-lines

INTERNAL_SCHEMA_NODE_KINDS = [node["namespace"] + node["name"] for node in internal_schema["nodes"]]

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

IGNORE_FOR_NODE = {"id", "state", "filters", "relationships", "attributes"}


class SchemaNamespace(BaseModel):
    name: str
    user_editable: bool


class SchemaBranch:
    def __init__(self, cache: Dict, name: Optional[str] = None, data: Optional[Dict[str, int]] = None):
        self._cache: Dict[str, Union[NodeSchema, GenericSchema]] = cache
        self.name: Optional[str] = name
        self.nodes: Dict[str, str] = {}
        self.generics: Dict[str, str] = {}
        self.profiles: Dict[str, str] = {}
        self._graphql_schema: Optional[GraphQLSchema] = None
        self._graphql_manager: Optional[GraphQLSchemaManager] = None

        if data:
            self.nodes = data.get("nodes", {})
            self.generics = data.get("generics", {})
            self.profiles = data.get("profiles", {})

    @property
    def node_names(self) -> List[str]:
        return list(self.nodes.keys())

    @property
    def generic_names(self) -> List[str]:
        return list(self.generics.keys())

    @property
    def profile_names(self) -> List[str]:
        return list(self.profiles.keys())

    def get_all_kind_id_map(self, exclude_profiles: bool = False) -> Dict[str, str]:
        kind_id_map = {}
        if exclude_profiles:
            names = self.node_names + [gn for gn in self.generic_names if gn != InfrahubKind.PROFILE]
        else:
            names = self.all_names
        for name in names:
            item = self.get(name=name, duplicate=False)
            kind_id_map[name] = item.id
        return kind_id_map

    @property
    def all_names(self) -> List[str]:
        return self.node_names + self.generic_names + self.profile_names

    def get_hash(self) -> str:
        """Calculate the hash for this objects based on the content of nodes and generics.

        Since the object themselves are considered immuable we just need to use the hash from each object to calculate the global hash.
        """
        md5hash = hashlib.md5()
        for key, value in sorted(tuple(self.nodes.items()) + tuple(self.generics.items())):
            md5hash.update(str(key).encode())
            md5hash.update(str(value).encode())

        return md5hash.hexdigest()

    def get_hash_full(self) -> SchemaBranchHash:
        return SchemaBranchHash(main=self.get_hash(), nodes=self.nodes, generics=self.generics)

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": self.nodes, "generics": self.generics, "profiles": self.profiles}

    def to_dict_schema_object(self, duplicate: bool = False) -> Dict[str, Dict[str, MainSchemaTypes]]:
        return {
            "nodes": {name: self.get(name, duplicate=duplicate) for name in self.nodes},
            "profiles": {name: self.get(name, duplicate=duplicate) for name in self.profiles},
            "generics": {name: self.get(name, duplicate=duplicate) for name in self.generics},
        }

    def clear_cache(self):
        self._graphql_manager = None
        self._graphql_schema = None

    def get_graphql_manager(self) -> GraphQLSchemaManager:
        if not self._graphql_manager:
            self._graphql_manager = GraphQLSchemaManager(schema=self)
        return self._graphql_manager

    def get_graphql_schema(
        self,
        include_query: bool = True,
        include_mutation: bool = True,
        include_subscription: bool = True,
        include_types: bool = True,
    ) -> GraphQLSchema:
        if not self._graphql_schema:
            self._graphql_schema = self.get_graphql_manager().generate(
                include_query=include_query,
                include_mutation=include_mutation,
                include_subscription=include_subscription,
                include_types=include_types,
            )
        return self._graphql_schema

    def diff(self, other: SchemaBranch) -> SchemaDiff:
        # Identify the nodes or generics that have been added or removed
        local_kind_id_map = self.get_all_kind_id_map(exclude_profiles=True)
        other_kind_id_map = other.get_all_kind_id_map(exclude_profiles=True)
        clean_local_ids = [id for id in local_kind_id_map.values() if id is not None]
        clean_other_ids = [id for id in other_kind_id_map.values() if id is not None]
        shared_ids = intersection(list1=clean_local_ids, list2=clean_other_ids)

        local_keys = [kind for kind, id in local_kind_id_map.items() if id not in shared_ids]
        other_keys = [kind for kind, id in other_kind_id_map.items() if id not in shared_ids]

        present_both, present_local_only, present_other_only = compare_lists(list1=local_keys, list2=other_keys)

        added_elements = {element: HashableModelDiff() for element in present_other_only}
        removed_elements = {element: HashableModelDiff() for element in present_local_only}
        schema_diff = SchemaDiff(added=added_elements, removed=removed_elements)

        # Process of the one that have been updated to identify the list of impacted fields
        for key in present_both:
            local_node = self.get(name=key, duplicate=False)
            other_node = other.get(name=key, duplicate=False)
            diff_node = other_node.diff(other=local_node)
            if diff_node.has_diff:
                schema_diff.changed[key] = diff_node

        reversed_map_local = dict(map(reversed, local_kind_id_map.items()))
        reversed_map_other = dict(map(reversed, other_kind_id_map.items()))

        for shared_id in shared_ids:
            local_node = self.get(name=reversed_map_local[shared_id], duplicate=False)
            other_node = other.get(name=reversed_map_other[shared_id], duplicate=False)
            diff_node = other_node.diff(other=local_node)
            if other_node.state == HashableModelState.ABSENT:
                schema_diff.removed[reversed_map_other[shared_id]] = None
            elif diff_node.has_diff:
                schema_diff.changed[reversed_map_other[shared_id]] = diff_node

        return schema_diff

    def update(self, schema: SchemaBranch) -> None:
        """Update another SchemaBranch into this one."""

        local_kinds = list(self.nodes.keys()) + list(self.generics.keys())
        other_kinds = list(schema.nodes.keys()) + list(schema.generics.keys())

        in_both, _, other_only = compare_lists(list1=local_kinds, list2=other_kinds)

        for item_kind in in_both:
            other_item = schema.get(name=item_kind)
            new_item = self.get(name=item_kind)
            new_item.update(other_item)
            self.set(name=item_kind, schema=new_item)

        for item_kind in other_only:
            other_item = schema.get(name=item_kind)
            self.set(name=item_kind, schema=other_item)

        # for item_kind in local_only:
        #     if item_kind in self.nodes:
        #         del self.nodes[item_kind]
        #     else:
        #         del self.generics[item_kind]

    def validate_update(self, other: SchemaBranch) -> SchemaUpdateValidationResult:
        diff = self.diff(other=other)
        result = SchemaUpdateValidationResult.init(diff=diff, schema=other)
        result.validate_all(migration_map=MIGRATION_MAP, validator_map=CONSTRAINT_VALIDATOR_MAP)
        return result

    def duplicate(self, name: Optional[str] = None) -> SchemaBranch:
        """Duplicate the current object but conserve the same cache."""
        return self.__class__(name=name, data=copy.deepcopy(self.to_dict()), cache=self._cache)

    def set(self, name: str, schema: MainSchemaTypes) -> str:
        """Store a NodeSchema or GenericSchema associated with a specific name.

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
        elif "Profile" in schema.__class__.__name__:
            self.profiles[name] = schema_hash

        return schema_hash

    def get(self, name: str, duplicate: bool = True) -> MainSchemaTypes:
        """Access a specific NodeSchema or GenericSchema, defined by its kind.

        To ensure that no-one will ever change an object in the cache,
        by default the function always returns a copy of the object, not the object itself

        If duplicate is set to false, the real object will be returned.
        """
        key = None
        if name in self.nodes:
            key = self.nodes[name]
        elif name in self.generics:
            key = self.generics[name]
        elif name in self.profiles:
            key = self.profiles[name]

        if key and duplicate:
            return self._cache[key].duplicate()
        if key and not duplicate:
            return self._cache[key]

        raise SchemaNotFoundError(
            branch_name=self.name, identifier=name, message=f"Unable to find the schema {name!r} in the registry"
        )

    def get_node(self, name: str, duplicate: bool = True) -> NodeSchema:
        """Access a specific NodeSchema, defined by its kind."""
        item = self.get(name=name, duplicate=duplicate)
        if not isinstance(item, NodeSchema):
            raise ValueError(f"{name!r} is not of type NodeSchema")
        return item

    def get_generic(self, name: str, duplicate: bool = True) -> GenericSchema:
        """Access a specific GenericSchema, defined by its kind."""
        item = self.get(name=name, duplicate=duplicate)
        if not isinstance(item, GenericSchema):
            raise ValueError(f"{name!r} is not of type GenericSchema")
        return item

    def get_profile(self, name: str, duplicate: bool = True) -> ProfileSchema:
        """Access a specific ProfileSchema, defined by its kind."""
        item = self.get(name=name, duplicate=duplicate)
        if not isinstance(item, ProfileSchema):
            raise ValueError(f"{name!r} is not of type ProfileSchema")
        return item

    def delete(self, name: str) -> None:
        if name in self.nodes:
            del self.nodes[name]
        elif name in self.generics:
            del self.generics[name]
        elif name in self.profiles:
            del self.profiles[name]
        else:
            raise SchemaNotFoundError(
                branch_name=self.name, identifier=name, message=f"Unable to find the schema {name!r} in the registry"
            )

    def get_by_id(self, id: str, duplicate: bool = True) -> MainSchemaTypes:
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)
            if node.id != id:
                continue
            if duplicate is False:
                return node
            return self.get(name=name, duplicate=True)

        raise SchemaNotFoundError(
            branch_name=self.name,
            identifier=id,
            message=f"Unable to find the schema with the id {id!r} in the registry",
        )

    def get_by_any_id(self, id: str) -> MainSchemaTypes:
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)
            if node.id == id:
                return node

            # search in the attributes and the relationships
            try:
                node.get_attribute_by_id(id=id)
                return node

            except ValueError:
                pass

            try:
                node.get_relationship_by_id(id=id)
                return node
            except ValueError:
                pass

        raise SchemaNotFoundError(
            branch_name=self.name,
            identifier=id,
            message=f"Unable to find the schema with the id {id!r} or with an attribute or a relationship with this id",
        )

    def has(self, name: str) -> bool:
        try:
            self.get(name=name, duplicate=False)
            return True
        except SchemaNotFoundError:
            return False

    def get_all(self, include_internal: bool = False, duplicate: bool = True) -> Dict[str, MainSchemaTypes]:
        """Retrieve everything in a single dictionary."""

        return {
            name: self.get(name=name, duplicate=duplicate)
            for name in self.all_names
            if include_internal or name not in INTERNAL_SCHEMA_NODE_KINDS
        }

    def get_namespaces(self, include_internal: bool = False) -> List[SchemaNamespace]:
        all_schemas = self.get_all(include_internal=include_internal, duplicate=False)
        namespaces: Dict[str, SchemaNamespace] = {}
        for schema in all_schemas.values():
            if schema.namespace in namespaces:
                continue
            namespaces[schema.namespace] = SchemaNamespace(
                name=schema.namespace, user_editable=schema.namespace not in RESTRICTED_NAMESPACES
            )

        return list(namespaces.values())

    def get_schemas_for_namespaces(
        self, namespaces: Optional[List[str]] = None, include_internal: bool = False
    ) -> List[MainSchemaTypes]:
        """Retrive everything in a single dictionary."""
        all_schemas = self.get_all(include_internal=include_internal, duplicate=False)
        if namespaces:
            return [schema for schema in all_schemas.values() if schema.namespace in namespaces]
        return list(all_schemas.values())

    def get_schemas_by_rel_identifier(self, identifier: str) -> List[MainSchemaTypes]:
        nodes: List[RelationshipSchema] = []
        for node_name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=node_name, duplicate=False)
            rel = node.get_relationship_by_identifier(id=identifier, raise_on_error=False)
            if rel:
                nodes.append(self.get(name=node_name, duplicate=True))
        return nodes

    def load_schema(self, schema: SchemaRoot) -> None:
        """Load a SchemaRoot object and store all NodeSchema or GenericSchema.

        In the current implementation, if a schema object present in the SchemaRoot already exist, it will be overwritten.
        """
        for item in schema.nodes + schema.generics:
            try:
                if item.id:
                    new_item = self.get_by_id(id=item.id)
                    if new_item.kind != item.kind:
                        self.delete(name=new_item.kind)
                else:
                    new_item = self.get(name=item.kind)
                new_item.update(item)
                self.set(name=item.kind, schema=new_item)
            except SchemaNotFoundError:
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
        self.process_cardinality_counts()
        self.process_inheritance()
        self.process_hierarchy()
        self.process_branch_support()
        self.add_profile_schemas()

    def process_validate(self) -> None:
        self.validate_names()
        self.validate_menu_placements()
        self.validate_kinds()
        self.validate_count_against_cardinality()
        self.validate_identifiers()
        self.validate_uniqueness_constraints()
        self.validate_display_labels()
        self.validate_order_by()
        self.validate_default_filters()
        self.validate_parent_component()

    def process_post_validation(self) -> None:
        self.add_groups()
        self.add_hierarchy()
        self.add_profile_relationships()
        self.process_filters()
        self.generate_weight()
        self.process_labels()
        self.process_dropdowns()
        self.process_relationships()

    def generate_identifiers(self) -> None:
        """Generate the identifier for all relationships if it's not already present."""
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)
            rels_missing_identifier = [rel.name for rel in node.relationships if rel.identifier is None]
            if not rels_missing_identifier:
                continue

            node = node.duplicate()
            for rel in node.relationships:
                if rel.identifier:
                    continue
                rel.identifier = str("__".join(sorted([node.kind, rel.peer]))).lower()
            self.set(name=name, schema=node)

    def validate_identifiers(self) -> None:
        """Validate that all relationships have a unique identifier for a given model."""
        # Organize all the relationships per identifier and node
        rels_per_identifier: Dict[str, Dict[str, List[RelationshipSchema]]] = defaultdict(lambda: defaultdict(list))
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            for rel in node.relationships:
                rels_per_identifier[rel.identifier][name].append(rel)

        valid_options = [
            [RelationshipDirection.BIDIR, RelationshipDirection.BIDIR],
            sorted([RelationshipDirection.INBOUND, RelationshipDirection.OUTBOUND]),
        ]

        for identifier, rels_per_kind in rels_per_identifier.items():
            # Per node kind, check if the directions are good
            for kind, rels in rels_per_kind.items():
                directions = sorted([rel.direction.value for rel in rels])
                if not (len(rels) == 1 or (len(rels) == 2 and directions == ["inbound", "outbound"])):
                    names_directions = [(rel.name, rel.direction.value) for rel in rels]
                    raise ValueError(
                        f"{kind}: Identifier of relationships must be unique for a given direction > {identifier!r} : {names_directions}"
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

    def _validate_attribute_path(
        self,
        node_schema: BaseNodeSchema,
        path: str,
        schema_map_override: Dict[str, Union[NodeSchema, GenericSchema]],
        relationship_allowed: bool = False,
        relationship_attribute_allowed: bool = False,
        schema_attribute_name: Optional[str] = None,
    ) -> SchemaAttributePath:
        error_header = f"{node_schema.kind}"
        error_header += f".{schema_attribute_name}" if schema_attribute_name else ""
        allowed_leaf_properties = ["value", "version", "binary_address"]
        try:
            schema_attribute_path = node_schema.parse_attribute_path(path, schema_map_override=schema_map_override)
        except AttributePathParsingError as exc:
            raise ValueError(f"{error_header}: {exc}") from exc

        if schema_attribute_path.relationship_schema:
            if not relationship_allowed:
                raise ValueError(f"{error_header}: this property only supports attributes, not relationships")
            if schema_attribute_path.relationship_schema.cardinality != RelationshipCardinality.ONE:
                raise ValueError(
                    f"{error_header}: cannot use {schema_attribute_path.relationship_schema.name} relationship,"
                    " relationship must be of cardinality one"
                )
            if not relationship_attribute_allowed and schema_attribute_path.attribute_schema:
                raise ValueError(
                    f"{error_header}: cannot use attributes of related node in constraint, only the relationship"
                )

        if (
            schema_attribute_path.attribute_property_name
            and schema_attribute_path.attribute_property_name not in allowed_leaf_properties
        ):
            raise ValueError(
                f"{error_header}: attribute property must be one of {allowed_leaf_properties}, not {schema_attribute_path.attribute_property_name}"
            )
        return schema_attribute_path

    def validate_uniqueness_constraints(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.uniqueness_constraints:
                continue

            for constraint_paths in node_schema.uniqueness_constraints:
                for constraint_path in constraint_paths:
                    self._validate_attribute_path(
                        node_schema,
                        constraint_path,
                        schema_map,
                        schema_attribute_name="uniqueness_constraints",
                        relationship_allowed=True,
                    )

    def validate_display_labels(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if node_schema.display_labels:
                for display_label_path in node_schema.display_labels:
                    self._validate_attribute_path(
                        node_schema, display_label_path, schema_map, schema_attribute_name="display_labels"
                    )
            elif isinstance(node_schema, NodeSchema):
                generic_display_labels = []
                for generic in node_schema.inherit_from:
                    generic_schema = self.get(name=generic, duplicate=False)
                    if generic_schema.display_labels:
                        generic_display_labels.append(generic_schema.display_labels)

                if len(generic_display_labels) == 1:
                    # Only assign node display labels if a single generic has them defined
                    node_schema.display_labels = generic_display_labels[0]

    def validate_order_by(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.order_by:
                continue

            for order_by_path in node_schema.order_by:
                self._validate_attribute_path(
                    node_schema,
                    order_by_path,
                    schema_map,
                    relationship_allowed=True,
                    relationship_attribute_allowed=True,
                    schema_attribute_name="order_by",
                )

    def validate_default_filters(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.default_filter:
                continue

            self._validate_attribute_path(
                node_schema, node_schema.default_filter, schema_map, schema_attribute_name="default_filter"
            )

    def validate_parent_component(self) -> None:
        # {parent_kind: {component_kind_1, component_kind_2, ...}}
        dependency_map: dict[str, set[str]] = defaultdict(set)
        for name in self.generic_names + self.node_names:
            node_schema = self.get(name=name, duplicate=False)

            parent_relationships: list[RelationshipSchema] = []
            component_relationships: list[RelationshipSchema] = []
            for rel_schema in node_schema.relationships:
                if rel_schema.kind == RelationshipKind.PARENT and rel_schema.inherited is False:
                    parent_relationships.append(rel_schema)
                    dependency_map[rel_schema.peer].add(node_schema.kind)
                elif rel_schema.kind == RelationshipKind.COMPONENT:
                    component_relationships.append(rel_schema)
                    dependency_map[node_schema.kind].add(rel_schema.peer)

            if isinstance(node_schema, NodeSchema) and node_schema.inherit_from:
                for generic_schema_name in node_schema.inherit_from:
                    generic_schema = self.get_generic(name=generic_schema_name, duplicate=False)
                    generic_parent_relationships = generic_schema.get_relationships_of_kind(
                        relationship_kinds=[RelationshipKind.PARENT]
                    )
                    for gpr in generic_parent_relationships:
                        dependency_map[gpr.peer].add(node_schema.kind)
                    parent_relationships.extend(generic_parent_relationships)
                    generic_component_relationships = generic_schema.get_relationships_of_kind(
                        relationship_kinds=[RelationshipKind.COMPONENT]
                    )
                    for gcr in generic_component_relationships:
                        dependency_map[node_schema.kind].add(gcr.peer)

            if not parent_relationships and not component_relationships:
                continue

            self._validate_parents_one_schema(node_schema=node_schema, parent_relationships=parent_relationships)

        try:
            topological_sort(dependency_map)
        except DependencyCycleExistsError as exc:
            raise ValueError(f"Cycles exist among parents and components in schema: {exc.get_cycle_strings()}") from exc

    def _validate_parents_one_schema(
        self, node_schema: Union[NodeSchema, GenericSchema], parent_relationships: list[RelationshipSchema]
    ) -> None:
        if not parent_relationships:
            return
        if len(parent_relationships) > 1:
            parent_names = [pr.name for pr in parent_relationships]
            raise ValueError(
                f"{node_schema.kind}: Only one relationship of type parent is allowed, but all the following are of type parent: {parent_names}"
            )

        parent_relationship = parent_relationships[0]
        if parent_relationship.cardinality != RelationshipCardinality.ONE:
            raise ValueError(
                f"{node_schema.kind}.{parent_relationship.name}: Relationship of type parent must be cardinality=one"
            )
        if parent_relationship.optional is True:
            raise ValueError(
                f"{node_schema.kind}.{parent_relationship.name}: Relationship of type parent must not be optional"
            )

    def validate_names(self) -> None:
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

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
        menu_placements: Dict[str, str] = {}

        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name, duplicate=False)
            if node.menu_placement:
                try:
                    placement_node = self.get(name=node.menu_placement, duplicate=False)
                except SchemaNotFoundError:
                    raise ValueError(f"{node.kind}: {node.menu_placement} is not a valid menu placement") from None

                if node == placement_node:
                    raise ValueError(f"{node.kind}: cannot be placed under itself in the menu") from None

                if menu_placements.get(placement_node.kind) == node.kind:
                    raise ValueError(f"{node.kind}: cyclic menu placement with {placement_node.kind}") from None

                menu_placements[node.kind] = placement_node.kind

    def validate_kinds(self) -> None:
        for name in list(self.nodes.keys()):
            node = self.get(name=name, duplicate=False)

            for generic_kind in node.inherit_from:
                if self.has(name=generic_kind):
                    if not isinstance(self.get(name=generic_kind, duplicate=False), GenericSchema):
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

    def validate_count_against_cardinality(self) -> None:
        """Validate every RelationshipSchema cardinality against the min_count and max_count."""
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            for rel in node.relationships:
                if rel.cardinality == RelationshipCardinality.ONE:
                    if not rel.optional and (rel.min_count != 1 or rel.max_count != 1):
                        raise ValueError(
                            f"{node.kind}: Relationship {rel.name!r} is defined as cardinality.ONE but min_count or max_count are not 1"
                        ) from None
                elif rel.cardinality == RelationshipCardinality.MANY:
                    if rel.max_count and rel.min_count > rel.max_count:
                        raise ValueError(
                            f"{node.kind}: Relationship {rel.name!r} min_count must be lower than max_count"
                        )
                    if rel.max_count == 1:
                        raise ValueError(
                            f"{node.kind}: Relationship {rel.name!r} max_count must be 0 or greater than 1 when cardinality is MANY"
                        )

    def process_dropdowns(self) -> None:
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            attributes = [attr for attr in node.attributes if attr.kind == "Dropdown"]
            if not attributes:
                continue

            node = node.duplicate()
            changed = False

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
        def check_if_need_to_update_label(node) -> bool:
            if not node.label:
                return True
            for item in node.relationships + node.attributes:
                if not item.label:
                    return True
            return False

        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            if not check_if_need_to_update_label(node):
                continue

            node = node.duplicate()
            if not node.label:
                node.label = format_label(node.name)

            for attr in node.attributes:
                if not attr.label:
                    attr.label = format_label(attr.name)

            for rel in node.relationships:
                if not rel.label:
                    rel.label = format_label(rel.name)

            self.set(name=name, schema=node)

    def process_relationships(self) -> None:
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            schema_to_update: Optional[Union[NodeSchema, GenericSchema]] = None
            for relationship in node.relationships:
                if relationship.on_delete is not None:
                    continue
                if not schema_to_update:
                    schema_to_update = node.duplicate()

                relationship_to_update = schema_to_update.get_relationship(name=relationship.name)
                if relationship.kind == RelationshipKind.COMPONENT:
                    relationship_to_update.on_delete = RelationshipDeleteBehavior.CASCADE
                else:
                    relationship_to_update.on_delete = RelationshipDeleteBehavior.NO_ACTION

            if schema_to_update:
                self.set(name=schema_to_update.kind, schema=schema_to_update)

    def process_hierarchy(self) -> None:
        for name in self.nodes.keys():
            node = self.get(name=name, duplicate=False)

            if not node.hierarchy and not node.parent and not node.children:
                continue

            if not node.hierarchy and (node.parent is not None or node.children is not None):
                raise ValueError(f"{node.kind} Hierarchy must be provided if either parent or children is defined.")

            if node.hierarchy not in self.generics.keys():
                # TODO add a proper exception for all schema related issue
                raise ValueError(f"{node.kind} Unable to find the generic {node.hierarchy!r} provided in 'hierarchy'.")

            node = node.duplicate()
            changed = False

            if node.hierarchy not in node.inherit_from:
                node.inherit_from.append(node.hierarchy)
                changed = True

            if node.parent is None:
                node.parent = node.hierarchy
                changed = True
            elif node.parent and node.parent not in list(self.nodes.keys()) + list(self.generics.keys()):
                raise ValueError(f"{node.kind} Unable to find the node {node.parent!r} provided in 'parent'.")

            if node.children is None:
                node.children = node.hierarchy
                changed = True
            elif node.children and node.children not in list(self.nodes.keys()) + list(self.generics.keys()):
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
            node = self.get(name=name, duplicate=False)

            if node.inherit_from or node.namespace not in RESTRICTED_NAMESPACES:
                generics_used_by[InfrahubKind.NODE].append(node.kind)

            if not node.inherit_from:
                continue

            node = node.duplicate()

            if InfrahubKind.IPPREFIX in node.inherit_from and InfrahubKind.IPADDRESS in node.inherit_from:
                raise ValueError(
                    f"{node.kind} cannot inherit from both {InfrahubKind.IPPREFIX} and {InfrahubKind.IPADDRESS}"
                )

            generic_with_hierarchical_support = []
            for generic_kind in node.inherit_from:
                if generic_kind not in self.generics.keys():
                    # TODO add a proper exception for all schema related issue
                    raise ValueError(f"{node.kind} Unable to find the generic {generic_kind}")

                generic_kind_schema = self.get(generic_kind, duplicate=False)
                if generic_kind_schema.hierarchical:
                    generic_with_hierarchical_support.append(generic_kind)

                # Check if a node redefine protected generic attributes or relationships
                node.validate_inheritance(interface=generic_kind_schema)

                # Store the list of node referencing a specific generics
                generics_used_by[generic_kind].append(node.kind)
                node.inherit_from_interface(interface=generic_kind_schema)

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
        # pylint: disable=too-many-branches

        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            # Check if this node requires a change before duplicating
            change_required = False
            for attr in node.attributes:
                if attr.branch is None:
                    change_required = True
                    break
            if not change_required:
                for rel in node.relationships:
                    if rel.branch is None:
                        change_required = True
                        break

            if not change_required:
                continue

            node = node.duplicate()

            for attr in node.attributes:
                if attr.branch is not None:
                    continue

                attr.branch = node.branch

            for rel in node.relationships:
                if rel.branch is not None:
                    continue

                peer_node = self.get(name=rel.peer, duplicate=False)
                if node.branch == peer_node.branch:
                    rel.branch = node.branch
                elif BranchSupportType.LOCAL in (node.branch, peer_node.branch):
                    rel.branch = BranchSupportType.LOCAL
                else:
                    rel.branch = BranchSupportType.AWARE

            self.set(name=name, schema=node)

    def process_default_values(self) -> None:
        """Ensure that all attributes with a default value are flagged as optional: True."""
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            attrs_to_update = [attr for attr in node.attributes if attr.default_value is not None and not attr.optional]
            if not attrs_to_update:
                continue

            node = node.duplicate()
            for attr in attrs_to_update:
                attr.optional = True

            self.set(name=name, schema=node)

    def process_filters(self) -> Node:
        # Generate the filters for all nodes and generics, at the NodeSchema and at the relationships level.
        for name in self.all_names:
            node = self.get(name=name)
            node.filters = self.generate_filters(schema=node, include_relationships=True)

            for rel in node.relationships:
                peer_schema = self.get(name=rel.peer, duplicate=False)
                if not peer_schema:
                    continue

                rel.filters = self.generate_filters(schema=peer_schema, include_relationships=False)

            self.set(name=name, schema=node)

    def process_cardinality_counts(self) -> None:
        """Ensure that all relationships with a cardinality of ONE have a min_count and max_count of 1."""
        # pylint: disable=too-many-branches

        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            # Check if this node requires a change before duplicating
            change_required = False
            for rel in node.relationships:
                if rel.cardinality != RelationshipCardinality.ONE:
                    continue
                # Handle default values of RelationshipSchema when cardinality is ONE and set to valid values (1)
                # RelationshipSchema default values 0 for min_count and max_count
                if rel.optional and rel.min_count != 0:
                    change_required = True
                    break
                if rel.optional and rel.max_count != 1:
                    change_required = True
                    break
                if not rel.optional and rel.min_count == 0:
                    change_required = True
                    break
                if not rel.optional and rel.max_count == 0:
                    change_required = True
                    break

            if not change_required:
                continue

            node = node.duplicate()

            for rel in node.relationships:
                if rel.cardinality != RelationshipCardinality.ONE:
                    continue
                # Handle default values of RelationshipSchema when cardinality is ONE and set to valid values (1)
                # RelationshipSchema default values 0 for min_count and max_count
                if rel.optional and rel.min_count != 0:
                    rel.min_count = 0
                if rel.optional and rel.max_count != 1:
                    rel.max_count = 1
                if not rel.optional and rel.min_count == 0:
                    rel.min_count = 1
                if not rel.optional and rel.max_count == 0:
                    rel.max_count = 1

            self.set(name=name, schema=node)

    def generate_weight(self):
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)
            items_to_update = [item for item in node.attributes + node.relationships if not item.order_weight]
            if not items_to_update:
                continue

            node = node.duplicate()

            current_weight = 0
            for item in node.attributes + node.relationships:
                current_weight += 1000
                if not item.order_weight:
                    item.order_weight = current_weight

            self.set(name=name, schema=node)

    def add_groups(self):
        if not self.has(name=InfrahubKind.GENERICGROUP):
            return

        for node_name in self.all_names:
            schema: MainSchemaTypes = self.get(name=node_name, duplicate=False)
            changed = False

            if isinstance(schema, NodeSchema) and InfrahubKind.GENERICGROUP in schema.inherit_from:
                continue

            if schema.kind in INTERNAL_SCHEMA_NODE_KINDS or schema.kind == InfrahubKind.GENERICGROUP:
                continue

            if schema.kind in (InfrahubKind.LINEAGEOWNER, InfrahubKind.LINEAGESOURCE):
                continue

            if "member_of_groups" not in schema.relationship_names:
                if not changed:
                    schema = schema.duplicate()
                    changed = True
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
                if not changed:
                    schema = schema.duplicate()
                    changed = True
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

            if changed:
                self.set(name=node_name, schema=schema)

    def add_hierarchy(self):
        for generic_name in self.generics.keys():
            generic = self.get_generic(name=generic_name, duplicate=False)

            if not generic.hierarchical:
                continue

            generic = generic.duplicate()
            read_only = generic.kind == InfrahubKind.IPPREFIX

            if "parent" not in generic.relationship_names:
                generic.relationships.append(
                    RelationshipSchema(
                        name="parent",
                        identifier="parent__child",
                        peer=generic_name,
                        kind=RelationshipKind.HIERARCHY,
                        cardinality=RelationshipCardinality.ONE,
                        max_count=1,
                        branch=BranchSupportType.AWARE,
                        direction=RelationshipDirection.OUTBOUND,
                        hierarchical=generic_name,
                        read_only=read_only,
                    )
                )
            if "children" not in generic.relationship_names:
                generic.relationships.append(
                    RelationshipSchema(
                        name="children",
                        identifier="parent__child",
                        peer=generic_name,
                        kind=RelationshipKind.HIERARCHY,
                        cardinality=RelationshipCardinality.MANY,
                        branch=BranchSupportType.AWARE,
                        direction=RelationshipDirection.INBOUND,
                        hierarchical=generic_name,
                        read_only=read_only,
                    )
                )

            self.set(name=generic_name, schema=generic)

        for node_name in self.nodes.keys():
            node = self.get_node(name=node_name, duplicate=False)

            if node.parent is None and node.children is None:
                continue

            node = node.duplicate()
            read_only = InfrahubKind.IPPREFIX in node.inherit_from

            if node.parent and "parent" not in node.relationship_names:
                node.relationships.append(
                    RelationshipSchema(
                        name="parent",
                        identifier="parent__child",
                        peer=node.parent,
                        kind=RelationshipKind.HIERARCHY,
                        cardinality=RelationshipCardinality.ONE,
                        max_count=1,
                        branch=BranchSupportType.AWARE,
                        direction=RelationshipDirection.OUTBOUND,
                        hierarchical=node.hierarchy,
                        read_only=read_only,
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
                        read_only=read_only,
                    )
                )

            self.set(name=node_name, schema=node)

    def add_profile_schemas(self):
        if not self.has(name=InfrahubKind.PROFILE):
            core_profile_schema = GenericSchema(**core_profile_schema_definition)
            self.set(name=core_profile_schema.kind, schema=core_profile_schema)
        else:
            core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=False)
        profile_schema_kinds = set()
        for node_name in self.nodes.keys():
            node = self.get_node(name=node_name, duplicate=False)
            if node.namespace in RESTRICTED_NAMESPACES:
                continue

            profile = self.generate_profile_from_node(node=node)
            self.set(name=profile.kind, schema=profile)
            profile_schema_kinds.add(profile.kind)
        if not profile_schema_kinds:
            return
        core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=False)
        current_used_by = set(core_profile_schema.used_by)
        new_used_by = profile_schema_kinds - current_used_by
        if not new_used_by:
            return
        core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=True)
        core_profile_schema.used_by = sorted(list(profile_schema_kinds))
        self.set(name=core_profile_schema.kind, schema=core_profile_schema)

    def add_profile_relationships(self):
        for node_name in self.nodes.keys():
            node = self.get_node(name=node_name, duplicate=False)
            if node.namespace in RESTRICTED_NAMESPACES:
                continue

            if "profiles" in node.relationship_names:
                continue

            # Add relationship between node and profile
            node.relationships.append(
                RelationshipSchema(
                    name="profiles",
                    identifier="node__profile",
                    peer=self._get_profile_kind(node_kind=node.kind),
                    kind=RelationshipKind.PROFILE,
                    cardinality=RelationshipCardinality.MANY,
                    branch=BranchSupportType.AWARE,
                )
            )

        # Add relationship between group and profile

    def _get_profile_kind(self, node_kind: str) -> str:
        return f"Profile{node_kind}"

    def generate_profile_from_node(self, node: NodeSchema) -> ProfileSchema:
        core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=False)
        core_name_attr = core_profile_schema.get_attribute(name="profile_name")
        profile_name_attr = AttributeSchema(
            **core_name_attr.model_dump(exclude=["id", "inherited"]),
        )
        profile_name_attr.branch = node.branch
        core_priority_attr = core_profile_schema.get_attribute(name="profile_priority")
        profile_priority_attr = AttributeSchema(
            **core_priority_attr.model_dump(exclude=["id", "inherited"]),
        )
        profile_priority_attr.branch = node.branch
        profile = ProfileSchema(
            name=node.kind,
            namespace="Profile",
            description=f"Profile for {node.kind}",
            branch=node.branch,
            include_in_menu=False,
            display_labels=["profile_name__value"],
            inherit_from=[InfrahubKind.LINEAGESOURCE, InfrahubKind.PROFILE],
            default_filter="profile_name__value",
            attributes=[profile_name_attr, profile_priority_attr],
            relationships=[
                RelationshipSchema(
                    name="related_nodes",
                    identifier="node__profile",
                    peer=node.kind,
                    kind=RelationshipKind.PROFILE,
                    cardinality=RelationshipCardinality.MANY,
                    branch=BranchSupportType.AWARE,
                )
            ],
        )

        for node_attr in node.attributes:
            if node_attr.read_only or node_attr.optional is False:
                continue

            attr = AttributeSchema(
                optional=True,
                **node_attr.model_dump(exclude=["id", "unique", "optional", "read_only", "default_value", "inherited"]),
            )
            profile.attributes.append(attr)

        return profile

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
            peer_schema = self.get(name=rel.peer, duplicate=False)

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

    def set(self, name: str, schema: Union[NodeSchema, GenericSchema], branch: Optional[str] = None) -> int:
        branch = branch or registry.default_branch

        if branch not in self._branches:
            self._branches[branch] = SchemaBranch(cache=self._cache, name=branch)

        self._branches[branch].set(name=name, schema=schema)

        return hash(self._branches[branch])

    def has(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        try:
            self.get(name=name, branch=branch, duplicate=False)
            return True
        except SchemaNotFoundError:
            return False

    def get(self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True) -> MainSchemaTypes:
        # For now we assume that all branches are present, will see how we need to pull new branches later.
        branch = registry.get_branch_from_registry(branch=branch)

        if branch.name in self._branches:
            try:
                return self._branches[branch.name].get(name=name, duplicate=duplicate)
            except SchemaNotFoundError:
                pass

        default_branch = registry.default_branch
        return self._branches[default_branch].get(name=name, duplicate=duplicate)

    def get_node_schema(
        self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> NodeSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if isinstance(schema, NodeSchema):
            return schema

        raise ValueError("The selected node is not of type NodeSchema")

    def get_full(
        self, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> Dict[str, MainSchemaTypes]:
        branch = registry.get_branch_from_registry(branch=branch)

        branch_name = None
        if branch.name in self._branches:
            branch_name = branch.name
        else:
            branch_name = registry.default_branch

        return self._branches[branch_name].get_all(duplicate=duplicate)

    async def get_full_safe(
        self, branch: Optional[Union[Branch, str]] = None
    ) -> Dict[str, Union[NodeSchema, GenericSchema]]:
        await lock.registry.local_schema_wait()

        return self.get_full(branch=branch)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name in self._branches:
            return self._branches[name]

        self._branches[name] = SchemaBranch(cache=self._cache, name=name)
        return self._branches[name]

    def set_schema_branch(self, name: str, schema: SchemaBranch) -> None:
        schema.name = name
        self._branches[name] = schema

    def process_schema_branch(self, name: str):
        schema_branch = self.get_schema_branch(name=name)
        schema_branch.process()

    async def update_schema_branch(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = None,
        diff: Optional[SchemaDiff] = None,
        limit: Optional[List[str]] = None,
        update_db: bool = True,
    ):
        branch = await registry.get_branch(branch=branch, db=db)

        updated_schema = None
        if update_db:
            schema_diff = None
            if diff:
                schema_diff = await self.update_schema_to_db(schema=schema, db=db, branch=branch, diff=diff)
            else:
                await self.load_schema_to_db(schema=schema, db=db, branch=branch, limit=limit)
                # After updating the schema into the db
                # we need to pull a fresh version because some default value are managed/generated within the node object
                schema_diff = None
                if limit:
                    schema_diff = SchemaBranchDiff(
                        nodes=[name for name in list(schema.nodes.keys()) if name in limit],
                        generics=[name for name in list(schema.generics.keys()) if name in limit],
                    )

            updated_schema = await self.load_schema_from_db(
                db=db, branch=branch, schema=schema, schema_diff=schema_diff
            )

        self.set_schema_branch(name=branch.name, schema=updated_schema or schema)

    def register_schema(self, schema: SchemaRoot, branch: Optional[str] = None) -> SchemaBranch:
        """Register all nodes, generics & groups from a SchemaRoot object into the registry."""

        branch = branch or registry.default_branch
        schema_branch = self.get_schema_branch(name=branch)
        schema_branch.load_schema(schema=schema)
        schema_branch.process()
        return schema_branch

    async def update_schema_to_db(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        diff: SchemaDiff,
        branch: Optional[Union[str, Branch]] = None,
    ) -> SchemaBranchDiff:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await registry.get_branch(branch=branch, db=db)

        item_kinds = []
        for item_kind, item_diff in diff.added.items():
            item = schema.get(name=item_kind, duplicate=False)
            node = await self.load_node_to_db(node=item, branch=branch, db=db)
            schema.set(name=item_kind, schema=node)
            item_kinds.append(item_kind)

        for item_kind, item_diff in diff.changed.items():
            item = schema.get(name=item_kind, duplicate=False)
            if item_diff:
                node = await self.update_node_in_db_based_on_diff(node=item, branch=branch, db=db, diff=item_diff)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, db=db)
            schema.set(name=item_kind, schema=node)
            item_kinds.append(item_kind)

        for item_kind, item_diff in diff.removed.items():
            item = schema.get(name=item_kind, duplicate=False)
            node = await self.delete_node_in_db(node=item, branch=branch, db=db)
            schema.delete(name=item_kind)

        schema_diff = SchemaBranchDiff(
            nodes=[name for name in schema.node_names if name in item_kinds],
            generics=[name for name in schema.generic_names if name in item_kinds],
        )
        return schema_diff

    async def load_schema_to_db(
        self,
        schema: SchemaBranch,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
        limit: Optional[List[str]] = None,
    ) -> None:
        """Load all nodes, generics and groups from a SchemaRoot object into the database."""

        branch = await registry.get_branch(branch=branch, db=db)

        for item_kind in schema.node_names + schema.generic_names:
            if item_kind == InfrahubKind.PROFILE:
                continue
            if limit and item_kind not in limit:
                continue
            item = schema.get(name=item_kind, duplicate=False)
            if not item.id:
                node = await self.load_node_to_db(node=item, branch=branch, db=db)
                schema.set(name=item_kind, schema=node)
            else:
                node = await self.update_node_in_db(node=item, branch=branch, db=db)
                schema.set(name=item_kind, schema=node)

    async def load_node_to_db(
        self,
        node: Union[NodeSchema, GenericSchema],
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
    ) -> Union[NodeSchema, GenericSchema]:
        """Load a Node with its attributes and its relationships to the database."""
        branch = await registry.get_branch(branch=branch, db=db)

        node_type = "SchemaNode"
        if isinstance(node, GenericSchema):
            node_type = "SchemaGeneric"

        node_schema = self.get_node_schema(name=node_type, branch=branch, duplicate=False)
        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch, duplicate=False)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch, duplicate=False)

        # Duplicate the node in order to store the IDs after inserting them in the database
        new_node = node.duplicate()

        # Create the node first
        schema_dict = node.model_dump(exclude={"id", "state", "filters", "relationships", "attributes"})
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
        node: Union[NodeSchema, GenericSchema],
        branch: Optional[Union[str, Branch]] = None,
    ) -> Union[NodeSchema, GenericSchema]:
        """Update a Node with its attributes and its relationships in the database."""
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        schema_dict = node.model_dump(exclude=IGNORE_FOR_NODE)
        for key, value in schema_dict.items():
            getattr(obj, key).value = value

        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        new_node = node.duplicate()

        # Update the attributes and the relationships nodes as well
        await obj.attributes.update(db=db, data=[item.id for item in node.local_attributes if item.id])
        await obj.relationships.update(db=db, data=[item.id for item in node.local_relationships if item.id])
        await obj.save(db=db)

        # Then Update the Attributes and the relationships

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

        # Save back the node with the (potentially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def update_node_in_db_based_on_diff(  # pylint: disable=too-many-branches,too-many-statements
        self,
        db: InfrahubDatabase,
        diff: HashableModelDiff,
        node: Union[NodeSchema, GenericSchema],
        branch: Optional[Union[str, Branch]] = None,
    ) -> Union[NodeSchema, GenericSchema]:
        """Update a Node with its attributes and its relationships in the database based on a HashableModelDiff."""
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        properties_to_update = set(list(diff.added.keys()) + list(diff.changed.keys())) - IGNORE_FOR_NODE

        if properties_to_update:
            schema_dict = node.model_dump(exclude=IGNORE_FOR_NODE)
            for key, value in schema_dict.items():
                getattr(obj, key).value = value

        attribute_schema = self.get_node_schema(name="SchemaAttribute", branch=branch)
        relationship_schema = self.get_node_schema(name="SchemaRelationship", branch=branch)

        new_node = node.duplicate()

        # Update the attributes and the relationships nodes as well
        if "attributes" in diff.changed:
            await obj.attributes.update(db=db, data=[item.id for item in node.local_attributes if item.id])

        if "relationships" in diff.changed:
            await obj.relationships.update(db=db, data=[item.id for item in node.local_relationships if item.id])

        await obj.save(db=db)

        # Then Update the Attributes and the relationships
        def get_attrs_rels_to_update(diff: HashableModelDiff) -> List[str]:
            items_to_update = []
            if "attributes" in diff.changed.keys() and diff.changed["attributes"]:
                items_to_update.extend(list(diff.changed["attributes"].added.keys()))
                items_to_update.extend(list(diff.changed["attributes"].changed.keys()))
                items_to_update.extend(list(diff.changed["attributes"].removed.keys()))
            if "relationships" in diff.changed.keys() and diff.changed["relationships"]:
                items_to_update.extend(list(diff.changed["relationships"].added.keys()))
                items_to_update.extend(list(diff.changed["relationships"].changed.keys()))
                items_to_update.extend(list(diff.changed["relationships"].removed.keys()))
            return items_to_update

        attrs_rels_to_update = get_attrs_rels_to_update(diff=diff)

        items = await self.get_many(
            ids=[
                item.id
                for item in node.local_attributes + node.local_relationships
                if item.id and item.name in attrs_rels_to_update
            ],
            db=db,
            branch=branch,
            include_owner=True,
            include_source=True,
        )

        if "attributes" in diff.changed.keys() and diff.changed["attributes"]:
            for item in node.local_attributes:
                if item.name in diff.changed["attributes"].added:
                    created_item = await self.create_attribute_in_db(
                        schema=attribute_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_attr = new_node.get_attribute(name=item.name)
                    new_attr.id = created_item.id
                elif item.name in diff.changed["attributes"].changed and item.id and item.id in items:
                    await self.update_attribute_in_db(item=item, attr=items[item.id], db=db)
                elif item.name in diff.changed["attributes"].removed and item.id and item.id in items:
                    await items[item.id].delete(db=db)
                elif (
                    (item.name in diff.changed["attributes"].removed or item.name in diff.changed["attributes"].changed)
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find an attribute {item.name!r} to update or delete")

        if "relationships" in diff.changed.keys() and diff.changed["relationships"]:
            for item in node.local_relationships:
                if item.name in diff.changed["relationships"].added:
                    created_rel = await self.create_relationship_in_db(
                        schema=relationship_schema, item=item, branch=branch, db=db, parent=obj
                    )
                    new_rel = new_node.get_relationship(name=item.name)
                    new_rel.id = created_rel.id
                elif item.name in diff.changed["relationships"].changed and item.id and item.id in items:
                    await self.update_relationship_in_db(item=item, rel=items[item.id], db=db)
                elif item.name in diff.changed["relationships"].removed and item.id and item.id in items:
                    await items[item.id].delete(db=db)
                elif (
                    (
                        item.name in diff.changed["relationships"].removed
                        or item.name in diff.changed["relationships"].changed
                    )
                    and item.id
                    and item.id not in items
                ):
                    raise ValueError(f"Unable to find an relationship {item.name!r} to update or delete")

        # Save back the node with the (potentially) newly created IDs in the SchemaManager
        self.set(name=new_node.kind, schema=new_node, branch=branch.name)
        return new_node

    async def delete_node_in_db(
        self,
        db: InfrahubDatabase,
        node: Union[NodeSchema, GenericSchema],
        branch: Optional[Union[str, Branch]] = None,
    ) -> None:
        """Delete the node with its attributes and relationships."""
        branch = await registry.get_branch(branch=branch, db=db)

        obj = await self.get_one(id=node.get_id(), branch=branch, db=db)
        if not obj:
            raise SchemaNotFoundError(
                branch_name=branch.name,
                identifier=node.id,
                message=f"Unable to find the Schema associated with {node.id}, {node.kind}",
            )

        # First delete the attributes and the relationships
        items = await self.get_many(
            ids=[item.id for item in node.local_attributes + node.local_relationships if item.id],
            db=db,
            branch=branch,
            include_owner=True,
            include_source=True,
        )

        for item in items.values():
            await item.delete(db=db)

        await obj.delete(db=db)

    @staticmethod
    async def create_attribute_in_db(
        schema: NodeSchema, item: AttributeSchema, branch: Branch, parent: Node, db: InfrahubDatabase
    ) -> AttributeSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.model_dump(exclude={"id", "state", "filters"}), node=parent, db=db)
        await obj.save(db=db)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_attribute_in_db(item: AttributeSchema, attr: Node, db: InfrahubDatabase) -> None:
        item_dict = item.model_dump(exclude={"id", "state", "filters"})
        for key, value in item_dict.items():
            getattr(attr, key).value = value
        await attr.save(db=db)

    @staticmethod
    async def create_relationship_in_db(
        schema: NodeSchema, item: RelationshipSchema, branch: Branch, parent: Node, db: InfrahubDatabase
    ) -> RelationshipSchema:
        obj = await Node.init(schema=schema, branch=branch, db=db)
        await obj.new(**item.model_dump(exclude={"id", "state", "filters"}), node=parent, db=db)
        await obj.save(db=db)
        new_item = item.duplicate()
        new_item.id = obj.id
        return new_item

    @staticmethod
    async def update_relationship_in_db(item: RelationshipSchema, rel: Node, db: InfrahubDatabase) -> None:
        item_dict = item.model_dump(exclude={"id", "state", "filters"})
        for key, value in item_dict.items():
            getattr(rel, key).value = value
        await rel.save(db=db)

    async def load_schema(
        self,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
    ) -> SchemaBranch:
        """Load the schema either from the cache or from the database"""
        branch = await registry.get_branch(branch=branch, db=db)

        if not branch.is_default and branch.origin_branch:
            origin_branch: Branch = await registry.get_branch(branch=branch.origin_branch, db=db)

            if origin_branch.schema_hash.main == branch.schema_hash.main:
                origin_schema = self.get_schema_branch(name=origin_branch.name)
                new_branch_schema = origin_schema.duplicate()
                self.set_schema_branch(name=branch.name, schema=new_branch_schema)
                log.info("Loading schema from cache")
                return new_branch_schema

        current_schema = self.get_schema_branch(name=branch.name)
        schema_diff = current_schema.get_hash_full().compare(branch.schema_hash)
        branch_schema = await self.load_schema_from_db(
            db=db, branch=branch, schema=current_schema, schema_diff=schema_diff
        )
        branch_schema.clear_cache()
        self.set_schema_branch(name=branch.name, schema=branch_schema)
        return branch_schema

    async def load_schema_from_db(
        self,
        db: InfrahubDatabase,
        branch: Optional[Union[str, Branch]] = None,
        schema: Optional[SchemaBranch] = None,
        schema_diff: Optional[SchemaBranchDiff] = None,
        at: Optional[Timestamp] = None,
    ) -> SchemaBranch:
        """Query all the node of type NodeSchema and GenericSchema from the database and convert them to their respective type.

        Args:
            db: Database Driver
            branch: Name of the branch to load the schema from. Defaults to None.
            schema: (Optional) If a schema is provided, it will be updated with the latest value, if not a new one will be created.
            schema_diff: (Optional). List of nodes, generics & groups to query

        Returns:
            SchemaBranch
        """

        branch = await registry.get_branch(branch=branch, db=db)
        schema = schema or SchemaBranch(cache=self._cache, name=branch.name)

        # If schema_diff has been provided, we need to build the proper filters for the queries based on the namespace and the name of the object.
        # the namespace and the name will be extracted from the kind with the function `parse_node_kind`
        filters = {"generics": {}, "nodes": {}}
        has_filters = False

        # If a diff is provided but is empty there is nothing to query
        if schema_diff is not None and not schema_diff:
            return schema

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

        if not has_filters or filters["generics"]:
            generic_schema = self.get(name="SchemaGeneric", branch=branch)
            for schema_node in await self.query(
                schema=generic_schema,
                branch=branch,
                at=at,
                filters=filters["generics"],
                prefetch_relationships=True,
                db=db,
            ):
                kind = f"{schema_node.namespace.value}{schema_node.name.value}"
                schema.set(
                    name=kind,
                    schema=await self.convert_generic_schema_to_schema(schema_node=schema_node, db=db),
                )

        if not has_filters or filters["nodes"]:
            node_schema = self.get(name="SchemaNode", branch=branch)
            for schema_node in await self.query(
                schema=node_schema, branch=branch, at=at, filters=filters["nodes"], prefetch_relationships=True, db=db
            ):
                kind = f"{schema_node.namespace.value}{schema_node.name.value}"
                schema.set(
                    name=kind,
                    schema=await self.convert_node_schema_to_schema(schema_node=schema_node, db=db),
                )

        schema.process()

        return schema

    @classmethod
    async def _prepare_node_data(cls, schema_node: Node, db: InfrahubDatabase) -> dict[str, Any]:
        node_data = {"id": schema_node.id}

        # First pull all the local attributes at the top level, then convert all the local relationships
        #  for a standard node_schema, the relationships will be attributes and relationships
        for attr_name in schema_node._attributes:
            attr = getattr(schema_node, attr_name)
            node_data[attr_name] = attr.get_value()

        for rel_name in schema_node._relationships:
            if rel_name not in node_data:
                node_data[rel_name] = []

            rm = getattr(schema_node, rel_name)
            for rel in await rm.get(db=db):
                item = await rel.get_peer(db=db)
                item_data = {"id": item.id}
                for item_name in item._attributes:
                    item_attr = getattr(item, item_name)
                    item_data[item_name] = item_attr.get_value()

                node_data[rel_name].append(item_data)
        return node_data

    @classmethod
    async def convert_node_schema_to_schema(cls, schema_node: Node, db: InfrahubDatabase) -> NodeSchema:
        """Convert a schema_node object loaded from the database into NodeSchema object."""
        node_data = await cls._prepare_node_data(schema_node=schema_node, db=db)
        return NodeSchema(**node_data)

    @classmethod
    async def convert_generic_schema_to_schema(cls, schema_node: Node, db: InfrahubDatabase) -> GenericSchema:
        """Convert a schema_node object loaded from the database into GenericSchema object."""
        node_data = await cls._prepare_node_data(schema_node=schema_node, db=db)
        return GenericSchema(**node_data)
