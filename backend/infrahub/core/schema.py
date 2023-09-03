from __future__ import annotations

import copy
import enum
import keyword
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Extra, Field, root_validator, validator

from infrahub.core import registry
from infrahub.core.constants import (
    AccountRole,
    AccountType,
    ArtifactStatus,
    BranchSupportType,
    ContentType,
    CriticalityLevel,
    FilterSchemaKind,
    RelationshipCardinality,
    RelationshipKind,
    Severity,
    ValidatorConclusion,
    ValidatorState,
)
from infrahub.core.query import QueryNode, QueryRel
from infrahub.core.relationship import Relationship
from infrahub.types import ATTRIBUTE_TYPES
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
NODE_NAME_REGEX = r""

DEFAULT_NAME_MIN_LENGTH = 2
DEFAULT_NAME_MAX_LENGTH = 32
DEFAULT_KIND_MIN_LENGTH = 3
DEFAULT_KIND_MAX_LENGTH = 32
DEFAULT_DESCRIPTION_LENGTH = 128
DEFAULT_REL_IDENTIFIER_LENGTH = 128


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
            elif isinstance(value, dict):
                values.append(frozenset(value.items()))
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
    enum: Optional[List] = None
    object_kind: Optional[str] = None
    description: Optional[str] = None

    _sort_by: List[str] = ["name"]


class AttributeSchema(BaseSchemaModel):
    id: Optional[str]
    name: str = Field(regex=NODE_NAME_REGEX, min_length=DEFAULT_NAME_MIN_LENGTH, max_length=DEFAULT_NAME_MAX_LENGTH)
    kind: str  # AttributeKind
    namespace: str = "Attribute"
    label: Optional[str]
    description: Optional[str] = Field(max_length=DEFAULT_DESCRIPTION_LENGTH)
    default_value: Optional[Any]
    enum: Optional[List]
    regex: Optional[str]
    max_length: Optional[int]
    min_length: Optional[int]
    inherited: bool = False
    unique: bool = False
    branch: Optional[BranchSupportType]
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
    branch: Optional[BranchSupportType]
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

        if filter_name == "ids":
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type]),
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
    namespace: str = Field(
        regex=NODE_KIND_REGEX, min_length=DEFAULT_KIND_MIN_LENGTH, max_length=DEFAULT_KIND_MAX_LENGTH
    )
    description: Optional[str] = Field(max_length=DEFAULT_DESCRIPTION_LENGTH)
    default_filter: Optional[str]
    branch: BranchSupportType = BranchSupportType.AWARE
    order_by: Optional[List[str]]
    display_labels: Optional[List[str]]
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)

    _exclude_from_hash: List[str] = ["id", "attributes", "relationships"]
    _sort_by: List[str] = ["name"]

    @property
    def kind(self) -> str:
        if self.namespace == "Attribute":
            return self.name
        return self.namespace + self.name

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

    label: Optional[str]
    used_by: List[str] = Field(default_factory=list)


