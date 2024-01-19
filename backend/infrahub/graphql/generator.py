from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union

import graphene

from infrahub.core import get_branch, registry
from infrahub.core.constants import InfrahubKind, RelationshipKind
from infrahub.core.schema import GenericSchema, GroupSchema, NodeSchema
from infrahub.graphql.mutations.graphql_query import InfrahubGraphQLQueryMutation
from infrahub.types import ATTRIBUTE_TYPES, get_attribute_type

from .mutations import (
    InfrahubArtifactDefinitionMutation,
    InfrahubMutation,
    InfrahubProposedChangeMutation,
    InfrahubRepositoryMutation,
)
from .resolver import (
    ancestors_resolver,
    default_resolver,
    descendants_resolver,
    many_relationship_resolver,
    single_relationship_resolver,
)
from .schema import account_resolver, default_paginated_list_resolver
from .types import InfrahubInterface, InfrahubObject, InfrahubUnion, RelatedNodeInput

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# pylint: disable=protected-access,too-many-locals,too-many-lines


class DeleteInput(graphene.InputObjectType):
    id = graphene.String(required=True)


def load_attribute_types_in_registry(branch: Branch):
    for data_type in ATTRIBUTE_TYPES.values():
        registry.set_graphql_type(
            name=data_type.get_graphql_type_name(), graphql_type=data_type.get_graphql_type(), branch=branch.name
        )


def load_node_interface(branch: Branch):
    node_interface_schema = GenericSchema(
        name="Node", namespace="Core", description="Interface for all nodes in Infrahub"
    )
    interface = generate_interface_object(schema=node_interface_schema, branch=branch)
    edged_interface = generate_graphql_edged_object(schema=node_interface_schema, node=interface, branch=branch)
    paginated_interface = generate_graphql_paginated_object(schema=node_interface_schema, edge=edged_interface)

    registry.set_graphql_type(name=interface._meta.name, graphql_type=interface, branch=branch.name)
    registry.set_graphql_type(name=edged_interface._meta.name, graphql_type=edged_interface, branch=branch.name)
    registry.set_graphql_type(name=paginated_interface._meta.name, graphql_type=paginated_interface, branch=branch.name)


