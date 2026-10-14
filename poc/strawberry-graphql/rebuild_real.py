"""Rebuilds the real Infrahub GraphQL schema (schema/schema.graphql) with Strawberry at runtime.

Every type, field, argument, default value, description, enum, scalar, interface and directive is created
programmatically, the way a Strawberry-based GraphQLSchemaManager would create them from the Infrahub schema.
The printed result is then compared against the SDL that Graphene produces today.
"""

import enum
import sys
import time
import types as pytypes
from typing import Any, Optional

import strawberry
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
    value_from_ast,
)
from graphql.utilities import lexicographic_sort_schema
from strawberry.annotation import StrawberryAnnotation
from strawberry.directive import DirectiveLocation, StrawberryDirective
from strawberry.schema.config import StrawberryConfig
from strawberry.types.arguments import StrawberryArgument
from strawberry.types.field import StrawberryField
from strawberry.types.fields.resolver import StrawberryResolver

BUILTIN_SCALARS = {"String": str, "Int": int, "Float": float, "Boolean": bool, "ID": strawberry.ID}


def new_class(name: str, bases: tuple = (), namespace: dict | None = None) -> type:
    ns = dict(namespace or {})
    ns.setdefault("__annotations__", {})
    return pytypes.new_class(name, bases, {}, lambda n: n.update(ns))


def dict_or_attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _input_init(self: Any, **kwargs: Any) -> None:
    """Stands in for the dataclass constructor, which cannot see fields appended after the class was decorated."""
    for field in self.__strawberry_definition__.fields:
        setattr(self, field.python_name, kwargs.get(field.python_name, field.default))


