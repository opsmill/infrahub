"""Builds the synthetic schema the way backend/infrahub/graphql/manager.py does today."""

from __future__ import annotations

from typing import Any

import graphene
from graphene.types.generic import GenericScalar

from spec import Kind, attr_filter_names


class TextAttribute(graphene.ObjectType):
    id = graphene.String()
    value = graphene.String()
    is_protected = graphene.Boolean()
    updated_at = graphene.String()
    extra = GenericScalar()


def dict_or_attr(attname: str, default: Any, root: Any, info: Any, **_: Any) -> Any:
    if isinstance(root, dict):
        return root.get(attname, default)
    return getattr(root, attname, default)


def build(spec: list[Kind], resolvers: dict[str, Any]) -> graphene.Schema:
    types: dict[str, Any] = {}
    by_name = {k.name: k for k in spec}

    class BaseInterface(graphene.Interface):
        @classmethod
        def resolve_type(cls, instance: dict, info: Any) -> Any:
            return types[instance["__typename"]]

    node_iface = type(
        "CoreNode",
        (BaseInterface,),
        {"id": graphene.String(required=True), "Meta": type("Meta", (), {"name": "CoreNode"})},
    )
    types["CoreNode"] = node_iface

    for kind in spec:
        if not kind.is_generic:
            continue
        attrs: dict[str, Any] = {"id": graphene.String(), "display_label": graphene.String()}
        for a in kind.attrs:
            attrs[a] = graphene.Field(TextAttribute)
        attrs["Meta"] = type("Meta", (), {"name": kind.name})
        types[kind.name] = type(kind.name, (BaseInterface,), attrs)

    for kind in spec:
        if kind.is_generic:
            continue
        attrs = {"id": graphene.String(required=True), "display_label": graphene.String()}
        for a in kind.attrs:
            attrs[a] = graphene.Field(TextAttribute, description=f"{a} description")
        interfaces = [types[g] for g in kind.inherit_from] + [node_iface]
        attrs["Meta"] = type(
            "Meta", (), {"name": kind.name, "interfaces": interfaces, "default_resolver": dict_or_attr}
        )
        types[kind.name] = type(kind.name, (graphene.ObjectType,), attrs)

    for kind in spec:
        edge = type(
            f"NestedEdged{kind.name}",
            (graphene.ObjectType,),
            {"node": graphene.Field(types[kind.name]), "Meta": type("Meta", (), {"default_resolver": dict_or_attr})},
        )
        paginated = type(
            f"NestedPaginated{kind.name}",
            (graphene.ObjectType,),
            {
                "count": graphene.Int(required=True),
                "edges": graphene.List(graphene.NonNull(edge), required=True),
                "Meta": type("Meta", (), {"default_resolver": dict_or_attr}),
            },
        )
        types[edge.__name__] = edge
        types[paginated.__name__] = paginated
        top_edge = type(
            f"Edged{kind.name}",
            (graphene.ObjectType,),
            {"node": graphene.Field(types[kind.name]), "Meta": type("Meta", (), {"default_resolver": dict_or_attr})},
        )
        top_paginated = type(
            f"Paginated{kind.name}",
            (graphene.ObjectType,),
            {
                "count": graphene.Int(required=True),
                "edges": graphene.List(graphene.NonNull(top_edge), required=True),
                "Meta": type("Meta", (), {"default_resolver": dict_or_attr}),
            },
        )
        types[top_edge.__name__] = top_edge
        types[top_paginated.__name__] = top_paginated

    # Relationships are added after every type exists, by patching _meta.fields like manager.py does.
    for kind in spec:
        node_type = types[kind.name]
        for rel in kind.rels:
            peer = by_name[rel.peer]
            filters = {"offset": graphene.Int(), "limit": graphene.Int(), "ids": graphene.List(graphene.ID)}
            for a in peer.attrs:
                for f in attr_filter_names(a):
                    filters[f] = graphene.String()
            if rel.cardinality == "one":
                node_type._meta.fields[rel.name] = graphene.Field(
                    types[f"NestedEdged{peer.name}"], required=True, resolver=resolvers["one"]
                )
            else:
                node_type._meta.fields[rel.name] = graphene.Field(
                    types[f"NestedPaginated{peer.name}"], required=True, resolver=resolvers["many"], **filters
                )

    query_attrs: dict[str, Any] = {}
    for kind in spec:
        filters = {"offset": graphene.Int(), "limit": graphene.Int(), "ids": graphene.List(graphene.ID)}
        for a in kind.attrs:
            for f in attr_filter_names(a):
                filters[f] = graphene.String()
        for rel in kind.rels:
            for a in by_name[rel.peer].attrs:
                for f in attr_filter_names(a):
                    filters[f"{rel.name}__{f}"] = graphene.String()
        query_attrs[kind.name] = graphene.Field(
            types[f"Paginated{kind.name}"], required=True, resolver=resolvers["list"], **filters
        )

    Query = type("Query", (graphene.ObjectType,), query_attrs)

    class CreateInput(graphene.InputObjectType):
        name = graphene.String(required=True)
        extra = GenericScalar()

    class TestCreate(graphene.Mutation):
        class Arguments:
            data = CreateInput(required=True)

        ok = graphene.Boolean()

        @classmethod
        def mutate(cls, root: Any, info: Any, data: dict) -> TestCreate:
            return cls(ok=isinstance(data, dict))

    Mutation = type("Mutation", (graphene.ObjectType,), {"TestCreate": TestCreate.Field()})

    return graphene.Schema(query=Query, mutation=Mutation, types=list(types.values()), auto_camelcase=False)