async def generate_object_types(db: InfrahubDatabase, branch: Union[Branch, str]):  # pylint: disable=too-many-branches,too-many-statements
    """Generate all GraphQL objects for the schema and store them in the internal registry."""

    branch = await get_branch(db=db, branch=branch)

    full_schema = await registry.schema.get_full_safe(branch=branch)

    group_memberships = defaultdict(list)

    load_attribute_types_in_registry(branch=branch)
    load_node_interface(branch=branch)

    # Generate all GraphQL Interface  Object first and store them in the registry
    for node_name, node_schema in full_schema.items():
        if not isinstance(node_schema, GenericSchema):
            continue
        interface = generate_interface_object(schema=node_schema, branch=branch)
        edged_interface = generate_graphql_edged_object(schema=node_schema, node=interface, branch=branch)
        paginated_interface = generate_graphql_paginated_object(schema=node_schema, edge=edged_interface)

        registry.set_graphql_type(name=interface._meta.name, graphql_type=interface, branch=branch.name)
        registry.set_graphql_type(name=edged_interface._meta.name, graphql_type=edged_interface, branch=branch.name)
        registry.set_graphql_type(
            name=paginated_interface._meta.name, graphql_type=paginated_interface, branch=branch.name
        )

    # Define DataOwner and DataOwner
    data_source = registry.get_graphql_type(name="LineageSource", branch=branch)
    data_owner = registry.get_graphql_type(name="LineageOwner", branch=branch)
    define_relationship_property(branch=branch, data_source=data_source, data_owner=data_owner)
    relationship_property = registry.get_graphql_type(name="RelationshipProperty", branch=branch)
    for data_type in ATTRIBUTE_TYPES.values():
        gql_type = registry.get_graphql_type(name=data_type.get_graphql_type_name(), branch=branch)
        gql_type._meta.fields["source"] = graphene.Field(data_source)
        gql_type._meta.fields["owner"] = graphene.Field(data_owner)

    # Generate all Nested, Edged and NestedEdged Interfaces and store them in the registry
    for node_name, node_schema in full_schema.items():
        if not isinstance(node_schema, GenericSchema):
            continue

        node_interface = registry.get_graphql_type(name=node_name, branch=branch)

        nested_edged_interface = generate_nested_interface_object(
            schema=node_schema,
            base_interface=node_interface,
            relation_property=relationship_property,
        )

        nested_interface = generate_paginated_interface_object(
            schema=node_schema,
            base_interface=nested_edged_interface,
        )

        registry.set_graphql_type(name=nested_interface._meta.name, graphql_type=nested_interface, branch=branch.name)
        registry.set_graphql_type(
            name=nested_edged_interface._meta.name, graphql_type=nested_edged_interface, branch=branch.name
        )

    # Generate all GraphQL ObjectType, Nested, Paginated & NestedPaginated and store them in the registry
    for node_name, node_schema in full_schema.items():
        if isinstance(node_schema, NodeSchema):
            node_type = generate_graphql_object(schema=node_schema, branch=branch)
            node_type_edged = generate_graphql_edged_object(schema=node_schema, node=node_type, branch=branch)
            nested_node_type_edged = generate_graphql_edged_object(
                schema=node_schema, node=node_type, relation_property=relationship_property, branch=branch
            )

            node_type_paginated = generate_graphql_paginated_object(schema=node_schema, edge=node_type_edged)
            node_type_nested_paginated = generate_graphql_paginated_object(
                schema=node_schema, edge=nested_node_type_edged, nested=True
            )

            registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=branch.name)
            registry.set_graphql_type(name=node_type_edged._meta.name, graphql_type=node_type_edged, branch=branch.name)
            registry.set_graphql_type(
                name=nested_node_type_edged._meta.name, graphql_type=nested_node_type_edged, branch=branch.name
            )

            registry.set_graphql_type(
                name=node_type_paginated._meta.name, graphql_type=node_type_paginated, branch=branch.name
            )
            registry.set_graphql_type(
                name=node_type_nested_paginated._meta.name, graphql_type=node_type_nested_paginated, branch=branch.name
            )

            # Register this model to all the groups it belongs to.
            # if node_schema.groups:
            #     for group_name in node_schema.groups:
            #         group_memberships[group_name].append(f"Related{node_schema.kind}")

    # Generate all the Groups with associated ObjectType / RelatedObjectType
    for node_name, node_schema in full_schema.items():
        if (
            not isinstance(node_schema, GroupSchema)
            or node_name not in group_memberships
            or not group_memberships[node_name]
        ):
            continue
        group = generate_union_object(schema=node_schema, members=group_memberships.get(node_name, []), branch=branch)
        registry.set_graphql_type(name=group._meta.name, graphql_type=group, branch=branch.name)

    # Extend all types and related types with Relationships
    for node_name, node_schema in full_schema.items():
        if not isinstance(node_schema, (NodeSchema, GenericSchema)):
            continue

        node_type = registry.get_graphql_type(name=node_name, branch=branch.name)

        for rel in node_schema.relationships:
            peer_schema = await rel.get_peer_schema(branch=branch)
            if not isinstance(peer_schema, GroupSchema) and peer_schema.namespace == "Internal":
                continue
            peer_filters = await generate_filters(db=db, schema=peer_schema, top_level=False)

            if rel.cardinality == "one":
                if isinstance(peer_schema, GroupSchema):
                    peer_type = registry.get_graphql_type(name=peer_schema.kind, branch=branch.name)
                else:
                    peer_type = registry.get_graphql_type(name=f"NestedEdged{peer_schema.kind}", branch=branch.name)
                node_type._meta.fields[rel.name] = graphene.Field(peer_type, resolver=single_relationship_resolver)

            elif rel.cardinality == "many":
                if isinstance(peer_schema, GroupSchema):
                    peer_type = registry.get_graphql_type(name=peer_schema.kind, branch=branch.name)
                else:
                    peer_type = registry.get_graphql_type(name=f"NestedPaginated{peer_schema.kind}", branch=branch.name)

                if (isinstance(node_schema, NodeSchema) and node_schema.hierarchy) or (
                    isinstance(node_schema, GenericSchema) and node_schema.hierarchical
                ):
                    peer_filters["include_descendants"] = graphene.Boolean()

                node_type._meta.fields[rel.name] = graphene.Field(
                    peer_type, required=False, resolver=many_relationship_resolver, **peer_filters
                )

        if isinstance(node_schema, NodeSchema) and node_schema.hierarchy:
            schema = registry.schema.get(name=node_schema.hierarchy, branch=branch)

            peer_filters = await generate_filters(db=db, schema=schema, top_level=False)
            peer_type = registry.get_graphql_type(name=f"NestedPaginated{node_schema.hierarchy}", branch=branch.name)

            node_type._meta.fields["ancestors"] = graphene.Field(
                peer_type, required=False, resolver=ancestors_resolver, **peer_filters
            )
            node_type._meta.fields["descendants"] = graphene.Field(
                peer_type, required=False, resolver=descendants_resolver, **peer_filters
            )


