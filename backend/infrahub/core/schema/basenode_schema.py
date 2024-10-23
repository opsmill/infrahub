from __future__ import annotations

import hashlib
import keyword
import os
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable, Literal, Optional, Union, overload

from infrahub_sdk.utils import compare_lists, intersection
from pydantic import field_validator

from infrahub.core.constants import RelationshipKind
from infrahub.core.models import HashableModelDiff

from .attribute_schema import AttributeSchema
from .generated.base_node_schema import GeneratedBaseNodeSchema
from .relationship_schema import RelationshipSchema

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch

# pylint: disable=redefined-builtin


NODE_METADATA_ATTRIBUTES = ["_source", "_owner"]


class BaseNodeSchema(GeneratedBaseNodeSchema):  # pylint: disable=too-many-public-methods
    _exclude_from_hash: list[str] = ["attributes", "relationships"]
    _sort_by: list[str] = ["namespace", "name"]

    @property
    def is_node_schema(self) -> bool:
        return False

    @property
    def is_generic_schema(self) -> bool:
        return False

    @property
    def is_profile_schema(self) -> bool:
        return False

    @property
    def kind(self) -> str:
        if self.namespace == "Attribute":
            return self.name
        return self.namespace + self.name

    @property
    def menu_title(self) -> str:
        return self.label or self.name

    def get_id(self) -> str:
        if self.id:
            return self.id
        raise ValueError(f"id is not defined on {self.kind}")

    def __hash__(self) -> int:
        """Return a hash of the object.
        Be careful hash generated from hash() have a salt by default and they will not be the same across run"""
        return hash(self.get_hash())

    def get_hash(self, display_values: bool = False) -> str:
        """Extend the Hash Calculation to account for attributes and relationships."""

        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(super().get_hash(display_values=display_values).encode())

        for attr_name in sorted(self.attribute_names):
            md5hash.update(self.get_attribute(name=attr_name).get_hash(display_values=display_values).encode())

        for rel_name in sorted(self.relationship_names):
            md5hash.update(self.get_relationship(name=rel_name).get_hash(display_values=display_values).encode())

        return md5hash.hexdigest()

    def diff(self, other: Self) -> HashableModelDiff:
        """Extend the Diff Calculation to account for attributes and relationships."""

        node_diff = super().diff(other=other)

        # Attribute
        attrs_diff = self._diff_element(
            other=other,
            get_func=BaseNodeSchema.get_attribute,
            get_map_func=BaseNodeSchema.get_attributes_name_id_map,
            obj_type=AttributeSchema,
        )
        # Relationships
        rels_diff = self._diff_element(
            other=other,
            get_func=BaseNodeSchema.get_relationship,
            get_map_func=BaseNodeSchema.get_relationship_name_id_map,
            obj_type=RelationshipSchema,
        )

        if attrs_diff.has_diff:
            node_diff.changed["attributes"] = attrs_diff
        if rels_diff.has_diff:
            node_diff.changed["relationships"] = rels_diff

        return node_diff

    def _diff_element(
        self,
        other: Self,
        get_func: Callable,
        get_map_func: Callable,
        obj_type: type[Union[AttributeSchema, RelationshipSchema]],
    ) -> HashableModelDiff:
        """The goal of this function is to reduce the amount of code duplicated between Attribute and Relationship to calculate a diff
        The logic is the same for both, except that the functions we are using to access these objects are differents

        To map elements from the local and other objects together, we are using a combinasion of ID and name
        If the same id is present on both we'll use the ID to match the elements on both side
        If the id is not present on either side, we'll try to match with the name

        """
        # Build a mapping between name and id for all element as well as the reverse mapping to make it easy to access the data
        local_map: dict[str, str] = get_map_func(self)
        other_map: dict[str, str] = get_map_func(other)

        reversed_map_local = dict(map(reversed, local_map.items()))
        reversed_map_other = dict(map(reversed, other_map.items()))

        # Identify which elements are using the same id on both sides
        clean_local_ids = [id for id in local_map.values() if id is not None]
        clean_other_ids = [id for id in other_map.values() if id is not None]
        shared_ids = intersection(list1=clean_local_ids, list2=clean_other_ids)

        # Identify which elements are present on both side based on the name
        local_names = [name for name, id in local_map.items() if id not in shared_ids]
        other_names = [name for name, id in other_map.items() if id not in shared_ids]
        present_both, present_local, present_other = compare_lists(list1=local_names, list2=other_names)

        elements_diff = HashableModelDiff()
        if present_local:
            elements_diff.added = dict.fromkeys(present_local)
        if present_other:
            elements_diff.removed = dict.fromkeys(present_other)

        # Process element b
        for name in sorted(present_both):
            # If the element doesn't have an ID on either side
            # this most likely means it was added recently from the internal schema.
            if os.environ.get("PYTEST_RUNNING", "") != "true" and local_map[name] is None and other_map[name] is None:
                elements_diff.added[name] = None
                continue
            local_element: obj_type = get_func(self, name=name)
            other_element: obj_type = get_func(other, name=name)
            element_diff = local_element.diff(other_element)
            if element_diff.has_diff:
                elements_diff.changed[name] = element_diff

        for element_id in shared_ids:
            local_element: obj_type = get_func(self, name=reversed_map_local[element_id])
            other_element: obj_type = get_func(other, name=reversed_map_other[element_id])
            element_diff = local_element.diff(other_element)
            if element_diff.has_diff:
                elements_diff.changed[reversed_map_local[element_id]] = element_diff

        return elements_diff

    @overload
    def get_field(
        self, name: str, raise_on_error: Literal[True] = True
    ) -> Union[AttributeSchema, RelationshipSchema]: ...

    @overload
    def get_field(
        self, name: str, raise_on_error: Literal[False] = False
    ) -> Optional[Union[AttributeSchema, RelationshipSchema]]: ...

    def get_field(self, name: str, raise_on_error: bool = True) -> Optional[Union[AttributeSchema, RelationshipSchema]]:
        if field := self.get_attribute_or_none(name=name):
            return field

        if field := self.get_relationship_or_none(name=name):
            return field

        if raise_on_error:
            raise ValueError(f"Unable to find the field {name}")

        return None

    def get_attribute(self, name: str) -> AttributeSchema:
        for item in self.attributes:
            if item.name == name:
                return item

        raise ValueError(f"Unable to find the attribute {name}")

    def get_attribute_or_none(self, name: str) -> Optional[AttributeSchema]:
        for item in self.attributes:
            if item.name == name:
                return item
        return None

    def get_attribute_by_id(self, id: str) -> AttributeSchema:
        for item in self.attributes:
            if item.id == id:
                return item

        raise ValueError(f"Unable to find the attribute with the ID: {id}")

    def get_relationship(self, name: str) -> RelationshipSchema:
        for item in self.relationships:
            if item.name == name:
                return item
        raise ValueError(f"Unable to find the relationship {name}")

    def get_relationship_by_id(self, id: str) -> RelationshipSchema:
        for item in self.relationships:
            if item.id == id:
                return item

        raise ValueError(f"Unable to find the relationship with the ID: {id}")

    def get_relationship_or_none(self, name: str) -> Optional[RelationshipSchema]:
        for item in self.relationships:
            if item.name == name:
                return item
        return None

    @overload
    def get_relationship_by_identifier(self, id: str, raise_on_error: Literal[True] = True) -> RelationshipSchema: ...

    @overload
    def get_relationship_by_identifier(
        self, id: str, raise_on_error: Literal[False] = False
    ) -> Optional[RelationshipSchema]: ...

    def get_relationship_by_identifier(self, id: str, raise_on_error: bool = True) -> Optional[RelationshipSchema]:
        for item in self.relationships:
            if item.identifier == id:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {id}")

    def get_relationships_by_identifier(self, id: str) -> list[RelationshipSchema]:
        """Return a list of relationship instead of a single one"""
        rels: list[RelationshipSchema] = []
        for item in self.relationships:
            if item.identifier == id:
                rels.append(item)

        return rels

    def get_relationships_of_kind(self, relationship_kinds: Iterable[RelationshipKind]) -> list[RelationshipSchema]:
        return [r for r in self.relationships if r.kind in relationship_kinds]

    def get_attributes_name_id_map(self) -> dict[str, str]:
        name_id_map = {}
        for attr in self.attributes:
            name_id_map[attr.name] = attr.id
        return name_id_map

    def get_relationship_name_id_map(self) -> dict[str, str]:
        name_id_map = {}
        for rel in self.relationships:
            name_id_map[rel.name] = rel.id
        return name_id_map

    @property
    def has_parent_relationship(self) -> bool:
        for rel in self.relationships:
            if rel.kind == RelationshipKind.PARENT:
                return True
        return False

    @property
    def valid_input_names(self) -> list[str]:
        return self.attribute_names + self.relationship_names + NODE_METADATA_ATTRIBUTES

    @property
    def valid_local_names(self) -> list[str]:
        return self.local_attribute_names + self.local_relationship_names + NODE_METADATA_ATTRIBUTES

    @property
    def attribute_names(self) -> list[str]:
        return [item.name for item in self.attributes]

    @property
    def relationship_names(self) -> list[str]:
        return [item.name for item in self.relationships]

    @property
    def mandatory_input_names(self) -> list[str]:
        return self.mandatory_attribute_names + self.mandatory_relationship_names

    @property
    def mandatory_attribute_names(self) -> list[str]:
        return [item.name for item in self.attributes if not item.optional and item.default_value is None]

    @property
    def mandatory_relationship_names(self) -> list[str]:
        return [item.name for item in self.relationships if not item.optional]

    @property
    def local_attributes(self) -> list[AttributeSchema]:
        return [item for item in self.attributes if not item.inherited]

    @property
    def local_attribute_names(self) -> list[str]:
        return [item.name for item in self.local_attributes]

    @property
    def local_relationships(self) -> list[RelationshipSchema]:
        return [item for item in self.relationships if not item.inherited]

    @property
    def local_relationship_names(self) -> list[str]:
        return [item.name for item in self.local_relationships]

    @property
    def unique_attributes(self) -> list[AttributeSchema]:
        return [item for item in self.attributes if item.unique]

    @classmethod
    def convert_path_to_graphql_fields(cls, path: str) -> dict:
        subpaths = path.split("__", maxsplit=1)
        fields = {}
        if len(subpaths) == 1:
            fields[subpaths[0]] = None
        elif len(subpaths) == 2:
            fields[subpaths[0]] = cls.convert_path_to_graphql_fields(path=subpaths[1])
        return fields

    def generate_fields_for_display_label(self) -> Optional[dict]:
        """Generate a dictionary containing the list of fields that are required
        to generate the display_label.

        If display_labels is not defined, we return None which equal to everything.
        """

        if not self.display_labels:
            return None

        fields: dict[str, Union[str, None, dict[str, None]]] = {}
        for item in self.display_labels:
            fields.update(self.convert_path_to_graphql_fields(path=item))
        return fields

    def generate_fields_for_hfid(self) -> Optional[dict]:
        """Generate a dictionary containing the list of fields that are required
        to generate the hfid.

        If display_labels is not defined, we return None which equal to everything.
        """

        if not self.human_friendly_id:
            return None

        fields: dict[str, Union[str, None, dict[str, None]]] = {}
        for item in self.human_friendly_id:
            fields.update(self.convert_path_to_graphql_fields(path=item))
        return fields

    @field_validator("name")
    @classmethod
    def name_is_not_keyword(cls, value: str) -> str:
        if keyword.iskeyword(value):
            raise ValueError(f"Name can not be set to a reserved keyword '{value}' is not allowed.")

        return value

    def parse_schema_path(self, path: str, schema: Optional[SchemaBranch] = None) -> SchemaAttributePath:
        schema_path = SchemaAttributePath()
        relationship_piece: Optional[str] = None
        attribute_piece: Optional[str] = None
        property_piece: Optional[str] = None

        path_parts = path.split("__")
        if path_parts[0] in self.relationship_names:
            relationship_piece = path_parts[0]
            attribute_piece = path_parts[1] if len(path_parts) > 1 else None
            property_piece = path_parts[2] if len(path_parts) > 2 else None
        elif path_parts[0] in self.attribute_names:
            attribute_piece = path_parts[0]
            property_piece = path_parts[1] if len(path_parts) > 1 else None
        else:
            raise AttributePathParsingError(f"{path} is invalid on schema {self.kind}")

        if relationship_piece and not schema:
            raise AttributePathParsingError("schema must be provided in order to check a path with a relationship")

        if relationship_piece:
            relationship_schema = self.get_relationship(name=path_parts[0])
            schema_path.relationship_schema = relationship_schema
            schema_path.related_schema = schema.get(name=relationship_schema.peer, duplicate=True)

        if attribute_piece:
            schema_to_check = schema_path.related_schema or self
            if attribute_piece not in schema_to_check.attribute_names:
                raise AttributePathParsingError(f"{attribute_piece} is not a valid attribute of {schema_to_check.kind}")
            schema_path.attribute_schema = schema_to_check.get_attribute(name=attribute_piece)

            if property_piece:
                attr_class = schema_path.attribute_schema.get_class()
                if property_piece not in attr_class.get_allowed_property_in_path():
                    raise AttributePathParsingError(
                        f"{property_piece} is not a valid property of {schema_path.attribute_schema.name}"
                    )
                schema_path.attribute_property_name = property_piece

        return schema_path

    def get_unique_constraint_schema_attribute_paths(
        self,
        schema_branch: SchemaBranch,
        include_unique_attributes: bool = False,
    ) -> list[list[SchemaAttributePath]]:
        constraint_paths_groups = []
        if include_unique_attributes:
            for attribute_schema in self.unique_attributes:
                constraint_paths_groups.append(
                    [SchemaAttributePath(attribute_schema=attribute_schema, attribute_property_name="value")]
                )

        if not self.uniqueness_constraints:
            return constraint_paths_groups

        for uniqueness_path_group in self.uniqueness_constraints:
            constraint_paths_group = []
            for uniqueness_path_part in uniqueness_path_group:
                constraint_paths_group.append(self.parse_schema_path(path=uniqueness_path_part, schema=schema_branch))
            if constraint_paths_group not in constraint_paths_groups:
                constraint_paths_groups.append(constraint_paths_group)
        return constraint_paths_groups


