from __future__ import annotations

import enum
import hashlib
import keyword
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from infrahub_sdk.utils import compare_lists
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import (
    DEFAULT_DESCRIPTION_LENGTH,
    DEFAULT_KIND_MAX_LENGTH,
    DEFAULT_KIND_MIN_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    DEFAULT_NAME_MIN_LENGTH,
    DEFAULT_REL_IDENTIFIER_LENGTH,
    NAME_REGEX,
    NODE_KIND_REGEX,
    NODE_NAME_REGEX,
    RESTRICTED_NAMESPACES,
    BranchSupportType,
    FilterSchemaKind,  # noqa: TCH001
    RelationshipCardinality,
    RelationshipDirection,
    RelationshipKind,
    UpdateSupport,
)
from infrahub.core.enums import generate_python_enum
from infrahub.core.models import HashableModel, HashableModelDiff
from infrahub.core.query import QueryNode, QueryRel, QueryRelDirection
from infrahub.core.query.attribute import default_attribute_query_filter
from infrahub.core.relationship import Relationship
from infrahub.types import ATTRIBUTE_KIND_LABELS, ATTRIBUTE_TYPES

from .definitions.core import core_models
from .definitions.internal import internal
from .dropdown import DropdownChoice
from .generated.attribute_schema import GeneratedAttributeSchema

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryElement
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin

# Generate an Enum for Pydantic based on a List of String
attribute_dict = {attr.upper(): attr for attr in ATTRIBUTE_KIND_LABELS}
AttributeKind = enum.Enum("AttributeKind", dict(attribute_dict))

RELATIONSHIPS_MAPPING = {"Relationship": Relationship}
NODE_METADATA_ATTRIBUTES = ["_source", "_owner"]


