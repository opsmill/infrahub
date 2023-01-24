from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, root_validator, validator

from infrahub.core import registry
from infrahub.core.attribute import (
    AnyAttribute,
    Boolean,
    Integer,
    ListAttribute,
    String,
)
from infrahub.core.relationship import Relationship
from infrahub.utils import duplicates

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch

ATTRIBUTES_MAPPING = {
    "Any": AnyAttribute,
    "String": String,
    "Integer": Integer,
    "Boolean": Boolean,
    "List": ListAttribute,
}

RELATIONSHIPS_MAPPING = {"Relationship": Relationship}


class AttributeSchema(BaseModel):
    name: str
    kind: str
    label: Optional[str]
    description: Optional[str]
    default_value: Optional[Any]
    inherited: bool = False
    unique: bool = False
    branch: bool = True
    optional: bool = False

    @validator("kind")
    def kind_options(
        cls,
        v,
    ):
        if v not in ATTRIBUTES_MAPPING.keys():
            raise ValueError(f"Only valid Attribute Kind are : {ATTRIBUTES_MAPPING.keys()} ")
        return v

    def get_class(self):
        return ATTRIBUTES_MAPPING.get(self.kind, None)

    async def get_query_filter(self, session: AsyncSession, *args, **kwargs):
        return self.get_class().get_query_filter(*args, **kwargs)


class RelationshipSchema(BaseModel):
    name: str
    peer: str
    label: Optional[str]
    description: Optional[str]
    identifier: Optional[str]
    inherited: bool = False
    cardinality: str = "many"
    branch: bool = True
    optional: bool = True

    @validator("cardinality")
    def cardinality_options(
        cls,
        v,
    ):
        VALID_OPTIONS = ["one", "many"]
        if v not in VALID_OPTIONS:
            raise ValueError(f"Only valid value for cardinality are : {VALID_OPTIONS} ")
        return v

    def get_class(self):
        return Relationship

    async def get_peer_schema(self):
        return registry.get_schema(name=self.peer)

    async def get_query_filter(
        self,
        session: AsyncSession,
        name: str = None,
        filters: dict = None,
        branch: Branch = None,
        rels_offset: int = 0,
        include_match: bool = True,
        param_prefix: str = None,
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
                "-[r%s:%s]-(Relationship { name: $%s_rel_name })-[r%s:%s]-(p:%s { uuid: $peer_node_id })"
                % (
                    rels_offset + 1,
                    rel_type,
                    prefix,
                    rels_offset + 2,
                    rel_type,
                    peer_schema.kind,
                )
            )

            query_filters.append(query_filter)
            query_params["peer_node_id"] = filters["id"]

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
            query_filter += "-[r%s:%s]-(rl:Relationship { name: $%s_rel_name })-[r%s:%s]-(p:%s)" % (
                rels_offset + 1,
                rel_type,
                prefix,
                rels_offset + 2,
                rel_type,
                peer_schema.kind,
            )

            field = peer_schema.get_field(field_name)

            field_filter, field_params, field_nbr_rels = await field.get_query_filter(
                session=session,
                name=field_name,
                filters=attr_filters,
                branch=branch,
                rels_offset=2,
                include_match=False,
            )

            if field_nbr_rels > max_field_nbr_rels:
                max_field_nbr_rels = field_nbr_rels

            for filter in field_filter:
                query_filters.append(query_filter + filter)
                query_params.update(field_params)

        nbr_rels = 2 + max_field_nbr_rels
        return query_filters, query_params, nbr_rels


NODE_METADATA_ATTRIBUTES = ["_source", "_owner"]


class BaseNodeSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)

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
        return [item.name for item in self.attributes if not item.optional and not item.default_value]

    @property
    def mandatory_relationship_names(self) -> List[str]:
        return [item.name for item in self.relationships if not item.optional]

    @property
    def local_attributes(self) -> List[AttributeSchema]:
        return [item for item in self.attributes if not item.inherited]

    @property
    def local_relationships(self) -> List[RelationshipSchema]:
        return [item for item in self.relationships if not item.inherited]


