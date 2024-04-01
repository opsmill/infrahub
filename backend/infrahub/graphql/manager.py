from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Type, Union

import graphene

from infrahub import config
from infrahub.core.attribute import String
from infrahub.core.constants import InfrahubKind, RelationshipKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, ProfileSchema
from infrahub.graphql.mutations.attribute import BaseAttributeInput
from infrahub.graphql.mutations.graphql_query import InfrahubGraphQLQueryMutation
from infrahub.types import ATTRIBUTE_TYPES, InfrahubDataType, get_attribute_type

from .enums import generate_graphql_enum, get_enum_attribute_type_name
from .metrics import SCHEMA_GENERATE_GRAPHQL_METRICS
from .mutations import (
    InfrahubArtifactDefinitionMutation,
    InfrahubMutation,
    InfrahubProposedChangeMutation,
    InfrahubRepositoryMutation,
)
from .queries.diff.diff import (
    DiffSummaryElementAttribute,
    DiffSummaryElementRelationshipMany,
    DiffSummaryElementRelationshipOne,
)
from .resolver import (
    ancestors_resolver,
    default_resolver,
    descendants_resolver,
    many_relationship_resolver,
    single_relationship_resolver,
)
from .schema import InfrahubBaseMutation, InfrahubBaseQuery, account_resolver, default_paginated_list_resolver
from .subscription import InfrahubBaseSubscription
from .types import InfrahubInterface, InfrahubObject, RelatedNodeInput
from .types.attribute import BaseAttribute as BaseAttributeType
from .types.attribute import TextAttributeType

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.schema_manager import SchemaBranch


class DeleteInput(graphene.InputObjectType):
    id = graphene.String(required=True)


GraphQLTypes = Union[
    Type[InfrahubMutation], Type[BaseAttributeType], Type[graphene.Interface], Type[graphene.ObjectType]
]


@dataclass
class GraphqlMutations:
    create: Type[InfrahubMutation]
    update: Type[InfrahubMutation]
    upsert: Type[InfrahubMutation]
    delete: Type[InfrahubMutation]


def get_attr_kind(node_schema: Union[NodeSchema, GenericSchema, ProfileSchema], attr_schema: AttributeSchema) -> str:
    if not config.SETTINGS.experimental_features.graphql_enums or not attr_schema.enum:
        return attr_schema.kind
    return get_enum_attribute_type_name(node_schema=node_schema, attr_schema=attr_schema)