class AttributeSchema(GeneratedAttributeSchema):
    _sort_by: List[str] = ["name"]

    @property
    def is_attribute(self) -> bool:
        return True

    @property
    def is_relationship(self) -> bool:
        return False

    @field_validator("kind")
    @classmethod
    def kind_options(cls, v: str) -> str:
        if v not in ATTRIBUTE_KIND_LABELS:
            raise ValueError(f"Only valid Attribute Kind are : {ATTRIBUTE_KIND_LABELS} ")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_dropdown_choices(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that choices are defined for a dropdown but not for other kinds."""
        if values.get("kind") != "Dropdown" and values.get("choices"):
            raise ValueError(f"Can only specify 'choices' for kind=Dropdown: {values['kind'] }")

        if values.get("kind") == "Dropdown" and not values.get("choices"):
            raise ValueError("The property 'choices' is required for kind=Dropdown")

        return values

    def get_class(self) -> type[BaseAttribute]:
        return ATTRIBUTE_TYPES[self.kind].get_infrahub_class()

    @property
    def uses_enum_class(self) -> bool:
        return bool(self.enum) and config.SETTINGS.experimental_features.graphql_enums

    @property
    def _branch(self) -> BranchSupportType:
        if not self.branch:
            raise ValueError("branch hasn't been defined yet")
        return self.branch

    def get_attribute_enum_class(self) -> Optional[enum.EnumType]:
        if not self.uses_enum_class:
            return None
        return generate_python_enum(f"{self.name.title()}Enum", {v: v for v in self.enum})

    def convert_to_attribute_enum(self, value: Any) -> Any:
        if not self.uses_enum_class or not value:
            return value
        attribute_enum_class = self.get_attribute_enum_class()
        if isinstance(value, attribute_enum_class):
            return value
        if isinstance(value, enum.Enum):
            value = value.value
        return attribute_enum_class(value)

    def convert_to_enum_value(self, value: Any) -> Any:
        if not self.uses_enum_class:
            return value
        if isinstance(value, list):
            value = [self.convert_to_attribute_enum(element) for element in value]
            return [element.value if isinstance(element, enum.Enum) else element for element in value]
        value = self.convert_to_attribute_enum(value)
        return value.value if isinstance(value, enum.Enum) else value

    async def get_query_filter(
        self,
        name: str,
        filter_name: str,
        branch: Optional[Branch] = None,
        filter_value: Optional[Union[str, int, bool, list, enum.Enum]] = None,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
        db: Optional[InfrahubDatabase] = None,
        partial_match: bool = False,
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        filter_value = self.convert_to_enum_value(filter_value)
        return await default_attribute_query_filter(
            name=name,
            filter_name=filter_name,
            branch=branch,
            filter_value=filter_value,
            include_match=include_match,
            param_prefix=param_prefix,
            db=db,
            partial_match=partial_match,
        )


@dataclass
class SchemaAttributePath:
    relationship_schema: Optional[RelationshipSchema] = None
    related_schema: Optional[Union[NodeSchema, GenericSchema]] = None
    attribute_schema: Optional[AttributeSchema] = None
    attribute_property_name: Optional[str] = None


class AttributePathParsingError(Exception):
    ...


class FilterSchema(HashableModel):
    name: str
    kind: FilterSchemaKind
    enum: Optional[List] = None
    object_kind: Optional[str] = None
    description: Optional[str] = None

    _sort_by: List[str] = ["name"]


class BaseNodeSchema(HashableModel):  # pylint: disable=too-many-public-methods
    id: Optional[str] = None
    name: str = Field(
        pattern=NODE_NAME_REGEX,
        min_length=DEFAULT_NAME_MIN_LENGTH,
        max_length=DEFAULT_NAME_MAX_LENGTH,
        json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value},
    )
    namespace: str = Field(
        pattern=NODE_KIND_REGEX,
        min_length=DEFAULT_KIND_MIN_LENGTH,
        max_length=DEFAULT_KIND_MAX_LENGTH,
        json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value},
    )
    description: Optional[str] = Field(
        default=None, max_length=DEFAULT_DESCRIPTION_LENGTH, json_schema_extra={"update": UpdateSupport.ALLOWED.value}
    )
    default_filter: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    branch: BranchSupportType = Field(
        default=BranchSupportType.AWARE, json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value}
    )
    order_by: Optional[List[str]] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    display_labels: Optional[List[str]] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    attributes: List[AttributeSchema] = Field(
        default_factory=list, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value}
    )
    relationships: List[RelationshipSchema] = Field(
        default_factory=list, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value}
    )
    filters: List[FilterSchema] = Field(
        default_factory=list, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value}
    )
    include_in_menu: Optional[bool] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    menu_placement: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    icon: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    label: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    uniqueness_constraints: Optional[List[List[str]]] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value}
    )

    _exclude_from_hash: List[str] = ["attributes", "relationships"]
    _sort_by: List[str] = ["name"]

    @property
    def kind(self) -> str:
        if self.namespace == "Attribute":
            return self.name
        return self.namespace + self.name

    @property
    def menu_title(self) -> str:
        return self.label or self.name

    def __hash__(self) -> int:
        """Return a hash of the object.
        Be careful hash generated from hash() have a salt by default and they will not be the same across run"""
        return hash(self.get_hash())

    def get_hash(self, display_values: bool = False) -> str:
        """Extend the Hash Calculation to account for attributes and relationships."""

        md5hash = hashlib.md5()
        md5hash.update(super().get_hash(display_values=display_values).encode())

        for attr_name in sorted(self.attribute_names):
            md5hash.update(self.get_attribute(name=attr_name).get_hash(display_values=display_values).encode())

        for rel_name in sorted(self.relationship_names):
            md5hash.update(self.get_relationship(name=rel_name).get_hash(display_values=display_values).encode())

        return md5hash.hexdigest()

    def diff(self, other: Self) -> HashableModelDiff:
        """Extend the Diff Calculation to account for attributes and relationships."""

        node_diff = super().diff(other=other)

        attrs_both, attrs_local, attrs_other = compare_lists(list1=self.attribute_names, list2=other.attribute_names)

        attrs_diff = HashableModelDiff()
        if attrs_local:
            attrs_diff.added = {attr_name: None for attr_name in attrs_local}
        if attrs_other:
            attrs_diff.removed = {attr_name: None for attr_name in attrs_other}
        if attrs_both:
            for attr_name in sorted(attrs_both):
                local_attr = self.get_attribute(name=attr_name)
                other_attr = other.get_attribute(name=attr_name)
                attr_diff = local_attr.diff(other_attr)
                if attr_diff.has_diff:
                    attrs_diff.changed[attr_name] = attr_diff

        rels_diff = HashableModelDiff()
        rels_both, rels_local, rels_other = compare_lists(list1=self.relationship_names, list2=other.relationship_names)
        if rels_local:
            rels_diff.added = {rel_name: None for rel_name in rels_local}
        if rels_other:
            rels_diff.removed = {rel_name: None for rel_name in rels_other}
        if rels_both:
            for rel_name in sorted(rels_both):
                local_rel = self.get_relationship(name=rel_name)
                other_rel = other.get_relationship(name=rel_name)
                rel_diff = local_rel.diff(other_rel)
                if rel_diff.has_diff:
                    rels_diff.added[rel_name] = rel_diff

        if attrs_diff.has_diff:
            node_diff.changed["attributes"] = attrs_diff
        if rels_diff.has_diff:
            node_diff.changed["relationships"] = rels_diff

        return node_diff

    def with_public_relationships(self) -> Self:
        duplicate = self.duplicate()
        duplicate.relationships = [
            relationship for relationship in self.relationships if not relationship.internal_peer
        ]
        return duplicate

    def get_field(self, name: str, raise_on_error: bool = True) -> Optional[Union[AttributeSchema, RelationshipSchema]]:
        if field := self.get_attribute(name, raise_on_error=False):
            return field

        if field := self.get_relationship(name, raise_on_error=False):
            return field

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the field {name}")

    def get_attribute(self, name, raise_on_error: bool = True) -> AttributeSchema:
        for item in self.attributes:
            if item.name == name:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the attribute {name}")

    def get_relationship(self, name, raise_on_error: bool = True) -> RelationshipSchema:
        for item in self.relationships:
            if item.name == name:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {name}")

    def get_relationship_by_identifier(self, id: str, raise_on_error: bool = True) -> RelationshipSchema:
        for item in self.relationships:
            if item.identifier == id:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {id}")

    def get_relationships_by_identifier(self, id: str) -> List[RelationshipSchema]:
        """Return a list of relationship instead of a single one"""
        rels: List[RelationshipSchema] = []
        for item in self.relationships:
            if item.identifier == id:
                rels.append(item)

        return rels

    @property
    def valid_input_names(self) -> List[str]:
        return self.attribute_names + self.relationship_names + NODE_METADATA_ATTRIBUTES

    @property
    def attribute_names(self) -> List[str]:
        return [item.name for item in self.attributes]

    @property
    def relationship_names(self) -> List[str]:
        return [item.name for item in self.relationships]

    @property
    def mandatory_input_names(self) -> List[str]:
        return self.mandatory_attribute_names + self.mandatory_relationship_names

    @property
    def mandatory_attribute_names(self) -> List[str]:
        return [item.name for item in self.attributes if not item.optional and item.default_value is None]

    @property
    def mandatory_relationship_names(self) -> List[str]:
        return [item.name for item in self.relationships if not item.optional]

    @property
    def local_attributes(self) -> List[AttributeSchema]:
        return [item for item in self.attributes if not item.inherited]

    @property
    def local_relationships(self) -> List[RelationshipSchema]:
        return [item for item in self.relationships if not item.inherited]

    @property
    def unique_attributes(self) -> List[AttributeSchema]:
        return [item for item in self.attributes if item.unique]

    def generate_fields_for_display_label(self) -> Dict:
        """Generate a Dictionnary containing the list of fields that are required
        to generate the display_label.

        If display_labels is not defined, we return None which equal to everything.
        """

        if not hasattr(self, "display_labels") or not isinstance(self.display_labels, list):
            return None

        fields: dict[str, Union[str, None, dict[str, None]]] = {}
        for item in self.display_labels:
            elements = item.split("__")
            if len(elements) == 1:
                fields[elements[0]] = None
            elif len(elements) == 2:
                fields[elements[0]] = {elements[1]: None}
            else:
                raise ValueError(f"Unexpected value for display_labels, {item} is not valid.")

        return fields

    @field_validator("name")
    @classmethod
    def name_is_not_keyword(cls, value: str) -> str:
        if keyword.iskeyword(value):
            raise ValueError(f"Name can not be set to a reserved keyword '{value}' is not allowed.")

        return value

    def parse_attribute_path(
        self,
        attribute_path: str,
        branch: Optional[Union[Branch, str]] = None,
        schema_map_override: Optional[Dict[str, Union[NodeSchema, GenericSchema]]] = None,
    ) -> SchemaAttributePath:
        allowed_leaf_properties = ["value"]
        schema_path = SchemaAttributePath()
        relationship_piece: Optional[str] = None
        attribute_piece: Optional[str] = None
        property_piece: Optional[str] = None
        path_parts = attribute_path.split("__")
        if path_parts[0] in self.relationship_names:
            relationship_piece = path_parts[0]
            attribute_piece = path_parts[1] if len(path_parts) > 1 else None
            property_piece = path_parts[2] if len(path_parts) > 2 else None
        elif path_parts[0] in self.attribute_names:
            attribute_piece = path_parts[0]
            property_piece = path_parts[1] if len(path_parts) > 1 else None
        else:
            raise AttributePathParsingError(f"{attribute_path} is invalid on schema {self.kind}")
        if relationship_piece:
            if relationship_piece not in self.relationship_names:
                raise AttributePathParsingError(f"{relationship_piece} is not a relationship of schema {self.kind}")
            relationship_schema = self.get_relationship(path_parts[0])
            schema_path.relationship_schema = relationship_schema
            if schema_map_override:
                try:
                    schema_path.related_schema = schema_map_override.get(relationship_schema.peer)
                except KeyError as exc:
                    raise AttributePathParsingError(f"No schema {relationship_schema.peer} in map") from exc
            else:
                schema_path.related_schema = relationship_schema.get_peer_schema(branch=branch)
        if attribute_piece:
            schema_to_check = schema_path.related_schema or self
            if attribute_piece not in schema_to_check.attribute_names:
                raise AttributePathParsingError(f"{attribute_piece} is not a valid attribute of {schema_to_check.kind}")
            schema_path.attribute_schema = schema_to_check.get_attribute(attribute_piece)
        if property_piece:
            if property_piece not in allowed_leaf_properties:
                raise AttributePathParsingError(
                    f"{property_piece} is not a valid property of {schema_path.attribute_schema.name}"
                )
            schema_path.attribute_property_name = property_piece
        return schema_path

    def get_unique_constraint_schema_attribute_paths(self) -> List[List[SchemaAttributePath]]:
        if not self.uniqueness_constraints:
            return []

        constraint_paths_groups = []
        for uniqueness_path_group in self.uniqueness_constraints:
            constraint_paths_groups.append(
                [
                    self.parse_attribute_path(attribute_path=uniqueness_path_part)
                    for uniqueness_path_part in uniqueness_path_group
                ]
            )
        return constraint_paths_groups


class QueryArrow(BaseModel):
    start: str
    end: str


class QueryArrowInband(QueryArrow):
    start: str = "<-"
    end: str = "-"


class QueryArrowOutband(QueryArrow):
    start: str = "-"
    end: str = "->"


class QueryArrowBidir(QueryArrow):
    start: str = "-"
    end: str = "-"


class QueryArrows(BaseModel):
    left: QueryArrow
    right: QueryArrow


class RelationshipSchema(HashableModel):
    id: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value})
    name: str = Field(
        pattern=NAME_REGEX,
        min_length=DEFAULT_NAME_MIN_LENGTH,
        max_length=DEFAULT_NAME_MAX_LENGTH,
        json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value},
    )
    peer: str = Field(
        pattern=NODE_KIND_REGEX,
        min_length=DEFAULT_KIND_MIN_LENGTH,
        max_length=DEFAULT_KIND_MAX_LENGTH,
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
    kind: RelationshipKind = Field(
        default=RelationshipKind.GENERIC, json_schema_extra={"update": UpdateSupport.ALLOWED.value}
    )
    direction: RelationshipDirection = Field(
        default=RelationshipDirection.BIDIR, json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value}
    )
    label: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    description: Optional[str] = Field(
        default=None, max_length=DEFAULT_DESCRIPTION_LENGTH, json_schema_extra={"update": UpdateSupport.ALLOWED.value}
    )
    identifier: Optional[str] = Field(
        default=None,
        max_length=DEFAULT_REL_IDENTIFIER_LENGTH,
        json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value},
    )
    inherited: bool = Field(default=False, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value})
    cardinality: RelationshipCardinality = Field(
        default=RelationshipCardinality.MANY, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value}
    )
    branch: Optional[BranchSupportType] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value}
    )
    optional: bool = Field(default=True, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    hierarchical: Optional[str] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value}
    )
    filters: List[FilterSchema] = Field(
        default_factory=list, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value}
    )
    order_weight: Optional[int] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    min_count: int = Field(default=0, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    max_count: int = Field(default=0, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})

    _exclude_from_hash: List[str] = ["filters"]
    _sort_by: List[str] = ["name"]

    @property
    def is_attribute(self) -> bool:
        return False

    @property
    def is_relationship(self) -> bool:
        return True

    def get_class(self) -> type[Relationship]:
        return Relationship

    def get_peer_schema(self, branch: Optional[Union[Branch, str]] = None) -> Union[NodeSchema, GenericSchema]:
        return registry.schema.get(name=self.peer, branch=branch, duplicate=False)

    @property
    def internal_peer(self) -> bool:
        return self.peer.startswith("Internal")

    def get_identifier(self) -> str:
        if not self.identifier:
            raise ValueError("RelationshipSchema is not initialized")
        return self.identifier

    def get_query_arrows(self) -> QueryArrows:
        """Return (in 4 parts) the 2 arrows for the relationship R1 and R2 based on the direction of the relationship."""

        if self.direction == RelationshipDirection.OUTBOUND:
            return QueryArrows(left=QueryArrowOutband(), right=QueryArrowOutband())
        if self.direction == RelationshipDirection.INBOUND:
            return QueryArrows(left=QueryArrowInband(), right=QueryArrowInband())

        return QueryArrows(left=QueryArrowOutband(), right=QueryArrowInband())

    async def get_query_filter(
        self,
        db: InfrahubDatabase,
        filter_name: str,
        filter_value: Optional[Union[str, int, bool]] = None,
        name: Optional[str] = None,  # pylint: disable=unused-argument
        branch: Optional[Branch] = None,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
        partial_match: bool = False,
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        """Generate Query String Snippet to filter the right node."""

        query_filter: List[QueryElement] = []
        query_params: Dict[str, Any] = {}
        query_where: List[str] = []

        prefix = param_prefix or f"rel_{self.name}"

        query_params[f"{prefix}_rel_name"] = self.identifier

        rel_type = self.get_class().rel_type
        peer_schema = self.get_peer_schema(branch=branch)

        if include_match:
            query_filter.append(QueryNode(name="n"))

        # Determine in which direction the relationships should point based on the side of the query
        rels_direction = {
            "r1": QueryRelDirection.OUTBOUND,
            "r2": QueryRelDirection.INBOUND,
        }
        if self.direction == RelationshipDirection.OUTBOUND:
            rels_direction = {
                "r1": QueryRelDirection.OUTBOUND,
                "r2": QueryRelDirection.OUTBOUND,
            }
        if self.direction == RelationshipDirection.INBOUND:
            rels_direction = {
                "r1": QueryRelDirection.INBOUND,
                "r2": QueryRelDirection.INBOUND,
            }

        if filter_name == "id":
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type], direction=rels_direction["r1"]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type], direction=rels_direction["r2"]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

            if filter_value is not None:
                query_filter[-1].params = {"uuid": f"${prefix}_peer_id"}
                query_params[f"{prefix}_peer_id"] = filter_value

            return query_filter, query_params, query_where

        if filter_name == "ids":
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type], direction=rels_direction["r1"]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type], direction=rels_direction["r2"]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

            if filter_value is not None:
                query_params[f"{prefix}_peer_ids"] = filter_value
                query_where.append(f"peer.uuid IN ${prefix}_peer_ids")

            return query_filter, query_params, query_where

        if "__" not in filter_name:
            return query_filter, query_params, query_where

        # -------------------------------------------------------------------
        # Check if the filter is matching
        # -------------------------------------------------------------------
        filter_field_name, filter_next_name = filter_name.split("__", maxsplit=1)

        if filter_field_name not in peer_schema.valid_input_names:
            return query_filter, query_params, query_where

        if self.hierarchical:
            query_filter.extend(
                [
                    QueryRel(
                        labels=[rel_type],
                        direction=rels_direction["r1"],
                        length_min=2,
                        length_max=config.SETTINGS.database.max_depth_search_hierarchy * 2,
                        params={"hierarchy": self.hierarchical},
                    ),
                    QueryNode(name="peer", labels=[self.hierarchical]),
                ]
            )
        else:
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type], direction=rels_direction["r1"]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type], direction=rels_direction["r2"]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

        field = peer_schema.get_field(filter_field_name)

        field_filter, field_params, field_where = await field.get_query_filter(
            db=db,
            name=filter_field_name,
            filter_name=filter_next_name,
            filter_value=filter_value,
            branch=branch,
            include_match=False,
            param_prefix=prefix if param_prefix else None,
            partial_match=partial_match,
        )

        query_filter.extend(field_filter)
        query_where.extend(field_where)
        query_params.update(field_params)

        return query_filter, query_params, query_where


class NodeSchema(BaseNodeSchema):
    inherit_from: List[str] = Field(
        default_factory=list, json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value}
    )
    hierarchy: Optional[str] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value}
    )
    parent: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    children: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})

    def inherit_from_interface(self, interface: GenericSchema) -> None:
        existing_inherited_attributes = {item.name: idx for idx, item in enumerate(self.attributes) if item.inherited}
        existing_inherited_relationships = {
            item.name: idx for idx, item in enumerate(self.relationships) if item.inherited
        }
        existing_inherited_fields = list(existing_inherited_attributes.keys()) + list(
            existing_inherited_relationships.keys()
        )

        for item in interface.attributes + interface.relationships:
            if item.name in self.valid_input_names:
                continue

            new_item = item.duplicate()
            new_item.inherited = True

            if isinstance(item, AttributeSchema) and item.name not in existing_inherited_fields:
                self.attributes.append(new_item)
            elif isinstance(item, AttributeSchema) and item.name in existing_inherited_fields:
                item_idx = existing_inherited_attributes[item.name]
                self.attributes[item_idx] = new_item
            elif isinstance(item, RelationshipSchema) and item.name not in existing_inherited_fields:
                self.relationships.append(new_item)
            elif isinstance(item, RelationshipSchema) and item.name in existing_inherited_fields:
                item_idx = existing_inherited_relationships[item.name]
                self.relationships[item_idx] = new_item

    def get_hierarchy_schema(self, branch: Optional[Union[Branch, str]] = None) -> GenericSchema:
        schema = registry.schema.get(name=self.hierarchy, branch=branch)
        if not isinstance(schema, GenericSchema):
            raise TypeError
        return schema


class GenericSchema(BaseNodeSchema):
    """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

    hierarchical: bool = Field(default=False, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    used_by: List[str] = Field(default_factory=list, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value})

    def get_hierarchy_schema(self, branch: Optional[Union[Branch, str]] = None) -> GenericSchema:  # pylint: disable=unused-argument
        if self.hierarchical:
            return self

        raise ValueError(f"hierarchical mode is not enabled on {self.kind}")


# -----------------------------------------------------
# Extensions
#  For the initial implementation its possible to add attribute and relationships on Node
#  Later on we'll consider adding support for other Node attributes like inherited_from etc ...
#  And we'll look into adding support for Generic as well
class BaseNodeExtensionSchema(HashableModel):
    kind: str
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)


