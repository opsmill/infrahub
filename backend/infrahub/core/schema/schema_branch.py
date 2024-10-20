from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional, Union

from infrahub_sdk.topological_sort import DependencyCycleExistsError, topological_sort
from infrahub_sdk.utils import compare_lists, deep_merge_dict, duplicates, intersection
from typing_extensions import Self

from infrahub.core.constants import (
    RESERVED_ATTR_GEN_NAMES,
    RESERVED_ATTR_REL_NAMES,
    RESTRICTED_NAMESPACES,
    BranchSupportType,
    HashableModelState,
    InfrahubKind,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipDirection,
    RelationshipKind,
    SchemaElementPathType,
)
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.models import (
    HashableModelDiff,
    SchemaBranchHash,
    SchemaDiff,
    SchemaUpdateValidationResult,
)
from infrahub.core.schema import (
    AttributePathParsingError,
    AttributeSchema,
    BaseNodeSchema,
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
    RelationshipSchema,
    SchemaAttributePath,
    SchemaRoot,
)
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.log import get_logger
from infrahub.types import ATTRIBUTE_TYPES
from infrahub.utils import format_label
from infrahub.visuals import select_color

from .constants import INTERNAL_SCHEMA_NODE_KINDS, SchemaNamespace

log = get_logger()

if TYPE_CHECKING:
    from pydantic import ValidationInfo


# pylint: disable=redefined-builtin,too-many-public-methods,too-many-lines


