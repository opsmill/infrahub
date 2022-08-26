import graphene

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema

from .mutations import (
    AnyAttributeInput,
    BoolAttributeInput,
    InfrahubMutation,
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
from .types import Any
from .utils import extract_fields

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
    "Any": Any,
}


class DeleteInput(graphene.InputObjectType):
    id = graphene.String(required=True)


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
    node_schema = info.parent_type.graphene_type._meta.schema

    # If the field is an attribute, return its value directly
    if field_name not in node_schema.relationship_names:
        return parent.get(field_name, None)

    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch = info.context.get("infrahub_branch")
    account = info.context.get("infrahub_account", None)

    # Extract the name of the field in the GQL query
    fields = extract_fields(info.field_nodes[0].selection_set)

    # Extract the schema of the node on the other end of the relationship from
    # the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {f"{info.field_name}__{key}": value for key, value in kwargs.items() if "__" in key and value}

    objs = NodeManager.query_peers(
        id=parent["id"], schema=node_rel, filters=filters, at=at, branch=branch, account=account, include_source=True
    )

    if node_rel.cardinality == "many":
        return [obj.to_graphql(fields=fields) for obj in objs]

    # If cardinality is one
    if not objs:
        return None

    return objs[0].to_graphql(fields=fields)


def generate_object_types(branch=None):

    full_schema = registry.get_full_schema(branch=branch)

    # Generate all Graphql objectType and store them in the registry
    for node_name, node_schema in full_schema.items():
        node_type = generate_graphql_object(node_schema)
        registry.set_graphql_type(name=node_name, graphql_type=node_type, branch=branch)

    # Extend all type with relationships
    for node_name, node_schema in full_schema.items():
        node_type = registry.get_graphql_type(name=node_name, branch=branch)

        for rel in node_schema.relationships:

            peer_schema = rel.get_peer_schema()
            peer_filters = generate_filters(peer_schema, attribute_only=True)
            peer_type = registry.get_graphql_type(name=peer_schema.kind, branch=branch)

            if rel.cardinality == "one":
                node_type._meta.fields[rel.name] = graphene.Field(peer_type, resolver=default_resolver)

            elif rel.cardinality == "many":
                node_type._meta.fields[rel.name] = graphene.Field.mounted(graphene.List(peer_type, **peer_filters))


def generate_query_mixin(branch=None):

    class_attrs = {}

    full_schema = registry.get_full_schema(branch=branch)

    # # Generate all Graphql objectType and store them in the registry
    generate_object_types()

    for node_name, node_schema in full_schema.items():

        if "Schema" in node_name:
            continue

        node_type = registry.get_graphql_type(name=node_name, branch=branch)
        node_filters = generate_filters(node_schema)

        class_attrs[node_schema.name] = graphene.List(
            node_type,
            resolver=default_list_resolver,
            **node_filters,
        )

    return type("QueryMixin", (object,), class_attrs)


def generate_mutation_mixin(branch=None):

    class_attrs = {}

    full_schema = registry.get_full_schema(branch=branch)

    for node_name, node_schema in full_schema.items():

        if "Schema" in node_name:
            continue

        create, update, delete = generate_graphql_mutations(node_schema)
        class_attrs[f"{node_schema.name}_create"] = create.Field()
        class_attrs[f"{node_schema.name}_update"] = update.Field()
        class_attrs[f"{node_schema.name}_delete"] = delete.Field()

    return type("MutationMixin", (object,), class_attrs)


def generate_graphql_object(schema: NodeSchema, include_rel=False) -> InfrahubObject:

    main_attrs = {}
    meta_attrs = {
        "schema": schema,
        "name": schema.kind,
        "description": schema.description,
        "default_resolver": default_resolver,
    }

    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    main_attrs["id"] = graphene.String(required=True)

    for attr in schema.attributes:
        attr_type = TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]
        main_attrs[attr.name] = graphene.Field(attr_type, required=not attr.optional, description=attr.description)

    schema_type = type(schema.kind, (InfrahubObject,), main_attrs)

    return schema_type


def generate_graphql_mutations(schema: NodeSchema):

    create = generate_graphql_mutation_create(schema)
    update = generate_graphql_mutation_update(schema)
    delete = generate_graphql_mutation_delete(schema)

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
        if rel.cardinality == "one":
            attrs[rel.name] = graphene.InputField(graphene.String, required=False, description=rel.description)

        elif rel.cardinality == "many":
            attrs[rel.name] = graphene.InputField(
                graphene.List(graphene.String), required=False, description=rel.description
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
            attrs[rel.name] = graphene.InputField(graphene.String, required=False, description=rel.description)

        elif rel.cardinality == "many":
            attrs[rel.name] = graphene.InputField(
                graphene.List(graphene.String), required=False, description=rel.description
            )

    return type(f"{schema.kind}UpdateInput", (graphene.InputObjectType,), attrs)


def generate_graphql_mutation_create(schema: NodeSchema):

    name = f"{schema.kind}Create"

    object_type = generate_graphql_object(schema)
    input_type = generate_graphql_mutation_create_input(schema)

    main_attrs = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": input_type(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (InfrahubMutation,), main_attrs)


def generate_graphql_mutation_update(schema: NodeSchema):

    name = f"{schema.kind}Update"

    object_type = generate_graphql_object(schema)
    input_type = generate_graphql_mutation_update_input(schema)

    main_attrs = {"ok": graphene.Boolean(), "object": graphene.Field(object_type)}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": input_type(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (InfrahubMutation,), main_attrs)


def generate_graphql_mutation_delete(schema: NodeSchema):

    name = f"{schema.kind}Delete"

    main_attrs = {"ok": graphene.Boolean()}

    meta_attrs = {"schema": schema, "name": name, "description": schema.description}
    main_attrs["Meta"] = type("Meta", (object,), meta_attrs)

    args_attrs = {
        "data": DeleteInput(required=True),
    }
    main_attrs["Arguments"] = type("Arguments", (object,), args_attrs)

    return type(name, (InfrahubMutation,), main_attrs)


def generate_filters(schema: NodeSchema, attribute_only=False) -> dict:

    filters = {"id": graphene.UUID()}
    for attr in schema.attributes:
        attr_type = FILTER_TYPES_MAPPING_INFRAHUB_GRAPHQL[attr.kind]
        filters[f"{attr.name}__value"] = attr_type()

    if attribute_only:
        return filters

    for rel in schema.relationships:
        peer_schema = rel.get_peer_schema()
        peer_filters = generate_filters(peer_schema, attribute_only=True)

        for key, value in peer_filters.items():
            filters[f"{rel.name}__{key}"] = value

    return filters