class GenericSchema(BaseNodeSchema):
    """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

    label: Optional[str]


class NodeSchema(BaseNodeSchema):
    label: Optional[str]
    inherit_from: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    branch: bool = True
    default_filter: Optional[str]

    # TODO add validation to ensure that 2 attributes can't have the same name

    @root_validator
    def unique_names(cls, values):
        attr_names = [attr.name for attr in values.get("attributes", [])]
        rel_names = [rel.name for rel in values.get("relationships", [])]

        if names_dup := duplicates(attr_names + rel_names):
            raise ValueError(f"Names of attributes and relationships must be unique : {names_dup}")
        return values

    @root_validator
    def generate_identifier(
        cls,
        values,
    ):
        identifiers = []

        for rel in values.get("relationships", []):
            if not rel.identifier:
                identifier = "__".join(sorted([values.get("kind"), rel.peer]))
                rel.identifier = identifier.lower()

            identifiers.append(rel.identifier)

        if identifier_dup := duplicates(identifiers):
            raise ValueError(f"Identifier of relationships must be unique : {identifier_dup}")
        return values

    def extend_with_interface(self, interface: GenericSchema) -> NodeSchema:
        existing_node_names = self.valid_input_names

        for item in interface.attributes + interface.relationships:
            if item.name in existing_node_names:
                continue

            new_item = copy.deepcopy(item)
            new_item.inherited = True

            if isinstance(item, AttributeSchema):
                self.attributes.append(new_item)
            elif isinstance(item, RelationshipSchema):
                self.relationships.append(new_item)


class GroupSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]


class SchemaRoot(BaseModel):
    generics: List[GenericSchema] = Field(default_factory=list)
    nodes: List[NodeSchema] = Field(default_factory=list)
    groups: List[GroupSchema] = Field(default_factory=list)

    def extend_nodes_with_interfaces(self) -> SchemaRoot:
        """Extend all the nodes with the attributes and relationships
        from the Interface objects defined in inherited_from.

        In the current implementation, we are only looking for Generic/interface in the local object.
        Pretty soon, we will mostlikely need to extend that to the registry/db to allow a model to use a generic he hasn't defined
        """

        generics = {item.kind: item for item in self.generics}

        # For all node_schema, add the attributes & relationships from the generic / interface
        for node in self.nodes:
            for generic_kind in node.inherit_from:
                if generic_kind not in generics:
                    # TODO add a proper exception for all schema related issue
                    raise ValueError(f"{node.kind} Unable to find the generic {generic_kind}")

                node.extend_with_interface(interface=generics[generic_kind])

        return self


# TODO need to investigate how we could generate the internal schema
# directly from the Pydantic Models to avoid the duplication of effort
internal_schema = {
    "nodes": [
        {
            "name": "node_schema",
            "kind": "NodeSchema",
            "branch": True,
            "default_filter": "name__value",
            "attributes": [
                {
                    "name": "name",
                    "kind": "String",
                    "unique": True,
                },
                {
                    "name": "kind",
                    "kind": "String",
                },
                {
                    "name": "label",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "description",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "branch",
                    "kind": "Boolean",
                    "default": True,
                },
                {
                    "name": "default_filter",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "inherit_from",
                    "kind": "List",
                },
                {
                    "name": "groups",
                    "kind": "List",
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
            "name": "attribute_schema",
            "kind": "AttributeSchema",
            "branch": True,
            "default_filter": None,
            "attributes": [
                {
                    "name": "name",
                    "kind": "String",
                },
                {
                    "name": "kind",
                    "kind": "String",
                },
                {
                    "name": "label",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "description",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "unique",
                    "kind": "Boolean",
                },
                {
                    "name": "optional",
                    "kind": "Boolean",
                },
                {
                    "name": "branch",
                    "kind": "Boolean",
                    "default": True,
                },
                {
                    "name": "default_value",
                    "kind": "Any",
                    "optional": True,
                },
                {
                    "name": "inherited",
                    "kind": "Boolean",
                    "default": False,
                },
            ],
        },
        {
            "name": "relationship_schema",
            "kind": "RelationshipSchema",
            "branch": True,
            "default_filter": None,
            "attributes": [
                {
                    "name": "name",
                    "kind": "String",
                },
                {
                    "name": "peer",
                    "kind": "String",
                },
                {
                    "name": "label",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "description",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "identifier",
                    "kind": "String",
                },
                {
                    "name": "cardinality",
                    "kind": "String",
                },
                {
                    "name": "optional",
                    "kind": "Boolean",
                    "default": False,
                },
                {
                    "name": "branch",
                    "kind": "Boolean",
                    "default": True,
                },
                {
                    "name": "inherited",
                    "kind": "Boolean",
                    "default": False,
                },
            ],
        },
        {
            "name": "generic_schema",
            "kind": "GenericSchema",
            "branch": True,
            "default_filter": "name__value",
            "attributes": [
                {
                    "name": "name",
                    "kind": "String",
                    "unique": True,
                },
                {
                    "name": "kind",
                    "kind": "String",
                },
                {
                    "name": "label",
                    "kind": "String",
                    "optional": True,
                },
                {
                    "name": "description",
                    "kind": "String",
                    "optional": True,
                },
            ],
            "relationships": [
                {
                    "name": "attributes",
                    "peer": "AttributeSchema",
                    "identifier": "schema__generic__attributes",
                    "cardinality": "many",
                    "branch": True,
                    "optional": True,
                },
                {
                    "name": "relationships",
                    "peer": "RelationshipSchema",
                    "identifier": "schema__generic__relationships",
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
            "attributes": [
                {
                    "name": "name",
                    "kind": "String",
                    "unique": True,
                },
                {
                    "name": "kind",
                    "kind": "String",
                },
                {
                    "name": "description",
                    "kind": "String",
                    "optional": True,
                },
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
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
        },
        {
            "name": "data_source",
            "description": "Any Entities that stores or produces data.",
            "kind": "DataSource",  # Repository, Account ...
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
        },
    ],
    "nodes": [
        {
            "name": "criticality",
            "kind": "Criticality",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "level", "kind": "Integer"},
                {"name": "description", "kind": "String", "optional": True},
            ],
        },
        {
            "name": "tag",
            "kind": "Tag",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
        },
        {
            "name": "organization",
            "kind": "Organization",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "account",
            "kind": "Account",
            "default_filter": "name__value",
            "branch": True,
            "inherit_from": ["DataOwner", "DataSource"],
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "type", "kind": "String", "default_value": "USER"},  # USER, BOT, GIT
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
            "branch": True,
            "attributes": [
                {"name": "token", "kind": "String", "unique": True},
                {"name": "expiration_date", "kind": "String", "optional": True},  # Should be date here
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
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "members", "peer": "Account", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "status",
            "kind": "Status",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
        },
        {
            "name": "role",
            "kind": "Role",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
        },
        {
            "name": "location",
            "kind": "Location",
            "default_filter": "name__value",
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "type", "kind": "String"},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "repository",
            "kind": "Repository",
            "default_filter": "name__value",
            "branch": True,
            "inherit_from": ["DataOwner", "DataSource"],
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "location", "kind": "String"},
                {"name": "type", "kind": "String", "default_value": "LOCAL"},
                {"name": "default_branch", "kind": "String", "default_value": "main"},
                {"name": "commit", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "account", "peer": "Account", "optional": True, "cardinality": "one"},
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
                {"name": "rfiles", "peer": "RFile", "optional": True, "cardinality": "many"},
                {"name": "queries", "peer": "GraphQLQuery", "optional": True, "cardinality": "many"},
                {"name": "checks", "peer": "Check", "optional": True, "cardinality": "many"},
                {"name": "transform_python", "peer": "TransformPython", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "rfile",
            "kind": "RFile",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "template_path", "kind": "String"},
            ],
            "relationships": [
                {
                    "name": "template_repository",
                    "peer": "Repository",
                    "identifier": "rfile_template_repository",
                    "cardinality": "one",
                    "optional": False,
                },
                {"name": "query", "peer": "GraphQLQuery", "cardinality": "one", "optional": False},
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "check",
            "kind": "Check",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "file_path", "kind": "String"},
                {"name": "class_name", "kind": "String"},
                {"name": "timeout", "kind": "Integer", "default_value": 10},
                {"name": "rebase", "kind": "Boolean", "default_value": False},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "Repository",
                    "cardinality": "one",
                    "optional": False,
                },
                {"name": "query", "peer": "GraphQLQuery", "cardinality": "one", "optional": True},
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "transform_python",
            "kind": "TransformPython",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "file_path", "kind": "String"},
                {"name": "class_name", "kind": "String"},
                {"name": "url", "kind": "String"},
                {"name": "timeout", "kind": "Integer", "default_value": 10},
                {"name": "rebase", "kind": "Boolean", "default_value": False},
            ],
            "relationships": [
                {
                    "name": "repository",
                    "peer": "Repository",
                    "cardinality": "one",
                    "optional": False,
                },
                {"name": "query", "peer": "GraphQLQuery", "cardinality": "one", "optional": True},
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "graphql_query",
            "kind": "GraphQLQuery",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "query", "kind": "String"},
            ],
            "relationships": [
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
    ],
}