class NodeSchema(BaseNodeSchema):
    label: Optional[str]
    inherit_from: Optional[List[str]] = Field(default_factory=list)
    groups: Optional[List[str]] = Field(default_factory=list)
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
            if not rel.get("identifier", None) and values.get("namespace") and rel.get("peer"):
                identifier = "__".join(sorted([f'{values.get("namespace")}{values.get("name")}', rel.get("peer")]))
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
            "name": "Node",
            "namespace": "Schema",
            "branch": BranchSupportType.AWARE.value,
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
                    "name": "namespace",
                    "kind": "Text",
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
                    "kind": "Text",
                    "enum": BranchSupportType.available_types(),
                    "default_value": BranchSupportType.AWARE.value,
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
                    "peer": "SchemaAttribute",
                    "kind": "Component",
                    "identifier": "schema__node__attributes",
                    "cardinality": "many",
                    "branch": BranchSupportType.AWARE.value,
                    "optional": True,
                },
                {
                    "name": "relationships",
                    "peer": "SchemaRelationship",
                    "kind": "Component",
                    "identifier": "schema__node__relationships",
                    "cardinality": "many",
                    "branch": BranchSupportType.AWARE.value,
                    "optional": True,
                },
            ],
        },
        {
            "name": "Attribute",
            "namespace": "Schema",
            "branch": BranchSupportType.AWARE.value,
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
                    "name": "namespace",
                    "kind": "Text",
                    "regex": str(NODE_KIND_REGEX),
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                    "optional": True,
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
                {
                    "name": "branch",
                    "kind": "Text",
                    "enum": BranchSupportType.available_types(),
                    "optional": True,
                },
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
                    "peer": "SchemaNode",
                    "kind": "Parent",
                    "identifier": "schema__node__attributes",
                    "cardinality": "one",
                    "branch": BranchSupportType.AWARE.value,
                    "optional": False,
                }
            ],
        },
        {
            "name": "Relationship",
            "namespace": "Schema",
            "branch": BranchSupportType.AWARE.value,
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
                {
                    "name": "kind",
                    "kind": "Text",
                    "enum": RelationshipKind.available_types(),
                    "default_value": "Generic",
                },
                {"name": "label", "kind": "Text", "optional": True, "max_length": DEFAULT_NAME_MAX_LENGTH},
                {"name": "description", "kind": "Text", "optional": True, "max_length": DEFAULT_DESCRIPTION_LENGTH},
                {"name": "identifier", "kind": "Text", "max_length": DEFAULT_REL_IDENTIFIER_LENGTH, "optional": True},
                {"name": "cardinality", "kind": "Text", "enum": RelationshipCardinality.available_types()},
                {"name": "order_weight", "kind": "Number", "optional": True},
                {
                    "name": "optional",
                    "kind": "Boolean",
                    "default_value": False,
                    "optional": True,
                },
                {
                    "name": "branch",
                    "kind": "Text",
                    "enum": BranchSupportType.available_types(),
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
                    "peer": "SchemaNode",
                    "kind": "Parent",
                    "identifier": "schema__node__relationships",
                    "cardinality": "one",
                    "branch": BranchSupportType.AWARE.value,
                    "optional": False,
                }
            ],
        },
        {
            "name": "Generic",
            "namespace": "Schema",
            "branch": BranchSupportType.AWARE.value,
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
                    "name": "namespace",
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
                    "kind": "Text",
                    "enum": BranchSupportType.available_types(),
                    "default_value": BranchSupportType.AWARE.value,
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
                    "peer": "SchemaAttribute",
                    "identifier": "schema__node__attributes",
                    "cardinality": "many",
                    "branch": BranchSupportType.AWARE.value,
                    "optional": True,
                },
                {
                    "name": "relationships",
                    "peer": "SchemaRelationship",
                    "identifier": "schema__node__relationships",
                    "cardinality": "many",
                    "branch": BranchSupportType.AWARE.value,
                    "optional": True,
                },
            ],
        },
        {
            "name": "Group",
            "namespace": "Schema",
            "branch": BranchSupportType.AWARE.value,
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
            "name": "Node",
            "namespace": "Core",
            "description": "Base Node in Infrahub.",
            "label": "Node",
        },
        {
            "name": "Owner",
            "namespace": "Lineage",
            "description": "Any Entities that is responsible for some data.",
            "label": "Owner",
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Source",
            "namespace": "Lineage",
            "description": "Any Entities that stores or produces data.",
            "label": "Source",
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Comment",
            "namespace": "Core",
            "description": "A comment on a Proposed Change",
            "label": "Comment",
            "display_labels": ["text__value"],
            "order_by": ["created_at__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "text", "kind": "TextArea", "unique": False, "optional": False},
                {"name": "created_at", "kind": "DateTime", "optional": True},
            ],
            "relationships": [
                {
                    "name": "created_by",
                    "peer": "CoreAccount",
                    "optional": True,
                    "branch": BranchSupportType.AGNOSTIC.value,
                    "cardinality": "one",
                },
            ],
        },
        {
            "name": "Thread",
            "namespace": "Core",
            "description": "A thread on a Proposed Change",
            "label": "Thread",
            "order_by": ["created_at__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "resolved", "kind": "Boolean", "default_value": False},
                {"name": "created_at", "kind": "DateTime", "optional": True},
            ],
            "relationships": [
                {
                    "name": "change",
                    "peer": "CoreProposedChange",
                    "identifier": "proposedchange__thread",
                    "kind": "Parent",
                    "optional": False,
                    "cardinality": "one",
                },
                {
                    "name": "comments",
                    "peer": "CoreThreadComment",
                    "identifier": "thread__threadcomment",
                    "kind": "Component",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "created_by",
                    "peer": "CoreAccount",
                    "optional": True,
                    "branch": BranchSupportType.AGNOSTIC.value,
                    "cardinality": "one",
                },
            ],
        },
        {
            "name": "Group",
            "namespace": "Core",
            "description": "Generic Group Object.",
            "label": "Group",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {
                    "name": "members",
                    "peer": "CoreNode",
                    "optional": True,
                    "identifier": "group_member",
                    "cardinality": "many",
                },
                {
                    "name": "subscribers",
                    "peer": "CoreNode",
                    "optional": True,
                    "identifier": "group_subscriber",
                    "cardinality": "many",
                },
            ],
        },
        {
            "name": "Validator",
            "namespace": "Core",
            "description": "",
            "label": "Validator",
            "order_by": ["started_at__value"],
            "display_labels": ["state__value", "conclusion__value", "started_at__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {
                    "name": "state",
                    "kind": "Text",
                    "enum": ValidatorState.available_types(),
                    "default_value": ValidatorState.QUEUED.value,
                },
                {
                    "name": "conclusion",
                    "kind": "Text",
                    "enum": ValidatorConclusion.available_types(),
                    "default_value": ValidatorConclusion.UNKNOWN.value,
                },
                {"name": "completed_at", "kind": "DateTime", "optional": True},
                {"name": "started_at", "kind": "DateTime", "optional": True},
            ],
            "relationships": [
                {
                    "name": "proposed_change",
                    "peer": "CoreProposedChange",
                    "kind": "Parent",
                    "optional": False,
                    "cardinality": "one",
                    "identifier": "proposed_change__validator",
                },
                {
                    "name": "checks",
                    "peer": "CoreCheck",
                    "kind": "Component",
                    "optional": True,
                    "cardinality": "many",
                    "identifier": "validator__check",
                },
            ],
        },
        {
            "name": "Check",
            "namespace": "Core",
            "description": "",
            "label": "Check",
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "name", "kind": "Text", "optional": True},
                {"name": "origin", "kind": "Text", "optional": False},
                {
                    "name": "kind",
                    "kind": "Text",
                    "regex": "^[A-Z][a-zA-Z0-9]+$",
                    "optional": False,
                    "min_length": DEFAULT_KIND_MIN_LENGTH,
                    "max_length": DEFAULT_KIND_MAX_LENGTH,
                },
                {"name": "message", "kind": "TextArea", "optional": True},
                {
                    "name": "conclusion",
                    "kind": "Text",
                    "enum": ValidatorConclusion.available_types(),
                    "default_value": ValidatorConclusion.UNKNOWN.value,
                    "optional": True,
                },
                {
                    "name": "severity",
                    "kind": "Text",
                    "enum": Severity.available_types(),
                    "default_value": Severity.INFO.value,
                    "optional": True,
                },
                {"name": "created_at", "kind": "DateTime", "optional": True},
            ],
            "relationships": [
                {
                    "name": "validator",
                    "peer": "CoreValidator",
                    "identifier": "validator__check",
                    "kind": "Parent",
                    "optional": False,
                    "cardinality": "one",
                },
            ],
        },
        {
            "name": "Transformation",
            "namespace": "Core",
            "description": "Generic Transformation Object.",
            "label": "Transformation",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "timeout", "kind": "Number", "default_value": 10},
                {"name": "rebase", "kind": "Boolean", "default_value": False},
            ],
            "relationships": [
                {
                    "name": "query",
                    "peer": "CoreGraphQLQuery",
                    "identifier": "graphql_query__transformation",
                    "kind": "Attribute",
                    "cardinality": "one",
                    "optional": False,
                },
                {
                    "name": "repository",
                    "peer": "CoreRepository",
                    "kind": "Attribute",
                    "cardinality": "one",
                    "identifier": "repository__transformation",
                    "optional": False,
                },
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "ArtifactTarget",
            "namespace": "Core",
            "description": "Extend a node to be associated with artifacts",
            "label": "Artifact Target",
            "relationships": [
                {
                    "name": "artifacts",
                    "peer": "CoreArtifact",
                    "optional": True,
                    "cardinality": "many",
                    "kind": "Generic",
                    "identifier": "artifact__node",
                },
            ],
        },
    ],
    "nodes": [
        {
            "name": "StandardGroup",
            "namespace": "Core",
            "description": "Group of nodes of any kind.",
            "label": "StandardGroup",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "inherit_from": ["CoreGroup"],
        },
        {
            "name": "Criticality",
            "namespace": "Builtin",
            "description": "Level of criticality expressed from 1 to 10.",
            "label": "Criticality",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "level", "kind": "Number", "enum": CriticalityLevel.available_types()},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Tag",
            "namespace": "Builtin",
            "description": "Standard Tag object to attached to other objects to provide some context.",
            "label": "Tag",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Organization",
            "namespace": "Core",
            "description": "An organization represent a legal entity, a company.",
            "label": "Organization",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "Account",
            "namespace": "Core",
            "description": "User Account for Infrahub",
            "label": "Account",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": BranchSupportType.AWARE.value,
            "inherit_from": ["LineageOwner", "LineageSource"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "password", "kind": "HashedPassword", "unique": False},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
                {
                    "name": "type",
                    "kind": "Text",
                    "default_value": AccountType.USER.value,
                    "enum": AccountType.available_types(),
                },
                {
                    "name": "role",
                    "kind": "Text",
                    "default_value": AccountRole.READ_ONLY.value,
                    "enum": AccountRole.available_types(),
                },
            ],
            "relationships": [
                {"name": "tokens", "peer": "InternalAccountToken", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "AccountToken",
            "namespace": "Internal",
            "description": "Token for User Account",
            "label": "Account Token",
            "default_filter": "token__value",
            "display_labels": ["token__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "name", "kind": "Text", "optional": True},
                {"name": "token", "kind": "Text", "unique": True},
                {"name": "expiration", "kind": "DateTime", "optional": True},
            ],
            "relationships": [
                {
                    "name": "account",
                    "peer": "CoreAccount",
                    "optional": False,
                    "cardinality": "one",
                    "branch": BranchSupportType.AGNOSTIC.value,
                },
            ],
        },
        {
            "name": "RefreshToken",
            "namespace": "Internal",
            "description": "Refresh Token",
            "label": "Refresh Token",
            "display_labels": [],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "expiration", "kind": "DateTime", "optional": False},
            ],
            "relationships": [
                {
                    "name": "account",
                    "peer": "CoreAccount",
                    "optional": False,
                    "cardinality": "one",
                    "branch": BranchSupportType.AGNOSTIC.value,
                },
            ],
        },
        {
            "name": "ProposedChange",
            "namespace": "Core",
            "description": "Metadata related to a proposed change",
            "label": "Proposed Change",
            "default_filter": "name__value",
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "name", "kind": "Text", "optional": False},
                {"name": "source_branch", "kind": "Text", "optional": False},
                {"name": "destination_branch", "kind": "Text", "optional": False},
            ],
            "relationships": [
                {
                    "name": "approved_by",
                    "peer": "CoreAccount",
                    "optional": True,
                    "cardinality": "many",
                    "kind": "Attribute",
                    "branch": BranchSupportType.AGNOSTIC.value,
                    "identifier": "coreaccount__proposedchange_approved_by",
                },
                {
                    "name": "reviewers",
                    "peer": "CoreAccount",
                    "optional": True,
                    "kind": "Attribute",
                    "cardinality": "many",
                    "branch": BranchSupportType.AGNOSTIC.value,
                    "identifier": "coreaccount__proposedchange_reviewed_by",
                },
                {
                    "name": "created_by",
                    "peer": "CoreAccount",
                    "optional": True,
                    "cardinality": "one",
                    "branch": BranchSupportType.AGNOSTIC.value,
                    "identifier": "coreaccount__proposedchange_created_by",
                },
                {
                    "name": "comments",
                    "peer": "CoreChangeComment",
                    "kind": "Component",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "threads",
                    "peer": "CoreThread",
                    "identifier": "proposedchange__thread",
                    "kind": "Component",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "validations",
                    "peer": "CoreValidator",
                    "kind": "Component",
                    "identifier": "proposed_change__validator",
                    "optional": True,
                    "cardinality": "many",
                },
            ],
        },
        {
            "name": "ChangeThread",
            "namespace": "Core",
            "description": "A thread on proposed change",
            "label": "Change Thread",
            "branch": BranchSupportType.AGNOSTIC.value,
            "inherit_from": ["CoreThread"],
            "attributes": [],
            "relationships": [],
        },
        {
            "name": "FileThread",
            "namespace": "Core",
            "description": "A thread related to a file on a proposed change",
            "label": "Thread - File",
            "branch": BranchSupportType.AGNOSTIC.value,
            "inherit_from": ["CoreThread"],
            "attributes": [
                {"name": "file", "kind": "Text", "optional": True},
                {"name": "commit", "kind": "Text", "optional": True},
                {"name": "line_number", "kind": "Number", "optional": True},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "CoreRepository",
                    "optional": False,
                    "cardinality": "one",
                    "branch": BranchSupportType.AGNOSTIC.value,
                },
            ],
        },
        {
            "name": "ArtifactThread",
            "namespace": "Core",
            "description": "A thread related to an artifact on a proposed change",
            "label": "Thread - Artifact",
            "branch": BranchSupportType.AGNOSTIC.value,
            "inherit_from": ["CoreThread"],
            "attributes": [
                {"name": "artifact_id", "kind": "Text", "optional": True},
                {"name": "storage_id", "kind": "Text", "optional": True},
                {"name": "line_number", "kind": "Number", "optional": True},
            ],
            "relationships": [],
        },
        {
            "name": "ObjectThread",
            "namespace": "Core",
            "description": "A thread related to an object on a proposed change",
            "label": "Thread - Object",
            "branch": BranchSupportType.AGNOSTIC.value,
            "inherit_from": ["CoreThread"],
            "attributes": [
                {"name": "object_path", "kind": "Text", "optional": False},
            ],
            "relationships": [],
        },
        {
            "name": "ChangeComment",
            "namespace": "Core",
            "description": "A comment on proposed change",
            "label": "Change Comment",
            "default_filter": "text__value",
            "display_labels": ["text__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "inherit_from": ["CoreComment"],
            "relationships": [
                {
                    "name": "change",
                    "kind": "Parent",
                    "peer": "CoreProposedChange",
                    "cardinality": "one",
                    "optional": False,
                },
            ],
        },
        {
            "name": "ThreadComment",
            "namespace": "Core",
            "description": "A comment on thread within a Proposed Change",
            "label": "Thread Comment",
            "default_filter": "text__value",
            "display_labels": ["text__value"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "inherit_from": ["CoreComment"],
            "attributes": [],
            "relationships": [
                {
                    "name": "thread",
                    "peer": "CoreThread",
                    "kind": "Parent",
                    "identifier": "thread__threadcomment",
                    "cardinality": "one",
                    "optional": False,
                },
            ],
        },
        {
            "name": "Status",
            "namespace": "Builtin",
            "description": "Represent the status of an object: active, maintenance",
            "label": "Status",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Role",
            "namespace": "Builtin",
            "description": "Represent the role of an object",
            "label": "Role",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["label__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Location",
            "namespace": "Builtin",
            "description": "A location represent a physical element: a building, a site, a city",
            "label": "Location",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "type", "kind": "Text"},
            ],
            "relationships": [
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "Repository",
            "namespace": "Core",
            "description": "A Git Repository integrated with Infrahub",
            "label": "Repository",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "inherit_from": ["LineageOwner", "LineageSource"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "location", "kind": "Text", "unique": True},
                {"name": "default_branch", "kind": "Text", "default_value": "main"},
                {"name": "commit", "kind": "Text", "optional": True, "branch": BranchSupportType.LOCAL.value},
                {"name": "username", "kind": "Text", "optional": True},
                {"name": "password", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "account", "peer": "CoreAccount", "kind": "Attribute", "optional": True, "cardinality": "one"},
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
                {
                    "name": "transformations",
                    "peer": "CoreTransformation",
                    "identifier": "repository__transformation",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "queries",
                    "peer": "CoreGraphQLQuery",
                    "identifier": "graphql_query__repository",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "checks",
                    "peer": "CoreCheckDefinition",
                    "identifier": "check_definition__repository",
                    "optional": True,
                    "cardinality": "many",
                },
            ],
        },
        {
            "name": "RFile",
            "namespace": "Core",
            "description": "A file rendered from a Jinja2 template",
            "label": "RFile",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "inherit_from": ["CoreTransformation"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "template_path", "kind": "Text"},
            ],
        },
        {
            "name": "DataCheck",
            "namespace": "Core",
            "description": "A check related to some Data",
            "label": "Data Check",
            "inherit_from": ["CoreCheck"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "paths", "kind": "List"},
            ],
        },
        {
            "name": "StandardCheck",
            "namespace": "Core",
            "description": "A standard check",
            "label": "Standard Check",
            "inherit_from": ["CoreCheck"],
            "branch": BranchSupportType.AGNOSTIC.value,
        },
        {
            "name": "SchemaCheck",
            "namespace": "Core",
            "description": "A check related to the schema",
            "label": "Schema Check",
            "inherit_from": ["CoreCheck"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "paths", "kind": "List"},
            ],
        },
        {
            "name": "FileCheck",
            "namespace": "Core",
            "description": "A check related to a file in a Git Repository",
            "label": "File Check",
            "inherit_from": ["CoreCheck"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "files", "kind": "List", "optional": True},
                {"name": "commit", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "ArtifactCheck",
            "namespace": "Core",
            "description": "A check related to an artifact",
            "label": "Artifact Check",
            "inherit_from": ["CoreCheck"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "attributes": [
                {"name": "artifact_id", "kind": "Text", "optional": True},
                {"name": "storage_id", "kind": "Text", "optional": True},
                {"name": "line_number", "kind": "Number", "optional": True},
            ],
        },
        {
            "name": "DataValidator",
            "namespace": "Core",
            "description": "A check to validate the data integrity between two branches",
            "label": "Data Validator",
            "inherit_from": ["CoreValidator"],
            "branch": BranchSupportType.AGNOSTIC.value,
        },
        {
            "name": "RepositoryValidator",
            "namespace": "Core",
            "description": "A Validator related to a specific repository",
            "label": "Repository Validator",
            "inherit_from": ["CoreValidator"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "relationships": [
                {
                    "name": "repository",
                    "peer": "CoreRepository",
                    "kind": "Attribute",
                    "optional": False,
                    "cardinality": "one",
                    "branch": BranchSupportType.AGNOSTIC.value,
                },
            ],
        },
        {
            "name": "SchemaValidator",
            "namespace": "Core",
            "description": "A validator related to the schema",
            "label": "Schema Validator",
            "inherit_from": ["CoreValidator"],
            "branch": BranchSupportType.AGNOSTIC.value,
        },
        {
            "name": "ArtifactValidator",
            "namespace": "Core",
            "description": "A validator related to the artifacts",
            "label": "Artifact Validator",
            "inherit_from": ["CoreValidator"],
            "branch": BranchSupportType.AGNOSTIC.value,
            "relationships": [
                {
                    "name": "definition",
                    "peer": "CoreArtifactDefinition",
                    "kind": "Attribute",
                    "optional": False,
                    "cardinality": "one",
                    "branch": BranchSupportType.AGNOSTIC.value,
                },
            ],
        },
        {
            "name": "CheckDefinition",
            "namespace": "Core",
            "label": "Check Definition",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "file_path", "kind": "Text"},
                {"name": "class_name", "kind": "Text"},
                {"name": "timeout", "kind": "Number", "default_value": 10},
                {"name": "rebase", "kind": "Boolean", "default_value": False},
                {"name": "parameters", "kind": "JSON", "optional": True},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "CoreRepository",
                    "kind": "Attribute",
                    "cardinality": "one",
                    "identifier": "check_definition__repository",
                    "optional": False,
                },
                {
                    "name": "query",
                    "peer": "CoreGraphQLQuery",
                    "kind": "Attribute",
                    "identifier": "check_definition__graphql_query",
                    "cardinality": "one",
                    "optional": True,
                },
                {
                    "name": "targets",
                    "peer": "CoreGroup",
                    "kind": "Attribute",
                    "identifier": "check_definition___group",
                    "cardinality": "one",
                    "optional": True,
                },
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "TransformPython",
            "namespace": "Core",
            "description": "A transform function written in Python",
            "label": "Transform Python",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "inherit_from": ["CoreTransformation"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "file_path", "kind": "Text"},
                {"name": "class_name", "kind": "Text"},
                {"name": "url", "kind": "Text", "unique": True},
            ],
        },
        {
            "name": "GraphQLQuery",
            "namespace": "Core",
            "description": "A pre-defined GraphQL Query",
            "label": "GraphQL Query",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "query", "kind": "TextArea"},
                {"name": "variables", "kind": "JSON", "description": "variables in use in the query", "optional": True},
                {
                    "name": "operations",
                    "kind": "List",
                    "description": "Operations in use in the query, valid operations: 'query', 'mutation' or 'subscription'",
                    "optional": True,
                },
                {
                    "name": "models",
                    "kind": "List",
                    "description": "List of models associated with this query",
                    "optional": True,
                },
                {
                    "name": "depth",
                    "kind": "Number",
                    "description": "number of nested levels in the query",
                    "optional": True,
                },
                {
                    "name": "height",
                    "kind": "Number",
                    "description": "total number of fields requested in the query",
                    "optional": True,
                },
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "CoreRepository",
                    "kind": "Attribute",
                    "identifier": "graphql_query__repository",
                    "cardinality": "one",
                    "optional": True,
                },
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "Artifact",
            "namespace": "Core",
            "label": "Artifact",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text"},
                {
                    "name": "status",
                    "kind": "Text",
                    "enum": ArtifactStatus.available_types(),
                },
                {
                    "name": "content_type",
                    "kind": "Text",
                    "enum": ContentType.available_types(),
                },
                {"name": "checksum", "kind": "Text", "optional": True},
                {
                    "name": "storage_id",
                    "kind": "Text",
                    "optional": True,
                    "description": "ID of the file in the object store",
                },
                {"name": "parameters", "kind": "JSON", "optional": True},
            ],
            "relationships": [
                {
                    "name": "object",
                    "peer": "CoreNode",
                    "kind": "Attribute",
                    "identifier": "artifact__node",
                    "cardinality": "one",
                    "optional": False,
                },
                {
                    "name": "definition",
                    "peer": "CoreArtifactDefinition",
                    "kind": "Attribute",
                    "identifier": "artifact__artifact_definition",
                    "cardinality": "one",
                    "optional": False,
                },
                {"name": "tags", "peer": "BuiltinTag", "kind": "Attribute", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "ArtifactDefinition",
            "namespace": "Core",
            "label": "Artifact Definition",
            "default_filter": "name__value",
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "branch": BranchSupportType.AWARE.value,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "artifact_name", "kind": "Text"},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "parameters", "kind": "JSON"},
                {
                    "name": "content_type",
                    "kind": "Text",
                    "enum": ContentType.available_types(),
                },
            ],
            "relationships": [
                {
                    "name": "targets",
                    "peer": "CoreGroup",
                    "kind": "Attribute",
                    "identifier": "artifact_definition___group",
                    "cardinality": "one",
                    "optional": False,
                },
                {
                    "name": "transformation",
                    "peer": "CoreTransformation",
                    "kind": "Attribute",
                    "identifier": "artifact_definition___transformation",
                    "cardinality": "one",
                    "optional": False,
                },
            ],
        },
    ],
}