class GraphQLSchemaManager:  # pylint: disable=too-many-public-methods
    _extra_types: Dict[str, GraphQLTypes] = {
        "DiffSummaryElementAttribute": DiffSummaryElementAttribute,
        "DiffSummaryElementRelationshipOne": DiffSummaryElementRelationshipOne,
        "DiffSummaryElementRelationshipMany": DiffSummaryElementRelationshipMany,
    }

    def __init__(self, schema: SchemaBranch):
        self.schema = schema

        self._graphql_types: Dict[str, GraphQLTypes] = {}

        self._load_attribute_types()
        if config.SETTINGS.experimental_features.graphql_enums:
            self._load_all_enum_types(node_schemas=self.schema.get_all().values())
        self._load_node_interface()

    def generate(
        self,
        include_query: bool = True,
        include_mutation: bool = True,
        include_subscription: bool = True,
        include_types: bool = True,
    ) -> GraphQLSchema:
        with SCHEMA_GENERATE_GRAPHQL_METRICS.labels(self.schema.name).time():
            if include_types:
                self.generate_object_types()
                types_dict = self.get_all()
                types = list(types_dict.values())
            else:
                types = []

            query = self.get_gql_query() if include_query else None
            mutation = self.get_gql_mutation() if include_mutation else None
            subscription = self.get_gql_subscription() if include_subscription else None

            graphene_schema = graphene.Schema(
                query=query, mutation=mutation, subscription=subscription, types=types, auto_camelcase=False
            )

            return graphene_schema.graphql_schema

    def get_gql_query(self) -> type[InfrahubBaseQuery]:
        QueryMixin = self.generate_query_mixin()

        class Query(InfrahubBaseQuery, QueryMixin):  # type: ignore
            pass

        return Query

    def get_gql_mutation(self) -> type[InfrahubBaseMutation]:
        MutationMixin = self.generate_mutation_mixin()

        class Mutation(InfrahubBaseMutation, MutationMixin):  # type: ignore
            pass

        return Mutation

    def get_gql_subscription(self) -> type[InfrahubBaseSubscription]:
        class Subscription(InfrahubBaseSubscription):
            pass

        return Subscription

    def get_type(self, name: str) -> Type[InfrahubObject]:
        if name in self._graphql_types and issubclass(
            self._graphql_types[name], (BaseAttributeType, graphene.Interface, graphene.ObjectType)
        ):
            return self._graphql_types[name]
        raise ValueError(f"Unable to find {name!r}")

    def get_mutation(self, name: str) -> Type[InfrahubMutation]:
        if name in self._graphql_types and issubclass(self._graphql_types[name], InfrahubMutation):
            return self._graphql_types[name]
        raise ValueError(f"Unable to find {name!r}")

    def get_all(self) -> Dict[str, GraphQLTypes]:
        infrahub_types = self._graphql_types
        infrahub_types.update(self._extra_types)
        return infrahub_types

    def set_type(self, name: str, graphql_type: GraphQLTypes) -> None:
        self._graphql_types[name] = graphql_type

    def _load_attribute_types(self) -> None:
        for data_type in ATTRIBUTE_TYPES.values():
            self.set_type(name=data_type.get_graphql_type_name(), graphql_type=data_type.get_graphql_type())

    def _load_node_interface(self) -> None:
        node_interface_schema = GenericSchema(
            name="Node", namespace="Core", description="Interface for all nodes in Infrahub"
        )
        interface = self.generate_interface_object(schema=node_interface_schema, populate_cache=True)
        edged_interface = self.generate_graphql_edged_object(
            schema=node_interface_schema, node=interface, populate_cache=True
        )
        self.generate_graphql_paginated_object(schema=node_interface_schema, edge=edged_interface, populate_cache=True)

    def _load_all_enum_types(self, node_schemas: Iterable[Union[NodeSchema, GenericSchema, ProfileSchema]]) -> None:
        for node_schema in node_schemas:
            self._load_enum_type(node_schema=node_schema)

    def _load_enum_type(self, node_schema: Union[NodeSchema, GenericSchema, ProfileSchema]) -> None:
        for attr_schema in node_schema.attributes:
            if not attr_schema.enum:
                continue
            base_enum_name = get_enum_attribute_type_name(node_schema, attr_schema)
            enum_value_name = f"{base_enum_name}Value"
            input_class_name = f"{base_enum_name}AttributeInput"
            data_type_class_name = f"{base_enum_name}EnumType"
            graphene_enum = generate_graphql_enum(name=enum_value_name, options=attr_schema.enum)
            default_value = None
            if attr_schema.default_value:
                for g_enum in graphene_enum:
                    if g_enum.value == attr_schema.default_value:
                        default_value = g_enum.name
                        break
            graphene_field = graphene.Field(graphene_enum, default_value=default_value)
            input_class = type(input_class_name, (BaseAttributeInput,), {"value": graphene_field})
            data_type_class: Type[InfrahubDataType] = type(
                data_type_class_name,
                (InfrahubDataType,),
                {
                    "label": data_type_class_name,
                    "graphql": graphene.String,
                    "graphql_query": TextAttributeType,
                    "graphql_input": input_class,
                    "graphql_filter": graphene_enum,
                    "infrahub": String,
                },
            )
            self.set_type(
                name=data_type_class.get_graphql_type_name(),
                graphql_type=data_type_class.get_graphql_type(),
            )
            ATTRIBUTE_TYPES[base_enum_name] = data_type_class

    def generate_object_types(self) -> None:  # pylint: disable=too-many-branches,too-many-statements
        """Generate all GraphQL objects for the schema and store them in the internal registry."""

        full_schema = self.schema.get_all(duplicate=False)

        # Generate all GraphQL Interface  Object first and store them in the registry
        for node_name, node_schema in full_schema.items():
            if not isinstance(node_schema, GenericSchema):
                continue
            interface = self.generate_interface_object(schema=node_schema, populate_cache=True)
            edged_interface = self.generate_graphql_edged_object(
                schema=node_schema, node=interface, populate_cache=True
            )
            self.generate_graphql_paginated_object(schema=node_schema, edge=edged_interface, populate_cache=True)

        # Define LineageSource and LineageOwner
        data_source = self.get_type(name=InfrahubKind.LINEAGESOURCE)
        data_owner = self.get_type(name=InfrahubKind.LINEAGEOWNER)
        self.define_relationship_property(data_source=data_source, data_owner=data_owner)
        relationship_property = self.get_type(name="RelationshipProperty")
        for data_type in ATTRIBUTE_TYPES.values():
            gql_type = self.get_type(name=data_type.get_graphql_type_name())
            gql_type._meta.fields["source"] = graphene.Field(data_source)
            gql_type._meta.fields["owner"] = graphene.Field(data_owner)

        # Generate all Nested, Edged and NestedEdged Interfaces and store them in the registry
        for node_name, node_schema in full_schema.items():
            if not isinstance(node_schema, GenericSchema):
                continue

            node_interface = self.get_type(name=node_name)

            nested_edged_interface = self.generate_nested_interface_object(
                schema=node_schema,
                base_interface=node_interface,
                relation_property=relationship_property,
            )

            nested_interface = self.generate_paginated_interface_object(
                schema=node_schema,
                base_interface=nested_edged_interface,
            )

            self.set_type(name=nested_interface._meta.name, graphql_type=nested_interface)
            self.set_type(name=nested_edged_interface._meta.name, graphql_type=nested_edged_interface)

        # Generate all GraphQL ObjectType, Nested, Paginated & NestedPaginated and store them in the registry
        for node_name, node_schema in full_schema.items():
            if isinstance(node_schema, (NodeSchema, ProfileSchema)):
                node_type = self.generate_graphql_object(schema=node_schema, populate_cache=True)
                node_type_edged = self.generate_graphql_edged_object(
                    schema=node_schema, node=node_type, populate_cache=True
                )
                nested_node_type_edged = self.generate_graphql_edged_object(
                    schema=node_schema, node=node_type, relation_property=relationship_property, populate_cache=True
                )

                self.generate_graphql_paginated_object(schema=node_schema, edge=node_type_edged, populate_cache=True)
                self.generate_graphql_paginated_object(
                    schema=node_schema, edge=nested_node_type_edged, nested=True, populate_cache=True
                )

        # Extend all types and related types with Relationships
        for node_name, node_schema in full_schema.items():
            node_type = self.get_type(name=node_name)

            for rel in node_schema.relationships:
                peer_schema = self.schema.get(name=rel.peer, duplicate=False)
                if peer_schema.namespace == "Internal":
                    continue
                peer_filters = self.generate_filters(schema=peer_schema, top_level=False)

                if rel.cardinality == "one":
                    peer_type = self.get_type(name=f"NestedEdged{peer_schema.kind}")
                    node_type._meta.fields[rel.name] = graphene.Field(peer_type, resolver=single_relationship_resolver)

                elif rel.cardinality == "many":
                    peer_type = self.get_type(name=f"NestedPaginated{peer_schema.kind}")

                    if (isinstance(node_schema, NodeSchema) and node_schema.hierarchy) or (
                        isinstance(node_schema, GenericSchema) and node_schema.hierarchical
                    ):
                        peer_filters["include_descendants"] = graphene.Boolean()

                    node_type._meta.fields[rel.name] = graphene.Field(
                        peer_type, required=False, resolver=many_relationship_resolver, **peer_filters
                    )

            if isinstance(node_schema, NodeSchema) and node_schema.hierarchy:
                schema = self.schema.get(name=node_schema.hierarchy, duplicate=False)

                peer_filters = self.generate_filters(schema=schema, top_level=False)
                peer_type = self.get_type(name=f"NestedPaginated{node_schema.hierarchy}")

                node_type._meta.fields["ancestors"] = graphene.Field(
                    peer_type, required=False, resolver=ancestors_resolver, **peer_filters
                )
                node_type._meta.fields["descendants"] = graphene.Field(
                    peer_type, required=False, resolver=descendants_resolver, **peer_filters
                )

    def generate_query_mixin(self) -> Type[object]:
        class_attrs = {}

        full_schema = self.schema.get_all(duplicate=False)

        # Generate all Graphql objectType and store internally
        self.generate_object_types()

        for node_name, node_schema in full_schema.items():
            if node_schema.namespace == "Internal":
                continue

            node_type = self.get_type(name=f"Paginated{node_name}")
            node_filters = self.generate_filters(schema=node_schema, top_level=True)

            class_attrs[node_schema.kind] = graphene.Field(
                node_type,
                resolver=default_paginated_list_resolver,
                **node_filters,
            )
            if node_name == InfrahubKind.ACCOUNT:
                node_type = self.get_type(name=InfrahubKind.ACCOUNT)
                class_attrs["AccountProfile"] = graphene.Field(
                    node_type,
                    resolver=account_resolver,
                )

        return type("QueryMixin", (object,), class_attrs)

    def generate_mutation_mixin(self) -> Type[object]:
        class_attrs: Dict[str, Any] = {}

        full_schema = self.schema.get_all(duplicate=False)

        for node_schema in full_schema.values():
            if not isinstance(node_schema, (NodeSchema, ProfileSchema)):
                continue

            if node_schema.namespace == "Internal":
                continue

            mutation_map: Dict[str, Type[InfrahubMutation]] = {
                InfrahubKind.ARTIFACTDEFINITION: InfrahubArtifactDefinitionMutation,
                InfrahubKind.REPOSITORY: InfrahubRepositoryMutation,
                InfrahubKind.READONLYREPOSITORY: InfrahubRepositoryMutation,
                InfrahubKind.PROPOSEDCHANGE: InfrahubProposedChangeMutation,
                InfrahubKind.GRAPHQLQUERY: InfrahubGraphQLQueryMutation,
            }
            base_class = mutation_map.get(node_schema.kind, InfrahubMutation)

            mutations = self.generate_graphql_mutations(schema=node_schema, base_class=base_class)

            class_attrs[f"{node_schema.kind}Create"] = mutations.create.Field()
            class_attrs[f"{node_schema.kind}Update"] = mutations.update.Field()
            class_attrs[f"{node_schema.kind}Upsert"] = mutations.upsert.Field()
            class_attrs[f"{node_schema.kind}Delete"] = mutations.delete.Field()

        return type("MutationMixin", (object,), class_attrs)

    def generate_graphql_object(
        self, schema: Union[NodeSchema, ProfileSchema], populate_cache: bool = False
    ) -> Type[InfrahubObject]:
        """Generate a GraphQL object Type from a Infrahub NodeSchema."""

        interfaces: Set[Type[InfrahubObject]] = set()

        if schema.inherit_from:
            for generic_name in schema.inherit_from:
                generic = self.get_type(name=generic_name)
                interfaces.add(generic)

        if not schema.inherit_from or InfrahubKind.GENERICGROUP not in schema.inherit_from:
            node_interface = self.get_type(name="CoreNode")
            interfaces.add(node_interface)

        meta_attrs = {
            "schema": schema,
            "name": schema.kind,
            "description": schema.description,
            "interfaces": interfaces,
        }

        main_attrs = {
            "id": graphene.String(required=True),
            "_updated_at": graphene.DateTime(required=False),
            "display_label": graphene.String(required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        for attr in schema.local_attributes:
            attr_kind = get_attr_kind(schema, attr)
            attr_type = self.get_type(name=get_attribute_type(kind=attr_kind).get_graphql_type_name())
            main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

        graphql_object = type(schema.kind, (InfrahubObject,), main_attrs)

        if populate_cache:
            self.set_type(name=schema.kind, graphql_type=graphql_object)

        return graphql_object

    def generate_interface_object(
        self, schema: GenericSchema, populate_cache: bool = False
    ) -> Type[graphene.Interface]:
        meta_attrs = {
            "name": schema.kind,
            "description": schema.description,
        }

        main_attrs = {
            "display_label": graphene.String(required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        for attr in schema.attributes:
            attr_kind = get_attr_kind(node_schema=schema, attr_schema=attr)
            attr_type = self.get_type(name=get_attribute_type(kind=attr_kind).get_graphql_type_name())
            main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

        main_attrs["id"] = graphene.Field(graphene.String, required=False, description="Unique identifier")

        interface_object = type(schema.kind, (InfrahubInterface,), main_attrs)

        if populate_cache:
            self.set_type(name=schema.kind, graphql_type=interface_object)

        return interface_object

    def define_relationship_property(self, data_source: Type[InfrahubObject], data_owner: Type[InfrahubObject]) -> None:
        type_name = "RelationshipProperty"

        meta_attrs = {
            "name": type_name,
            "description": "Defines properties for relationships",
        }

        main_attrs = {
            "is_visible": graphene.Boolean(required=False),
            "is_protected": graphene.Boolean(required=False),
            "updated_at": graphene.DateTime(required=False),
            "source": graphene.Field(data_source),
            "owner": graphene.Field(data_owner),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        relationship_property = type(type_name, (graphene.ObjectType,), main_attrs)

        self.set_type(name=type_name, graphql_type=relationship_property)

    def generate_graphql_mutations(
        self, schema: Union[NodeSchema, ProfileSchema], base_class: Type[InfrahubMutation]
    ) -> GraphqlMutations:
        graphql_mutation_create_input = self.generate_graphql_mutation_create_input(schema)
        graphql_mutation_update_input = self.generate_graphql_mutation_update_input(schema)

        create = self.generate_graphql_mutation_create(
            schema=schema, base_class=base_class, input_type=graphql_mutation_create_input
        )
        upsert = self.generate_graphql_mutation_create(
            schema=schema,
            base_class=base_class,
            input_type=graphql_mutation_create_input,
            mutation_type="Upsert",
        )
        update = self.generate_graphql_mutation_update(
            schema=schema, base_class=base_class, input_type=graphql_mutation_update_input
        )
        delete = self.generate_graphql_mutation_delete(schema=schema, base_class=base_class)

        self.set_type(name=create._meta.name, graphql_type=create)
        self.set_type(name=update._meta.name, graphql_type=update)
        self.set_type(name=upsert._meta.name, graphql_type=upsert)
        self.set_type(name=delete._meta.name, graphql_type=delete)

        return GraphqlMutations(create=create, update=update, upsert=upsert, delete=delete)

    @staticmethod
    def generate_graphql_mutation_create_input(
        schema: Union[NodeSchema, ProfileSchema],
    ) -> Type[graphene.InputObjectType]:
        """Generate an InputObjectType Object from a Infrahub NodeSchema

        Example of Object Generated by this function:
            class StatusCreateInput(InputObjectType):
                id = String(required=False)
                label = InputField(StringAttributeInput, required=True)
                slug = InputField(StringAttributeInput, required=True)
                description = InputField(StringAttributeInput, required=False)
        """
        attrs: Dict[str, Union[graphene.String, graphene.InputField]] = {"id": graphene.String(required=False)}

        for attr in schema.attributes:
            if attr.read_only:
                continue

            attr_kind = get_attr_kind(schema, attr)
            attr_type = get_attribute_type(kind=attr_kind).get_graphql_input()

            # A Field is not required if explicitly indicated or if a default value has been provided
            required = not attr.optional if not attr.default_value else False

            attrs[attr.name] = graphene.InputField(attr_type, required=required, description=attr.description)

        for rel in schema.relationships:
            if rel.internal_peer:
                continue
            required = not rel.optional
            if rel.cardinality == "one":
                attrs[rel.name] = graphene.InputField(RelatedNodeInput, required=required, description=rel.description)

            elif rel.cardinality == "many":
                attrs[rel.name] = graphene.InputField(
                    graphene.List(RelatedNodeInput), required=required, description=rel.description
                )

        return type(f"{schema.kind}CreateInput", (graphene.InputObjectType,), attrs)

    @staticmethod
    def generate_graphql_mutation_update_input(
        schema: Union[NodeSchema, ProfileSchema],
    ) -> Type[graphene.InputObjectType]:
        """Generate an InputObjectType Object from a Infrahub NodeSchema

        Example of Object Generated by this function:
            class StatusUpdateInput(InputObjectType):
                id = String(required=True)
                label = InputField(StringAttributeInput, required=False)
                slug = InputField(StringAttributeInput, required=False)
                description = InputField(StringAttributeInput, required=False)
        """
        attrs: Dict[str, Union[graphene.String, graphene.InputField]] = {"id": graphene.String(required=True)}

        for attr in schema.attributes:
            if attr.read_only:
                continue
            attr_kind = get_attr_kind(schema, attr)
            attr_type = get_attribute_type(kind=attr_kind).get_graphql_input()
            attrs[attr.name] = graphene.InputField(attr_type, required=False, description=attr.description)

        for rel in schema.relationships:
            if rel.internal_peer:
                continue
            if rel.cardinality == "one":
                attrs[rel.name] = graphene.InputField(RelatedNodeInput, required=False, description=rel.description)

            elif rel.cardinality == "many":
                attrs[rel.name] = graphene.InputField(
                    graphene.List(RelatedNodeInput), required=False, description=rel.description
                )

        return type(f"{schema.kind}UpdateInput", (graphene.InputObjectType,), attrs)

    def generate_graphql_mutation_create(
        self,
        schema: Union[NodeSchema, ProfileSchema],
        input_type: Type[graphene.InputObjectType],
        base_class: Type[InfrahubMutation] = InfrahubMutation,
        mutation_type: str = "Create",
    ) -> Type[InfrahubMutation]:
        """Generate a GraphQL Mutation to CREATE an object based on the specified NodeSchema."""
        name = f"{schema.kind}{mutation_type}"

        object_type = self.generate_graphql_object(schema=schema)

        main_attrs: Dict[str, Any] = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

        meta_attrs: Dict[str, Any] = {"schema": schema, "name": name, "description": schema.description}
        main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

        args_attrs = {
            "data": input_type(required=True),
        }
        main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

        return type(name, (base_class,), main_attrs)

    def generate_graphql_mutation_update(
        self,
        schema: Union[NodeSchema, ProfileSchema],
        input_type: Type[graphene.InputObjectType],
        base_class: Type[InfrahubMutation] = InfrahubMutation,
    ) -> Type[InfrahubMutation]:
        """Generate a GraphQL Mutation to UPDATE an object based on the specified NodeSchema."""
        name = f"{schema.kind}Update"

        object_type = self.generate_graphql_object(schema=schema)

        main_attrs: Dict[str, Any] = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

        meta_attrs: Dict[str, Any] = {"schema": schema, "name": name, "description": schema.description}
        main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

        args_attrs = {
            "data": input_type(required=True),
        }
        main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

        return type(name, (base_class,), main_attrs)

    @staticmethod
    def generate_graphql_mutation_delete(
        schema: Union[NodeSchema, ProfileSchema],
        base_class: Type[InfrahubMutation] = InfrahubMutation,
    ) -> Type[InfrahubMutation]:
        """Generate a GraphQL Mutation to DELETE an object based on the specified NodeSchema."""
        name = f"{schema.kind}Delete"

        main_attrs: Dict[str, Any] = {"ok": graphene.Boolean()}

        meta_attrs = {"schema": schema, "name": name, "description": schema.description}
        main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

        args_attrs: Dict[str, Any] = {
            "data": DeleteInput(required=True),
        }
        main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

        return type(name, (base_class,), main_attrs)

    def generate_filters(
        self,
        schema: Union[NodeSchema, GenericSchema, ProfileSchema],
        top_level: bool = False,
        include_properties: bool = True,
    ) -> Dict[str, Union[graphene.Scalar, graphene.List]]:
        """Generate the GraphQL filters for a given Schema object.

        The generated filter will be different if we are at the top_level (query)
        or if we are generating the filter for a relationship inside a node.

        At the top, level it will be possible to query with a list of ID
        Inside a node, it's only possible to query with a single ID

        Args:
            schema (Union[NodeSchema, GenericSchema]): Schema to generate the filters
            top_level (bool, optional): Flag to indicate if are at the top level or not. Defaults to False.

        Returns:
            dict: A Dictionnary containing all the filters with their name as the key and their Type as value
        """

        filters: Dict[str, Any] = {"offset": graphene.Int(), "limit": graphene.Int()}
        default_filters: List[str] = list(filters.keys())

        filters["ids"] = graphene.List(graphene.ID)

        for attr in schema.attributes:
            attr_kind = get_attr_kind(node_schema=schema, attr_schema=attr)
            filters.update(
                get_attribute_type(kind=attr_kind).get_graphql_filters(
                    name=attr.name, include_properties=include_properties
                )
            )

        if top_level:
            filters.update(get_attribute_type().get_graphql_filters(name="any"))
            filters["partial_match"] = graphene.Boolean()

        if not top_level:
            return filters

        for rel in schema.relationships:
            peer_schema = self.schema.get(name=rel.peer, duplicate=False)

            if peer_schema.namespace == "Internal":
                continue

            if rel.kind == RelationshipKind.GROUP:
                peer_filters = self.generate_filters(schema=peer_schema, top_level=False, include_properties=False)
            else:
                peer_filters = self.generate_filters(schema=peer_schema, top_level=False)

            for key, value in peer_filters.items():
                if key in default_filters:
                    continue
                filters[f"{rel.name}__{key}"] = value

        return filters

    def generate_graphql_edged_object(
        self,
        schema: Union[NodeSchema, GenericSchema, ProfileSchema],
        node: Type[InfrahubObject],
        relation_property: Optional[Type[InfrahubObject]] = None,
        populate_cache: bool = False,
        node_name: Optional[str] = None,
    ) -> Type[InfrahubObject]:
        """Generate a edged GraphQL object Type from a Infrahub NodeSchema for pagination."""

        object_name = f"Edged{node_name or schema.kind}"
        if relation_property:
            object_name = f"NestedEdged{node_name or schema.kind}"

        meta_attrs: Dict[str, Any] = {
            "schema": schema,
            "name": object_name,
            "description": schema.description,
            "interfaces": set(),
        }

        main_attrs: Dict[str, Any] = {
            "node": graphene.Field(node, required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        if relation_property:
            main_attrs["properties"] = graphene.Field(relation_property)

        graphql_edged_object = type(object_name, (InfrahubObject,), main_attrs)

        if populate_cache:
            self.set_type(name=object_name, graphql_type=graphql_edged_object)

        return graphql_edged_object

    def generate_graphql_paginated_object(
        self,
        schema: Union[NodeSchema, GenericSchema, ProfileSchema],
        edge: Type[InfrahubObject],
        nested: bool = False,
        populate_cache: bool = False,
        node_name: Optional[str] = None,
    ) -> Type[InfrahubObject]:
        """Generate a paginated GraphQL object Type from a Infrahub NodeSchema."""

        object_name = f"Paginated{node_name or schema.kind}"
        if nested:
            object_name = f"NestedPaginated{node_name or schema.kind}"

        meta_attrs: Dict[str, Any] = {
            "schema": schema,
            "name": object_name,
            "description": schema.description,
            "default_resolver": default_resolver,
            "interfaces": set(),
        }

        main_attrs: Dict[str, Any] = {
            "count": graphene.Int(required=False),
            "edges": graphene.List(of_type=edge),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        graphql_paginated_object = type(object_name, (InfrahubObject,), main_attrs)

        if populate_cache:
            self.set_type(name=object_name, graphql_type=graphql_paginated_object)

        return graphql_paginated_object

    def generate_nested_interface_object(
        self,
        schema: GenericSchema,
        relation_property: graphene.ObjectType,
        base_interface: graphene.ObjectType,
        populate_cache: bool = False,
    ) -> Type[InfrahubObject]:
        meta_attrs: Dict[str, Any] = {
            "name": f"NestedEdged{schema.kind}",
            "schema": schema,
            "description": schema.description,
        }

        main_attrs: Dict[str, Any] = {
            "node": graphene.Field(base_interface, required=False),
            "_updated_at": graphene.DateTime(required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        if relation_property:
            main_attrs["properties"] = graphene.Field(relation_property)

        object_name = f"NestedEdged{schema.kind}"
        nested_interface_object = type(object_name, (InfrahubObject,), main_attrs)

        if populate_cache:
            self.set_type(name=object_name, graphql_type=nested_interface_object)

        return nested_interface_object

    @staticmethod
    def generate_paginated_interface_object(
        schema: GenericSchema,
        base_interface: Type[graphene.ObjectType],
    ) -> Type[InfrahubObject]:
        meta_attrs: Dict[str, Any] = {
            "name": f"NestedPaginated{schema.kind}",
            "schema": schema,
            "description": schema.description,
        }

        main_attrs: Dict[str, Any] = {
            "count": graphene.Int(required=False),
            "edges": graphene.List(of_type=base_interface),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        return type(f"NestedPaginated{schema.kind}", (InfrahubObject,), main_attrs)
