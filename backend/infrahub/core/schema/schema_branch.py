from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from itertools import chain, combinations
from typing import Any
from uuid import uuid4

from infrahub_sdk.template import Jinja2Template
from infrahub_sdk.template.exceptions import JinjaTemplateError, JinjaTemplateOperationViolationError
from infrahub_sdk.topological_sort import DependencyCycleExistsError, topological_sort
from infrahub_sdk.utils import compare_lists, deep_merge_dict, duplicates, intersection
from typing_extensions import Self

from infrahub.computed_attribute.constants import VALID_KINDS as VALID_COMPUTED_ATTRIBUTE_KINDS
from infrahub.core.constants import (
    OBJECT_TEMPLATE_NAME_ATTR,
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    RESERVED_ATTR_GEN_NAMES,
    RESERVED_ATTR_REL_NAMES,
    RESTRICTED_NAMESPACES,
    BranchSupportType,
    ComputedAttributeKind,
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
    TemplateSchema,
)
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.attribute_schema import get_attribute_schema_class_for_kind
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.log import get_logger
from infrahub.types import ATTRIBUTE_TYPES
from infrahub.utils import format_label
from infrahub.visuals import select_color

from ... import config
from ..constants.schema import PARENT_CHILD_IDENTIFIER
from .constants import INTERNAL_SCHEMA_NODE_KINDS, SchemaNamespace
from .schema_branch_computed import ComputedAttributes

log = get_logger()


