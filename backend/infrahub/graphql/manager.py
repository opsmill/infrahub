from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

import graphene

from infrahub import config
from infrahub.core.attribute import String
from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
    RelationshipSchema,
    TemplateSchema,
)
from infrahub.graphql.mutations.attribute import BaseAttributeCreate, BaseAttributeUpdate
from infrahub.graphql.mutations.graphql_query import InfrahubGraphQLQueryMutation
from infrahub.graphql.mutations.profile import InfrahubProfileMutation
from infrahub.types import ATTRIBUTE_TYPES, InfrahubDataType, get_attribute_type

from .directives import DIRECTIVES
from .enums import generate_graphql_enum, get_enum_attribute_type_name
from .metrics import SCHEMA_GENERATE_GRAPHQL_METRICS
from .mutations.action import InfrahubTriggerRuleMatchMutation, InfrahubTriggerRuleMutation
from .mutations.artifact_definition import InfrahubArtifactDefinitionMutation
from .mutations.ipam import (
    InfrahubIPAddressMutation,
    InfrahubIPNamespaceMutation,
    InfrahubIPPrefixMutation,
)
from .mutations.main import InfrahubMutation
from .mutations.menu import InfrahubCoreMenuMutation
from .mutations.proposed_change import InfrahubProposedChangeMutation
from .mutations.repository import InfrahubRepositoryMutation
from .mutations.resource_manager import (
    InfrahubNumberPoolMutation,
)
from .mutations.webhook import InfrahubWebhookMutation
from .registry import registry
from .resolvers.ipam import ipam_paginated_list_resolver
from .resolvers.resolver import (
    account_resolver,
    ancestors_resolver,
    default_paginated_list_resolver,
    default_resolver,
    descendants_resolver,
    many_relationship_resolver,
    parent_field_name_resolver,
    single_relationship_resolver,
)
from .schema import InfrahubBaseMutation, InfrahubBaseQuery
from .subscription import InfrahubBaseSubscription
from .types import (
    InfrahubInterface,
    InfrahubObject,
    PaginatedObjectPermission,
    RelatedIPAddressNodeInput,
    RelatedIPPrefixNodeInput,
    RelatedNodeInput,
)
from .types.attribute import BaseAttribute as BaseAttributeType
from .types.attribute import TextAttributeType
from .types.context import ContextInput
from .types.event import EVENT_TYPES

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.schema.schema_branch import SchemaBranch


class DeleteInput(graphene.InputObjectType):
    id = graphene.String(required=False)
    hfid = graphene.List(of_type=graphene.String, required=False)


GraphQLTypes = type[InfrahubMutation] | type[BaseAttributeType] | type[graphene.Interface] | type[graphene.ObjectType]


class OrderInput(graphene.InputObjectType):
    disable = graphene.Boolean(required=False)


@dataclass
class GraphqlMutations:
    create: type[InfrahubMutation]
    update: type[InfrahubMutation]
    upsert: type[InfrahubMutation]
    delete: type[InfrahubMutation]


@dataclass
class InterfaceReference:
    reference: type[graphene.Interface]
    reference_hash: str


@dataclass
class InfrahubObjectReference:
    reference: type[InfrahubObject]
    reference_hash: str


@dataclass
class InfrahubEdgedReference:
    reference: type[InfrahubObject]
    reference_hash: str


def get_attr_kind(node_schema: MainSchemaTypes, attr_schema: AttributeSchema) -> str:
    if not config.SETTINGS.experimental_features.graphql_enums or not attr_schema.enum:
        return attr_schema.kind
    return get_enum_attribute_type_name(node_schema=node_schema, attr_schema=attr_schema)


