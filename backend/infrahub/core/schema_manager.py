from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from infrahub_sdk.utils import compare_lists, duplicates
from pydantic import BaseModel, ConfigDict, Field

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
    SchemaPathType,
    UpdateSupport,
    UpdateValidationErrorType,
)
from infrahub.core.manager import NodeManager
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.models import HashableModelDiff, SchemaBranchDiff, SchemaBranchHash
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.property import FlagPropertyMixin, NodePropertyMixin
from infrahub.core.schema import (
    AttributePathParsingError,
    AttributeSchema,
    BaseNodeSchema,
    FilterSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaAttributePath,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.utils import parse_node_kind
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.exceptions import SchemaNotFound
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
SUPPORTED_SCHEMA_NODE_TYPE = [
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
    model_config = ConfigDict(extra="forbid")
    added: Dict[str, HashableModelDiff] = Field(default_factory=dict)
    changed: Dict[str, HashableModelDiff] = Field(default_factory=dict)
    removed: Dict[str, HashableModelDiff] = Field(default_factory=dict)

    @property
    def all(self) -> List[str]:
        return list(self.changed.keys()) + list(self.added.keys()) + list(self.removed.keys())


class SchemaUpdateValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    error: UpdateValidationErrorType
    message: Optional[str] = None

    def to_string(self) -> str:
        return f"{self.error.value!r}: {self.path.schema_kind} {self.path.field_name} {self.message}"


class SchemaUpdateMigrationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    migration_name: str

    @property
    def routing_key(self):
        return "schema.migration.path"


class SchemaUpdateConstraintInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    constraint_name: str

    @property
    def routing_key(self):
        return "schema.validator.path"

    def __hash__(self) -> int:
        return hash((type(self),) + tuple([self.constraint_name + self.path.get_path()]))


class SchemaUpdateValidationResult(BaseModel):
    errors: List[SchemaUpdateValidationError] = Field(default_factory=list)
    constraints: List[SchemaUpdateConstraintInfo] = Field(default_factory=list)
    migrations: List[SchemaUpdateMigrationInfo] = Field(default_factory=list)
    diff: SchemaDiff


class SchemaNamespace(BaseModel):
    name: str
    user_editable: bool


class SchemaBranch:
    def __init__(self, cache: Dict, name: Optional[str] = None, data: Optional[Dict[str, int]] = None):
        self._cache: Dict[str, Union[NodeSchema, GenericSchema]] = cache
        self.name: Optional[str] = name
        self.nodes: Dict[str, str] = {}
        self.generics: Dict[str, str] = {}
        self._graphql_schema: Optional[GraphQLSchema] = None
        self._graphql_manager: Optional[GraphQLSchemaManager] = None

        if data:
            self.nodes = data.get("nodes", {})
            self.generics = data.get("generics", {})

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
        return {"nodes": self.nodes, "generics": self.generics}

    def to_dict_schema_object(self) -> Dict[str, Dict[str, Union[NodeSchema, GenericSchema]]]:
        return {
            "nodes": {name: self.get(name) for name in self.nodes},
            "generics": {name: self.get(name) for name in self.generics},
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
        local_keys = list(self.nodes.keys()) + list(self.generics.keys())
        other_keys = list(other.nodes.keys()) + list(other.generics.keys())
        present_both, present_local_only, present_other_only = compare_lists(list1=local_keys, list2=other_keys)

        added_elements = {element: HashableModelDiff() for element in present_other_only}
        removed_elements = {element: HashableModelDiff() for element in present_local_only}
        schema_diff = SchemaDiff(added=added_elements, removed=removed_elements)

        # Process of the one that have been updated to identify the list of fields impacted
        for key in present_both:
            local_node = self.get(name=key, duplicate=False)
            other_node = other.get(name=key, duplicate=False)
            diff_node = other_node.diff(other=local_node)
            if diff_node.has_diff:
                schema_diff.changed[key] = diff_node

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

        result = SchemaUpdateValidationResult(diff=diff)

        for schema_name, schema_diff in diff.changed.items():
            schema = self.get(name=schema_name, duplicate=False)

            # Nothing to do today if we add a new model in the schema
            # for node_field_name, _ in schema_diff.added.items():
            #     pass

            # Not possible today, we need to add some specific mutations to support that
            # for node_field_name, _ in schema_diff.removed.items():
            #     pass

            for node_field_name, node_field_diff in schema_diff.changed.items():
                if node_field_diff and node_field_name in ["attributes", "relationships"]:
                    field_type = node_field_name[:-1]  # Remove the trailing 's's
                    path_type = SchemaPathType.ATTRIBUTE if field_type == "attribute" else SchemaPathType.RELATIONSHIP
                    for field_name, _ in node_field_diff.added.items():
                        if field_type == "attribute":
                            result.migrations.append(
                                SchemaUpdateMigrationInfo(
                                    path=SchemaPath(
                                        schema_kind=schema_name, path_type=path_type, field_name=field_name
                                    ),
                                    migration_name="node.attribute.add",
                                )
                            )

                    for field_name, _ in node_field_diff.removed.items():
                        result.migrations.append(
                            SchemaUpdateMigrationInfo(
                                path=SchemaPath(schema_kind=schema_name, path_type=path_type, field_name=field_name),
                                migration_name=f"node.{field_type}.remove",
                            )
                        )

                    for field_name, sub_field_diff in node_field_diff.changed.items():
                        field = schema.get_field(name=field_name)

                        for prop_name, _ in sub_field_diff.changed.items():
                            field_info = field.model_fields[prop_name]
                            field_update = field_info.json_schema_extra.get("update")

                            schema_path = SchemaPath(
                                schema_kind=schema_name,
                                path_type=path_type,
                                field_name=field_name,
                                property_name=prop_name,
                            )

                            self._validate_field(
                                schema_path=schema_path,
                                field_update=field_update,
                                result=result,
                            )

                else:
                    field_info = schema.model_fields[node_field_name]
                    field_update = field_info.json_schema_extra.get("update")

                    schema_path = SchemaPath(
                        schema_kind=schema_name,
                        path_type=SchemaPathType.NODE,
                        field_name=node_field_name,
                        property_name=node_field_name,
                    )
                    self._validate_field(
                        schema_path=schema_path,
                        field_update=field_update,
                        result=result,
                    )

        return result

    def _validate_field(
        self,
        schema_path: SchemaPath,
        field_update: str,
        result: SchemaUpdateValidationResult,
    ) -> None:
        if field_update == UpdateSupport.NOT_SUPPORTED.value:
            result.errors.append(
                SchemaUpdateValidationError(
                    path=schema_path,
                    error=UpdateValidationErrorType.NOT_SUPPORTED,
                )
            )
        elif field_update == UpdateSupport.MIGRATION_REQUIRED.value:
            migration_name = f"{schema_path.path_type.value}.{schema_path.field_name}.update"
            result.migrations.append(
                SchemaUpdateMigrationInfo(
                    path=schema_path,
                    migration_name=migration_name,
                )
            )
            if MIGRATION_MAP.get(migration_name, None) is None:
                result.errors.append(
                    SchemaUpdateValidationError(
                        path=schema_path,
                        error=UpdateValidationErrorType.MIGRATION_NOT_AVAILABLE,
                        message=f"Migration {migration_name!r} is not available yet",
                    )
                )
        elif field_update == UpdateSupport.VALIDATE_CONSTRAINT.value:
            constraint_name = f"{schema_path.path_type.value}.{schema_path.property_name}.update"
            result.constraints.append(
                SchemaUpdateConstraintInfo(
                    path=schema_path,
                    constraint_name=constraint_name,
                )
            )
            if CONSTRAINT_VALIDATOR_MAP.get(constraint_name, None) is None:
                result.errors.append(
                    SchemaUpdateValidationError(
                        path=schema_path,
                        error=UpdateValidationErrorType.VALIDATOR_NOT_AVAILABLE,
                        message=f"Validator {constraint_name!r} is not available yet",
                    )
                )

    def duplicate(self, name: Optional[str] = None) -> SchemaBranch:
        """Duplicate the current object but conserve the same cache."""
        return self.__class__(name=name, data=copy.deepcopy(self.to_dict()), cache=self._cache)

    def set(self, name: str, schema: Union[NodeSchema, GenericSchema]) -> str:
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

        return schema_hash

    def get(self, name: str, duplicate: bool = True) -> Union[NodeSchema, GenericSchema]:
        """Access a specific NodeSchema or GenericSchema, defined by its kind.

        To ensure that no-one will ever change an object in the cache,
        by default the function always returns a copy of the object, not the object itself

        If duplicate is set to false, the real objet will be returned.
        """
        key = None
        if name in self.nodes:
            key = self.nodes[name]
        elif name in self.generics:
            key = self.generics[name]

        if key and duplicate:
            return self._cache[key].duplicate()
        if key and not duplicate:
            return self._cache[key]

        raise SchemaNotFound(
            branch_name=self.name, identifier=name, message=f"Unable to find the schema '{name}' in the registry"
        )

    def has(self, name: str) -> bool:
        try:
            self.get(name=name, duplicate=False)
            return True
        except SchemaNotFound:
            return False

    def get_all(self, include_internal: bool = False) -> Dict[str, Union[NodeSchema, GenericSchema]]:
        """Retrive everything in a single dictionary."""

        return {
            name: self.get(name=name)
            for name in list(self.nodes.keys()) + list(self.generics.keys())
            if include_internal or name not in INTERNAL_SCHEMA_NODE_KINDS
        }

    def get_namespaces(self, include_internal: bool = False) -> List[SchemaNamespace]:
        all_schemas = self.get_all(include_internal=include_internal)
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
    ) -> List[Union[NodeSchema, GenericSchema]]:
        """Retrive everything in a single dictionary."""
        all_schemas = self.get_all(include_internal=include_internal)
        if namespaces:
            return [schema for schema in all_schemas.values() if schema.namespace in namespaces]
        return list(all_schemas.values())

    def get_schemas_by_rel_identifier(self, identifier: str) -> List[Union[NodeSchema, GenericSchema]]:
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
                new_item = self.get(name=item.kind)
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
        self.process_cardinality_counts()
        self.process_inheritance()
        self.process_hierarchy()
        self.process_branch_support()

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
            node = self.get(name=name, duplicate=False)

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

    def _validate_attribute_path(
        self,
        node_schema: BaseNodeSchema,
        path: str,
        schema_map_override: Dict[str, Union[NodeSchema, GenericSchema]],
        relationship_allowed: bool = False,
        schema_attribute_name: Optional[str] = None,
    ) -> SchemaAttributePath:
        error_header = f"{node_schema.kind}"
        error_header += f".{schema_attribute_name}" if schema_attribute_name else ""
        allowed_leaf_properties = ["value"]
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
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.uniqueness_constraints:
                continue

            for constraint_paths in node_schema.uniqueness_constraints:
                for constraint_path in constraint_paths:
                    self._validate_attribute_path(
                        node_schema, constraint_path, schema_map, schema_attribute_name="uniqueness_constraints"
                    )

    def validate_display_labels(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.display_labels:
                continue

            for display_label_path in node_schema.display_labels:
                self._validate_attribute_path(
                    node_schema, display_label_path, schema_map, schema_attribute_name="display_labels"
                )

    def validate_order_by(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.order_by:
                continue

            for order_by_path in node_schema.order_by:
                self._validate_attribute_path(
                    node_schema, order_by_path, schema_map, relationship_allowed=True, schema_attribute_name="order_by"
                )

    def validate_default_filters(self) -> None:
        full_schema_objects = self.to_dict_schema_object()
        schema_map = full_schema_objects["nodes"] | full_schema_objects["generics"]
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.default_filter:
                continue

            self._validate_attribute_path(
                node_schema, node_schema.default_filter, schema_map, schema_attribute_name="default_filter"
            )

    def validate_names(self) -> None:
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
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
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name, duplicate=False)
            if node.menu_placement:
                try:
                    self.get(name=node.menu_placement, duplicate=False)
                except SchemaNotFound:
                    raise ValueError(f"{node.kind}: {node.menu_placement} is not a valid menu placement") from None

    def validate_kinds(self) -> None:
        for name in list(self.nodes.keys()):
            node = self.get(name=name, duplicate=False)

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

    def validate_count_against_cardinality(self) -> None:
        """Validate every RelationshipSchema cardinality against the min_count and max_count."""
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

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
                if node.branch == peer_node.branch:
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
                if not peer_schema:
                    continue

                rel.filters = self.generate_filters(schema=peer_schema, include_relationships=False)

            self.set(name=name, schema=node)

    def process_cardinality_counts(self) -> None:
        """Ensure that all relationships with a cardinality of ONE have a min_count and max_count of 1."""
        for name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=name)

            changed = False
            for rel in node.relationships:
                if rel.cardinality == RelationshipCardinality.ONE:
                    # Handle default values of RelationshipSchema when cardinality is ONE and set to valid values (1)
                    # RelationshipSchema default values 0 for min_count and max_count
                    if rel.optional and rel.min_count != 0:
                        rel.min_count = 0
                        changed = True
                    if rel.optional and rel.max_count != 1:
                        rel.max_count = 1
                        changed = True
                    if not rel.optional and rel.min_count == 0:
                        rel.min_count = 1
                        changed = True
                    if not rel.optional and rel.max_count == 0:
                        rel.max_count = 1
                        changed = True

            if changed:
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

    async def get_constraints_per_model(  # pylint: disable=too-many-branches
        self, name: str, filter_invalid: bool = True
    ) -> List[SchemaUpdateConstraintInfo]:
        schema = self.get(name=name, duplicate=False)
        constraints: List[SchemaUpdateConstraintInfo] = []

        for prop_name, prop_field_info in schema.model_fields.items():
            if prop_name in ["attributes", "relationships"] or not prop_field_info.json_schema_extra:
                continue

            prop_field_update = prop_field_info.json_schema_extra.get("update")
            if prop_field_update != UpdateSupport.VALIDATE_CONSTRAINT.value:
                continue

            if getattr(schema, prop_name) is None:
                continue

            schema_path = SchemaPath(
                schema_kind=schema.kind,
                path_type=SchemaPathType.NODE,
                field_name=prop_name,
                property_name=prop_name,
            )
            constraint_name = f"node.{prop_name}.update"

            constraints.append(SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path))

        for field_name in schema.attribute_names + schema.relationship_names:
            field: Union[AttributeSchema, RelationshipSchema]
            if field_name in schema.attribute_names:
                field = schema.get_attribute(name=field_name)
            else:
                field = schema.get_relationship(name=field_name)

            for prop_name, prop_field_info in field.model_fields.items():
                if not prop_field_info.json_schema_extra:
                    continue

                prop_field_update = prop_field_info.json_schema_extra.get("update")
                if prop_field_update != UpdateSupport.VALIDATE_CONSTRAINT.value:
                    continue

                if getattr(field, prop_name) is None:
                    continue

                path_type = SchemaPathType.ATTRIBUTE
                constraint_name = f"attribute.{prop_name}.update"
                if isinstance(field, RelationshipSchema):
                    if field.kind == RelationshipKind.GROUP:
                        continue
                    path_type = SchemaPathType.RELATIONSHIP
                    constraint_name = f"relationship.{prop_name}.update"

                schema_path = SchemaPath(
                    schema_kind=schema.kind,
                    path_type=path_type,
                    field_name=field_name,
                    property_name=prop_name,
                )

                constraints.append(SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path))

        if not filter_invalid:
            return constraints

        validated_constraints: List[SchemaUpdateConstraintInfo] = []
        for constraint in constraints:
            if CONSTRAINT_VALIDATOR_MAP.get(constraint.constraint_name, None):
                validated_constraints.append(constraint)
            else:
                log.warning(
                    f"Unable to validate: {constraint.constraint_name!r} for {constraint.path.get_path()!r}, validator not available",
                    constraint_name=constraint.constraint_name,
                    path=constraint.path.get_path(),
                )

        return validated_constraints


