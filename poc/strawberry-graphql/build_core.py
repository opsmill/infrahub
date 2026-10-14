"""Builds the same synthetic schema directly with graphql-core, without any framework."""

from __future__ import annotations

from typing import Any

from graphql import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
)

from spec import Kind, attr_filter_names

GenericScalar = GraphQLScalarType(
    "GenericScalar",
    description=(
        "The `GenericScalar` scalar type represents a generic\nGraphQL scalar value that could be:\n"
        "String, Boolean, Int, Float, List or Object."
    ),
    serialize=lambda v: v,
    parse_value=lambda v: v,
)


def dict_or_attr(root: Any, info: Any, **_: Any) -> Any:
    if isinstance(root, dict):
        return root.get(info.field_name)
    return getattr(root, info.field_name, None)


TextAttribute = GraphQLObjectType(
    "TextAttribute",
    {
        "id": GraphQLField(GraphQLString),
        "value": GraphQLField(GraphQLString),
        "is_protected": GraphQLField(GraphQLBoolean),
        "updated_at": GraphQLField(GraphQLString),
        "extra": GraphQLField(GenericScalar),
    },
)


def build(spec: list[Kind], resolvers: dict[str, Any]) -> GraphQLSchema:
    by_name = {k.name: k for k in spec}
    gql: dict[str, Any] = {}

    def resolve_type(obj: dict, info: Any, abstract_type: Any) -> str:
        return obj["__typename"]

    def obj_fields(kind: Kind):
        def thunk() -> dict[str, GraphQLField]:
            fields = {
                "id": GraphQLField(GraphQLNonNull(GraphQLString) if not kind.is_generic else GraphQLString),
                "display_label": GraphQLField(GraphQLString),
            }
            for a in kind.attrs:
                fields[a] = GraphQLField(TextAttribute, description=None if kind.is_generic else f"{a} description")
            if kind.is_generic:
                return fields
            for rel in kind.rels:
                peer = by_name[rel.peer]
                if rel.cardinality == "one":
                    fields[rel.name] = GraphQLField(
                        GraphQLNonNull(gql[f"NestedEdged{peer.name}"]), resolve=resolvers["one"]
                    )
                else:
                    args = {
                        "offset": GraphQLArgument(GraphQLInt),
                        "limit": GraphQLArgument(GraphQLInt),
                        "ids": GraphQLArgument(GraphQLList(GraphQLID)),
                    }
                    for pa in peer.attrs:
                        for f in attr_filter_names(pa):
                            args[f] = GraphQLArgument(GraphQLString)
                    fields[rel.name] = GraphQLField(
                        GraphQLNonNull(gql[f"NestedPaginated{peer.name}"]), args=args, resolve=resolvers["many"]
                    )
            return fields

        return thunk

    gql["CoreNode"] = GraphQLInterfaceType(
        "CoreNode", {"id": GraphQLField(GraphQLNonNull(GraphQLString))}, resolve_type=resolve_type
    )
    for kind in spec:
        if kind.is_generic:
            gql[kind.name] = GraphQLInterfaceType(kind.name, obj_fields(kind), resolve_type=resolve_type)
    for kind in spec:
        if not kind.is_generic:
            gql[kind.name] = GraphQLObjectType(
                kind.name,
                obj_fields(kind),
                interfaces=[gql[g] for g in kind.inherit_from] + [gql["CoreNode"]],
            )
    for kind in spec:
        for prefix in ("NestedEdged", "Edged"):
            gql[f"{prefix}{kind.name}"] = GraphQLObjectType(
                f"{prefix}{kind.name}", {"node": GraphQLField(gql[kind.name])}
            )
        for prefix, edge_prefix in (("NestedPaginated", "NestedEdged"), ("Paginated", "Edged")):
            gql[f"{prefix}{kind.name}"] = GraphQLObjectType(
                f"{prefix}{kind.name}",
                {
                    "count": GraphQLField(GraphQLNonNull(GraphQLInt)),
                    "edges": GraphQLField(
                        GraphQLNonNull(GraphQLList(GraphQLNonNull(gql[f"{edge_prefix}{kind.name}"])))
                    ),
                },
            )

    query_fields = {}
    for kind in spec:
        args = {
            "offset": GraphQLArgument(GraphQLInt),
            "limit": GraphQLArgument(GraphQLInt),
            "ids": GraphQLArgument(GraphQLList(GraphQLID)),
        }
        for a in kind.attrs:
            for f in attr_filter_names(a):
                args[f] = GraphQLArgument(GraphQLString)
        for rel in kind.rels:
            for a in by_name[rel.peer].attrs:
                for f in attr_filter_names(a):
                    args[f"{rel.name}__{f}"] = GraphQLArgument(GraphQLString)
        query_fields[kind.name] = GraphQLField(
            GraphQLNonNull(gql[f"Paginated{kind.name}"]), args=args, resolve=resolvers["list"]
        )

    create_input = GraphQLInputObjectType(
        "CreateInput",
        {"name": GraphQLInputField(GraphQLNonNull(GraphQLString)), "extra": GraphQLInputField(GenericScalar)},
    )
    test_create = GraphQLObjectType("TestCreate", {"ok": GraphQLField(GraphQLBoolean)})
    mutation = GraphQLObjectType(
        "Mutation",
        {
            "TestCreate": GraphQLField(
                test_create,
                args={"data": GraphQLArgument(GraphQLNonNull(create_input))},
                resolve=lambda root, info, data: {"ok": isinstance(data, dict)},
            )
        },
    )

    return GraphQLSchema(
        query=GraphQLObjectType("Query", query_fields),
        mutation=mutation,
        types=list(gql.values()),
    )