class SchemaBranch:
    def __init__(self, cache: dict, name: str | None = None, data: dict[str, dict[str, str]] | None = None):
        self._cache: dict[str, Union[NodeSchema, GenericSchema]] = cache
        self.name: str | None = name
        self.nodes: dict[str, str] = {}
        self.generics: dict[str, str] = {}
        self.profiles: dict[str, str] = {}

        if data:
            self.nodes = data.get("nodes", {})
            self.generics = data.get("generics", {})
            self.profiles = data.get("profiles", {})

    @classmethod
    def __get_validators__(cls) -> Iterator[Callable[..., Any]]:  # noqa: PLW3201
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, info: ValidationInfo) -> Self:  # pylint: disable=unused-argument
        if isinstance(v, cls):
            return v
        if isinstance(v, dict):
            return cls.from_dict_schema_object(data=v)
        raise ValueError("must be a class or a dict")

    @property
    def node_names(self) -> list[str]:
        return list(self.nodes.keys())

    @property
    def generic_names(self) -> list[str]:
        return list(self.generics.keys())

    @property
    def profile_names(self) -> list[str]:
        return list(self.profiles.keys())

    def get_all_kind_id_map(self, exclude_profiles: bool = False) -> dict[str, str]:
        kind_id_map = {}
        if exclude_profiles:
            names = self.node_names + [gn for gn in self.generic_names if gn != InfrahubKind.PROFILE]
        else:
            names = self.all_names
        for name in names:
            if name == InfrahubKind.NODE:
                continue
            item = self.get(name=name, duplicate=False)
            kind_id_map[name] = item.id
        return kind_id_map

    @property
    def all_names(self) -> list[str]:
        return self.node_names + self.generic_names + self.profile_names

    def get_hash(self) -> str:
        """Calculate the hash for this objects based on the content of nodes and generics.

        Since the object themselves are considered immutable we just need to use the hash from each object to calculate the global hash.
        """
        md5hash = hashlib.md5(usedforsecurity=False)
        for key, value in sorted(tuple(self.nodes.items()) + tuple(self.generics.items())):
            md5hash.update(str(key).encode())
            md5hash.update(str(value).encode())

        return md5hash.hexdigest()

    def get_hash_full(self) -> SchemaBranchHash:
        return SchemaBranchHash(main=self.get_hash(), nodes=self.nodes, generics=self.generics)

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": self.nodes, "generics": self.generics, "profiles": self.profiles}

    def to_dict_schema_object(self, duplicate: bool = False) -> dict[str, dict[str, MainSchemaTypes]]:
        return {
            "nodes": {name: self.get(name, duplicate=duplicate) for name in self.nodes},
            "profiles": {name: self.get(name, duplicate=duplicate) for name in self.profiles},
            "generics": {name: self.get(name, duplicate=duplicate) for name in self.generics},
        }

    @classmethod
    def from_dict_schema_object(cls, data: dict) -> Self:
        type_mapping = {
            "nodes": NodeSchema,
            "generics": GenericSchema,
            "profiles": ProfileSchema,
        }

        cache: dict[str, MainSchemaTypes] = {}
        nodes: dict[str, dict[str, str]] = {"nodes": {}, "generics": {}, "profiles": {}}

        for node_type, node_class in type_mapping.items():
            for node_name, node_data in data[node_type].items():
                node: MainSchemaTypes = node_class(**node_data)
                node_hash = node.get_hash()
                nodes[node_type][node_name] = node_hash

                cache[node_hash] = node

        return cls(cache=cache, data=nodes)

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

    def validate_update(self, other: SchemaBranch, enforce_update_support: bool = True) -> SchemaUpdateValidationResult:
        diff = self.diff(other=other)
        result = SchemaUpdateValidationResult.init(
            diff=diff, schema=other, enforce_update_support=enforce_update_support
        )
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

    def get_all(self, include_internal: bool = False, duplicate: bool = True) -> dict[str, MainSchemaTypes]:
        """Retrieve everything in a single dictionary."""

        return {
            name: self.get(name=name, duplicate=duplicate)
            for name in self.all_names
            if include_internal or name not in INTERNAL_SCHEMA_NODE_KINDS
        }

    def get_namespaces(self, include_internal: bool = False) -> list[SchemaNamespace]:
        all_schemas = self.get_all(include_internal=include_internal, duplicate=False)
        namespaces: dict[str, SchemaNamespace] = {}
        for schema in all_schemas.values():
            if schema.namespace in namespaces:
                continue
            namespaces[schema.namespace] = SchemaNamespace(
                name=schema.namespace, user_editable=schema.namespace not in RESTRICTED_NAMESPACES
            )

        return list(namespaces.values())

    def get_schemas_for_namespaces(
        self, namespaces: Optional[list[str]] = None, include_internal: bool = False
    ) -> list[MainSchemaTypes]:
        """Retrive everything in a single dictionary."""
        all_schemas = self.get_all(include_internal=include_internal, duplicate=False)
        if namespaces:
            return [schema for schema in all_schemas.values() if schema.namespace in namespaces]
        return list(all_schemas.values())

    def get_schemas_by_rel_identifier(self, identifier: str) -> list[MainSchemaTypes]:
        nodes: list[RelationshipSchema] = []
        for node_name in list(self.nodes.keys()) + list(self.generics.keys()):
            node = self.get(name=node_name, duplicate=False)
            rel = node.get_relationship_by_identifier(id=identifier, raise_on_error=False)
            if rel:
                nodes.append(self.get(name=node_name, duplicate=True))
        return nodes

    def generate_fields_for_display_label(self, name: str) -> Optional[dict]:
        node = self.get(name=name, duplicate=False)
        if isinstance(node, (NodeSchema, ProfileSchema)):
            return node.generate_fields_for_display_label()

        fields: dict[str, Union[str, None, dict[str, None]]] = {}
        if isinstance(node, GenericSchema):
            for child_node_name in node.used_by:
                child_node = self.get(name=child_node_name, duplicate=False)
                resp = child_node.generate_fields_for_display_label()
                if not resp:
                    continue
                fields = deep_merge_dict(dicta=fields, dictb=resp)

        return fields or None

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

    def process(self, validate_schema: bool = True) -> None:
        self.process_pre_validation()
        if validate_schema:
            self.process_validate()
        self.process_post_validation()

    def process_pre_validation(self) -> None:
        self.generate_identifiers()
        self.process_default_values()
        self.process_cardinality_counts()
        self.process_inheritance()
        self.process_hierarchy()
        self.process_branch_support()
        self.manage_profile_schemas()
        self.manage_profile_relationships()

    def process_validate(self) -> None:
        self.validate_names()
        self.validate_kinds()
        self.validate_default_values()
        self.validate_count_against_cardinality()
        self.validate_identifiers()
        self.sync_uniqueness_constraints_and_unique_attributes()
        self.validate_uniqueness_constraints()
        self.validate_display_labels()
        self.validate_order_by()
        self.validate_default_filters()
        self.validate_parent_component()
        self.validate_human_friendly_id()
        self.validate_required_relationships()

    def process_post_validation(self) -> None:
        self.add_groups()
        self.add_hierarchy()
        self.generate_weight()
        self.process_labels()
        self.process_dropdowns()
        self.process_relationships()
        self.process_human_friendly_id()

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
        rels_per_identifier: dict[str, dict[str, list[RelationshipSchema]]] = defaultdict(lambda: defaultdict(list))
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

    def validate_schema_path(
        self,
        node_schema: BaseNodeSchema,
        path: str,
        allowed_path_types: SchemaElementPathType,
        element_name: Optional[str] = None,
    ) -> SchemaAttributePath:
        error_header = f"{node_schema.kind}"
        error_header += f".{element_name}" if element_name else ""

        try:
            schema_attribute_path = node_schema.parse_schema_path(path=path, schema=self)
        except AttributePathParsingError as exc:
            raise ValueError(f"{error_header}: {exc}") from exc

        if not (SchemaElementPathType.ATTR & allowed_path_types) and schema_attribute_path.is_type_attribute:
            raise ValueError(f"{error_header}: this property only supports relationships not attributes")

        if not (SchemaElementPathType.REL & allowed_path_types) and schema_attribute_path.is_type_relationship:
            raise ValueError(f"{error_header}: this property only supports attributes, not relationships")

        if not (SchemaElementPathType.ATTR_NO_PROP & allowed_path_types) and schema_attribute_path.is_type_attribute:
            required_properties = tuple(
                schema_attribute_path.attribute_schema.get_class().get_allowed_property_in_path()
            )
            if schema_attribute_path.attribute_property_name not in required_properties:
                raise ValueError(
                    f"{error_header}: invalid attribute, it must end with one of the following properties:"
                    f" {', '.join(required_properties)}. (`{path}`)"
                )

        if schema_attribute_path.is_type_relationship:
            if schema_attribute_path.relationship_schema.cardinality == RelationshipCardinality.ONE:
                if not SchemaElementPathType.REL_ONE & allowed_path_types:
                    raise ValueError(
                        f"{error_header}: cannot use {schema_attribute_path.relationship_schema.name} relationship,"
                        f" relationship must be of cardinality many. (`{path}`)"
                    )
                if (
                    not SchemaElementPathType.REL_ONE_OPTIONAL & allowed_path_types
                    and schema_attribute_path.relationship_schema.optional
                    and not (
                        schema_attribute_path.relationship_schema.name == "ip_namespace"
                        and isinstance(node_schema, NodeSchema)
                        and (node_schema.is_ip_address() or node_schema.is_ip_prefix)
                    )
                ):
                    raise ValueError(
                        f"{error_header}: cannot use {schema_attribute_path.relationship_schema.name} relationship,"
                        f" relationship must be mandatory. (`{path}`)"
                    )

            if (
                schema_attribute_path.relationship_schema.cardinality == RelationshipCardinality.MANY
                and not SchemaElementPathType.REL_MANY & allowed_path_types
            ):
                raise ValueError(
                    f"{error_header}: cannot use {schema_attribute_path.relationship_schema.name} relationship,"
                    f" relationship must be of cardinality one (`{path}`)"
                )

            if schema_attribute_path.has_property and not SchemaElementPathType.REL_ATTR & allowed_path_types:
                raise ValueError(
                    f"{error_header}: cannot use attributes of related node, only the relationship. (`{path}`)"
                )
            if not schema_attribute_path.has_property and not SchemaElementPathType.RELS_NO_ATTR & allowed_path_types:
                raise ValueError(f"{error_header}: Must use attributes of related node. (`{path}`)")

        return schema_attribute_path

    def sync_uniqueness_constraints_and_unique_attributes(self) -> None:
        for name in self.generic_names + self.node_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.unique_attributes and not node_schema.uniqueness_constraints:
                continue

            unique_attrs_in_constraints = set()
            for constraint_paths in node_schema.uniqueness_constraints or []:
                if len(constraint_paths) > 1:
                    continue
                constraint_path = constraint_paths[0]
                schema_attribute_path = node_schema.parse_schema_path(path=constraint_path, schema=self)
                if (
                    schema_attribute_path.is_type_attribute
                    and schema_attribute_path.attribute_property_name == "value"
                    and schema_attribute_path.attribute_schema
                ):
                    unique_attrs_in_constraints.add(schema_attribute_path.attribute_schema.name)

            unique_attrs_in_attrs = {attr_schema.name for attr_schema in node_schema.unique_attributes}
            if unique_attrs_in_attrs == unique_attrs_in_constraints:
                continue

            attrs_to_make_unique = unique_attrs_in_constraints - unique_attrs_in_attrs
            attrs_to_add_to_constraints = unique_attrs_in_attrs - unique_attrs_in_constraints
            node_schema = self.get(name=name, duplicate=True)

            for attr_name in attrs_to_make_unique:
                attr_schema = node_schema.get_attribute(name=attr_name)
                attr_schema.unique = True
            if attrs_to_add_to_constraints:
                node_schema.uniqueness_constraints = (node_schema.uniqueness_constraints or []) + sorted(
                    [[f"{attr_name}__value"] for attr_name in attrs_to_add_to_constraints]
                )
            self.set(name=name, schema=node_schema)

    def validate_uniqueness_constraints(self) -> None:
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.uniqueness_constraints:
                continue

            for constraint_paths in node_schema.uniqueness_constraints:
                for constraint_path in constraint_paths:
                    element_name = "uniqueness_constraints"
                    self.validate_schema_path(
                        node_schema=node_schema,
                        path=constraint_path,
                        allowed_path_types=SchemaElementPathType.ATTR_WITH_PROP
                        | SchemaElementPathType.REL_ONE_MANDATORY_NO_ATTR,
                        element_name=element_name,
                    )

    def validate_display_labels(self) -> None:
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if node_schema.display_labels:
                for path in node_schema.display_labels:
                    self.validate_schema_path(
                        node_schema=node_schema,
                        path=path,
                        allowed_path_types=SchemaElementPathType.ATTR,
                        element_name="display_labels",
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
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.order_by:
                continue

            allowed_types = SchemaElementPathType.ATTR_WITH_PROP | SchemaElementPathType.REL_ONE_ATTR_WITH_PROP
            for order_by_path in node_schema.order_by:
                element_name = "order_by"
                self.validate_schema_path(
                    node_schema=node_schema,
                    path=order_by_path,
                    allowed_path_types=allowed_types,
                    element_name=element_name,
                )

    def validate_default_filters(self) -> None:
        for name in self.all_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.default_filter:
                continue

            self.validate_schema_path(
                node_schema=node_schema,
                path=node_schema.default_filter,
                allowed_path_types=SchemaElementPathType.ATTR,
                element_name="default_filter",
            )

    def validate_default_values(self) -> None:
        for name in self.generic_names + self.node_names:
            node_schema = self.get(name=name, duplicate=False)
            for node_attr in node_schema.local_attributes:
                if node_attr.default_value is None:
                    continue

                infrahub_attribute_type = ATTRIBUTE_TYPES[node_attr.kind].get_infrahub_class()
                try:
                    infrahub_attribute_type.validate_format(
                        value=node_attr.default_value, name=node_attr.name, schema=node_attr
                    )
                    infrahub_attribute_type.validate_content(
                        value=node_attr.default_value, name=node_attr.name, schema=node_attr
                    )
                except ValidationError as exc:
                    raise ValidationError(
                        f"{node_schema.namespace}{node_schema.name}: default value {exc.message}"
                    ) from exc

    def validate_human_friendly_id(self) -> None:
        for name in self.generic_names + self.node_names:
            node_schema = self.get(name=name, duplicate=False)
            hf_attr_names = set()

            if not node_schema.human_friendly_id:
                continue

            allowed_types = SchemaElementPathType.ATTR_WITH_PROP | SchemaElementPathType.REL_ONE_MANDATORY_ATTR
            for hfid_path in node_schema.human_friendly_id:
                schema_path = self.validate_schema_path(
                    node_schema=node_schema,
                    path=hfid_path,
                    allowed_path_types=allowed_types,
                    element_name="human_friendly_id",
                )

                if schema_path.is_type_attribute:
                    hf_attr_names.add(schema_path.attribute_schema.name)

    def validate_required_relationships(self) -> None:
        reverse_dependency_map: dict[str, set[str]] = {}
        for name in self.node_names + self.generic_names:
            node_schema = self.get(name=name, duplicate=False)
            for relationship_schema in node_schema.relationships:
                if relationship_schema.optional:
                    continue

                peer_kind = relationship_schema.peer
                if peer_kind in reverse_dependency_map.get(node_schema.kind, set()):
                    raise ValueError(
                        f"'{node_schema.kind}' and '{peer_kind}' cannot both have required relationships to one another."
                    )
                if peer_kind not in reverse_dependency_map:
                    reverse_dependency_map[peer_kind] = set()
                reverse_dependency_map[peer_kind].add(node_schema.kind)

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

    def validate_kinds(self) -> None:
        for name in list(self.nodes.keys()):
            node = self.get_node(name=name, duplicate=False)

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

    def process_human_friendly_id(self) -> None:
        for name in self.generic_names + self.node_names:
            node = self.get(name=name, duplicate=False)

            # If human_friendly_id IS NOT defined
            #   but some the model has some unique attribute, we generate a human_friendly_id
            # If human_friendly_id IS defined
            #   but no unique attributes and no uniquess constraints, we add a uniqueness_constraint
            if not node.human_friendly_id and node.unique_attributes:
                for attr in node.unique_attributes:
                    node = self.get(name=name, duplicate=True)
                    node.human_friendly_id = [f"{attr.name}__value"]
                    self.set(name=node.kind, schema=node)
                    break
                continue

            # if no human_friendly_id and a uniqueness_constraint with a single attribute exists
            # then use that attribute as the human_friendly_id
            if not node.human_friendly_id and node.uniqueness_constraints:
                for constraint_paths in node.uniqueness_constraints:
                    if len(constraint_paths) > 1:
                        continue
                    constraint_path = constraint_paths[0]
                    schema_path = node.parse_schema_path(path=constraint_path, schema=node)
                    if (
                        schema_path.is_type_attribute
                        and schema_path.attribute_property_name == "value"
                        and schema_path.attribute_schema
                    ):
                        node = self.get(name=name, duplicate=True)
                        node.human_friendly_id = [f"{schema_path.attribute_schema.name}__value"]
                        self.set(name=node.kind, schema=node)
                        break

            if node.human_friendly_id and not node.uniqueness_constraints:
                uniqueness_constraints: list[str] = []
                for item in node.human_friendly_id:
                    schema_attribute_path = node.parse_schema_path(path=item, schema=self)
                    if schema_attribute_path.is_type_attribute:
                        uniqueness_constraints.append(item)
                    elif schema_attribute_path.is_type_relationship:
                        uniqueness_constraints.append(schema_attribute_path.relationship_schema.name)

                node.uniqueness_constraints = [uniqueness_constraints]
                self.set(name=node.kind, schema=node)

    def process_hierarchy(self) -> None:
        for name in self.nodes.keys():
            node = self.get_node(name=name, duplicate=False)

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
            node = self.get_node(name=name, duplicate=False)

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

                generic_kind_schema = self.get_generic(generic_kind, duplicate=False)
                if generic_kind_schema.hierarchical:
                    generic_with_hierarchical_support.append(generic_kind)

                # Perform checks to validate that the node is not breaking inheritance rules
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

            attr_names_to_update = [
                attr.name for attr in node.attributes if attr.default_value is not None and not attr.optional
            ]
            if not attr_names_to_update:
                continue

            node = node.duplicate()
            for attr_name in attr_names_to_update:
                attr = node.get_attribute(name=attr_name)
                attr.optional = True

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

    def generate_weight(self) -> None:
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

    def add_groups(self) -> None:
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

    def add_hierarchy(self) -> None:
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

    def manage_profile_schemas(self) -> None:
        if not self.has(name=InfrahubKind.PROFILE):
            core_profile_schema = GenericSchema(**core_profile_schema_definition)
            self.set(name=core_profile_schema.kind, schema=core_profile_schema)
        else:
            core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=False)

        profile_schema_kinds = set()
        for node_name in self.node_names + self.generic_names:
            node = self.get(name=node_name, duplicate=False)
            if node.namespace in RESTRICTED_NAMESPACES or not node.generate_profile:
                try:
                    self.delete(name=self._get_profile_kind(node_kind=node.kind))
                except SchemaNotFoundError:
                    ...
                continue

            profile = self.generate_profile_from_node(node=node)
            self.set(name=profile.kind, schema=profile)
            profile_schema_kinds.add(profile.kind)
        if not profile_schema_kinds:
            return

        # Update used_by list for CoreProfile and CoreNode
        core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=False)
        current_used_by_profile = set(core_profile_schema.used_by)
        new_used_by_profile = profile_schema_kinds - current_used_by_profile

        if new_used_by_profile:
            core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=True)
            core_profile_schema.used_by = sorted(list(profile_schema_kinds))
            self.set(name=InfrahubKind.PROFILE, schema=core_profile_schema)

        if self.has(name=InfrahubKind.NODE):
            core_node_schema = self.get(name=InfrahubKind.NODE, duplicate=False)
            current_used_by_node = set(core_node_schema.used_by)
            new_used_by_node = profile_schema_kinds - current_used_by_node

            if new_used_by_node:
                core_node_schema = self.get(name=InfrahubKind.NODE, duplicate=True)
                updated_used_by_node = set(chain(profile_schema_kinds, set(core_node_schema.used_by)))
                core_node_schema.used_by = sorted(list(updated_used_by_node))
                self.set(name=InfrahubKind.NODE, schema=core_node_schema)

    def manage_profile_relationships(self) -> None:
        for node_name in self.node_names + self.generic_names:
            node = self.get(name=node_name, duplicate=False)

            if node.namespace in RESTRICTED_NAMESPACES:
                continue

            profiles_rel_settings: dict[str, Any] = {
                "name": "profiles",
                "identifier": "node__profile",
                "peer": InfrahubKind.PROFILE,
                "kind": RelationshipKind.PROFILE,
                "cardinality": RelationshipCardinality.MANY,
                "branch": BranchSupportType.AWARE,
            }

            # Add relationship between node and profile
            if "profiles" not in node.relationship_names:
                node_schema = self.get(name=node_name, duplicate=True)

                node_schema.relationships.append(RelationshipSchema(**profiles_rel_settings))
                self.set(name=node_name, schema=node_schema)
            else:
                has_changes: bool = False
                rel_profiles = node.get_relationship(name="profiles")
                for name, value in profiles_rel_settings.items():
                    if getattr(rel_profiles, name) != value:
                        has_changes = True

                if not has_changes:
                    continue

                node_schema = self.get(name=node_name, duplicate=True)
                rel_profiles = node_schema.get_relationship(name="profiles")
                for name, value in profiles_rel_settings.items():
                    if getattr(rel_profiles, name) != value:
                        setattr(rel_profiles, name, value)

                self.set(name=node_name, schema=node_schema)

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
            label=f"Profile {node.label}",
            description=f"Profile for {node.kind}",
            branch=node.branch,
            include_in_menu=False,
            display_labels=["profile_name__value"],
            inherit_from=[InfrahubKind.LINEAGESOURCE, InfrahubKind.PROFILE, InfrahubKind.NODE],
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