async def generate_query_mixin(db: InfrahubDatabase, branch: Union[Branch, str] = None) -> Type[object]:
    class_attrs = {}

    full_schema = await registry.schema.get_full_safe(branch=branch)

    # Generate all Graphql objectType and store them in the registry
    await generate_object_types(db=db, branch=branch)

    for node_name, node_schema in full_schema.items():
        if not isinstance(node_schema, (NodeSchema, GenericSchema)):
            continue

        if node_schema.namespace == "Internal":
            continue

        node_type = registry.get_graphql_type(name=f"Paginated{node_name}", branch=branch)
        node_filters = await generate_filters(db=db, schema=node_schema, top_level=True)

        class_attrs[node_schema.kind] = graphene.Field(
            node_type,
            resolver=default_paginated_list_resolver,
            **node_filters,
        )
        if node_name == InfrahubKind.ACCOUNT:
            node_type = registry.get_graphql_type(name=InfrahubKind.ACCOUNT, branch=branch)
            class_attrs["AccountProfile"] = graphene.Field(
                node_type,
                resolver=account_resolver,
            )

    return type("QueryMixin", (object,), class_attrs)


async def generate_mutation_mixin(db: InfrahubDatabase, branch: Union[Branch, str] = None) -> Type[object]:
    class_attrs = {}

    branch = await get_branch(branch=branch, db=db)

    full_schema = registry.schema.get_full(branch=branch)

    for node_schema in full_schema.values():
        if not isinstance(node_schema, NodeSchema):
            continue

        if node_schema.namespace == "Internal":
            continue

        base_class = InfrahubMutation
        mutation_map = {
            InfrahubKind.ARTIFACTDEFINITION: InfrahubArtifactDefinitionMutation,
            InfrahubKind.REPOSITORY: InfrahubRepositoryMutation,
            InfrahubKind.READONLYREPOSITORY: InfrahubRepositoryMutation,
            InfrahubKind.PROPOSEDCHANGE: InfrahubProposedChangeMutation,
            InfrahubKind.GRAPHQLQUERY: InfrahubGraphQLQueryMutation,
        }
        base_class = mutation_map.get(node_schema.kind, InfrahubMutation)

        mutations = generate_graphql_mutations(branch=branch, schema=node_schema, base_class=base_class)

        class_attrs[f"{node_schema.kind}Create"] = mutations.create.Field()
        class_attrs[f"{node_schema.kind}Update"] = mutations.update.Field()
        class_attrs[f"{node_schema.kind}Upsert"] = mutations.upsert.Field()
        class_attrs[f"{node_schema.kind}Delete"] = mutations.delete.Field()

    return type("MutationMixin", (object,), class_attrs)


