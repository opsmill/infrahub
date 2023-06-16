from __future__ import annotations

import copy
import enum
import keyword
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Extra, Field, root_validator, validator

from infrahub.core import registry
from infrahub.core.query import QueryNode, QueryRel
from infrahub.core.relationship import Relationship
from infrahub.types import ATTRIBUTE_TYPES
from infrahub.utils import BaseEnum
from infrahub_client.utils import duplicates, intersection

if TYPE_CHECKING:
    from neo4j import AsyncSession
    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryElement

# pylint: disable=no-self-argument,redefined-builtin,too-many-lines

ATTRIBUTE_KIND_LABELS = list(ATTRIBUTE_TYPES.keys())

# Generate an Enum for Pydantic based on a List of String
attribute_dict = {attr.upper(): attr for attr in ATTRIBUTE_KIND_LABELS}
AttributeKind = enum.Enum("AttributeKind", dict(attribute_dict))

RELATIONSHIPS_MAPPING = {"Relationship": Relationship}

NODE_KIND_REGEX = r"^[A-Z][a-zA-Z0-9]+$"
NODE_NAME_REGEX = r"^[a-z0-9\_]+$"

DEFAULT_NAME_MIN_LENGTH = 2
DEFAULT_NAME_MAX_LENGTH = 32
DEFAULT_KIND_MIN_LENGTH = 3
DEFAULT_KIND_MAX_LENGTH = 32
DEFAULT_DESCRIPTION_LENGTH = 128
DEFAULT_REL_IDENTIFIER_LENGTH = 128


class FilterSchemaKind(str, BaseEnum):
    TEXT = "Text"
    LIST = "Text"
    NUMBER = "Number"
    BOOLEAN = "Boolean"
    OBJECT = "Object"
    MULTIOBJECT = "MultiObject"
    ENUM = "Enum"


class RelationshipCardinality(str, BaseEnum):
    ONE = "one"
    MANY = "many"


class RelationshipKind(str, BaseEnum):
    GENERIC = "Generic"
    ATTRIBUTE = "Attribute"
    COMPONENT = "Component"
    PARENT = "Parent"


# Generate a list of String based on Enums
RELATIONSHIP_KINDS = [RelationshipKind.__members__[member].value for member in list(RelationshipKind.__members__)]
RELATIONSHIP_CARDINALITY = [
    RelationshipCardinality.__members__[member].value for member in list(RelationshipCardinality.__members__)
]