@dataclass
class SchemaAttributePath:
    relationship_schema: Optional[RelationshipSchema] = None
    related_schema: Optional[Union[NodeSchema, GenericSchema]] = None
    attribute_schema: Optional[AttributeSchema] = None
    attribute_property_name: Optional[str] = None

    @property
    def is_type_attribute(self) -> bool:
        return bool(self.attribute_schema and not self.related_schema and not self.relationship_schema)

    @property
    def is_type_relationship(self) -> bool:
        return bool(self.relationship_schema and self.related_schema)

    @property
    def has_property(self) -> bool:
        return bool(self.attribute_property_name)

    @property
    def active_relationship_schema(self) -> RelationshipSchema:
        if self.relationship_schema:
            return self.relationship_schema
        raise AttributePathParsingError("A relation_schema was expected but not found")

    @property
    def active_attribute_schema(self) -> AttributeSchema:
        if self.attribute_schema:
            return self.attribute_schema
        raise AttributePathParsingError("An attribute_schema was expected but not found")

    @property
    def active_attribute_property_name(self) -> str:
        if self.attribute_property_name:
            return self.attribute_property_name
        raise AttributePathParsingError("An attribute_property_name was expected but not found")


@dataclass
class SchemaAttributePathValue(SchemaAttributePath):
    value: Any = None

    @classmethod
    def from_schema_attribute_path(
        cls, schema_attribute_path: SchemaAttributePath, value: Any
    ) -> SchemaAttributePathValue:
        return cls(**asdict(schema_attribute_path), value=value)


class AttributePathParsingError(Exception): ...