class GraphQLSchemaManager:
    def __init__(self, schema: SchemaBranch) -> None:
        self.schema = schema
        self.schema_hash = schema.get_hash()

        self._full_graphql_schema: GraphQLSchema | None = None
        self._graphql_types: dict[str, GraphQLTypes] = {}

        self._load_attribute_types()
        self._load_event_types()
        if config.SETTINGS.experimental_features.graphql_enums:
            self._load_all_enum_types(node_schemas=self.schema.get_all().values())
        self._load_node_interface()

    def get_graphql_types(self) -> dict[str, GraphQLTypes]:
        return self._graphql_types

    def get_graphql_schema(
        self,
        include_query: bool = True,
        include_mutation: bool = True,
        include_subscription: bool = True,
        include_types: bool = True,
    ) -> GraphQLSchema:
        if all((include_query, include_mutation, include_subscription, include_types)):
            if not self._full_graphql_schema:
                self._full_graphql_schema = self.generate()
            return self._full_graphql_schema
        return self.generate(
            include_query=include_query,
            include_mutation=include_mutation,
            include_subscription=include_subscription,
            include_types=include_types,
        )

    def generate(
        self,
        include_query: bool = True,
        include_mutation: bool = True,
        include_subscription: bool = True,
        include_types: bool = True,
    ) -> GraphQLSchema:
        with SCHEMA_GENERATE_GRAPHQL_METRICS.labels(self.schema.name).time():
            query = self.get_gql_query() if include_query else None

            if include_types:
                if not include_query:
                    self.generate_object_types()
                types_dict = self.get_all()
                types = list(types_dict.values())
            else:
                types = []

            mutation = self.get_gql_mutation() if include_mutation else None
            subscription = None
            if include_subscription:
                partial_graphene_schema = graphene.Schema(
                    query=query,
                    mutation=mutation,
                    types=types,
                    auto_camelcase=False,
                    directives=DIRECTIVES,
                )
                subscription = self.get_gql_subscription(partial_graphql_schema=partial_graphene_schema.graphql_schema)

            graphene_schema = graphene.Schema(
                query=query,
                mutation=mutation,
                subscription=subscription,
                types=types,
                auto_camelcase=False,
                directives=DIRECTIVES,
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

    def get_gql_subscription(self, partial_graphql_schema: graphene.Schema) -> type[InfrahubBaseSubscription]:
        class Subscription(InfrahubBaseSubscription):
            graphql_schema = partial_graphql_schema

        return Subscription

    def get_type(self, name: str) -> type[InfrahubObject]:
        if name in self._graphql_types and issubclass(
            self._graphql_types[name], BaseAttributeType | graphene.Interface | graphene.ObjectType
        ):
            return self._graphql_types[name]
        raise ValueError(f"Unable to find {name!r}")

    def get_mutation(self, name: str) -> type[InfrahubMutation]:
        if name in self._graphql_types and issubclass(self._graphql_types[name], InfrahubMutation):
            return self._graphql_types[name]
        raise ValueError(f"Unable to find {name!r}")

    def get_all(self) -> dict[str, GraphQLTypes]:
        return self._graphql_types

    def set_type(self, name: str, graphql_type: GraphQLTypes) -> None:
        self._graphql_types[name] = graphql_type

    def _load_attribute_types(self) -> None:
        for data_type in ATTRIBUTE_TYPES.values():
            self.set_type(name=data_type.get_graphql_type_name(), graphql_type=data_type.get_graphql_type())

    def _load_event_types(self) -> None:
        for event in EVENT_TYPES.values():
            self.set_type(name=event._meta.name, graphql_type=event)

    def _load_node_interface(self) -> None:
        node_interface_schema = GenericSchema(
            name="Node", namespace="Core", description="Interface for all nodes in Infrahub"
        )
        interface = self.generate_interface_object(schema=node_interface_schema, populate_cache=True)
        edged_interface = self.generate_graphql_edged_object(
            schema=node_interface_schema, node=interface, populate_cache=True
        )
        self.generate_graphql_paginated_object(schema=node_interface_schema, edge=edged_interface, populate_cache=True)

    def _load_all_enum_types(self, node_schemas: Iterable[MainSchemaTypes]) -> None:
        for node_schema in node_schemas:
            self._load_enum_type(node_schema=node_schema)

    def _load_enum_type(self, node_schema: MainSchemaTypes) -> None:
        for attr_schema in node_schema.attributes:
            if not attr_schema.enum:
                continue
            base_enum_name = get_enum_attribute_type_name(node_schema, attr_schema)
            enum_value_name = f"{base_enum_name}Value"
            graphene_enum = generate_graphql_enum(name=enum_value_name, options=attr_schema.enum)
            data_type_class_name = f"{base_enum_name}EnumType"

            default_value = None
            if attr_schema.default_value:
                for g_enum in graphene_enum:
                    if g_enum.value == attr_schema.default_value:
                        default_value = g_enum.name
                        break

            graphene_field = graphene.Field(graphene_enum, default_value=default_value)
            create_class = type(f"{base_enum_name}AttributeCreate", (BaseAttributeCreate,), {"value": graphene_field})
            update_class = type(f"{base_enum_name}AttributeUpdate", (BaseAttributeUpdate,), {"value": graphene_field})
            data_type_class: type[InfrahubDataType] = type(
                data_type_class_name,
                (InfrahubDataType,),
                {
                    "label": data_type_class_name,
                    "graphql": graphene.String,
                    "graphql_query": TextAttributeType,
                    "graphql_create": create_class,
                    "graphql_update": update_class,
                    "graphql_filter": graphene_enum,
                    "infrahub": String,
                },
            )
            self.set_type(
                name=data_type_class.get_graphql_type_name(),
                graphql_type=data_type_class.get_graphql_type(),
            )
            ATTRIBUTE_TYPES[base_enum_name] = data_type_class

    def _get_related_input_type(
        self, relationship: RelationshipSchema
    ) -> type[RelatedNodeInput | RelatedIPPrefixNodeInput | RelatedIPAddressNodeInput]:
        peer_schema = self.schema.get(name=relationship.peer, duplicate=False)
        if peer_schema.is_ip_prefix:
            return RelatedIPPrefixNodeInput

        if peer_schema.is_ip_address:
            return RelatedIPAddressNodeInput

        return RelatedNodeInput

    def generate_object_types(self) -> None:
        """Generate all GraphQL objects for the schema and store them in the internal registry."""

        full_schema = self.schema.get_all(duplicate=False)

        # Generate all GraphQL Interface  Object first and store them in the registry
        for node_schema in full_schema.values():
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
        for node_schema in full_schema.values():
            if isinstance(node_schema, NodeSchema | ProfileSchema | TemplateSchema):
                node_object_type = self.generate_graphql_object(schema=node_schema, populate_cache=True)
                node_type_edged = self.generate_graphql_edged_object(
                    schema=node_schema, node=node_object_type, populate_cache=True
                )
                nested_node_type_edged = self.generate_graphql_edged_object(
                    schema=node_schema,
                    node=node_object_type,
                    relation_property=relationship_property,
                    populate_cache=True,
                )

                self.generate_graphql_paginated_object(schema=node_schema, edge=node_type_edged, populate_cache=True)
                self.generate_graphql_paginated_object(
                    schema=node_schema, edge=nested_node_type_edged, nested=True, populate_cache=True
                )

        # Extend all types and related types with Relationships
        for node_name, node_schema in full_schema.items():
            node_type = self.get_type(name=node_name)

            for rel in node_schema.relationships:
                # Exclude hierarchical relationships, we will add them later
                if (
                    (isinstance(node_schema, NodeSchema) and node_schema.hierarchy)
                    or (isinstance(node_schema, GenericSchema) and node_schema.hierarchical)
                ) and rel.name in ("parent", "children", "ancestors", "descendants"):
                    continue

                peer_schema = self.schema.get(name=rel.peer, duplicate=False)
                if peer_schema.namespace == "Internal":
                    continue
                peer_filters = self.generate_filters(schema=peer_schema, top_level=False)

                if rel.cardinality == RelationshipCardinality.ONE:
                    peer_type = self.get_type(name=f"NestedEdged{peer_schema.kind}")
                    node_type._meta.fields[rel.name] = graphene.Field(
                        peer_type, resolver=single_relationship_resolver, required=True
                    )

                elif rel.cardinality == RelationshipCardinality.MANY:
                    peer_type = self.get_type(name=f"NestedPaginated{peer_schema.kind}")

                    if (isinstance(node_schema, NodeSchema) and node_schema.hierarchy) or (
                        isinstance(node_schema, GenericSchema) and node_schema.hierarchical
                    ):
                        peer_filters["include_descendants"] = graphene.Boolean()

                    node_type._meta.fields[rel.name] = graphene.Field(
                        peer_type, required=True, resolver=many_relationship_resolver, **peer_filters
                    )

            if (isinstance(node_schema, NodeSchema) and node_schema.hierarchy) or (
                isinstance(node_schema, GenericSchema) and node_schema.hierarchical
            ):
                if isinstance(node_schema, NodeSchema):
                    schema = self.schema.get(name=node_schema.hierarchy, duplicate=False)  # type: ignore[arg-type]
                    hierarchy_name = node_schema.hierarchy
                else:
                    schema = node_schema
                    hierarchy_name = node_schema.kind

                peer_filters = self.generate_filters(schema=schema, top_level=False)
                peer_type = self.get_type(name=f"NestedPaginated{hierarchy_name}")
                peer_type_edge = self.get_type(name=f"NestedEdged{hierarchy_name}")

                node_type._meta.fields["parent"] = graphene.Field(
                    peer_type_edge, required=True, resolver=single_relationship_resolver
                )
                node_type._meta.fields["children"] = graphene.Field(
                    peer_type, required=True, resolver=many_relationship_resolver, **peer_filters
                )
                node_type._meta.fields["ancestors"] = graphene.Field(
                    peer_type, required=True, resolver=ancestors_resolver, **peer_filters
                )
                node_type._meta.fields["descendants"] = graphene.Field(
                    peer_type, required=True, resolver=descendants_resolver, **peer_filters
                )

    def generate_query_mixin(self) -> type[object]:
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
                resolver=default_paginated_list_resolver
                if node_name not in [InfrahubKind.IPADDRESS, InfrahubKind.IPPREFIX]
                else ipam_paginated_list_resolver,
                required=True,
                **node_filters,
            )
            if node_name == InfrahubKind.GENERICACCOUNT:
                node_type = self.get_type(name=InfrahubKind.GENERICACCOUNT)
                class_attrs["AccountProfile"] = graphene.Field(node_type, resolver=account_resolver)

        return type("QueryMixin", (object,), class_attrs)

    def generate_mutation_mixin(self) -> type[object]:
        class_attrs: dict[str, Any] = {}

        full_schema = self.schema.get_all(duplicate=False)

        for node_schema in full_schema.values():
            if node_schema.namespace == "Internal":
                continue

            mutation_map: dict[str, type[InfrahubMutation]] = {
                InfrahubKind.ARTIFACTDEFINITION: InfrahubArtifactDefinitionMutation,
                InfrahubKind.REPOSITORY: InfrahubRepositoryMutation,
                InfrahubKind.READONLYREPOSITORY: InfrahubRepositoryMutation,
                InfrahubKind.PROPOSEDCHANGE: InfrahubProposedChangeMutation,
                InfrahubKind.GRAPHQLQUERY: InfrahubGraphQLQueryMutation,
                InfrahubKind.NAMESPACE: InfrahubIPNamespaceMutation,
                InfrahubKind.NUMBERPOOL: InfrahubNumberPoolMutation,
                InfrahubKind.MENUITEM: InfrahubCoreMenuMutation,
                InfrahubKind.STANDARDWEBHOOK: InfrahubWebhookMutation,
                InfrahubKind.CUSTOMWEBHOOK: InfrahubWebhookMutation,
                InfrahubKind.NODETRIGGERRULE: InfrahubTriggerRuleMutation,
                InfrahubKind.NODETRIGGERATTRIBUTEMATCH: InfrahubTriggerRuleMatchMutation,
                InfrahubKind.NODETRIGGERRELATIONSHIPMATCH: InfrahubTriggerRuleMatchMutation,
            }

            if isinstance(node_schema, NodeSchema) and node_schema.is_ip_prefix:
                base_class = InfrahubIPPrefixMutation
            elif isinstance(node_schema, NodeSchema) and node_schema.is_ip_address:
                base_class = InfrahubIPAddressMutation
            elif isinstance(node_schema, ProfileSchema):
                base_class = InfrahubProfileMutation
            else:
                base_class = mutation_map.get(node_schema.kind, InfrahubMutation)

            if isinstance(node_schema, NodeSchema | ProfileSchema | TemplateSchema):
                mutations = self.generate_graphql_mutations(schema=node_schema, base_class=base_class)

                class_attrs[f"{node_schema.kind}Create"] = mutations.create.Field()
                class_attrs[f"{node_schema.kind}Update"] = mutations.update.Field()
                class_attrs[f"{node_schema.kind}Upsert"] = mutations.upsert.Field()
                class_attrs[f"{node_schema.kind}Delete"] = mutations.delete.Field()

            elif (
                isinstance(node_schema, GenericSchema)
                and (len(node_schema.attributes) + len(node_schema.relationships)) > 0
            ):
                graphql_mutation_update_input = self.generate_graphql_mutation_update_input(node_schema)
                update = self.generate_graphql_mutation_update(
                    schema=node_schema, base_class=base_class, input_type=graphql_mutation_update_input
                )
                self.set_type(name=update._meta.name, graphql_type=update)
                class_attrs[f"{node_schema.kind}Update"] = update.Field()

        return type("MutationMixin", (object,), class_attrs)

    def generate_graphql_object(self, schema: MainSchemaTypes, populate_cache: bool = False) -> InfrahubObjectReference:
        """Generate a GraphQL object Type from a Infrahub NodeSchema."""

        interfaces: set[type[InfrahubObject]] = set()
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{schema.kind}{schema.get_hash()}".encode())

        if isinstance(schema, NodeSchema | ProfileSchema | TemplateSchema) and schema.inherit_from:
            for generic_name in sorted(schema.inherit_from):
                generic = self.get_type(name=generic_name)
                interfaces.add(generic)

        if isinstance(schema, NodeSchema):
            if not schema.inherit_from or InfrahubKind.GENERICGROUP not in schema.inherit_from:
                node_interface = self.get_type(name=InfrahubKind.NODE)
                interfaces.add(node_interface)

        meta_attrs = {
            "schema": schema,
            "name": schema.kind,
            "description": schema.description,
            "interfaces": interfaces,
        }

        main_attrs = {
            "id": graphene.Field(graphene.String, required=True, description="Unique identifier"),
            "hfid": graphene.Field(
                graphene.List(of_type=graphene.NonNull(graphene.String)),
                required=False,
                description="Human friendly identifier",
            ),
            "_updated_at": graphene.DateTime(required=False),
            "display_label": graphene.String(required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        for attr in schema.local_attributes:
            attr_kind = get_attr_kind(schema, attr)
            attr_type = self.get_type(name=get_attribute_type(kind=attr_kind).get_graphql_type_name())
            req = "" if attr.optional else " (required)"
            main_attrs[attr.name] = graphene.Field(attr_type, description=f"{attr.description}{req}")

        object_hash = md5hash.hexdigest()

        graphql_object = type(schema.kind, (InfrahubObject,), main_attrs)
        registry.set_object_type(reference=graphql_object, reference_hash=object_hash, schema_hash=self.schema_hash)

        if populate_cache:
            self.set_type(name=schema.kind, graphql_type=graphql_object)

        return InfrahubObjectReference(reference=graphql_object, reference_hash=object_hash)

    def generate_interface_object(self, schema: GenericSchema, populate_cache: bool = False) -> InterfaceReference:
        meta_attrs = {
            "name": schema.kind,
            "description": schema.description,
        }

        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"interface-{schema.kind}{schema.get_hash()}".encode())
        interface_hash = md5hash.hexdigest()

        main_attrs = {
            "id": graphene.Field(graphene.String, required=False, description="Unique identifier"),
            "hfid": graphene.Field(
                graphene.List(of_type=graphene.NonNull(graphene.String)),
                required=False,
                description="Human friendly identifier",
            ),
            "display_label": graphene.String(required=False),
        }

        for attr in schema.attributes:
            attr_kind = get_attr_kind(node_schema=schema, attr_schema=attr)
            attr_type = self.get_type(name=get_attribute_type(kind=attr_kind).get_graphql_type_name())
            main_attrs[attr.name] = graphene.Field(attr_type, description=attr.description)

        interface_object = registry.get_interface_type(reference_hash=interface_hash, schema_hash=self.schema_hash)
        if not interface_object:
            main_attrs["Meta"] = type("Meta", (object,), meta_attrs)
            interface_object = type(schema.kind, (InfrahubInterface,), main_attrs)

        interface_reference = InterfaceReference(reference=interface_object, reference_hash=interface_hash)
        registry.set_interface_type(reference=interface_reference, schema_hash=self.schema_hash)

        if populate_cache:
            self.set_type(name=schema.kind, graphql_type=interface_object)

        return interface_reference

    def define_relationship_property(self, data_source: type[InfrahubObject], data_owner: type[InfrahubObject]) -> None:
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
        self,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        base_class: type[InfrahubMutation],
    ) -> GraphqlMutations:
        graphql_mutation_create_input = self.generate_graphql_mutation_create_input(schema)
        graphql_mutation_update_input = self.generate_graphql_mutation_update_input(schema)
        graphql_mutation_upsert_input = self.generate_graphql_mutation_upsert_input(schema)

        create = self.generate_graphql_mutation_create(
            schema=schema, base_class=base_class, input_type=graphql_mutation_create_input
        )
        upsert = self.generate_graphql_mutation_create(
            schema=schema,
            base_class=base_class,
            input_type=graphql_mutation_upsert_input,
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

    def generate_graphql_mutation_create_input(
        self, schema: NodeSchema | ProfileSchema | TemplateSchema
    ) -> type[graphene.InputObjectType]:
        """Generate an InputObjectType Object from a Infrahub NodeSchema

        Example of Object Generated by this function:
            class StatusCreateInput(InputObjectType):
                id = String(required=False)
                label = InputField(StringAttributeCreate, required=True)
                slug = InputField(StringAttributeCreate, required=True)
                description = InputField(StringAttributeCreate, required=False)
        """
        attrs: dict[str, graphene.String | graphene.InputField] = {"id": graphene.String(required=False)}

        for attr in schema.attributes:
            if attr.read_only:
                continue

            attr_kind = get_attr_kind(schema, attr)
            attr_type = get_attribute_type(kind=attr_kind).get_graphql_create()

            attrs[attr.name] = graphene.InputField(attr_type, description=attr.description)

        for rel in schema.relationships:
            if rel.internal_peer or rel.read_only:
                continue

            input_type = self._get_related_input_type(relationship=rel)

            if rel.cardinality == RelationshipCardinality.ONE:
                attrs[rel.name] = graphene.InputField(input_type, description=rel.description)

            elif rel.cardinality == RelationshipCardinality.MANY:
                attrs[rel.name] = graphene.InputField(graphene.List(input_type), description=rel.description)

        input_name = f"{schema.kind}CreateInput"
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{input_name}{schema.get_hash()}".encode())
        input_hash = md5hash.hexdigest()
        mutation_input_type = registry.get_input_type(reference_hash=input_hash, schema_hash=self.schema_hash)
        if not mutation_input_type:
            mutation_input_type = type(input_name, (graphene.InputObjectType,), attrs)
            registry.set_input_type(
                reference=mutation_input_type, reference_hash=input_hash, schema_hash=self.schema_hash
            )

        return mutation_input_type

    def generate_graphql_mutation_update_input(self, schema: MainSchemaTypes) -> type[graphene.InputObjectType]:
        """Generate an InputObjectType Object from a Infrahub NodeSchema

        Example of Object Generated by this function:
            class StatusUpdateInput(InputObjectType):
                id = String(required=False)
                hfid = InputField(List(of_type=String), required=False)
                label = InputField(StringAttributeUpdate, required=False)
                slug = InputField(StringAttributeUpdate, required=False)
                description = InputField(StringAttributeUpdate, required=False)
        """
        attrs: dict[str, graphene.String | graphene.InputField | graphene.List] = {
            "id": graphene.String(required=False),
            "hfid": graphene.List(of_type=graphene.String, required=False),
        }

        for attr in schema.attributes:
            if attr.read_only:
                continue
            attr_kind = get_attr_kind(schema, attr)
            attr_type = get_attribute_type(kind=attr_kind).get_graphql_update()
            attrs[attr.name] = graphene.InputField(attr_type, required=False, description=attr.description)

        for rel in schema.relationships:
            if rel.internal_peer or rel.read_only:
                continue

            input_type = self._get_related_input_type(relationship=rel)

            if rel.cardinality == RelationshipCardinality.ONE:
                attrs[rel.name] = graphene.InputField(input_type, required=False, description=rel.description)

            elif rel.cardinality == RelationshipCardinality.MANY:
                attrs[rel.name] = graphene.InputField(
                    graphene.List(input_type), required=False, description=rel.description
                )

        input_name = f"{schema.kind}UpdateInput"
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{input_name}{schema.get_hash()}".encode())
        input_hash = md5hash.hexdigest()
        mutation_input_type = registry.get_input_type(reference_hash=input_hash, schema_hash=self.schema_hash)
        if not mutation_input_type:
            mutation_input_type = type(input_name, (graphene.InputObjectType,), attrs)
            registry.set_input_type(
                reference=mutation_input_type, reference_hash=input_hash, schema_hash=self.schema_hash
            )

        return mutation_input_type

    def generate_graphql_mutation_upsert_input(
        self, schema: NodeSchema | ProfileSchema | TemplateSchema
    ) -> type[graphene.InputObjectType]:
        """Generate an InputObjectType Object from a Infrahub NodeSchema

        Example of Object Generated by this function:
            class StatusUpsertInput(InputObjectType):
                id = String(required=False)
                hfid = InputField(List(of_type=String), required=False)
                label = InputField(StringAttributeUpdate, required=True)
                slug = InputField(StringAttributeUpdate, required=True)
                description = InputField(StringAttributeUpdate, required=False)
        """
        attrs: dict[str, graphene.String | graphene.InputField | graphene.List] = {
            "id": graphene.String(required=False),
            "hfid": graphene.List(of_type=graphene.String, required=False),
        }

        for attr in schema.attributes:
            if attr.read_only:
                continue

            attr_kind = get_attr_kind(schema, attr)
            attr_type = get_attribute_type(kind=attr_kind).get_graphql_update()

            # A Field is not required if explicitly indicated or if a default value has been provided
            required = not attr.optional if not attr.default_value else False

            attrs[attr.name] = graphene.InputField(attr_type, required=required, description=attr.description)

        for rel in schema.relationships:
            if rel.internal_peer or rel.read_only:
                continue

            input_type = self._get_related_input_type(relationship=rel)

            required = not rel.optional
            if rel.cardinality == RelationshipCardinality.ONE:
                attrs[rel.name] = graphene.InputField(input_type, required=required, description=rel.description)

            elif rel.cardinality == RelationshipCardinality.MANY:
                attrs[rel.name] = graphene.InputField(
                    graphene.List(input_type), required=required, description=rel.description
                )
        input_name = f"{schema.kind}UpsertInput"
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{input_name}{schema.get_hash()}".encode())
        input_hash = md5hash.hexdigest()
        mutation_input_type = registry.get_input_type(reference_hash=input_hash, schema_hash=self.schema_hash)
        if not mutation_input_type:
            mutation_input_type = type(input_name, (graphene.InputObjectType,), attrs)
            registry.set_input_type(
                reference=mutation_input_type, reference_hash=input_hash, schema_hash=self.schema_hash
            )

        return mutation_input_type

    def generate_graphql_mutation_create(
        self,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        input_type: type[graphene.InputObjectType],
        base_class: type[InfrahubMutation] = InfrahubMutation,
        mutation_type: str = "Create",
    ) -> type[InfrahubMutation]:
        """Generate a GraphQL Mutation to CREATE an object based on the specified NodeSchema."""
        name = f"{schema.kind}{mutation_type}"

        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{name}{schema.get_hash()}".encode())
        mutation_hash = md5hash.hexdigest()

        mutation_object = registry.get_mutation_type(reference_hash=mutation_hash, schema_hash=self.schema_hash)
        if not mutation_object:
            object_type = self.generate_graphql_object(schema=schema)

            main_attrs: dict[str, Any] = {"ok": graphene.Boolean(), "object": graphene.Field(object_type.reference)}

            meta_attrs: dict[str, Any] = {"schema": schema, "name": name, "description": schema.description}
            main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

            args_attrs = {"data": input_type(required=True), "context": ContextInput(required=False)}
            main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)
            mutation_object = type(name, (base_class,), main_attrs)
            registry.set_mutation_type(
                reference=mutation_object, reference_hash=mutation_hash, schema_hash=self.schema_hash
            )

        return mutation_object

    def generate_graphql_mutation_update(
        self,
        schema: MainSchemaTypes,
        input_type: type[graphene.InputObjectType],
        base_class: type[InfrahubMutation] = InfrahubMutation,
    ) -> type[InfrahubMutation]:
        """Generate a GraphQL Mutation to UPDATE an object based on the specified NodeSchema."""
        name = f"{schema.kind}Update"

        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{name}{schema.get_hash()}".encode())
        mutation_hash = md5hash.hexdigest()

        mutation_object = registry.get_mutation_type(reference_hash=mutation_hash, schema_hash=self.schema_hash)
        if not mutation_object:
            object_type = self.generate_graphql_object(schema=schema)

            main_attrs: dict[str, Any] = {"ok": graphene.Boolean(), "object": graphene.Field(object_type.reference)}

            meta_attrs: dict[str, Any] = {"schema": schema, "name": name, "description": schema.description}
            main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

            args_attrs = {"data": input_type(required=True), "context": ContextInput(required=False)}
            main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

            mutation_object = type(name, (base_class,), main_attrs)
            registry.set_mutation_type(
                reference=mutation_object, reference_hash=mutation_hash, schema_hash=self.schema_hash
            )

        return mutation_object

    def generate_graphql_mutation_delete(
        self, schema: NodeSchema | ProfileSchema | TemplateSchema, base_class: type[InfrahubMutation] = InfrahubMutation
    ) -> type[InfrahubMutation]:
        """Generate a GraphQL Mutation to DELETE an object based on the specified NodeSchema."""
        name = f"{schema.kind}Delete"
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{name}{schema.get_hash()}".encode())
        mutation_hash = md5hash.hexdigest()
        mutation_object = registry.get_mutation_type(reference_hash=mutation_hash, schema_hash=self.schema_hash)
        if not mutation_object:
            main_attrs: dict[str, Any] = {"ok": graphene.Boolean()}
            meta_attrs = {"schema": schema, "name": name, "description": schema.description}
            main_attrs["Meta"] = type("Meta", (object,), meta_attrs)
            args_attrs: dict[str, Any] = {"data": DeleteInput(required=True), "context": ContextInput(required=False)}
            main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)
            mutation_object = type(name, (base_class,), main_attrs)
            registry.set_mutation_type(
                reference=mutation_object, reference_hash=mutation_hash, schema_hash=self.schema_hash
            )

        return mutation_object

    def generate_filters(
        self, schema: MainSchemaTypes, top_level: bool = False, include_properties: bool = True
    ) -> dict[str, graphene.Scalar | graphene.List]:
        """Generate the GraphQL filters for a given Schema object.

        The generated filter will be different if we are at the top_level (query)
        or if we are generating the filter for a relationship inside a node.

        At the top, level it will be possible to query with a list of ID
        Inside a node, it's only possible to query with a single ID

        Args:
            schema (Union[NodeSchema, GenericSchema]): Schema to generate the filters
            top_level (bool, optional): Flag to indicate if are at the top level or not. Defaults to False.

        Returns:
            dict: A Dictionary containing all the filters with their name as the key and their Type as value
        """

        filters: dict[str, Any] = {"offset": graphene.Int(), "limit": graphene.Int(), "order": OrderInput()}
        default_filters: list[str] = list(filters.keys())

        filters["ids"] = graphene.List(graphene.ID)
        if not top_level:
            filters["isnull"] = graphene.Boolean()

        if schema.human_friendly_id and top_level:
            # HFID filter limited to top level because we can't filter on HFID for relationships (yet)
            filters["hfid"] = graphene.List(graphene.String)

        for attr in schema.attributes:
            attr_kind = get_attr_kind(node_schema=schema, attr_schema=attr)
            filters.update(
                get_attribute_type(kind=attr_kind).get_graphql_filters(
                    name=attr.name, include_properties=include_properties, include_isnull=top_level
                )
            )

        if top_level:
            filters.update(get_attribute_type().get_graphql_filters(name="any"))
            filters["partial_match"] = graphene.Boolean()

            if schema.kind in [InfrahubKind.IPADDRESS, InfrahubKind.IPPREFIX]:
                # This is only available for IPAM generics
                filters["include_available"] = graphene.Boolean()
                filters["kinds"] = graphene.List(graphene.NonNull(graphene.String))

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
        schema: MainSchemaTypes,
        node: InterfaceReference | InfrahubObjectReference,
        relation_property: type[InfrahubObject] | None = None,
        populate_cache: bool = False,
    ) -> InfrahubEdgedReference:
        """Generate a edged GraphQL object Type from a Infrahub NodeSchema for pagination."""

        object_name = f"Edged{schema.kind}"
        if relation_property:
            object_name = f"NestedEdged{schema.kind}"

        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{object_name}{schema.get_hash()}{node.reference_hash}".encode())
        edge_hash = md5hash.hexdigest()

        meta_attrs: dict[str, Any] = {
            "schema": schema,
            "name": object_name,
            "description": schema.description,
            "interfaces": set(),
        }

        main_attrs: dict[str, Any] = {
            "node": graphene.Field(node.reference, required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        if relation_property:
            main_attrs["properties"] = graphene.Field(relation_property, required=False)

        graphql_edged_object = registry.get_edge_type(reference_hash=edge_hash, schema_hash=self.schema_hash)
        if not graphql_edged_object:
            graphql_edged_object = type(object_name, (InfrahubObject,), main_attrs)
            registry.set_edge_type(
                reference=graphql_edged_object, reference_hash=edge_hash, schema_hash=self.schema_hash
            )

        if populate_cache:
            self.set_type(name=object_name, graphql_type=graphql_edged_object)

        return InfrahubEdgedReference(reference=graphql_edged_object, reference_hash=edge_hash)

    def generate_graphql_paginated_object(
        self, schema: MainSchemaTypes, edge: InfrahubEdgedReference, nested: bool = False, populate_cache: bool = False
    ) -> type[InfrahubObject]:
        """Generate a paginated GraphQL object Type from a Infrahub NodeSchema."""

        object_name = f"Paginated{schema.kind}"
        if nested:
            object_name = f"NestedPaginated{schema.kind}"

        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{object_name}{schema.get_hash()}{edge.reference_hash}".encode())
        paginated_hash = md5hash.hexdigest()

        meta_attrs: dict[str, Any] = {
            "schema": schema,
            "name": object_name,
            "description": schema.description,
            "default_resolver": default_resolver,
            "interfaces": set(),
        }

        main_attrs: dict[str, Any] = {
            "count": graphene.Int(required=True),
            "edges": graphene.List(of_type=graphene.NonNull(edge.reference), required=True),
            "permissions": graphene.Field(
                PaginatedObjectPermission, required=True, resolver=parent_field_name_resolver
            ),
        }

        graphql_paginated_object = registry.get_paginated_type(
            reference_hash=paginated_hash, schema_hash=self.schema_hash
        )
        if not graphql_paginated_object:
            main_attrs["Meta"] = type("Meta", (object,), meta_attrs)
            graphql_paginated_object = type(object_name, (InfrahubObject,), main_attrs)
            registry.set_paginated_type(
                reference=graphql_paginated_object, reference_hash=paginated_hash, schema_hash=self.schema_hash
            )

        if populate_cache:
            self.set_type(name=object_name, graphql_type=graphql_paginated_object)

        return graphql_paginated_object

    def generate_nested_interface_object(
        self,
        schema: GenericSchema,
        relation_property: graphene.ObjectType,
        base_interface: graphene.ObjectType,
        populate_cache: bool = False,
    ) -> type[InfrahubObject]:
        meta_attrs: dict[str, Any] = {
            "name": f"NestedEdged{schema.kind}",
            "schema": schema,
            "description": schema.description,
        }

        main_attrs: dict[str, Any] = {
            "node": graphene.Field(base_interface, required=False),
            "_updated_at": graphene.DateTime(required=False),
            "Meta": type("Meta", (object,), meta_attrs),
        }

        if relation_property:
            main_attrs["properties"] = graphene.Field(relation_property, required=False)

        object_name = f"NestedEdged{schema.kind}"
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{object_name}{schema.get_hash()}".encode())
        paginated_hash = md5hash.hexdigest()
        nested_interface_object = registry.get_paginated_type(
            reference_hash=paginated_hash, schema_hash=self.schema_hash
        )
        if not nested_interface_object:
            nested_interface_object = type(object_name, (InfrahubObject,), main_attrs)
            registry.set_paginated_type(
                reference=nested_interface_object, reference_hash=paginated_hash, schema_hash=self.schema_hash
            )

        if populate_cache:
            self.set_type(name=object_name, graphql_type=nested_interface_object)

        return nested_interface_object

    def generate_paginated_interface_object(
        self, schema: GenericSchema, base_interface: type[graphene.ObjectType]
    ) -> type[InfrahubObject]:
        object_name = f"NestedPaginated{schema.kind}"
        md5hash = hashlib.md5(usedforsecurity=False)
        md5hash.update(f"{object_name}{schema.get_hash()}".encode())
        paginated_hash = md5hash.hexdigest()

        nested_interface_object = registry.get_paginated_type(
            reference_hash=paginated_hash, schema_hash=self.schema_hash
        )
        if not nested_interface_object:
            meta_attrs: dict[str, Any] = {
                "name": object_name,
                "schema": schema,
                "description": schema.description,
            }

            main_attrs: dict[str, Any] = {
                "count": graphene.Int(required=True),
                "edges": graphene.List(of_type=graphene.NonNull(base_interface)),
                "Meta": type("Meta", (object,), meta_attrs),
            }

            nested_interface_object = type(object_name, (InfrahubObject,), main_attrs)
            registry.set_paginated_type(
                reference=nested_interface_object, reference_hash=paginated_hash, schema_hash=self.schema_hash
            )

        return nested_interface_object


registry._register_manager(manager=GraphQLSchemaManager)