class BaseSchemaModel(BaseModel):
    _exclude_from_hash: List[str] = []
    _sort_by: List[str] = []

    class Config:
        extra = Extra.forbid
        underscore_attrs_are_private = True

    def __hash__(self):
        """Generate a hash for the object.

        Calculating a hash can be very complicated if the data that we are storing is dynamic
        In order for this function to work, it's recommended to exclude all objects or list of objects with _exclude_from_hash
        List of hashable elements are fine and they will be converted automatically to Tuple.
        """

        values = []

        for field_name in sorted(self.__fields__.keys()):
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            value = getattr(self, field_name)
            if isinstance(value, list):
                values.append(tuple(sorted(tuple(value))))
            else:
                values.append(value)

        return hash(tuple(values))

    @property
    def _sorting_id(self) -> Set[Any]:
        return tuple(getattr(self, key) for key in self._sort_by if hasattr(self, key))

    def _sorting_keys(self, other: BaseSchemaModel) -> Tuple[List[Any], List[Any]]:
        """Retrieve the values of the attributes listed in the _sort_key list, for both objects."""
        if not self._sort_by:
            raise TypeError(f"Sorting not supported for instance of {self.__class__.__name__}")

        if not hasattr(other, "_sort_by") and not other._sort_by:
            raise TypeError(
                f"Sorting not supported between instance of {other.__class__.__name__} and {self.__class__.__name__}"
            )

        self_sort_keys: List[Any] = [getattr(self, key) for key in self._sort_by if hasattr(self, key)]
        other_sort_keys: List[Any] = [getattr(other, key) for key in other._sort_by if hasattr(other, key)]

        return self_sort_keys, other_sort_keys

    def __lt__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) < tuple(other_sort_keys)

    def __le__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) <= tuple(other_sort_keys)

    def __gt__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) > tuple(other_sort_keys)

    def __ge__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) >= tuple(other_sort_keys)

    def duplicate(self) -> Self:
        """Duplicate the current object by doing a deep copy of everything and recreating a new object."""
        return self.__class__(**copy.deepcopy(self.dict()))

    @staticmethod
    def is_list_composed_of_schema_model(items) -> bool:
        for item in items:
            if not isinstance(item, BaseSchemaModel):
                return False
        return True

    @staticmethod
    def is_list_composed_of_standard_type(items) -> bool:
        for item in items:
            if not isinstance(item, (int, str, bool, float)):
                return False
        return True

    @staticmethod
    def update_list_schema_model(field_name, attr_local, attr_other):
        # merging the list is not easy, we need to create a unique id based on the
        # sorting keys and if we have 2 sub items with the same key we can merge them recursively with update()
        local_sub_items = {item._sorting_id: item for item in attr_local if hasattr(item, "_sorting_id")}
        other_sub_items = {item._sorting_id: item for item in attr_other if hasattr(item, "_sorting_id")}

        new_list = []

        if len(local_sub_items) != len(attr_local) or len(other_sub_items) != len(attr_other):
            raise ValueError(f"Unable to merge the list for {field_name}, not all items are supporting _sorting_id")

        if duplicates(list(local_sub_items.keys())) or duplicates(list(other_sub_items.keys())):
            raise ValueError(f"Unable to merge the list for {field_name}, some items have the same _sorting_id")

        shared_ids = intersection(list(local_sub_items.keys()), list(other_sub_items.keys()))
        local_only_ids = set(list(local_sub_items.keys())) - set(shared_ids)
        other_only_ids = set(list(other_sub_items.keys())) - set(shared_ids)

        new_list = [value for key, value in local_sub_items.items() if key in local_only_ids]
        new_list.extend([value for key, value in other_sub_items.items() if key in other_only_ids])

        for item_id in shared_ids:
            other_item = other_sub_items[item_id]
            local_item = local_sub_items[item_id]
            new_list.append(local_item.update(other_item))

        return new_list

    @staticmethod
    def update_list_standard(local_list, other_list):
        pass

    def update(self, other: Self) -> Self:
        """Update the current object with the new value from the new one if they are defined.

        Currently this method works for the following type of field
            int, str, bool, float: If present the value from Other is overwriting the local value
            list[BaseSchemaModel]: The list will be merge if all elements in the list have a _sorting_id and if it's unique.

        TODO Implement other fields type like dict
        """

        for field_name, _ in other.__fields__.items():
            if not hasattr(self, field_name):
                setattr(self, field_name, getattr(other, field_name))
                continue

            attr_other = getattr(other, field_name)
            attr_local = getattr(self, field_name)
            if attr_other is None or attr_local == attr_other:
                continue

            if attr_local is None or isinstance(attr_other, (int, str, bool, float)):
                setattr(self, field_name, getattr(other, field_name))
                continue

            if isinstance(attr_local, list) and isinstance(attr_other, list):
                if self.is_list_composed_of_schema_model(attr_local) and self.is_list_composed_of_schema_model(
                    attr_other
                ):
                    new_attr = self.update_list_schema_model(
                        field_name=field_name, attr_local=attr_local, attr_other=attr_other
                    )
                    setattr(self, field_name, new_attr)

                elif self.is_list_composed_of_standard_type(attr_local) and self.is_list_composed_of_standard_type(
                    attr_other
                ):
                    new_attr = list(dict.fromkeys(attr_local + attr_other))
                    setattr(self, field_name, new_attr)

        return self


class FilterSchema(BaseSchemaModel):
    name: str
    kind: FilterSchemaKind
    enum: Optional[List]
    object_kind: Optional[str]
    description: Optional[str]

    _sort_by: List[str] = ["name"]


