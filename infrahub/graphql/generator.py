from __future__ import annotations

from typing import TYPE_CHECKING, Tuple, Type, Union

import graphene
from graphene.types.generic import GenericScalar

import infrahub.config as config
from infrahub.core import get_branch, registry
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema

from .mutations import (
    AnyAttributeInput,
    BoolAttributeInput,
    InfrahubMutation,
    InfrahubRepositoryMutation,
    IntAttributeInput,
    StringAttributeInput,
)
from .query import (
    AnyAttributeType,
    BoolAttributeType,
    InfrahubObject,
    IntAttributeType,
    StrAttributeType,
)
from .schema import default_list_resolver
from .utils import extract_fields

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch

TYPES_MAPPING_INFRAHUB_GRAPHQL = {
    "String": StrAttributeType,
    "Integer": IntAttributeType,
    "Boolean": BoolAttributeType,
    "Any": AnyAttributeType,
}

INPUT_TYPES_MAPPING_INFRAHUB_GRAPHQL = {
    "String": StringAttributeInput,
    "Integer": IntAttributeInput,
    "Boolean": BoolAttributeInput,
    "Any": AnyAttributeInput,
}

FILTER_TYPES_MAPPING_INFRAHUB_GRAPHQL = {
    "String": graphene.String,
    "Integer": graphene.Int,
    "Boolean": graphene.Boolean,
    "Any": GenericScalar,
}


class DeleteInput(graphene.InputObjectType):
    id = graphene.String(required=True)


class RelatedNodeInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    _relation__is_visible = graphene.Boolean(required=False)
    _relation__is_protected = graphene.Boolean(required=False)
    _relation__owner = graphene.String(required=False)
    _relation__source = graphene.String(required=False)


async def default_resolver(*args, **kwargs):
    """Not sure why but the default resolver returns sometime 4 positional args and sometime 2.

    When it returns 4, they are organized as follow
        - field name
        - ???
        - parent
        - info
    When it returns 2, they are organized as follow
        - parent
        - info
    """

    parent = None
    info = None
    field_name = None

    if len(args) == 4:
        parent = args[2]
        info = args[3]
        field_name = args[0]
    elif len(args) == 2:
        parent = args[0]
        info = args[1]
        field_name = info.field_name
    else:
        raise ValueError(f"expected either 2 or 4 args for default_resolver, got {len(args)}")

    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # If the field is an attribute, return its value directly
    if field_name not in node_schema.relationship_names:
        return parent.get(field_name, None)

    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch = info.context.get("infrahub_branch")
    account = info.context.get("infrahub_account", None)
    session = info.context.get("infrahub_session")
    db = info.context.get("infrahub_database")

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {f"{info.field_name}__{key}": value for key, value in kwargs.items() if "__" in key and value}

    async with db.session(database=config.SETTINGS.database.database) as new_session:
        objs = await NodeManager.query_peers(
            session=new_session,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            at=at,
            branch=branch,
            account=account,
            include_source=True,
        )

    if node_rel.cardinality == "many":
        return [await obj.to_graphql(session=session, fields=fields) for obj in objs]

    # If cardinality is one
    if not objs:
        return None

    return await objs[0].to_graphql(session=session, fields=fields)


async def generate_object_types(session: AsyncSession, branch: Union[Branch, str] = None):
    """Generate all GraphQL objects for the schema and store them in the internal registry."""

    branch = await get_branch(session=session, branch=branch)

    full_schema = await registry.get_full_schema(session=session, branch=branch)

    # Generate all Graphql ObjectType & RelatedObjectType and store them in the registry
    for node_name, node_schema in full_schema.items():
        node_type = generate_graphql_object(schema=node_schema)
        related_node_type = generate_related_graphql_object(schema=node_schema)
        await registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=branch.name)
        await registry.set_graphql_type(
            name=related_node_type._meta.name, graphql_type=related_node_type, branch=branch.name
        )

    # Extend all types and related types with Relationships
    for node_name, node_schema in full_schema.items():
        node_type = await registry.get_graphql_type(session=session, name=node_name, branch=branch)
        related_node_type = await registry.get_graphql_type(session=session, name=f"Related{node_name}", branch=branch)

        for rel in node_schema.relationships:

            peer_schema = await rel.get_peer_schema(session=session)
            peer_filters = await generate_filters(session=session, schema=peer_schema, attribute_only=True)
            peer_type = await registry.get_graphql_type(
                session=session, name=f"Related{peer_schema.kind}", branch=branch
            )

            if rel.cardinality == "one":
                node_type._meta.fields[rel.name] = graphene.Field(peer_type, resolver=default_resolver)
                related_node_type._meta.fields[rel.name] = graphene.Field(peer_type, resolver=default_resolver)

            elif rel.cardinality == "many":
                node_type._meta.fields[rel.name] = graphene.Field.mounted(graphene.List(peer_type, **peer_filters))
                related_node_type._meta.fields[rel.name] = graphene.Field.mounted(
                    graphene.List(peer_type, **peer_filters)
                )