# pylint: disable=too-many-public-methods
class SchemaManager(NodeManager):
    def __init__(self):
        self._cache: Dict[int, Any] = {}
        self._branches: Dict[str, SchemaBranch] = {}

    def _get_from_cache(self, key):
        return self._cache[key]

    def set(self, name: str, schema: Union[NodeSchema, GenericSchema], branch: Optional[str] = None) -> int:
        branch = branch or config.SETTINGS.main.default_branch

        if branch not in self._branches:
            self._branches[branch] = SchemaBranch(cache=self._cache, name=branch)

        self._branches[branch].set(name=name, schema=schema)

        return hash(self._branches[branch])

    def has(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        try:
            self.get(name=name, branch=branch, duplicate=False)
            return True
        except SchemaNotFound:
            return False

    def get(
        self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> Union[NodeSchema, GenericSchema]:
        # For now we assume that all branches are present, will see how we need to pull new branches later.
        branch = get_branch_from_registry(branch=branch)

        if branch.name in self._branches:
            try:
                return self._branches[branch.name].get(name=name, duplicate=duplicate)
            except SchemaNotFound:
                pass

        default_branch = config.SETTINGS.main.default_branch
        return self._branches[default_branch].get(name=name, duplicate=duplicate)

    def get_full(self, branch: Optional[Union[Branch, str]] = None) -> Dict[str, Union[NodeSchema, GenericSchema]]:
        branch = get_branch_from_registry(branch=branch)

        branch_name = None
        if branch.name in self._branches:
            branch_name = branch.name
        else:
            branch_name = config.SETTINGS.main.default_branch

        return self._branches[branch_name].get_all()

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
        limit: Optional[List[str]] = None,
        update_db: bool = True,
    ):
        branch = await get_branch(branch=branch, db=db)

        updated_schema = None
        if update_db:
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

        for item_kind in list(schema.generics.keys()) + list(schema.nodes.keys()):
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
        node: Union[NodeSchema, GenericSchema],
        db: InfrahubDatabase,
        branch: Union[str, Branch] = None,
    ) -> None:
        """Load a Node with its attributes and its relationships to the database.

        FIXME Currently this function only support adding new node, we need to update it to update existing nodes as well.
        """
        branch = await get_branch(branch=branch, db=db)

        node_type = "SchemaNode"
        if isinstance(node, GenericSchema):
            node_type = "SchemaGeneric"

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
        node: Union[NodeSchema, GenericSchema],
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
        current_schema.clear_cache()
        schema_diff = current_schema.get_hash_full().compare(branch.schema_hash)
        branch_schema = await self.load_schema_from_db(
            db=db, branch=branch, schema=current_schema, schema_diff=schema_diff
        )
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

        branch = await get_branch(branch=branch, db=db)
        schema = schema or SchemaBranch(cache=self._cache, name=branch.name)

        # If schema_diff has been provided, we need to build the proper filters for the queries based on the namespace and the name of the object.
        # the namespace and the name will be extracted from the kind with the function `parse_node_kind`
        filters = {"generics": {}, "nodes": {}}
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
