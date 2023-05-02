from __future__ import annotations

import copy
import keyword
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Extra, Field, root_validator, validator
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.relationship import Relationship
from infrahub.types import ATTRIBUTE_TYPES
from infrahub.utils import BaseEnum, duplicates

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


# pylint: disable=no-self-argument,redefined-builtin,too-many-lines

ATTRIBUTE_KIND_LABELS = list(ATTRIBUTE_TYPES.keys())

RELATIONSHIP_KINDS = ["Generic", "Attribute", "Component", "Parent"]
RELATIONSHIPS_MAPPING = {"Relationship": Relationship}

NODE_KIND_REGEX = r"^[A-Z][a-zA-Z0-9]+$"
NODE_NAME_REGEX = r"^[a-z0-9\_]+$"


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


class FilterSchema(BaseSchemaModel):
    name: str
    kind: FilterSchemaKind
    enum: Optional[List]
    object_kind: Optional[str]
    description: Optional[str]

    _sort_by: List[str] = ["name"]


class AttributeSchema(BaseSchemaModel):
    id: Optional[str]
    name: str
    kind: str
    label: Optional[str]
    description: Optional[str]
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

    async def get_query_filter(self, session: AsyncSession, *args, **kwargs):  # pylint: disable=unused-argument
        return self.get_class().get_query_filter(*args, **kwargs)


class RelationshipSchema(BaseSchemaModel):
    id: Optional[str]
    name: str
    peer: str
    kind: RelationshipKind = RelationshipKind.GENERIC
    label: Optional[str]
    description: Optional[str]
    identifier: Optional[str]
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

    async def get_peer_schema(self):
        return registry.get_schema(name=self.peer)

    async def get_query_filter(
        self,
        session: AsyncSession,
        name: Optional[str] = None,  # pylint: disable=unused-argument
        filters: Optional[dict] = None,
        branch: Branch = None,
        rels_offset: int = 0,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
    ) -> Tuple[List[str], Dict, int]:
        query_filters = []
        query_params = {}
        nbr_rels = 0

        prefix = param_prefix or f"rel_{self.name}"

        if not filters:
            return query_filters, query_params, nbr_rels

        peer_schema = await self.get_peer_schema()

        query_params[f"{prefix}_rel_name"] = self.identifier

        rel_type = self.get_class().rel_type

        if "id" in filters.keys():
            query_filter = ""
            if include_match:
                query_filter += "MATCH (n)"

            query_filter += (
                "-[r%s:%s]-(Relationship { name: $%s_rel_name })-[r%s:%s]-(p:Node { uuid: $%s_peer_id })"
                % (rels_offset + 1, rel_type, prefix, rels_offset + 2, rel_type, prefix)
            )

            query_filters.append(query_filter)
            query_params[f"{prefix}_peer_id"] = filters["id"]

        # -------------------------------------------------------------------
        # Check if any of the filters are matching an existing field
        # -------------------------------------------------------------------
        max_field_nbr_rels = 0

        for field_name in peer_schema.valid_input_names:
            query_filter = ""

            attr_filters = {
                key.replace(f"{field_name}__", ""): value
                for key, value in filters.items()
                if key.startswith(f"{field_name}__")
            }
            if not attr_filters:
                continue

            # remote_attr = self.node.__fields__[key]

            if include_match:
                query_filter += "MATCH (n)"

            # TODO Validate if filters are valid
            query_filter += "-[r%s:%s]-(rl:Relationship { name: $%s_rel_name })-[r%s:%s]-(p:Node)" % (
                rels_offset + 1,
                rel_type,
                prefix,
                rels_offset + 2,
                rel_type,
            )

            field = peer_schema.get_field(field_name)

            field_filter, field_params, field_nbr_rels = await field.get_query_filter(
                session=session,
                name=field_name,
                filters=attr_filters,
                branch=branch,
                rels_offset=2,
                include_match=False,
                param_prefix=prefix if param_prefix else None,
            )

            if field_nbr_rels > max_field_nbr_rels:
                max_field_nbr_rels = field_nbr_rels

            for filter in field_filter:
                query_filters.append(query_filter + filter)
                query_params.update(field_params)

        nbr_rels = 2 + max_field_nbr_rels
        return query_filters, query_params, nbr_rels


NODE_METADATA_ATTRIBUTES = ["_source", "_owner"]


