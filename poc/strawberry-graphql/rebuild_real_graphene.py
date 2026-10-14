"""Rebuilds the real Infrahub GraphQL schema with Graphene, as the baseline for rebuild_real.py."""

import enum
import sys
import time
from typing import Any

import graphene
from graphql import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    Undefined,
    build_schema,
    print_schema,
)
from graphql.utilities import lexicographic_sort_schema

BUILTIN = {
    "String": graphene.String,
    "Int": graphene.Int,
    "Float": graphene.Float,
    "Boolean": graphene.Boolean,
    "ID": graphene.ID,
}


class Rebuilder:
    def __init__(self, source: Any) -> None:
        self.source = source
        self.g: dict[str, Any] = {}

    def wrap(self, gql_type: Any) -> Any:
        if isinstance(gql_type, GraphQLNonNull):
            return graphene.NonNull(self.wrap(gql_type.of_type))
        if isinstance(gql_type, GraphQLList):
            return graphene.List(self.wrap(gql_type.of_type))
        name = gql_type.name
        return lambda: self.g[name]

    def default(self, gql_type: Any, value: Any) -> Any:
        if value is Undefined:
            return Undefined
        named = gql_type
        while isinstance(named, (GraphQLNonNull, GraphQLList)):
            named = named.of_type
        if isinstance(named, GraphQLEnumType) and value is not None:
            return self.g[named.name]._meta.enum[value]
        return value

    def build(self) -> graphene.Schema:
        types = {n: t for n, t in self.source.type_map.items() if not n.startswith("__")}
        for name, t in types.items():
            if name in BUILTIN:
                self.g[name] = BUILTIN[name]
            elif isinstance(t, GraphQLScalarType):
                self.g[name] = type(
                    name,
                    (graphene.Scalar,),
                    {
                        "serialize": staticmethod(lambda v: v),
                        "parse_value": staticmethod(lambda v: v),
                        "Meta": type("Meta", (), {"name": name, "description": t.description}),
                    },
                )
            elif isinstance(t, GraphQLEnumType):
                py_enum = enum.Enum(name, {k: k for k in t.values})
                descriptions = {k: v.description for k, v in t.values.items()}
                self.g[name] = graphene.Enum.from_enum(
                    py_enum,
                    description=lambda v, d=descriptions, t=t: d[v.name] if v else t.description,
                    deprecation_reason=lambda v, t=t: t.values[v.name].deprecation_reason if v else None,
                )

        def fields_of(t: Any, input_type: bool) -> dict[str, Any]:
            attrs: dict[str, Any] = {}
            for field_name, f in t.fields.items():
                if input_type:
                    attrs[field_name] = graphene.InputField(
                        self.wrap(f.type),
                        description=f.description,
                        default_value=self.default(f.type, f.default_value),
                        deprecation_reason=f.deprecation_reason,
                    )
                else:
                    args = {
                        n: graphene.Argument(
                            self.wrap(a.type),
                            description=a.description,
                            default_value=self.default(a.type, a.default_value),
                            deprecation_reason=a.deprecation_reason,
                        )
                        for n, a in f.args.items()
                    }
                    attrs[field_name] = graphene.Field(
                        self.wrap(f.type), args=args, description=f.description, deprecation_reason=f.deprecation_reason
                    )
            return attrs

        def resolve_type(cls: type, instance: dict, info: Any) -> Any:
            return self.g[instance["__kind__"]]

        for name, t in types.items():
            if isinstance(t, GraphQLInterfaceType):
                attrs = fields_of(t, False)
                attrs["Meta"] = type("Meta", (), {"name": name, "description": t.description})
                attrs["resolve_type"] = classmethod(resolve_type)
                self.g[name] = type(name, (graphene.Interface,), attrs)
        for name, t in types.items():
            if isinstance(t, GraphQLObjectType):
                attrs = fields_of(t, False)
                attrs["Meta"] = type(
                    "Meta",
                    (),
                    {"name": name, "description": t.description, "interfaces": [self.g[i.name] for i in t.interfaces]},
                )
                self.g[name] = type(name, (graphene.ObjectType,), attrs)
            elif isinstance(t, GraphQLInputObjectType):
                attrs = fields_of(t, True)
                attrs["Meta"] = type("Meta", (), {"name": name, "description": t.description})
                self.g[name] = type(name, (graphene.InputObjectType,), attrs)

        roots = {r: getattr(self.source, f"{r}_type") for r in ("query", "mutation", "subscription")}
        root_names = {t.name for t in roots.values() if t}
        return graphene.Schema(
            query=self.g[roots["query"].name],
            mutation=self.g[roots["mutation"].name] if roots["mutation"] else None,
            subscription=self.g[roots["subscription"].name] if roots["subscription"] else None,
            types=[v for k, v in self.g.items() if k not in root_names and k not in BUILTIN],
            directives=self.source.directives,
            auto_camelcase=False,
        )


def main() -> None:
    reference_sdl = open(sys.argv[1]).read()
    source = build_schema(reference_sdl)
    samples = []
    for _ in range(3):
        start = time.perf_counter()
        schema = Rebuilder(source).build()
        schema.graphql_schema.type_map  # noqa: B018
        samples.append(time.perf_counter() - start)
    print("graphene build of real schema (s):", [round(s, 2) for s in samples])
    rebuilt = print_schema(lexicographic_sort_schema(build_schema(print_schema(schema.graphql_schema))))
    reference = print_schema(lexicographic_sort_schema(source))
    print("SDL identical:", rebuilt == reference)
    if rebuilt != reference:
        import difflib

        diff = list(difflib.unified_diff(reference.splitlines(), rebuilt.splitlines(), lineterm="", n=0))
        print(len(diff), "diff lines")
        print("\n".join(diff[:20]))


if __name__ == "__main__":
    main()