async def generate_query_mixin(session: AsyncSession, branch: Union[Branch, str] = None) -> Type[object]:

    class_attrs = {}

    full_schema = await registry.get_full_schema(session=session, branch=branch)

    # Generate all Graphql objectType and store them in the registry
    await generate_object_types(session=session)

    for node_name, node_schema in full_schema.items():

        node_type = await registry.get_graphql_type(session=session, name=node_name, branch=branch)
        node_filters = await generate_filters(session=session, schema=node_schema)

        class_attrs[node_schema.name] = graphene.List(
            node_type,
            resolver=default_list_resolver,
            **node_filters,
        )

    return type("QueryMixin", (object,), class_attrs)


async def generate_mutation_mixin(session: AsyncSession, branch: Union[Branch, str] = None) -> Type[object]:

    class_attrs = {}

    full_schema = await registry.get_full_schema(session=session, branch=branch)

    for node_schema in full_schema.values():

        base_class = InfrahubMutation
        if node_schema.name == "repository":
            base_class = InfrahubRepositoryMutation

        create, update, delete = generate_graphql_mutations(schema=node_schema, base_class=base_class)

        class_attrs[f"{node_schema.name}_create"] = create.Field()
        class_attrs[f"{node_schema.name}_update"] = update.Field()
        class_attrs[f"{node_schema.name}_delete"] = delete.Field()

    return type("MutationMixin", (object,), class_attrs)


def generate_graphql_object(schema: NodeSchema) -> Type[InfrahubObject]:
    """Generate a GraphQL object Type from a Infrahub NodeSchema."""

    meta_attrs = {
        "schema": schema,
        "name": schema.kind,
        "description": schema.description,
        "default_resolver": default_resolver,
    }

    main_attrs = {
        "id": graphene.String(required=True),
        "_updated_at": graphene.DateTime(required=False),
        "Meta": type("Meta", (object,), meta_attrs),
    }

    for attr in schema.attributes:
        attr_type = TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]
        main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

    return type(schema.kind, (InfrahubObject,), main_attrs)


def generate_related_graphql_object(schema: NodeSchema) -> Type[InfrahubObject]:
    """Generate a GraphQL object Type from a Infrahub NodeSchema for a Related Node."""

    meta_attrs = {
        "schema": schema,
        "name": f"Related{schema.kind}",
        "description": schema.description,
        "default_resolver": default_resolver,
    }

    main_attrs = {
        "id": graphene.String(required=True),
        "_updated_at": graphene.DateTime(required=False),
        "_relation__updated_at": graphene.DateTime(required=False),
        "_relation__is_visible": graphene.Boolean(required=False),
        "_relation__is_protected": graphene.Boolean(required=False),
        "_relation__owner": graphene.Field("infrahub.graphql.query.AccountType", required=False),
        "_relation__source": graphene.Field("infrahub.graphql.query.AccountType", required=False),
        "Meta": type("Meta", (object,), meta_attrs),
    }
    for attr in schema.attributes:

        attr_type = TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]
        main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

    return type(f"Related{schema.kind}", (InfrahubObject,), main_attrs)


def generate_graphql_mutations(
    schema: NodeSchema, base_class: type[InfrahubMutation]
) -> Tuple[Type[InfrahubMutation], Type[InfrahubMutation], Type[InfrahubMutation]]:

    create = generate_graphql_mutation_create(schema=schema, base_class=base_class)
    update = generate_graphql_mutation_update(schema=schema, base_class=base_class)
    delete = generate_graphql_mutation_delete(schema=schema, base_class=base_class)

    return create, update, delete