class BaseNodeSchema(BaseSchemaModel):
    id: Optional[str]
    name: str
    kind: str
    description: Optional[str]
    default_filter: Optional[str]
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

    @validator("attributes")
    def set_attribute_order_weight(cls, attributes: List[AttributeSchema]) -> List[AttributeSchema]:
        weights = [attribute.order_weight for attribute in attributes]
        if None not in weights:
            # If the weights are already set they are coming from the
            # database and can be used as is.
            return attributes
        ordered = []
        for index, attribute in enumerate(attributes):
            attribute.order_weight = attribute.order_weight or index * 1000 + 1000
            ordered.append(attribute)

        return ordered

    @validator("relationships")
    def set_relationship_order_weight(cls, relationships: List[RelationshipSchema]) -> List[RelationshipSchema]:
        weights = [relationship.order_weight for relationship in relationships]
        if None not in weights:
            # If the weights are already set they are coming from the
            # database and can be used as is.
            return relationships
        ordered = []
        for index, relationship in enumerate(relationships):
            relationship.order_weight = relationship.order_weight or index * 1000 + 100000
            ordered.append(relationship)

        return ordered


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

            new_item = copy.deepcopy(item)
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
    name: str
    kind: str
    description: Optional[str]


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
                    "description": "Node name, must be unique and must be a all lowercase.",
                    "unique": True,
                    "regex": str(NODE_NAME_REGEX),
                    "min_length": 3,
                    "max_length": 32,
                },
                {
                    "name": "kind",
                    "kind": "Text",
                    "description": "Node kind, must be unique and must be in CamelCase",
                    "regex": str(NODE_KIND_REGEX),
                    "min_length": 3,
                    "max_length": 32,
                },
                {
                    "name": "label",
                    "kind": "Text",
                    "description": "Human friendly representation of the name/kind",
                    "optional": True,
                    "max_length": 32,
                },
                {
                    "name": "description",
                    "kind": "Text",
                    #  "description": "",
                    "optional": True,
                    "max_length": 128,
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
                {"name": "name", "kind": "Text", "regex": str(NODE_NAME_REGEX), "min_length": 3, "max_length": 32},
                {
                    "name": "kind",
                    "kind": "Text",
                    "enum": ATTRIBUTE_KIND_LABELS,
                    "min_length": 3,
                    "max_length": 32,
                },
                {"name": "enum", "kind": "List", "optional": True},
                {"name": "regex", "kind": "Text", "optional": True},
                {"name": "max_length", "kind": "Number", "optional": True},
                {"name": "min_length", "kind": "Number", "optional": True},
                {"name": "label", "kind": "Text", "optional": True, "max_length": 32},
                {"name": "description", "kind": "Text", "optional": True, "max_length": 128},
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
                {"name": "name", "kind": "Text", "regex": str(NODE_NAME_REGEX), "min_length": 3, "max_length": 32},
                {"name": "peer", "kind": "Text", "regex": str(NODE_KIND_REGEX), "min_length": 3, "max_length": 32},
                {"name": "kind", "kind": "Text", "enum": RELATIONSHIP_KINDS, "default_value": "Generic"},
                {"name": "label", "kind": "Text", "optional": True, "max_length": 32},
                {"name": "description", "kind": "Text", "optional": True, "max_length": 128},
                {"name": "identifier", "kind": "Text", "max_length": 128, "optional": True},
                {"name": "cardinality", "kind": "Text", "enum": ["one", "many"]},
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
                    "min_length": 3,
                    "max_length": 32,
                },
                {"name": "kind", "kind": "Text", "regex": str(NODE_KIND_REGEX), "min_length": 3, "max_length": 32},
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
                    "name": "display_labels",
                    "kind": "List",
                    "description": "List of attributes to use to generate the display label",
                    "optional": True,
                },
                {"name": "description", "kind": "Text", "optional": True, "max_length": 128},
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
                    "min_length": 3,
                    "max_length": 32,
                },
                {"name": "kind", "kind": "Text", "regex": str(NODE_KIND_REGEX), "min_length": 3, "max_length": 32},
                {"name": "description", "kind": "Text", "optional": True, "max_length": 128},
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
            "display_labels": ["label__value"],
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "account",
            "kind": "Account",
            "default_filter": "name__value",
            "display_labels": ["label__value"],
            "branch": True,
            "inherit_from": ["DataOwner", "DataSource"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "label", "kind": "Text", "optional": True},
                {"name": "description", "kind": "Text", "optional": True},
                {
                    "name": "type",
                    "kind": "Text",
                    "default_value": "User",
                    "enum": ["User", "Script", "Bot", "Git"],
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
            "display_labels": ["name__value"],
            "branch": True,
            "attributes": [
                {"name": "token", "kind": "Text", "unique": True},
                {"name": "expiration_date", "kind": "Text", "optional": True},  # Should be date here
            ],
            "relationships": [
                {"name": "account", "peer": "Account", "optional": False, "cardinality": "one"},
            ],
        },
        {
            "name": "group",
            "kind": "Group",
            "default_filter": "name__value",
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
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "description", "kind": "Text", "optional": True},
                {"name": "type", "kind": "Text"},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "repository",
            "kind": "Repository",
            "default_filter": "name__value",
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
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
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
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "check",
            "kind": "Check",
            "default_filter": "name__value",
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
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "transform_python",
            "kind": "TransformPython",
            "default_filter": "name__value",
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
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "graphql_query",
            "kind": "GraphQLQuery",
            "default_filter": "name__value",
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
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
    ],
}