class Rebuilder:
    """Builds `source` with Strawberry; `only` and `root_fields` restrict the build to part of the schema."""

    def __init__(
        self,
        source: Any,
        only: set[str] | None = None,
        root_fields: dict[str, set[str]] | None = None,
        resolvers: dict[tuple[str, str], Any] | None = None,
    ) -> None:
        self.source = source
        self.only = only
        self.root_fields = root_fields or {}
        self.resolvers = resolvers or {}
        self.py: dict[str, Any] = {}
        self._annotations: dict[str, StrawberryAnnotation] = {}

    def shared_annotation(self, gql_type: Any) -> StrawberryAnnotation:
        """Reuses one annotation per GraphQL type, so Strawberry evaluates each type once instead of per argument."""
        key = str(gql_type)
        if key not in self._annotations:
            self._annotations[key] = StrawberryAnnotation(self.annotation(gql_type))
        return self._annotations[key]

    def annotation(self, gql_type: Any) -> Any:
        if isinstance(gql_type, GraphQLNonNull):
            return self._inner(gql_type.of_type)
        return Optional[self._inner(gql_type)]

    def _inner(self, gql_type: Any) -> Any:
        if isinstance(gql_type, GraphQLList):
            return list[self.annotation(gql_type.of_type)]
        return self.py[gql_type.name]

    def default(self, gql_type: Any, value: Any, source: Any = None) -> Any:
        # graphql-core 3.3 keeps SDL defaults as literals in `default` instead of `default_value`.
        stored = getattr(source, "default", None)
        if value is Undefined and stored is not None:
            literal = getattr(stored, "literal", Undefined)
            value = value_from_ast(literal, gql_type) if literal is not Undefined else stored.value
        if value is Undefined:
            return strawberry.UNSET
        if value is None:
            return None
        named = gql_type
        while isinstance(named, (GraphQLNonNull, GraphQLList)):
            named = named.of_type
        if isinstance(named, GraphQLEnumType):
            return self.py[named.name][next(k for k, v in named.values.items() if v.value == value)]
        return value

    def build(self) -> strawberry.Schema:
        types = {n: t for n, t in self.source.type_map.items() if not n.startswith("__")}
        if self.only is not None:
            root_names = {
                r.name for r in (self.source.query_type, self.source.mutation_type, self.source.subscription_type) if r
            }
            types = {n: t for n, t in types.items() if n in self.only or n in root_names or n in BUILTIN_SCALARS}

        for name, t in types.items():
            if name in BUILTIN_SCALARS:
                self.py[name] = BUILTIN_SCALARS[name]
            elif isinstance(t, GraphQLScalarType):
                self.py[name] = strawberry.scalar(
                    new_class(name),
                    name=name,
                    description=t.description,
                    serialize=lambda v: v,
                    parse_value=lambda v: v,
                )
            elif isinstance(t, GraphQLEnumType):
                py_enum = enum.Enum(name, {k: k for k in t.values})
                self.py[name] = strawberry.enum(
                    py_enum,
                    name=name,
                    description=t.description,
                )
                for k, v in t.values.items():
                    value_def = self.py[name].__strawberry_definition__.values
                    match = next(ev for ev in value_def if ev.name == k)
                    match.description = v.description
                    match.deprecation_reason = v.deprecation_reason

        # Phase 1: class shells. Interfaces first, so object types can inherit from them.
        def resolve_type(cls: type, obj: Any, info: Any, abstract_type: Any) -> str:
            return obj["__kind__"]

        for name, t in types.items():
            if isinstance(t, GraphQLInterfaceType):
                self.py[name] = strawberry.interface(
                    new_class(name, (), {"resolve_type": classmethod(resolve_type)}), description=t.description
                )
        for name, t in types.items():
            if isinstance(t, GraphQLObjectType):
                bases = tuple(self.py[i.name] for i in t.interfaces)
                self.py[name] = strawberry.type(
                    new_class(name, bases, {"is_type_of": classmethod(lambda cls, obj, info: True)}),
                    description=t.description,
                )
            elif isinstance(t, GraphQLInputObjectType):
                self.py[name] = strawberry.input(
                    new_class(name, (), {"__init__": _input_init}), description=t.description
                )

        # Phase 2: fields and arguments, appended once every class exists so cycles resolve.
        for name, t in types.items():
            if not isinstance(t, (GraphQLObjectType, GraphQLInterfaceType, GraphQLInputObjectType)):
                continue
            definition = self.py[name].__strawberry_definition__
            inherited = {f.python_name for f in definition.fields}
            definition.fields[:] = [f for f in definition.fields if f.python_name not in t.fields]
            for field_name, f in t.fields.items():
                if name in self.root_fields and field_name not in self.root_fields[name]:
                    continue
                kwargs: dict[str, Any] = {}
                if isinstance(t, GraphQLInputObjectType):
                    kwargs["default"] = self.default(f.type, f.default_value, f)
                field = StrawberryField(
                    python_name=field_name,
                    graphql_name=field_name,
                    type_annotation=self.shared_annotation(f.type),
                    description=f.description,
                    deprecation_reason=f.deprecation_reason,
                    base_resolver=StrawberryResolver(self.resolvers[name, field_name])
                    if (name, field_name) in self.resolvers
                    else None,
                    **kwargs,
                )
                field.origin = self.py[name]
                if not isinstance(t, GraphQLInputObjectType):
                    field.arguments = [
                        StrawberryArgument(
                            python_name=arg_name,
                            graphql_name=arg_name,
                            type_annotation=self.shared_annotation(arg.type),
                            description=arg.description,
                            default=self.default(arg.type, arg.default_value, arg),
                            deprecation_reason=arg.deprecation_reason,
                        )
                        for arg_name, arg in f.args.items()
                    ]
                definition.fields.append(field)
            del inherited

        directives = []
        for d in self.source.directives:
            if d.name not in ("expand",):
                continue
            arguments = [
                StrawberryArgument(
                    python_name=n,
                    graphql_name=n,
                    type_annotation=StrawberryAnnotation(self.annotation(a.type)),
                    description=a.description,
                )
                for n, a in d.args.items()
            ]
            directive = StrawberryDirective(
                python_name=d.name,
                graphql_name=d.name,
                resolver=lambda value, **kwargs: value,
                locations=[DirectiveLocation[loc.name] for loc in d.locations],
                description=d.description,
            )
            directive.__dict__["arguments"] = arguments
            directives.append(directive)

        query = self.py[self.source.query_type.name]
        mutation = self.py[self.source.mutation_type.name] if self.source.mutation_type else None
        subscription = self.py[self.source.subscription_type.name] if self.source.subscription_type else None
        roots = {
            getattr(self.source, f"{r}_type").name
            for r in ("query", "mutation", "subscription")
            if getattr(self.source, f"{r}_type")
        }
        extra = [v for k, v in self.py.items() if k not in roots and hasattr(v, "__strawberry_definition__")]
        return strawberry.Schema(
            query=query,
            mutation=mutation,
            subscription=subscription,
            types=extra,
            directives=directives,
            config=StrawberryConfig(auto_camel_case=False, default_resolver=dict_or_attr),
        )


def normalise(sdl: str) -> str:
    return print_schema(lexicographic_sort_schema(build_schema(sdl)))


def main() -> None:
    sdl_path = sys.argv[1]
    reference_sdl = open(sdl_path).read()
    source = build_schema(reference_sdl)

    samples = []
    for _ in range(3):
        start = time.perf_counter()
        schema = Rebuilder(source).build()
        samples.append(time.perf_counter() - start)
    print("strawberry build of real schema (s):", [round(s, 2) for s in samples])

    rebuilt = normalise(print_schema(schema._schema))
    reference = normalise(reference_sdl)
    if rebuilt == reference:
        print(f"SDL identical: True ({len(reference.splitlines())} lines)")
    else:
        import difflib

        diff = list(
            difflib.unified_diff(
                reference.splitlines(), rebuilt.splitlines(), "graphene", "strawberry", lineterm="", n=0
            )
        )
        print(f"SDL identical: False, {len(diff)} diff lines")
        print("\n".join(diff[:80]))
    open("rebuilt_schema.graphql", "w").write(rebuilt)


if __name__ == "__main__":
    main()