class SchemaBranch:
    def __init__(
        self,
        cache: dict,
        name: str | None = None,
        data: dict[str, dict[str, str]] | None = None,
        computed_attributes: ComputedAttributes | None = None,
    ):
        self._cache: dict[str, NodeSchema | GenericSchema] = cache
        self.name: str | None = name
        self.nodes: dict[str, str] = {}
        self.generics: dict[str, str] = {}
        self.profiles: dict[str, str] = {}
        self.templates: dict[str, str] = {}
        self.computed_attributes = computed_attributes or ComputedAttributes()

        if data:
            self.nodes = data.get("nodes", {})
            self.generics = data.get("generics", {})
            self.profiles = data.get("profiles", {})
            self.templates = data.get("templates", {})

    @classmethod
    def validate(cls, data: Any) -> Self:
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            return cls.from_dict_schema_object(data=data)
        raise ValueError("must be a class or a dict")

    @property
    def node_names(self) -> list[str]:
        return list(self.nodes.keys())

    @property
    def generic_names(self) -> list[str]:
        return list(self.generics.keys())

    @property
    def generic_names_without_templates(self) -> list[str]:
        return [g for g in self.generic_names if not g.startswith("Template")]

    @property
    def profile_names(self) -> list[str]:
        return list(self.profiles.keys())

    @property
    def template_names(self) -> list[str]:
        return list(self.templates.keys())

    def get_all_kind_id_map(self, nodes_and_generics_only: bool = False) -> dict[str, str]:
        kind_id_map = {}
        if nodes_and_generics_only:
            names = self.node_names + self.generic_names_without_templates
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
        return self.node_names + self.generic_names + self.profile_names + self.template_names

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
        return {"nodes": self.nodes, "generics": self.generics, "profiles": self.profiles, "templates": self.templates}

    def to_dict_schema_object(self, duplicate: bool = False) -> dict[str, dict[str, MainSchemaTypes]]:
        return {
            "nodes": {name: self.get(name, duplicate=duplicate) for name in self.nodes},
            "profiles": {name: self.get(name, duplicate=duplicate) for name in self.profiles},
            "generics": {name: self.get(name, duplicate=duplicate) for name in self.generics},
            "templates": {name: self.get(name, duplicate=duplicate) for name in self.templates},
        }

    @classmethod
    def from_dict_schema_object(cls, data: dict) -> Self:
        type_mapping = {
            "nodes": NodeSchema,
            "generics": GenericSchema,
            "profiles": ProfileSchema,
            "templates": TemplateSchema,
        }

        cache: dict[str, MainSchemaTypes] = {}
        nodes: dict[str, dict[str, str]] = {"nodes": {}, "generics": {}, "profiles": {}, "templates": {}}

        for node_type, node_class in type_mapping.items():
            for node_name, node_data in data[node_type].items():
                node: MainSchemaTypes = node_class(**node_data)
                node_hash = node.get_hash()
                nodes[node_type][node_name] = node_hash

                cache[node_hash] = node

        return cls(cache=cache, data=nodes)

    def diff(self, other: SchemaBranch) -> SchemaDiff:
        # Identify the nodes or generics that have been added or removed
        local_kind_id_map = self.get_all_kind_id_map(nodes_and_generics_only=True)
        other_kind_id_map = other.get_all_kind_id_map(nodes_and_generics_only=True)
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

    def validate_node_deletions(self, diff: SchemaDiff) -> None:
        """Given a diff, check if a deleted node is still used in relationships of other nodes."""
        removed_schema_names = set(diff.removed.keys())
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)
            for relationship in node.relationships:
                if relationship.peer in removed_schema_names:
                    raise ValueError(
                        f"'{relationship.peer}' has been removed but is still referenced in '{name}.{relationship.name}'; keep it or delete the "
                        "relationship"
                    )

    def validate_update(
        self, other: SchemaBranch, diff: SchemaDiff, enforce_update_support: bool = True
    ) -> SchemaUpdateValidationResult:
        result = SchemaUpdateValidationResult.init(
            diff=diff, schema=other, enforce_update_support=enforce_update_support
        )
        result.validate_all(migration_map=MIGRATION_MAP, validator_map=CONSTRAINT_VALIDATOR_MAP)
        return result

    def duplicate(self, name: str | None = None) -> SchemaBranch:
        """Duplicate the current object but conserve the same cache."""
        return self.__class__(
            name=name,
            data=copy.deepcopy(self.to_dict()),
            cache=self._cache,
            computed_attributes=self.computed_attributes.duplicate(),
        )

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
        elif "Template" in schema.__class__.__name__:
            self.templates[name] = schema_hash

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
        elif name in self.templates:
            key = self.templates[name]

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

    def get_template(self, name: str, duplicate: bool = True) -> TemplateSchema:
        """Access a specific TemplateSchema, defined by its kind."""
        item = self.get(name=name, duplicate=duplicate)
        if not isinstance(item, TemplateSchema):
            raise ValueError(f"{name!r} is not of type TemplateSchema")
        return item

    def delete(self, name: str) -> None:
        if name in self.nodes:
            del self.nodes[name]
        elif name in self.generics:
            del self.generics[name]
        elif name in self.profiles:
            del self.profiles[name]
        elif name in self.templates:
            del self.templates[name]
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
        self, namespaces: list[str] | None = None, include_internal: bool = False
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

    def generate_fields_for_display_label(self, name: str) -> dict | None:
        node = self.get(name=name, duplicate=False)
        if isinstance(node, NodeSchema | ProfileSchema | TemplateSchema):
            return node.generate_fields_for_display_label()

        fields: dict[str, str | dict[str, None] | None] = {}
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

                if (new_item.is_node_schema and not item.is_node_schema) or (
                    new_item.is_generic_schema and not item.is_generic_schema
                ):
                    current_node_type = "Node" if new_item.is_node_schema else "Generic"
                    raise ValidationError(
                        f"{item.kind} already exist in the schema as a {current_node_type}. Either rename it or delete the existing one."
                    )
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
        self.process_deprecations()
        self.process_cardinality_counts()
        self.process_inheritance()
        self.process_hierarchy()
        self.process_branch_support()
        self.manage_object_template_schemas()
        self.manage_object_template_relationships()
        self.manage_profile_schemas()
        self.manage_profile_relationships()
        self.add_hierarchy_generic()
        self.add_hierarchy_node()

    def process_validate(self) -> None:
        self.validate_names()
        self.validate_kinds()
        self.validate_computed_attributes()
        self.validate_attribute_parameters()
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
        self.cleanup_inherited_elements()
        self.add_groups()
        self.generate_weight()
        self.process_labels()
        self.process_dropdowns()
        self.process_relationships()
        self.process_human_friendly_id()

    def _generate_identifier_string(self, node_kind: str, peer_kind: str) -> str:
        return "__".join(sorted([node_kind, peer_kind])).lower()

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
                rel.identifier = self._generate_identifier_string(node.kind, rel.peer)
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
        element_name: str | None = None,
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
                        and (node_schema.is_ip_address() or node_schema.is_ip_prefix())
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
        for name in self.generic_names_without_templates + self.node_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.unique_attributes and not node_schema.uniqueness_constraints:
                continue

            unique_attrs_in_constraints = set()
            for constraint_paths in node_schema.uniqueness_constraints or []:
                if len(constraint_paths) > 1:
                    continue
                constraint_path = constraint_paths[0]
                try:
                    schema_attribute_path = node_schema.parse_schema_path(path=constraint_path, schema=self)
                except AttributePathParsingError as exc:
                    raise ValueError(
                        f"{node_schema.kind}: Requested unique constraint not found within node. (`{constraint_path}`)"
                    ) from exc

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
        for name in self.generic_names_without_templates + self.node_names:
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

    def _is_attr_combination_unique(
        self, attrs_paths: list[str], uniqueness_constraints: list[list[str]] | None
    ) -> bool:
        """
        Return whether at least one combination of any length of `attrs_paths` is equal to a uniqueness constraint.
        """

        if not uniqueness_constraints:
            return False

        unique_constraint_group_sets = [set(ucg) for ucg in uniqueness_constraints]
        for i in range(1, len(attrs_paths) + 1):
            for attr_combo in combinations(attrs_paths, i):
                if any(ucg == set(attr_combo) for ucg in unique_constraint_group_sets):
                    return True
        return False

    def validate_human_friendly_id(self) -> None:
        for name in self.generic_names_without_templates + self.node_names:
            node_schema = self.get(name=name, duplicate=False)

            if not node_schema.human_friendly_id:
                continue

            allowed_types = SchemaElementPathType.ATTR_WITH_PROP | SchemaElementPathType.REL_ONE_MANDATORY_ATTR

            # Mapping relationship identifiers -> list of attributes paths
            rel_schemas_to_paths: dict[str, tuple[MainSchemaTypes, list[str]]] = {}

            for hfid_path in node_schema.human_friendly_id:
                schema_path = self.validate_schema_path(
                    node_schema=node_schema,
                    path=hfid_path,
                    allowed_path_types=allowed_types,
                    element_name="human_friendly_id",
                )

                if schema_path.is_type_relationship:
                    # Construct the name without relationship prefix to match with how it would be defined in peer schema uniqueness constraint
                    rel_identifier = schema_path.relationship_schema.identifier
                    if rel_identifier not in rel_schemas_to_paths:
                        rel_schemas_to_paths[rel_identifier] = (schema_path.related_schema, [])
                    rel_schemas_to_paths[rel_identifier][1].append(schema_path.attribute_path_as_str)

            if config.SETTINGS.main.schema_strict_mode:
                # For every relationship referred within hfid, check whether the combination of attributes is unique is the peer schema node
                for related_schema, attrs_paths in rel_schemas_to_paths.values():
                    if not self._is_attr_combination_unique(attrs_paths, related_schema.uniqueness_constraints):
                        raise ValidationError(
                            f"HFID of {node_schema.kind} refers peer {related_schema.kind} with a non-unique combination of attributes {attrs_paths}"
                        )

    def validate_required_relationships(self) -> None:
        reverse_dependency_map: dict[str, set[str]] = {}
        for name in self.node_names + self.generic_names_without_templates:
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
        for name in self.generic_names_without_templates + self.node_names:
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
        self, node_schema: NodeSchema | GenericSchema, parent_relationships: list[RelationshipSchema]
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
                if not self.has(rel.peer) or self.get(rel.peer, duplicate=False).state == HashableModelState.ABSENT:
                    raise ValueError(
                        f"{node.kind}: Relationship {rel.name!r} is referring an invalid peer {rel.peer!r}"
                    ) from None
                if rel.common_relatives:
                    peer_schema = self.get(name=rel.peer, duplicate=False)
                    for common_relatives_rel_name in rel.common_relatives:
                        if common_relatives_rel_name not in peer_schema.relationship_names:
                            raise ValueError(
                                f"{node.kind}: Relationship {rel.name!r} set 'common_relatives' with invalid relationship from '{rel.peer}'"
                            ) from None

    def validate_attribute_parameters(self) -> None:
        for name in self.generics.keys():
            generic_schema = self.get_generic(name=name, duplicate=False)
            for attribute in generic_schema.attributes:
                if (
                    attribute.kind == "NumberPool"
                    and isinstance(attribute.parameters, NumberPoolParameters)
                    and not attribute.parameters.number_pool_id
                ):
                    attribute.parameters.number_pool_id = str(uuid4())

        for name in self.nodes.keys():
            node_schema = self.get_node(name=name, duplicate=False)
            for attribute in node_schema.attributes:
                if (
                    attribute.kind == "NumberPool"
                    and isinstance(attribute.parameters, NumberPoolParameters)
                    and not attribute.parameters.number_pool_id
                ):
                    self._validate_number_pool_parameters(
                        node_schema=node_schema, attribute=attribute, number_pool_parameters=attribute.parameters
                    )

    def _validate_number_pool_parameters(
        self, node_schema: NodeSchema, attribute: AttributeSchema, number_pool_parameters: NumberPoolParameters
    ) -> None:
        if attribute.optional:
            raise ValidationError(f"{node_schema.kind}.{attribute.name} is a NumberPool it can't be optional")

        if not attribute.read_only:
            raise ValidationError(
                f"{node_schema.kind}.{attribute.name} is a NumberPool it has to be a read_only attribute"
            )

        if attribute.inherited:
            generics_with_attribute = []
            for generic_name in node_schema.inherit_from:
                generic_schema = self.get_generic(name=generic_name, duplicate=False)
                if attribute.name in generic_schema.attribute_names:
                    generic_attribute = generic_schema.get_attribute(name=attribute.name)
                    generics_with_attribute.append(generic_schema)
                    if isinstance(generic_attribute.parameters, NumberPoolParameters):
                        number_pool_parameters.number_pool_id = generic_attribute.parameters.number_pool_id

            if len(generics_with_attribute) > 1:
                raise ValidationError(
                    f"{node_schema.kind}.{attribute.name} is a NumberPool inherited from more than one generic"
                )

        else:
            number_pool_parameters.number_pool_id = str(uuid4())

    def validate_computed_attributes(self) -> None:
        self.computed_attributes = ComputedAttributes()
        for name in self.nodes.keys():
            node_schema = self.get_node(name=name, duplicate=False)
            for attribute in node_schema.attributes:
                self._validate_computed_attribute(node=node_schema, attribute=attribute)

        for name in self.generics.keys():
            generic_schema = self.get_generic(name=name, duplicate=False)
            for attribute in generic_schema.attributes:
                if attribute.computed_attribute and attribute.computed_attribute.kind != ComputedAttributeKind.USER:
                    for inheriting_node in generic_schema.used_by:
                        node_schema = self.get_node(name=inheriting_node, duplicate=False)
                        self.computed_attributes.validate_generic_inheritance(
                            node=node_schema, attribute=attribute, generic=generic_schema
                        )

    def _validate_computed_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        if not attribute.computed_attribute or attribute.computed_attribute.kind == ComputedAttributeKind.USER:
            return

        if not attribute.read_only:
            raise ValueError(
                f"{node.kind}: Attribute {attribute.name!r} is a computed attribute but not marked as read_only"
            )
        if attribute.kind not in VALID_COMPUTED_ATTRIBUTE_KINDS:
            raise ValueError(
                f"{node.kind}: Attribute {attribute.name!r} is a computed attribute only {VALID_COMPUTED_ATTRIBUTE_KINDS} kinds are supported."
            )

        if (
            attribute.computed_attribute.kind == ComputedAttributeKind.JINJA2
            and not attribute.computed_attribute.jinja2_template
        ):
            raise ValueError(
                f"{node.kind}: Attribute {attribute.name!r} is a computed jinja2 attribute but no logic is defined"
            )
        if (
            attribute.computed_attribute.kind == ComputedAttributeKind.JINJA2
            and attribute.computed_attribute.jinja2_template
        ):
            allowed_path_types = (
                SchemaElementPathType.ATTR_WITH_PROP
                | SchemaElementPathType.REL_ONE_MANDATORY_ATTR_WITH_PROP
                | SchemaElementPathType.REL_ONE_ATTR_WITH_PROP
            )

            jinja_template = Jinja2Template(template=attribute.computed_attribute.jinja2_template)
            try:
                variables = jinja_template.get_variables()
                jinja_template.validate(restricted=config.SETTINGS.security.restrict_untrusted_jinja2_filters)
            except JinjaTemplateOperationViolationError as exc:
                raise ValueError(
                    f"{node.kind}: Attribute {attribute.name!r} is assigned by a jinja2 template, but has an invalid template: {exc.message}"
                ) from exc

            except JinjaTemplateError as exc:
                raise ValueError(
                    f"{node.kind}: Attribute {attribute.name!r} is assigned by a jinja2 template, but has an invalid template: : {exc.message}"
                ) from exc

            for variable in variables:
                try:
                    schema_path = self.validate_schema_path(
                        node_schema=node, path=variable, allowed_path_types=allowed_path_types
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"{node.kind}: Attribute {attribute.name!r} the '{variable}' variable is not found within the schema path"
                    ) from exc

                if schema_path.is_type_attribute and schema_path.active_attribute_schema.name == attribute.name:
                    raise ValueError(
                        f"{node.kind}: Attribute {attribute.name!r} the '{variable}' variable is a reference to itself"
                    )

                self.computed_attributes.register_computed_jinja2(
                    node=node, attribute=attribute, schema_path=schema_path
                )

        elif attribute.computed_attribute.kind == ComputedAttributeKind.TRANSFORM_PYTHON and not attribute.optional:
            raise ValueError(
                f"{node.kind}: Attribute {attribute.name!r} is a computed transform, it can't be mandatory"
            )

        elif attribute.computed_attribute.kind == ComputedAttributeKind.TRANSFORM_PYTHON:
            self.computed_attributes.add_python_attribute(node=node, attribute=attribute)

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
        def check_if_need_to_update_label(node: MainSchemaTypes) -> bool:
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

            schema_to_update: NodeSchema | GenericSchema | None = None
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
        """
        For each schema node, if there is no HFID defined, set it with:
        - The first unique attribute if existing
        - Otherwise the first uniqueness constraint with a single attribute

        Also, HFID is added to the uniqueness constraints.
        """
        for name in self.generic_names_without_templates + self.node_names:
            node = self.get(name=name, duplicate=False)

            if not node.human_friendly_id:
                if node.unique_attributes:
                    node = self.get(name=name, duplicate=True)
                    node.human_friendly_id = [f"{node.unique_attributes[0].name}__value"]
                    self.set(name=node.kind, schema=node)

                # if no human_friendly_id and a uniqueness_constraint with a single attribute exists
                # then use that attribute as the human_friendly_id
                elif node.uniqueness_constraints:
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

            # Add hfid to uniqueness constraint
            hfid_uniqueness_constraint = node.convert_hfid_to_uniqueness_constraint(schema_branch=self)
            if hfid_uniqueness_constraint:
                node = self.get(name=name, duplicate=True)
                # Make sure there is no duplicate regarding generics values.
                if node.uniqueness_constraints:
                    if hfid_uniqueness_constraint not in node.uniqueness_constraints:
                        node.uniqueness_constraints.append(hfid_uniqueness_constraint)
                else:
                    node.uniqueness_constraints = [hfid_uniqueness_constraint]
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

            if node.hierarchy and node.hierarchy not in node.inherit_from:
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

    def _get_generic_fields_map(
        self, node_schema: MainSchemaTypes
    ) -> dict[str, tuple[GenericSchema, AttributeSchema | RelationshipSchema]]:
        generic_fields_map: dict[str, tuple[GenericSchema, AttributeSchema | RelationshipSchema]] = {}
        if isinstance(node_schema, NodeSchema) and node_schema.inherit_from:
            for generic_kind in node_schema.inherit_from:
                generic_schema = self.get_generic(name=generic_kind, duplicate=False)
                for generic_attr in generic_schema.attributes:
                    if generic_attr.name in node_schema.attribute_names:
                        generic_fields_map[generic_attr.name] = (generic_schema, generic_attr)
                        continue
                for generic_rel in generic_schema.relationships:
                    if generic_rel.name in node_schema.relationship_names:
                        generic_fields_map[generic_rel.name] = (generic_schema, generic_rel)
                        continue
        return generic_fields_map

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
            generic = self.get_generic(name=generic_name)

            if generic.kind in generics_used_by:
                generic.used_by = sorted(generics_used_by[generic.kind])
            else:
                generic.used_by = []

            self.set(name=generic_name, schema=generic)

    def process_branch_support(self) -> None:
        """Set branch support flag on all attributes and relationships if not already defined.

        if either node on a relationship support branch, the relationship must be branch aware.
        """

        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            generic_fields_map = self._get_generic_fields_map(node_schema=node)

            attrs_to_update: dict[str, BranchSupportType] = {}
            for attr in node.attributes:
                if attr.inherited and attr.name in generic_fields_map:
                    generic_schema, generic_attr = generic_fields_map[attr.name]
                    if attr.branch == generic_schema.branch == generic_attr.branch != node.branch:
                        attrs_to_update[attr.name] = node.branch

                if attr.branch is None:
                    attrs_to_update[attr.name] = node.branch

            rels_to_update: dict[str, BranchSupportType] = {}
            for rel in node.relationships:
                if not rel.inherited and rel.branch is not None:
                    continue
                needs_update = rel.branch is None
                if needs_update is False and rel.inherited and rel.name in generic_fields_map:
                    generic_schema, generic_rel = generic_fields_map[rel.name]
                    if rel.branch == generic_schema.branch == generic_rel.branch != node.branch:
                        needs_update = True
                if needs_update:
                    peer_node = self.get(name=rel.peer, duplicate=False)
                    if node.branch == peer_node.branch:
                        rels_to_update[rel.name] = node.branch
                    elif BranchSupportType.LOCAL in (node.branch, peer_node.branch):
                        rels_to_update[rel.name] = BranchSupportType.LOCAL
                    else:
                        rels_to_update[rel.name] = BranchSupportType.AWARE

            if not attrs_to_update and not rels_to_update:
                continue

            node = node.duplicate()
            for node_attr in node.attributes:
                if node_attr.name in attrs_to_update:
                    node_attr.branch = attrs_to_update[node_attr.name]
            for node_rel in node.relationships:
                if node_rel.name in rels_to_update:
                    node_rel.branch = rels_to_update[node_rel.name]

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

    def process_deprecations(self) -> None:
        """Mark deprecated attributes and relationships as optional."""
        for name in self.all_names:
            node = self.get(name=name, duplicate=False)

            change_required = False
            for item in node.attributes + node.relationships:
                if item.is_deprecated:
                    log.warn(f"'{item.name}' for '{node.kind}' has been marked as deprecated, remember to clean it up")
                    if not item.optional:
                        change_required = True

            if not change_required:
                continue

            node = node.duplicate()

            for item in node.attributes + node.relationships:
                if item.is_deprecated and not item.optional:
                    item.optional = True

            self.set(name=name, schema=node)

    def generate_weight(self) -> None:
        for name in self.generic_names:
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

        for name in self.node_names + self.profile_names:
            node = self.get(name=name, duplicate=False)

            items_to_update = [item for item in node.attributes + node.relationships if not item.order_weight]

            if not items_to_update:
                continue
            node = node.duplicate()

            generic_fields_map = self._get_generic_fields_map(node_schema=node)

            current_weight = 0
            for item in node.attributes + node.relationships:
                current_weight += 1000
                if not item.order_weight:
                    if item.inherited:
                        _, generic_field = generic_fields_map[item.name]
                        if generic_field:
                            item.order_weight = generic_field.order_weight
                    if not item.order_weight:
                        item.order_weight = current_weight

            self.set(name=name, schema=node)

    def cleanup_inherited_elements(self) -> None:
        for name in self.node_names:
            node = self.get_node(name=name, duplicate=False)

            attributes_to_delete = []
            relationships_to_delete = []

            inherited_attribute_names = set(node.attribute_names) - set(node.local_attribute_names)
            inherited_relationship_names = set(node.relationship_names) - set(node.local_relationship_names)
            for item_name in inherited_attribute_names:
                found = False
                for generic_name in node.inherit_from:
                    generic = self.get_generic(name=generic_name, duplicate=False)
                    if item_name in generic.attribute_names:
                        attr = generic.get_attribute(name=item_name)
                        if attr.state != HashableModelState.ABSENT:
                            found = True
                if not found:
                    attributes_to_delete.append(item_name)

            for item_name in inherited_relationship_names:
                found = False
                for generic_name in node.inherit_from:
                    generic = self.get_generic(name=generic_name, duplicate=False)
                    if item_name in generic.relationship_names:
                        rel = generic.get_relationship(name=item_name)
                        if rel.state != HashableModelState.ABSENT:
                            found = True
                if not found:
                    relationships_to_delete.append(item_name)

            # If there is either an attribute or a relationship to delete
            # We clone the node and we set the attribute / relationship as ABSENT
            if attributes_to_delete or relationships_to_delete:
                node_copy = self.get_node(name=name, duplicate=True)
                for item_name in attributes_to_delete:
                    attr = node_copy.get_attribute(name=item_name)
                    attr.state = HashableModelState.ABSENT
                for item_name in relationships_to_delete:
                    rel = node_copy.get_relationship(name=item_name)
                    rel.state = HashableModelState.ABSENT
                self.set(name=name, schema=node_copy)

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

    def _get_hierarchy_child_rel(self, peer: str, hierarchical: str | None, read_only: bool) -> RelationshipSchema:
        return RelationshipSchema(
            name="children",
            identifier=PARENT_CHILD_IDENTIFIER,
            peer=peer,
            kind=RelationshipKind.HIERARCHY,
            cardinality=RelationshipCardinality.MANY,
            branch=BranchSupportType.AWARE,
            direction=RelationshipDirection.INBOUND,
            hierarchical=hierarchical,
            read_only=read_only,
        )

    def _get_hierarchy_parent_rel(
        self, peer: str, hierarchical: str | None, read_only: bool, optional: bool
    ) -> RelationshipSchema:
        return RelationshipSchema(
            name="parent",
            identifier=PARENT_CHILD_IDENTIFIER,
            peer=peer,
            kind=RelationshipKind.HIERARCHY,
            cardinality=RelationshipCardinality.ONE,
            min_count=0 if optional else 1,
            max_count=1,
            branch=BranchSupportType.AWARE,
            direction=RelationshipDirection.OUTBOUND,
            hierarchical=hierarchical,
            read_only=read_only,
            optional=optional,
        )

    def add_hierarchy_generic(self) -> None:
        for generic_name in self.generics.keys():
            generic = self.get_generic(name=generic_name, duplicate=False)

            if not generic.hierarchical:
                continue

            generic = generic.duplicate()
            read_only = generic.kind == InfrahubKind.IPPREFIX

            if "parent" not in generic.relationship_names:
                generic.relationships.append(
                    self._get_hierarchy_parent_rel(
                        peer=generic_name, hierarchical=generic_name, read_only=read_only, optional=True
                    )
                )
            if "children" not in generic.relationship_names:
                generic.relationships.append(
                    self._get_hierarchy_child_rel(peer=generic_name, hierarchical=generic_name, read_only=read_only)
                )

            self.set(name=generic_name, schema=generic)

    def add_hierarchy_node(self) -> None:
        for node_name in self.nodes.keys():
            node = self.get_node(name=node_name, duplicate=False)

            if node.parent is None and node.children is None:
                continue

            node = node.duplicate()
            read_only = InfrahubKind.IPPREFIX in node.inherit_from

            if node.parent:
                if "parent" not in node.relationship_names:
                    node.relationships.append(
                        self._get_hierarchy_parent_rel(
                            peer=node.parent,
                            hierarchical=node.hierarchy,
                            read_only=read_only,
                            optional=node.parent in [node_name] + self.generic_names,
                        )
                    )
                else:
                    parent_rel = node.get_relationship(name="parent")
                    if parent_rel.peer != node.parent:
                        parent_rel.peer = node.parent

            if node.children:
                if "children" not in node.relationship_names:
                    node.relationships.append(
                        self._get_hierarchy_child_rel(
                            peer=node.children, hierarchical=node.hierarchy, read_only=read_only
                        )
                    )
                else:
                    children_rel = node.get_relationship(name="children")
                    if children_rel.peer != node.children:
                        children_rel.peer = node.children

            self.set(name=node_name, schema=node)

    def manage_profile_schemas(self) -> None:
        if not self.has(name=InfrahubKind.PROFILE):
            # TODO: This logic is actually only for testing purposes as since 1.0.9 CoreProfile is loaded in db.
            #  Ideally, we would remove this and instead load CoreProfile properly within tests.
            self.set(name=core_profile_schema_definition.kind, schema=core_profile_schema_definition)

        profile_schema_kinds = set()
        for node_name in self.node_names + self.generic_names_without_templates:
            node = self.get(name=node_name, duplicate=False)
            if (
                node.namespace in RESTRICTED_NAMESPACES
                or not node.generate_profile
                or node.state == HashableModelState.ABSENT
            ):
                try:
                    self.delete(name=self._get_profile_kind(node_kind=node.kind))
                except SchemaNotFoundError:
                    ...
                continue

            profile = self.generate_profile_from_node(node=node)
            self.set(name=profile.kind, schema=profile)
            profile_schema_kinds.add(profile.kind)

        for previous_profile in list(self.profiles.keys()):
            # Ensure that we remove previous profile schemas if a node has been renamed
            if previous_profile not in profile_schema_kinds:
                self.delete(name=previous_profile)

        if not profile_schema_kinds:
            return

        # Update used_by list for CoreProfile and CoreNode
        core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=False)
        current_used_by_profile = set(core_profile_schema.used_by)
        new_used_by_profile = profile_schema_kinds - current_used_by_profile

        if new_used_by_profile:
            core_profile_schema = self.get(name=InfrahubKind.PROFILE, duplicate=True)
            core_profile_schema.used_by = sorted(profile_schema_kinds)
            self.set(name=InfrahubKind.PROFILE, schema=core_profile_schema)

        if self.has(name=InfrahubKind.NODE):
            core_node_schema = self.get(name=InfrahubKind.NODE, duplicate=False)
            current_used_by_node = set(core_node_schema.used_by)
            new_used_by_node = profile_schema_kinds - current_used_by_node

            if new_used_by_node:
                core_node_schema = self.get(name=InfrahubKind.NODE, duplicate=True)
                updated_used_by_node = set(chain(profile_schema_kinds, set(core_node_schema.used_by)))
                core_node_schema.used_by = sorted(updated_used_by_node)
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
        name_attr_schema_class = get_attribute_schema_class_for_kind(kind=core_name_attr.kind)
        profile_name_attr = name_attr_schema_class(
            **core_name_attr.model_dump(exclude=["id", "inherited"]),
        )
        profile_name_attr.branch = node.branch
        core_priority_attr = core_profile_schema.get_attribute(name="profile_priority")
        priority_attr_schema_class = get_attribute_schema_class_for_kind(kind=core_priority_attr.kind)
        profile_priority_attr = priority_attr_schema_class(
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
            human_friendly_id=["profile_name__value"],
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
            attr_schema_class = get_attribute_schema_class_for_kind(kind=node_attr.kind)
            attr = attr_schema_class(
                optional=True,
                **node_attr.model_dump(exclude=["id", "unique", "optional", "read_only", "default_value", "inherited"]),
            )
            profile.attributes.append(attr)

        return profile

    def _get_object_template_kind(self, node_kind: str) -> str:
        return f"Template{node_kind}"

    def manage_object_template_relationships(self) -> None:
        """Add an `object_template` relationship to all nodes that can be created from object templates.

        This relationship allows to record from which template an object has been created.
        """
        for node_name in self.node_names + self.generic_names:
            node = self.get(name=node_name, duplicate=False)

            if (
                node.namespace in RESTRICTED_NAMESPACES
                or not node.generate_template
                or node.state == HashableModelState.ABSENT
            ):
                continue

            template_rel_settings: dict[str, Any] = {
                "name": OBJECT_TEMPLATE_RELATIONSHIP_NAME,
                "identifier": "node__objecttemplate",
                "peer": self._get_object_template_kind(node.kind),
                "kind": RelationshipKind.TEMPLATE,
                "cardinality": RelationshipCardinality.ONE,
                "branch": BranchSupportType.AWARE,
                "order_weight": 1,
            }

            # Add relationship between node and template
            if OBJECT_TEMPLATE_RELATIONSHIP_NAME not in node.relationship_names:
                node_schema = self.get(name=node_name, duplicate=True)

                node_schema.relationships.append(RelationshipSchema(**template_rel_settings))
                self.set(name=node_name, schema=node_schema)
            else:
                has_changes: bool = False
                rel_template = node.get_relationship(name=OBJECT_TEMPLATE_RELATIONSHIP_NAME)
                for name, value in template_rel_settings.items():
                    if getattr(rel_template, name) != value:
                        has_changes = True

                if not has_changes:
                    continue

                node_schema = self.get(name=node_name, duplicate=True)
                rel_template = node_schema.get_relationship(name=OBJECT_TEMPLATE_RELATIONSHIP_NAME)
                for name, value in template_rel_settings.items():
                    if getattr(rel_template, name) != value:
                        setattr(rel_template, name, value)

                self.set(name=node_name, schema=node_schema)

    def add_relationships_to_template(self, node: NodeSchema | GenericSchema) -> None:
        template_schema = self.get(name=self._get_object_template_kind(node_kind=node.kind), duplicate=False)

        # Remove previous relationships to account for new ones
        template_schema.relationships = [
            r for r in template_schema.relationships if r.kind == RelationshipKind.TEMPLATE
        ]
        # Tell if the user explicitely requested this template
        is_autogenerated_subtemplate = node.generate_template is False

        for relationship in node.relationships:
            if relationship.peer in [InfrahubKind.GENERICGROUP, InfrahubKind.PROFILE] or relationship.kind not in [
                RelationshipKind.COMPONENT,
                RelationshipKind.PARENT,
                RelationshipKind.ATTRIBUTE,
                RelationshipKind.GENERIC,
            ]:
                continue

            rel_template_peer = (
                self._get_object_template_kind(node_kind=relationship.peer)
                if relationship.kind not in [RelationshipKind.ATTRIBUTE, RelationshipKind.GENERIC]
                else relationship.peer
            )
            template_schema.relationships.append(
                RelationshipSchema(
                    name=relationship.name,
                    peer=rel_template_peer,
                    kind=relationship.kind,
                    optional=relationship.optional
                    if is_autogenerated_subtemplate
                    else relationship.kind != RelationshipKind.PARENT,
                    cardinality=relationship.cardinality,
                    direction=relationship.direction,
                    branch=relationship.branch,
                    identifier=f"template_{relationship.identifier}"
                    if relationship.identifier
                    else self._generate_identifier_string(template_schema.kind, rel_template_peer),
                    min_count=relationship.min_count,
                    max_count=relationship.max_count,
                    label=f"{relationship.name} template".title()
                    if relationship.kind in [RelationshipKind.COMPONENT, RelationshipKind.PARENT]
                    else relationship.name.title(),
                    inherited=relationship.inherited,
                )
            )

            parent_hfid = f"{relationship.name}__template_name__value"
            if (
                not isinstance(template_schema, GenericSchema)
                and relationship.kind == RelationshipKind.PARENT
                and parent_hfid not in template_schema.human_friendly_id
            ):
                template_schema.human_friendly_id = [parent_hfid] + template_schema.human_friendly_id
                template_schema.uniqueness_constraints[0].append(relationship.name)

    def generate_object_template_from_node(
        self, node: NodeSchema | GenericSchema, need_templates: set[NodeSchema | GenericSchema]
    ) -> TemplateSchema | GenericSchema:
        # Tell if the user explicitely requested this template
        is_autogenerated_subtemplate = node.generate_template is False

        core_template_schema = (
            self.get(name=InfrahubKind.OBJECTCOMPONENTTEMPLATE, duplicate=False)
            if is_autogenerated_subtemplate
            else self.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=False)
        )
        core_name_attr = core_template_schema.get_attribute(name=OBJECT_TEMPLATE_NAME_ATTR)
        name_attr_schema_class = get_attribute_schema_class_for_kind(kind=core_name_attr.kind)
        template_name_attr = name_attr_schema_class(
            **core_name_attr.model_dump(exclude=["id", "inherited"]),
        )
        template_name_attr.branch = node.branch

        template: TemplateSchema | GenericSchema
        need_template_kinds = [n.kind for n in need_templates]

        if node.is_generic_schema:
            template = GenericSchema(
                name=node.kind,
                namespace="Template",
                label=f"Generic object template {node.label}",
                description=f"Generic object template for generic {node.kind}",
                generate_profile=False,
                branch=node.branch,
                include_in_menu=False,
                display_labels=["template_name__value"],
                human_friendly_id=["template_name__value"],
                attributes=[template_name_attr],
            )

            for used in node.used_by:
                if used in need_template_kinds:
                    template.used_by.append(self._get_object_template_kind(node_kind=used))
        else:
            template = TemplateSchema(
                name=node.kind,
                namespace="Template",
                label=f"Object template {node.label}",
                description=f"Object template for {node.kind}",
                branch=node.branch,
                include_in_menu=False,
                display_labels=["template_name__value"],
                human_friendly_id=["template_name__value"],
                uniqueness_constraints=[["template_name__value"]],
                inherit_from=[InfrahubKind.LINEAGESOURCE, InfrahubKind.NODE, core_template_schema.kind],
                attributes=[template_name_attr],
                relationships=[
                    RelationshipSchema(
                        name="related_nodes",
                        identifier="node__objecttemplate",
                        peer=node.kind,
                        kind=RelationshipKind.TEMPLATE,
                        cardinality=RelationshipCardinality.MANY,
                        branch=BranchSupportType.AWARE,
                    )
                ],
            )

            for inherited in node.inherit_from:
                if inherited in need_template_kinds:
                    template.inherit_from.append(self._get_object_template_kind(node_kind=inherited))

        for node_attr in node.attributes:
            if node_attr.unique or node_attr.read_only:
                continue

            attr_schema_class = get_attribute_schema_class_for_kind(kind=node_attr.kind)
            attr = attr_schema_class(
                optional=node_attr.optional if is_autogenerated_subtemplate else True,
                **node_attr.model_dump(exclude=["id", "unique", "optional", "read_only"]),
            )
            template.attributes.append(attr)

        return template

    def identify_required_object_templates(
        self, node_schema: NodeSchema | GenericSchema, identified: set[NodeSchema | GenericSchema]
    ) -> set[NodeSchema]:
        """Identify all templates required to turn a given node into a template."""
        if node_schema in identified or node_schema.state == HashableModelState.ABSENT:
            return identified

        identified.add(node_schema)

        if node_schema.is_node_schema:
            identified.update([self.get(name=kind, duplicate=False) for kind in node_schema.inherit_from])

        for relationship in node_schema.relationships:
            if (
                relationship.peer in [InfrahubKind.GENERICGROUP, InfrahubKind.PROFILE]
                or (relationship.kind == RelationshipKind.PARENT and node_schema.generate_template)
                or relationship.kind not in [RelationshipKind.PARENT, RelationshipKind.COMPONENT]
            ):
                continue

            peer_schema = self.get(name=relationship.peer, duplicate=False)
            if not isinstance(peer_schema, NodeSchema | GenericSchema) or peer_schema in identified:
                continue
            # In a context of a generic, we won't be able to create objects out of it, so any kind of nodes implementing the generic is a valid
            # option, we therefore need to have a template for each of those nodes
            if isinstance(peer_schema, GenericSchema) and peer_schema.used_by:
                if relationship.kind != RelationshipKind.PARENT or not any(
                    u in [i.kind for i in identified] for u in peer_schema.used_by
                ):
                    for used_by in peer_schema.used_by:
                        identified |= self.identify_required_object_templates(
                            node_schema=self.get(name=used_by, duplicate=False), identified=identified
                        )

            identified |= self.identify_required_object_templates(node_schema=peer_schema, identified=identified)

        return identified

    def manage_object_template_schemas(self) -> None:
        need_templates: set[NodeSchema | GenericSchema] = set()
        template_schema_kinds: set[str] = set()

        for node_name in self.node_names + self.generic_names_without_templates:
            node = self.get(name=node_name, duplicate=False)

            # Delete old object templates if schemas were removed
            if (
                node.namespace in RESTRICTED_NAMESPACES
                or not node.generate_template
                or node.state == HashableModelState.ABSENT
            ):
                try:
                    node.relationships = [r for r in node.relationships if r.name != OBJECT_TEMPLATE_RELATIONSHIP_NAME]
                    self.delete(name=self._get_object_template_kind(node_kind=node.kind))
                except SchemaNotFoundError:
                    ...
                continue

            need_templates |= self.identify_required_object_templates(node_schema=node, identified=need_templates)

        # Generate templates with their attributes
        for node in need_templates:
            template = self.generate_object_template_from_node(node=node, need_templates=need_templates)
            self.set(name=template.kind, schema=template)
            template_schema_kinds.add(template.kind)

        # Go back on templates and add relationships to them
        for node in need_templates:
            self.add_relationships_to_template(node=node)

        for previous_template in list(self.templates.keys()):
            # Ensure that we remove previous object template schemas if a node has been renamed
            if previous_template not in template_schema_kinds:
                self.delete(name=previous_template)

        if not template_schema_kinds:
            return

        core_template_schema = self.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=False)
        current_used_by_template = set(core_template_schema.used_by)
        new_used_by_template = template_schema_kinds - current_used_by_template

        if new_used_by_template:
            core_template_schema = self.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=True)
            core_template_schema.used_by = sorted(template_schema_kinds)
            self.set(name=InfrahubKind.OBJECTTEMPLATE, schema=core_template_schema)

        if self.has(name=InfrahubKind.NODE):
            core_node_schema = self.get(name=InfrahubKind.NODE, duplicate=False)
            current_used_by_node = set(core_node_schema.used_by)
            new_used_by_node = template_schema_kinds - current_used_by_node

            if new_used_by_node:
                core_node_schema = self.get(name=InfrahubKind.NODE, duplicate=True)
                updated_used_by_node = set(chain(template_schema_kinds, set(core_node_schema.used_by)))
                core_node_schema.used_by = sorted(updated_used_by_node)
                self.set(name=InfrahubKind.NODE, schema=core_node_schema)