class NodeExtensionSchema(BaseNodeExtensionSchema):
    pass


class SchemaExtension(HashableModel):
    nodes: List[NodeExtensionSchema] = Field(default_factory=list)


class SchemaRoot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Optional[str] = Field(default=None)
    generics: List[GenericSchema] = Field(default_factory=list)
    nodes: List[NodeSchema] = Field(default_factory=list)
    extensions: SchemaExtension = SchemaExtension()

    @classmethod
    def has_schema(cls, values: dict[str, Any], name: str) -> bool:
        """Check if a schema exist locally as a node or as a generic."""

        available_schemas = [item.kind for item in values.get("nodes", []) + values.get("generics", [])]
        if name not in available_schemas:
            return False

        return True

    def validate_namespaces(self) -> List[str]:
        models = self.nodes + self.generics
        errors: List[str] = []
        for model in models:
            if model.namespace in RESTRICTED_NAMESPACES:
                errors.append(f"Restricted namespace '{model.namespace}' used on '{model.name}'")

        return errors


internal_schema = internal.to_dict()

__all__ = [
    "core_models",
    "internal_schema",
    "AttributePathParsingError",
    "AttributeSchema",
    "BaseNodeSchema",
    "DropdownChoice",
    "FilterSchema",
    "NodeSchema",
    "GenericSchema",
    "RelationshipSchema",
    "SchemaAttributePath",
    "SchemaRoot",
]