def generate_graphql_mutation_create_input(schema: NodeSchema) -> graphene.InputObjectType:
    """Generate an InputObjectType Object from a Infrahub NodeSchema

    Example of Object Generated by this function:
        class StatusCreateInput(InputObjectType):
            id = String(required=False)
            label = InputField(StringAttributeInput, required=True)
            slug = InputField(StringAttributeInput, required=True)
            description = InputField(StringAttributeInput, required=False)
    """
    attrs = {"id": graphene.String(required=False)}

    for attr in schema.attributes:
        attr_type = INPUT_TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]

        # A Field is not required if explicitely indicated or if a default value has been provided
        required = not attr.optional if not attr.default_value else False

        attrs[attr.name] = graphene.InputField(attr_type, required=required, description=attr.description)

    for rel in schema.relationships:

        required = not rel.optional
        if rel.cardinality == "one":
            attrs[rel.name] = graphene.InputField(RelatedNodeInput, required=required, description=rel.description)

        elif rel.cardinality == "many":
            attrs[rel.name] = graphene.InputField(
                graphene.List(RelatedNodeInput), required=required, description=rel.description
            )

    return type(f"{schema.kind}CreateInput", (graphene.InputObjectType,), attrs)


def generate_graphql_mutation_update_input(schema: NodeSchema) -> graphene.InputObjectType:
    """Generate an InputObjectType Object from a Infrahub NodeSchema

    Example of Object Generated by this function:
        class StatusUpdateInput(InputObjectType):
            id = String(required=True)
            label = InputField(StringAttributeInput, required=False)
            slug = InputField(StringAttributeInput, required=False)
            description = InputField(StringAttributeInput, required=False)
    """
    attrs = {"id": graphene.String(required=True)}

    for attr in schema.attributes:
        attr_type = INPUT_TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]
        attrs[attr.name] = graphene.InputField(attr_type, required=False, description=attr.description)

    for rel in schema.relationships:
        if rel.cardinality == "one":
            attrs[rel.name] = graphene.InputField(RelatedNodeInput, required=False, description=rel.description)

        elif rel.cardinality == "many":
            attrs[rel.name] = graphene.InputField(
                graphene.List(RelatedNodeInput), required=False, description=rel.description
            )

    return type(f"{schema.kind}UpdateInput", (graphene.InputObjectType,), attrs)


def generate_graphql_mutation_create(
    schema: NodeSchema, base_class: type[InfrahubMutation] = InfrahubMutation
) -> Type[InfrahubMutation]:
    """Generate a GraphQL Mutation to CREATE an object based on the specified NodeSchema."""
    name = f"{schema.kind}Create"

    object_type = generate_graphql_object(schema=schema)
    input_type = generate_graphql_mutation_create_input(schema=schema)

    main_attrs = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": input_type(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (base_class,), main_attrs)


def generate_graphql_mutation_update(
    schema: NodeSchema, base_class: type[InfrahubMutation] = InfrahubMutation
) -> Type[InfrahubMutation]:
    """Generate a GraphQL Mutation to UPDATE an object based on the specified NodeSchema."""
    name = f"{schema.kind}Update"

    object_type = generate_graphql_object(schema=schema)
    input_type = generate_graphql_mutation_update_input(schema=schema)

    main_attrs = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": input_type(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (base_class,), main_attrs)


def generate_graphql_mutation_delete(
    schema: NodeSchema, base_class: type[InfrahubMutation] = InfrahubMutation
) -> Type[InfrahubMutation]:
    """Generate a GraphQL Mutation to DELETE an object based on the specified NodeSchema."""
    name = f"{schema.kind}Delete"

    main_attrs = {"ok": graphene.Boolean()}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": DeleteInput(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (base_class,), main_attrs)


async def generate_filters(session: AsyncSession, schema: NodeSchema, attribute_only: bool = False) -> dict:
    """Generate the GraphQL filters for a given NodeSchema object."""
    filters = {"id": graphene.UUID()}
    for attr in schema.attributes:
        attr_type = FILTER_TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]
        filters[f"{attr.name}__value"] = attr_type()

    if attribute_only:
        return filters

    for rel in schema.relationships:
        peer_schema = await rel.get_peer_schema(session=session)
        peer_filters = await generate_filters(session=session, schema=peer_schema, attribute_only=True)

        for key, value in peer_filters.items():
            filters[f"{rel.name}__{key}"] = value

    return filters