class AttributeSchema(BaseSchemaModel):
    id: Optional[str]
    name: str = Field(regex=NODE_NAME_REGEX, min_length=DEFAULT_NAME_MIN_LENGTH, max_length=DEFAULT_NAME_MAX_LENGTH)
    kind: str  # AttributeKind
    label: Optional[str]
    description: Optional[str] = Field(max_length=DEFAULT_DESCRIPTION_LENGTH)
    default_value: Optional[Any]
    enum: Optional[List]
    regex: Optional[str]
    max_length: Optional[int]
    min_length: Optional[int]
    inherited: bool = False
    unique: bool = False
    branch: bool = True
    optional: bool = False
    order_weight: Optional[int]

    _exclude_from_hash: List[str] = ["id"]
    _sort_by: List[str] = ["name"]

    @validator("kind")
    def kind_options(
        cls,
        v,
    ):
        if v not in ATTRIBUTE_KIND_LABELS:
            raise ValueError(f"Only valid Attribute Kind are : {ATTRIBUTE_KIND_LABELS} ")
        return v

    def get_class(self):
        return ATTRIBUTE_TYPES[self.kind].get_infrahub_class()

    async def get_query_filter(
        self, session: AsyncSession, *args, **kwargs  # pylint: disable=unused-argument
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        return self.get_class().get_query_filter(*args, **kwargs)


class RelationshipSchema(BaseSchemaModel):
    id: Optional[str]
    name: str = Field(regex=NODE_NAME_REGEX, min_length=DEFAULT_NAME_MIN_LENGTH, max_length=DEFAULT_NAME_MAX_LENGTH)
    peer: str = Field(regex=NODE_KIND_REGEX, min_length=DEFAULT_KIND_MIN_LENGTH, max_length=DEFAULT_KIND_MAX_LENGTH)
    kind: RelationshipKind = RelationshipKind.GENERIC
    label: Optional[str]
    description: Optional[str] = Field(max_length=DEFAULT_DESCRIPTION_LENGTH)
    identifier: Optional[str] = Field(max_length=DEFAULT_REL_IDENTIFIER_LENGTH)
    inherited: bool = False
    cardinality: RelationshipCardinality = RelationshipCardinality.MANY
    branch: bool = True
    optional: bool = True
    filters: List[FilterSchema] = Field(default_factory=list)
    order_weight: Optional[int]

    _exclude_from_hash: List[str] = ["id", "filters"]
    _sort_by: List[str] = ["name"]

    def get_class(self):
        return Relationship

    async def get_peer_schema(self, branch: Optional[Union[Branch, str]] = None):
        return registry.schema.get(name=self.peer, branch=branch)

    async def get_query_filter(
        self,
        session: AsyncSession,
        filter_name: str,
        filter_value: Optional[Union[str, int, bool]] = None,
        name: Optional[str] = None,  # pylint: disable=unused-argument
        branch: Branch = None,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        """Generate Query String Snippet to filter the right node."""

        query_filter: List[QueryElement] = []
        query_params: Dict[str, Any] = {}
        query_where: List[str] = []

        prefix = param_prefix or f"rel_{self.name}"

        query_params[f"{prefix}_rel_name"] = self.identifier

        rel_type = self.get_class().rel_type
        peer_schema = await self.get_peer_schema(branch=branch)

        if include_match:
            query_filter.append(QueryNode(name="n"))

        if filter_name == "id":
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

            if filter_value is not None:
                query_filter[-1].params = {"uuid": f"${prefix}_peer_id"}
                query_params[f"{prefix}_peer_id"] = filter_value

            return query_filter, query_params, query_where

        if "__" not in filter_name:
            return query_filter, query_params, query_where

        # -------------------------------------------------------------------
        # Check if the filter is matching
        # -------------------------------------------------------------------
        filter_field_name, filter_next_name = filter_name.split("__", maxsplit=1)

        if filter_field_name not in peer_schema.valid_input_names:
            return query_filter, query_params, query_where

        query_filter.extend(
            [
                QueryRel(name="r1", labels=[rel_type]),
                QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                QueryRel(name="r2", labels=[rel_type]),
                QueryNode(name="peer", labels=["Node"]),
            ]
        )

        field = peer_schema.get_field(filter_field_name)

        field_filter, field_params, field_where = await field.get_query_filter(
            session=session,
            name=filter_field_name,
            filter_name=filter_next_name,
            filter_value=filter_value,
            branch=branch,
            include_match=False,
            param_prefix=prefix if param_prefix else None,
        )

        query_filter.extend(field_filter)
        query_where.extend(field_where)
        query_params.update(field_params)

        return query_filter, query_params, query_where


NODE_METADATA_ATTRIBUTES = ["_source", "_owner"]


class BaseNodeSchema(BaseSchemaModel):
    id: Optional[str]
    name: str = Field(regex=NODE_NAME_REGEX, min_length=DEFAULT_NAME_MIN_LENGTH, max_length=DEFAULT_NAME_MAX_LENGTH)
    kind: str = Field(regex=NODE_KIND_REGEX, min_length=DEFAULT_KIND_MIN_LENGTH, max_length=DEFAULT_KIND_MAX_LENGTH)
    description: Optional[str] = Field(max_length=DEFAULT_DESCRIPTION_LENGTH)
    default_filter: Optional[str]
    order_by: Optional[List[str]]
    display_labels: Optional[List[str]]
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)

    _exclude_from_hash: List[str] = ["id", "attributes", "relationships"]
    _sort_by: List[str] = ["name"]

    def __hash__(self):
        """Extend the Hash Calculation to account for attributes and relationships."""
        super_hash = [super().__hash__()]

        for item in self.attributes + self.relationships:
            super_hash.append(hash(item))

        return hash(tuple(super_hash))

    def get_field(self, name, raise_on_error=True) -> Union[AttributeSchema, RelationshipSchema]:
        if field := self.get_attribute(name, raise_on_error=False):
            return field

        if field := self.get_relationship(name, raise_on_error=False):
            return field

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the field {name}")

    def get_attribute(self, name, raise_on_error=True) -> AttributeSchema:
        for item in self.attributes:
            if item.name == name:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the attribute {name}")

    def get_relationship(self, name, raise_on_error=True) -> RelationshipSchema:
        for item in self.relationships:
            if item.name == name:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {name}")

    def get_relationship_by_identifier(self, id, raise_on_error=True) -> RelationshipSchema:
        for item in self.relationships:
            if item.identifier == id:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {id}")

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
    def unique_attributes(self) -> List[str]:
        return [item for item in self.attributes if item.unique]

    def generate_fields_for_display_label(self) -> Dict:
        """Generate a Dictionnary containing the list of fields that are required
        to generate the display_label.

        If display_labels is not defined, we return None which equal to everything.
        """

        if not hasattr(self, "display_labels") or not isinstance(self.display_labels, list):
            return None

        fields = {}
        for item in self.display_labels:
            elements = item.split("__")
            if len(elements) == 1:
                fields[elements[0]] = None
            elif len(elements) == 2:
                fields[elements[0]] = {elements[1]: None}
            else:
                raise ValueError(f"Unexpected value for display_labels, {item} is not valid.")

        return fields

    @validator("name")
    def name_is_not_keyword(cls, value: str) -> str:
        if keyword.iskeyword(value):
            raise ValueError(f"Name can not be set to a reserved keyword '{value}' is not allowed.")

        return value


class GenericSchema(BaseNodeSchema):
    """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

    branch: bool = True
    label: Optional[str]
    used_by: List[str] = Field(default_factory=list)


class NodeSchema(BaseNodeSchema):
    label: Optional[str]
    inherit_from: Optional[List[str]] = Field(default_factory=list)
    groups: Optional[List[str]] = Field(default_factory=list)
    branch: bool = True
    filters: List[FilterSchema] = Field(default_factory=list)

    @root_validator
    def unique_names(cls, values):
        attr_names = [attr.name for attr in values.get("attributes", [])]
        rel_names = [rel.name for rel in values.get("relationships", [])]

        if names_dup := duplicates(attr_names + rel_names):
            raise ValueError(f"Names of attributes and relationships must be unique : {names_dup}")
        return values

    @root_validator(pre=True)
    def generate_identifier(
        cls,
        values,
    ):
        for rel in values.get("relationships", []):
            if not rel.get("identifier", None) and values.get("kind") and rel.get("peer"):
                identifier = "__".join(sorted([values.get("kind"), rel.get("peer")]))
                rel["identifier"] = identifier.lower()

        return values

    @root_validator(pre=False)
    def unique_identifiers(
        cls,
        values,
    ):
        identifiers = [rel.identifier for rel in values.get("relationships", [])]
        if identifier_dup := duplicates(identifiers):
            raise ValueError(f"Identifier of relationships must be unique : {identifier_dup}")

        return values

    def inherit_from_interface(self, interface: GenericSchema) -> NodeSchema:
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


class GroupSchema(BaseSchemaModel):
    id: Optional[str]
    name: str = Field(regex=NODE_NAME_REGEX, min_length=DEFAULT_NAME_MIN_LENGTH, max_length=DEFAULT_NAME_MAX_LENGTH)
    kind: str = Field(regex=NODE_KIND_REGEX, min_length=DEFAULT_KIND_MIN_LENGTH, max_length=DEFAULT_KIND_MAX_LENGTH)
    description: Optional[str] = Field(max_length=DEFAULT_DESCRIPTION_LENGTH)


# -----------------------------------------------------
# Extensions
#  For the initial implementation its possible to add attribute and relationships on Node
#  Later on we'll consider adding support for other Node attributes like inherited_from etc ...
#  And we'll look into adding support for Generic as well
class BaseNodeExtensionSchema(BaseSchemaModel):
    kind: str
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)


class NodeExtensionSchema(BaseNodeExtensionSchema):
    pass


class SchemaExtension(BaseSchemaModel):
    nodes: List[NodeExtensionSchema] = Field(default_factory=list)


class SchemaRoot(BaseModel):
    version: Optional[str]
    generics: List[GenericSchema] = Field(default_factory=list)
    nodes: List[NodeSchema] = Field(default_factory=list)
    groups: List[GroupSchema] = Field(default_factory=list)
    extensions: SchemaExtension = SchemaExtension()

    class Config:
        extra = Extra.forbid

    @classmethod
    def has_schema(cls, values, name: str) -> bool:
        """Check if a schema exist locally as a node or as a generic."""

        available_schemas = [item.kind for item in values.get("nodes", []) + values.get("generics", [])]
        if name not in available_schemas:
            return False

        return True


# TODO need to investigate how we could generate the internal schema
# directly from the Pydantic Models to avoid the duplication of effort
internal_schema = {
    "nodes": [
        {
            "name": "node_schema",
            "kind": "NodeSchema",
            "branch": True,
            "default_filter": "name__value",
            "display_labels": ["name__value"],
            "attributes": [
                {
                    "name": "name",
                    "kind": "Text",
                    "description": "Node name, must be unique and must be all lowercase.",
                    "unique": True,
                    "regex": str(NODE_NAME_REGEX),
                    "min_length": DEFAULT_NAME_MIN_LENGTH,
                    "max_length": DEFAULT_NAME_MAX_LENGTH,
                },
                {
                    "name": "kind",
                    "kind": "Text",
                    "description": "Node kind, must be unique and must be in CamelCase",
                    "regex": str(NODE_KIND_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {
                    "name": "label",
                    "kind": "Text",
                    "description": "Human friendly representation of the name/kind",
                    "optional": True,
                    "max_length": DEFAULT_NAME_MAX_LENGTH,
                },
                {
                    "name": "description",
                    "kind": "Text",
                    #  "description": "",
                    "optional": True,
                    "max_length": DEFAULT_DESCRIPTION_LENGTH,
                },
                {
                    "name": "branch",
                    "kind": "Boolean",
                    "default_value": True,
                    "optional": True,
                },
                {
                    "name": "default_filter",
                    "kind": "Text",
                    "description": "Default filter used to search for a node in addition to its ID.",
                    "optional": True,
                },
                {
                    "name": "display_labels",
                    "kind": "List",
                    "description": "List of attributes to use to generate the display label",
                    "optional": True,
                },
                {
                    "name": "order_by",
                    "kind": "List",
                    "description": "List of attributes to use to order the results by default",
                    "optional": True,
                },
                {
                    "name": "inherit_from",
                    "kind": "List",
                    "description": "List of Generic Kind that this node is inheriting from",
                    "optional": True,
                },
                {
                    "name": "groups",
                    "kind": "List",
                    "description": "List of Group that this node is part of",
                    "optional": True,
                },
            ],
            "relationships": [
                {
                    "name": "attributes",
                    "peer": "AttributeSchema",
                    "kind": "Component",
                    "identifier": "schema__node__attributes",
                    "cardinality": "many",
                    "branch": True,
                    "optional": True,
                },
                {
                    "name": "relationships",
                    "peer": "RelationshipSchema",
                    "kind": "Component",
                    "identifier": "schema__node__relationships",
                    "cardinality": "many",
                    "branch": True,
                    "optional": True,
                },
            ],
        },
        {
            "name": "attribute_schema",
            "kind": "AttributeSchema",
            "branch": True,
            "default_filter": None,
            "display_labels": ["name__value"],
            "attributes": [
                {
                    "name": "name",
                    "kind": "Text",
                    "regex": str(NODE_NAME_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {
                    "name": "kind",
                    "kind": "Text",
                    "enum": ATTRIBUTE_KIND_LABELS,
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {"name": "enum", "kind": "List", "optional": True},
                {"name": "regex", "kind": "Text", "optional": True},
                {"name": "max_length", "kind": "Number", "optional": True},
                {"name": "min_length", "kind": "Number", "optional": True},
                {"name": "label", "kind": "Text", "optional": True, "max_length": DEFAULT_NAME_MAX_LENGTH},
                {"name": "description", "kind": "Text", "optional": True, "max_length": DEFAULT_DESCRIPTION_LENGTH},
                {"name": "unique", "kind": "Boolean", "default_value": False, "optional": True},
                {"name": "optional", "kind": "Boolean", "default_value": True, "optional": True},
                {"name": "branch", "kind": "Boolean", "default_value": True, "optional": True},
                {"name": "order_weight", "kind": "Number", "optional": True},
                {
                    "name": "default_value",
                    "kind": "Any",
                    "optional": True,
                },
                {"name": "inherited", "kind": "Boolean", "default_value": False, "optional": True},
            ],
            "relationships": [
                {
                    "name": "node",
                    "peer": "NodeSchema",
                    "kind": "Parent",
                    "identifier": "schema__node__attributes",
                    "cardinality": "one",
                    "branch": True,
                    "optional": False,
                }
            ],
        },
        {
            "name": "relationship_schema",
            "kind": "RelationshipSchema",
            "branch": True,
            "default_filter": None,
            "display_labels": ["name__value"],
            "attributes": [
                {
                    "name": "name",
                    "kind": "Text",
                    "regex": str(NODE_NAME_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {
                    "name": "peer",
                    "kind": "Text",
                    "regex": str(NODE_KIND_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {"name": "kind", "kind": "Text", "enum": RELATIONSHIP_KINDS, "default_value": "Generic"},
                {"name": "label", "kind": "Text", "optional": True, "max_length": DEFAULT_NAME_MAX_LENGTH},
                {"name": "description", "kind": "Text", "optional": True, "max_length": DEFAULT_DESCRIPTION_LENGTH},
                {"name": "identifier", "kind": "Text", "max_length": DEFAULT_REL_IDENTIFIER_LENGTH, "optional": True},
                {"name": "cardinality", "kind": "Text", "enum": RELATIONSHIP_CARDINALITY},
                {"name": "order_weight", "kind": "Number", "optional": True},
                {
                    "name": "optional",
                    "kind": "Boolean",
                    "default_value": False,
                    "optional": True,
                },
                {
                    "name": "branch",
                    "kind": "Boolean",
                    "default_value": True,
                    "optional": True,
                },
                {
                    "name": "inherited",
                    "kind": "Boolean",
                    "default_value": False,
                    "optional": True,
                },
            ],
            "relationships": [
                {
                    "name": "node",
                    "peer": "NodeSchema",
                    "kind": "Parent",
                    "identifier": "schema__node__relationships",
                    "cardinality": "one",
                    "branch": True,
                    "optional": False,
                }
            ],
        },
        {
            "name": "generic_schema",
            "kind": "GenericSchema",
            "branch": True,
            "default_filter": "name__value",
            "display_labels": ["label__value"],
            "attributes": [
                {
                    "name": "name",
                    "kind": "Text",
                    "unique": True,
                    "regex": str(NODE_NAME_REGEX),
                    "min_length": DEFAULT_NAME_MIN_LENGTH,
                    "max_length": DEFAULT_NAME_MAX_LENGTH,
                },
                {
                    "name": "kind",
                    "kind": "Text",
                    "regex": str(NODE_KIND_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {
                    "name": "label",
                    "kind": "Text",
                    "optional": True,
                    "max_length": 32,
                },
                {
                    "name": "branch",
                    "kind": "Boolean",
                    "default_value": True,
                    "optional": True,
                },
                {
                    "name": "default_filter",
                    "kind": "Text",
                    "description": "Default filter used to search for a node in addition to its ID.",
                    "optional": True,
                },
                {
                    "name": "order_by",
                    "kind": "List",
                    "description": "List of attributes to use to order the results by default",
                    "optional": True,
                },
                {
                    "name": "display_labels",
                    "kind": "List",
                    "description": "List of attributes to use to generate the display label",
                    "optional": True,
                },
                {"name": "description", "kind": "Text", "optional": True, "max_length": DEFAULT_DESCRIPTION_LENGTH},
                {
                    "name": "used_by",
                    "kind": "List",
                    "description": "List of Nodes that are referencing this Generic",
                    "optional": True,
                },
            ],
            "relationships": [
                {
                    "name": "attributes",
                    "peer": "AttributeSchema",
                    "identifier": "schema__node__attributes",
                    "cardinality": "many",
                    "branch": True,
                    "optional": True,
                },
                {
                    "name": "relationships",
                    "peer": "RelationshipSchema",
                    "identifier": "schema__node__relationships",
                    "cardinality": "many",
                    "branch": True,
                    "optional": True,
                },
            ],
        },
        {
            "name": "group_schema",
            "kind": "GroupSchema",
            "branch": True,
            "default_filter": "name__value",
            "display_labels": ["name__value"],
            "attributes": [
                {
                    "name": "name",
                    "kind": "Text",
                    "unique": True,
                    "regex": str(NODE_NAME_REGEX),
                    "min_length": DEFAULT_NAME_MIN_LENGTH,
                    "max_length": DEFAULT_NAME_MAX_LENGTH,
                },
                {
                    "name": "kind",
                    "kind": "Text",
                    "regex": str(NODE_KIND_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {"name": "description", "kind": "Text", "optional": True, "max_length": DEFAULT_DESCRIPTION_LENGTH},
            ],
        },
    ]
}

core_models = {
    "groups": [],
    "generics": [
        {
            "name": "data_owner",
            "kind": "DataOwner",  # Account, Group, Script ?
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "data_source",
            "description": "Any Entities that stores or produces data.",
            "kind": "DataSource",  # Repository, Account ...
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
    ],
    "nodes": [
        {
            "name": "criticality",
            "kind": "Criticality",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "level", "kind": "Number", "enum": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "tag",
            "kind": "Tag",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "organization",
            "kind": "Organization",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "account",
            "kind": "Account",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": True,
            "inherit_from": ["DataOwner", "DataSource"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "password", "kind": "HashedPassword", "unique": False},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
                {
                    "name": "type",
                    "kind": "Text",
                    "default_value": "User",
                    "enum": ["User", "Script", "Bot", "Git"],
                },
                {
                    "name": "role",
                    "kind": "Text",
                    "default_value": "read-only",
                    "enum": ["admin", "read-only", "read-write"],
                },
            ],
            "relationships": [
                {"name": "tokens", "peer": "AccountToken", "optional": True, "cardinality": "many"},
                {"name": "groups", "peer": "Group", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "account_token",
            "kind": "AccountToken",
            "default_filter": "token__value",
            "display_labels": ["token__value"],
            "branch": True,
            "attributes": [
                {"name": "token", "kind": "Text", "unique": True},
                {"name": "expiration", "kind": "DateTime", "optional": True},
            ],
            "relationships": [
                {"name": "account", "peer": "Account", "optional": False, "cardinality": "one"},
            ],
        },
        {
            "name": "refresh_token",
            "kind": "RefreshToken",
            "display_labels": [],
            "branch": True,
            "attributes": [
                {"name": "expiration", "kind": "DateTime", "optional": False},
            ],
            "relationships": [
                {"name": "account", "peer": "Account", "optional": False, "cardinality": "one"},
            ],
        },
        {
            "name": "group",
            "kind": "Group",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "inherit_from": ["DataOwner"],
            "display_labels": ["label__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "members", "peer": "Account", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "status",
            "kind": "Status",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "role",
            "kind": "Role",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "location",
            "kind": "Location",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "type", "kind": "Text"},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "repository",
            "kind": "Repository",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "inherit_from": ["DataOwner", "DataSource"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "location", "kind": "Text"},
                # {"name": "type", "kind": "Text", "default_value": "LOCAL", "enum" },
                {"name": "default_branch", "kind": "Text", "default_value": "main"},
                {"name": "commit", "kind": "Text", "optional": True},
                {"name": "username", "kind": "Text", "optional": True},
                {"name": "password", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "account", "peer": "Account", "kind": "Attribute", "optional": True, "cardinality": "one"},
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
                {
                    "name": "rfiles",
                    "peer": "RFile",
                    "identifier": "repository__rfile",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "queries",
                    "peer": "GraphQLQuery",
                    "identifier": "graphql_query__repository",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "checks",
                    "peer": "Check",
                    "identifier": "check__repository",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "transform_python",
                    "peer": "TransformPython",
                    "identifier": "repository__transform_python",
                    "optional": True,
                    "cardinality": "many",
                },
            ],
        },
        {
            "name": "rfile",
            "kind": "RFile",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "template_path", "kind": "Text"},
            ],
            "relationships": [
                {
                    "name": "template_repository",
                    "peer": "Repository",
                    "kind": "Attribute",
                    "identifier": "repository__rfile",
                    "cardinality": "one",
                    "optional": False,
                },
                {
                    "name": "query",
                    "peer": "GraphQLQuery",
                    "identifier": "graphql_query__rfile",
                    "kind": "Attribute",
                    "cardinality": "one",
                    "optional": False,
                },
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "check",
            "kind": "Check",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "file_path", "kind": "Text"},
                {"name": "class_name", "kind": "Text"},
                {"name": "timeout", "kind": "Number", "default_value": 10},
                {"name": "rebase", "kind": "Boolean", "default_value": False},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "Repository",
                    "kind": "Attribute",
                    "cardinality": "one",
                    "identifier": "check__repository",
                    "optional": False,
                },
                {
                    "name": "query",
                    "peer": "GraphQLQuery",
                    "kind": "Attribute",
                    "identifier": "check__graphql_query",
                    "cardinality": "one",
                    "optional": True,
                },
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "transform_python",
            "kind": "TransformPython",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "file_path", "kind": "Text"},
                {"name": "class_name", "kind": "Text"},
                {"name": "url", "kind": "Text"},
                {"name": "timeout", "kind": "Number", "default_value": 10},
                {"name": "rebase", "kind": "Boolean", "default_value": False},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "Repository",
                    "kind": "Attribute",
                    "cardinality": "one",
                    "identifier": "repository__transform_python",
                    "optional": False,
                },
                {
                    "name": "query",
                    "peer": "GraphQLQuery",
                    "kind": "Attribute",
                    "identifier": "graphql_query__transform_python",
                    "cardinality": "one",
                    "optional": True,
                },
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "graphql_query",
            "kind": "GraphQLQuery",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "query", "kind": "TextArea"},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "Repository",
                    "kind": "Attribute",
                    "identifier": "graphql_query__repository",
                    "cardinality": "one",
                    "optional": True,
                },
                {"name": "tags", "peer": "Tag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
    ],
}