def generate_graphql_object(schema: NodeSchema, branch: Branch) -> Type[InfrahubObject]:
    """Generate a GraphQL object Type from a Infrahub NodeSchema."""

    meta_attrs = {
        "schema": schema,
        "name": schema.kind,
        "description": schema.description,
        "interfaces": set(),
    }

    if schema.inherit_from:
        for generic in schema.inherit_from:
            generic = registry.get_graphql_type(name=generic, branch=branch.name)
            meta_attrs["interfaces"].add(generic)

    if not schema.inherit_from or InfrahubKind.GENERICGROUP not in schema.inherit_from:
        node_interface = registry.get_graphql_type(name="CoreNode", branch=branch.name)
        meta_attrs["interfaces"].add(node_interface)

    main_attrs = {
        "id": graphene.String(required=True),
        "_updated_at": graphene.DateTime(required=False),
        "display_label": graphene.String(required=False),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    for attr in schema.local_attributes:
        attr_type = registry.get_graphql_type(
            name=get_attribute_type(kind=attr.kind).get_graphql_type_name(), branch=branch.name
        )
        main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

    return type(schema.kind, (InfrahubObject,), main_attrs)


def define_relationship_property(branch: Branch, data_source: InfrahubObject, data_owner: InfrahubObject) -> None:
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

    registry.set_graphql_type(name=type_name, graphql_type=relationship_property, branch=branch.name)


def generate_graphql_edged_object(
    schema: NodeSchema,
    node: Type[InfrahubObject],
    branch: Branch,  # pylint: disable=unused-argument
    relation_property: Optional[InfrahubObject] = None,
) -> Type[InfrahubObject]:
    """Generate a edged GraphQL object Type from a Infrahub NodeSchema for pagination."""

    object_name = f"Edged{schema.kind}"
    if relation_property:
        object_name = f"NestedEdged{schema.kind}"

    meta_attrs = {
        "schema": schema,
        "name": object_name,
        "description": schema.description,
        "interfaces": set(),
    }

    main_attrs = {
        "node": graphene.Field(node, required=False),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    if relation_property:
        main_attrs["properties"] = graphene.Field(relation_property)

    return type(object_name, (InfrahubObject,), main_attrs)


def generate_graphql_paginated_object(
    schema: NodeSchema, edge: Type[InfrahubObject], nested: bool = False
) -> Type[InfrahubObject]:
    """Generate a paginated GraphQL object Type from a Infrahub NodeSchema."""

    object_name = f"Paginated{schema.kind}"
    if nested:
        object_name = f"NestedPaginated{schema.kind}"

    meta_attrs = {
        "schema": schema,
        "name": object_name,
        "description": schema.description,
        "default_resolver": default_resolver,
        "interfaces": set(),
    }

    main_attrs = {
        "count": graphene.Int(required=False),
        "edges": graphene.List(of_type=edge),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    return type(object_name, (InfrahubObject,), main_attrs)


def generate_union_object(
    schema: GroupSchema,
    members: List,
    branch: Branch,
) -> Type[graphene.Union]:
    types = [registry.get_graphql_type(name=member, branch=branch.name) for member in members]

    if not types:
        return None

    meta_attrs = {
        "schema": schema,
        "name": schema.kind,
        "description": schema.description,
        "types": types,
    }

    main_attrs = {
        "Meta": type("Meta", (object,), meta_attrs),
    }

    return type(schema.kind, (InfrahubUnion,), main_attrs)


def generate_interface_object(schema: GenericSchema, branch: Branch) -> Type[graphene.Interface]:
    meta_attrs = {
        "name": schema.kind,
        "description": schema.description,
    }

    main_attrs = {
        "display_label": graphene.String(required=False),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    for attr in schema.attributes:
        attr_type = registry.get_graphql_type(
            name=get_attribute_type(kind=attr.kind).get_graphql_type_name(), branch=branch.name
        )
        main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

    main_attrs["id"] = graphene.Field(graphene.String, required=False, description="Unique identifier")

    return type(schema.kind, (InfrahubInterface,), main_attrs)


def generate_nested_interface_object(
    schema: GenericSchema,
    relation_property: graphene.ObjectType,
    base_interface: graphene.ObjectType,
) -> Type[InfrahubObject]:
    meta_attrs = {
        "name": f"NestedEdged{schema.kind}",
        "schema": schema,
        "description": schema.description,
    }

    main_attrs = {
        "node": graphene.Field(base_interface, required=False),
        "_updated_at": graphene.DateTime(required=False),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    if relation_property:
        main_attrs["properties"] = graphene.Field(relation_property)

    return type(f"NestedEdged{schema.kind}", (InfrahubObject,), main_attrs)


def generate_paginated_interface_object(
    schema: GenericSchema,
    base_interface: Type[graphene.ObjectType],
) -> Type[InfrahubObject]:
    meta_attrs = {
        "name": f"NestedPaginated{schema.kind}",
        "schema": schema,
        "description": schema.description,
    }

    main_attrs = {
        "count": graphene.Int(required=False),
        "edges": graphene.List(of_type=base_interface),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    return type(f"NestedPaginated{schema.kind}", (InfrahubObject,), main_attrs)


@dataclass
class GraphqlMutations:
    create: Type[InfrahubMutation]
    update: Type[InfrahubMutation]
    upsert: Type[InfrahubMutation]
    delete: Type[InfrahubMutation]


def generate_graphql_mutations(
    schema: NodeSchema, base_class: type[InfrahubMutation], branch: Branch
) -> GraphqlMutations:
    graphql_mutation_create_input = generate_graphql_mutation_create_input(schema)
    graphql_mutation_update_input = generate_graphql_mutation_update_input(schema)

    create = generate_graphql_mutation_create(
        branch=branch, schema=schema, base_class=base_class, input_type=graphql_mutation_create_input
    )
    upsert = generate_graphql_mutation_create(
        branch=branch,
        schema=schema,
        base_class=base_class,
        input_type=graphql_mutation_create_input,
        mutation_type="Upsert",
    )
    update = generate_graphql_mutation_update(
        branch=branch, schema=schema, base_class=base_class, input_type=graphql_mutation_update_input
    )
    delete = generate_graphql_mutation_delete(branch=branch, schema=schema, base_class=base_class)

    registry.set_graphql_type(name=create._meta.name, graphql_type=create, branch=branch.name)
    registry.set_graphql_type(name=update._meta.name, graphql_type=update, branch=branch.name)
    registry.set_graphql_type(name=upsert._meta.name, graphql_type=upsert, branch=branch.name)
    registry.set_graphql_type(name=delete._meta.name, graphql_type=delete, branch=branch.name)

    return GraphqlMutations(create=create, update=update, upsert=upsert, delete=delete)


def generate_graphql_mutation_create_input(schema: NodeSchema) -> Type[graphene.InputObjectType]:
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

        attr_type = get_attribute_type(kind=attr.kind).get_graphql_input()

        # A Field is not required if explicitely indicated or if a default value has been provided
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


def generate_graphql_mutation_update_input(schema: NodeSchema) -> Type[graphene.InputObjectType]:
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
        attr_type = get_attribute_type(kind=attr.kind).get_graphql_input()
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
    schema: NodeSchema,
    branch: Branch,
    input_type: Type[graphene.InputObjectType],
    base_class: type[InfrahubMutation] = InfrahubMutation,
    mutation_type: str = "Create",
) -> Type[InfrahubMutation]:
    """Generate a GraphQL Mutation to CREATE an object based on the specified NodeSchema."""
    name = f"{schema.kind}{mutation_type}"

    object_type = generate_graphql_object(schema=schema, branch=branch)

    main_attrs = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": input_type(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (base_class,), main_attrs)


def generate_graphql_mutation_update(
    schema: NodeSchema,
    branch: Branch,
    input_type: Type[graphene.InputObjectType],
    base_class: type[InfrahubMutation] = InfrahubMutation,
) -> Type[InfrahubMutation]:
    """Generate a GraphQL Mutation to UPDATE an object based on the specified NodeSchema."""
    name = f"{schema.kind}Update"

    object_type = generate_graphql_object(schema=schema, branch=branch)

    main_attrs = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": input_type(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (base_class,), main_attrs)


def generate_graphql_mutation_delete(
    schema: NodeSchema,
    base_class: type[InfrahubMutation] = InfrahubMutation,
    branch: Union[Branch, str] = None,  # pylint: disable=unused-argument
) -> Type[InfrahubMutation]:
    """Generate a GraphQL Mutation to DELETE an object based on the specified NodeSchema."""
    name = f"{schema.kind}Delete"

    main_attrs: Dict[str, Any] = {"ok": graphene.Boolean()}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": DeleteInput(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (base_class,), main_attrs)


async def generate_filters(
    db: InfrahubDatabase,
    schema: Union[NodeSchema, GenericSchema, GroupSchema],
    top_level: bool = False,
    include_properties: bool = True,
) -> Dict[str, Union[graphene.Scalar, graphene.List]]:
    """Generate the GraphQL filters for a given Schema object.

    The generated filter will be different if we are at the top_level (query)
    or if we are generating the filter for a relationship inside a node.

    At the top, level it will be possible to query with a list of ID
    Inside a node, it's only possible to query with a single ID

    Args:
        session (AsyncSession): Active session to the database
        schema (Union[NodeSchema, GenericSchema, GroupSchema]): Schema to generate the filters
        top_level (bool, optional): Flag to indicate if are at the top level or not. Defaults to False.

    Returns:
        dict: A Dictionnary containing all the filters with their name as the key and their Type as value
    """

    filters: Dict[str, Any] = {"offset": graphene.Int(), "limit": graphene.Int()}
    default_filters: List[str] = list(filters.keys())

    filters["ids"] = graphene.List(graphene.ID)

    if isinstance(schema, GroupSchema):
        return filters

    for attr in schema.attributes:
        filters.update(
            get_attribute_type(kind=attr.kind).get_graphql_filters(
                name=attr.name, include_properties=include_properties
            )
        )

    if top_level:
        filters.update(get_attribute_type().get_graphql_filters(name="any"))

    if not top_level:
        return filters

    for rel in schema.relationships:
        peer_schema = await rel.get_peer_schema()

        if not isinstance(peer_schema, (NodeSchema, GenericSchema)):
            continue

        if peer_schema.namespace == "Internal":
            continue

        if rel.kind == RelationshipKind.GROUP:
            peer_filters = await generate_filters(db=db, schema=peer_schema, top_level=False, include_properties=False)
        else:
            peer_filters = await generate_filters(db=db, schema=peer_schema, top_level=False)

        for key, value in peer_filters.items():
            if key in default_filters:
                continue
            filters[f"{rel.name}__{key}"] = value

    return filters
