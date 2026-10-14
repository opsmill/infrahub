"""Builds the real Infrahub GraphQL schema from two parts and checks that the result matches today's schema.

- Hand-written part: the types that do not depend on the Infrahub schema, built once with Strawberry.
- Generated part: the types derived from the Infrahub schema, plus the hand-written types that reference them,
  built with graphql-core for each schema.

type_classification.json lists which type belongs to which part; classify_types.py produces it from Infrahub.
"""

import json
import pathlib
import statistics
import sys
import time
from typing import Any

import strawberry
from graphql import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    Undefined,
    build_schema,
    execute,
    graphql_sync,
    parse,
    print_schema,
    validate,
    value_from_ast,
)

from rebuild_real import Rebuilder, normalise

ROOTS = ("Query", "Mutation", "Subscription")


def source_default(gql_type: Any, item: Any) -> Any:
    """Returns the internal default value of an argument or input field in either graphql-core 3.2 or 3.3."""
    if item.default_value is not Undefined:
        return item.default_value
    stored = getattr(item, "default", None)
    if stored is None:
        return Undefined
    literal = getattr(stored, "literal", Undefined)
    return value_from_ast(literal, gql_type) if literal is not Undefined else stored.value


def resolve_kind(obj: Any, info: Any, abstract_type: Any) -> str:
    return obj["__kind__"]


class GeneratedPart:
    """Builds graphql-core types for `names`, taking every other named type from `shared`.

    In Infrahub the descriptions of these types would come from the schema nodes. In this POC they are copied from
    `source`, so the result can be compared with the SDL that Graphene produces.
    """

    def __init__(self, source: GraphQLSchema, names: set[str], shared: dict[str, GraphQLNamedType], resolvers: dict):
        self.source = source
        self.names = names
        self.shared = shared
        self.resolvers = resolvers
        self.types: dict[str, GraphQLNamedType] = {}

    def ref(self, gql_type: Any) -> Any:
        if isinstance(gql_type, GraphQLNonNull):
            return GraphQLNonNull(self.ref(gql_type.of_type))
        if isinstance(gql_type, GraphQLList):
            return GraphQLList(self.ref(gql_type.of_type))
        return self.types.get(gql_type.name) or self.shared[gql_type.name]

    def output_fields(self, type_name: str, fields: dict[str, GraphQLField]) -> dict[str, GraphQLField]:
        return {
            name: GraphQLField(
                self.ref(f.type),
                args={
                    arg_name: GraphQLArgument(
                        self.ref(a.type),
                        default_value=source_default(a.type, a),
                        description=a.description,
                        deprecation_reason=a.deprecation_reason,
                    )
                    for arg_name, a in f.args.items()
                },
                resolve=self.resolvers.get((type_name, name)),
                description=f.description,
                deprecation_reason=f.deprecation_reason,
            )
            for name, f in fields.items()
        }

    def build(self) -> None:
        source_types = {n: self.source.type_map[n] for n in sorted(self.names)}
        for name, t in source_types.items():
            if isinstance(t, GraphQLInterfaceType):
                self.types[name] = GraphQLInterfaceType(
                    name,
                    fields=lambda t=t: self.output_fields(t.name, t.fields),
                    interfaces=lambda t=t: [self.ref(i) for i in t.interfaces],
                    resolve_type=resolve_kind,
                    description=t.description,
                )
            elif isinstance(t, GraphQLObjectType):
                self.types[name] = GraphQLObjectType(
                    name,
                    fields=lambda t=t: self.output_fields(t.name, t.fields),
                    interfaces=lambda t=t: [self.ref(i) for i in t.interfaces],
                    description=t.description,
                )
            elif isinstance(t, GraphQLInputObjectType):
                self.types[name] = GraphQLInputObjectType(
                    name,
                    fields=lambda t=t: {
                        n: GraphQLInputField(
                            self.ref(f.type),
                            default_value=source_default(f.type, f),
                            description=f.description,
                            deprecation_reason=f.deprecation_reason,
                        )
                        for n, f in t.fields.items()
                    },
                    description=t.description,
                )
            elif isinstance(t, GraphQLEnumType):
                self.types[name] = GraphQLEnumType(
                    name,
                    {
                        k: GraphQLEnumValue(v.value, description=v.description, deprecation_reason=v.deprecation_reason)
                        for k, v in t.values.items()
                    },
                    description=t.description,
                )
            elif isinstance(t, GraphQLScalarType):
                raise ValueError(f"Scalars are hand-written, {name} should not be generated")

    def root_fields(self, root: GraphQLObjectType | None, exclude: set[str]) -> dict[str, GraphQLField]:
        if root is None:
            return {}
        return self.output_fields(root.name, {n: f for n, f in root.fields.items() if n not in exclude})


def assemble(handwritten: GraphQLSchema, generated: GeneratedPart, static_roots: dict[str, set[str]]) -> GraphQLSchema:
    """Joins the two parts into one schema; root types merge the hand-written and generated root fields."""
    roots: dict[str, GraphQLObjectType | None] = {}
    for root_name, attr in zip(ROOTS, ("query_type", "mutation_type", "subscription_type"), strict=True):
        handwritten_root = getattr(handwritten, attr)
        generated_fields = generated.root_fields(getattr(generated.source, attr), static_roots[root_name])
        if handwritten_root is None and not generated_fields:
            roots[root_name] = None
            continue
        roots[root_name] = GraphQLObjectType(
            root_name,
            fields=lambda h=handwritten_root, g=generated_fields: {**(h.fields if h else {}), **g},
        )
    shared = [t for n, t in handwritten.type_map.items() if not n.startswith("__") and n not in ROOTS]
    schema = GraphQLSchema(
        query=roots["Query"],
        mutation=roots["Mutation"],
        subscription=roots["Subscription"],
        types=shared + list(generated.types.values()),
        directives=handwritten.directives,
    )
    # Strawberry's Info.schema reads its own schema object from this attribute of the graphql-core schema.
    schema._strawberry_schema = handwritten._strawberry_schema  # type: ignore[attr-defined]
    return schema


def load_classification() -> tuple[set[str], set[str], dict[str, set[str]]]:
    data = json.loads((pathlib.Path(__file__).parent / "type_classification.json").read_text())
    static_roots = {
        "Query": set(data["static_root_fields"]["query_type"]),
        "Mutation": set(data["static_root_fields"]["mutation_type"]),
        "Subscription": set(data["static_root_fields"]["subscription_type"]),
    }
    return set(data["static"]), set(data["generated"]) | set(data["schema_dependent_static"]), static_roots


CALLS: dict[str, Any] = {}


def branch_resolver(root: Any, info: strawberry.Info, **kwargs: Any) -> list[dict]:
    CALLS["Branch"] = kwargs
    return [{"id": "b1", "name": "main", "is_default": True}]


def branch_create_resolver(root: Any, info: strawberry.Info, **kwargs: Any) -> dict:
    data = kwargs["data"]
    CALLS["BranchCreate"] = (type(data).__name__, data.name)
    return {"ok": True}


def builtin_tag_resolver(root: Any, info: Any, **kwargs: Any) -> dict:
    CALLS["BuiltinTag"] = kwargs
    tag = {
        "__kind__": "BuiltinTag",
        "id": "t1",
        "name": {"value": "red", "source": {"__kind__": "CoreAccount", "id": "a1", "display_label": "admin"}},
    }
    return {"count": 1, "edges": [{"node": tag}]}


HANDWRITTEN_RESOLVERS = {("Query", "Branch"): branch_resolver, ("Mutation", "BranchCreate"): branch_create_resolver}
GENERATED_RESOLVERS = {("Query", "BuiltinTag"): builtin_tag_resolver}

CROSS_PART_QUERY = """
query {
  Branch(name: "main") { id name is_default }
  BuiltinTag(order: {by: [{field: "name__value"}]}, name__value: "red") {
    count
    edges { node { id name { value source { id display_label } } ... on CoreNode { core_node_id: id } } }
  }
}
"""
CROSS_PART_MUTATION = 'mutation { BranchCreate(data: {name: "b2"}) { ok } }'


def median_time(fn: Any, repeat: int = 5) -> float:
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def main() -> None:
    reference_sdl = pathlib.Path(sys.argv[1]).read_text()
    source = build_schema(reference_sdl)
    static, generated_names, static_roots = load_classification()
    print(f"hand-written types: {len(static)}, generated types: {len(generated_names)}")
    print(f"hand-written root fields: { {k: len(v) for k, v in static_roots.items()} }")

    def build_handwritten() -> GraphQLSchema:
        return Rebuilder(source, only=static, root_fields=static_roots, resolvers=HANDWRITTEN_RESOLVERS).build()._schema

    handwritten = build_handwritten()

    def build_generated() -> GraphQLSchema:
        part = GeneratedPart(source, generated_names, handwritten.type_map, GENERATED_RESOLVERS)
        part.build()
        schema = assemble(handwritten, part, static_roots)
        _ = [t.fields for t in schema.type_map.values() if hasattr(t, "fields")]
        return schema

    combined = build_generated()

    print("\n== build time (s, median of 5) ==")
    print(f"hand-written part with Strawberry, once per process: {median_time(build_handwritten):.2f}")
    print(f"generated part with graphql-core plus assembly, per schema: {median_time(build_generated):.2f}")

    print("\n== SDL parity with the schema Graphene produces ==")
    rebuilt = normalise(print_schema(combined))
    reference = normalise(reference_sdl)
    print(f"SDL identical: {rebuilt == reference} ({len(reference.splitlines())} lines)")
    if rebuilt != reference:
        import difflib

        print(
            "\n".join(list(difflib.unified_diff(reference.splitlines(), rebuilt.splitlines(), lineterm="", n=0))[:40])
        )

    print("\n== queries that cross the two parts ==")
    document = parse(CROSS_PART_QUERY)
    errors = validate(combined, document)
    result = execute(combined, document) if not errors else None
    print("query errors:", errors or result.errors)
    print("query data:", json.dumps(result.data) if result else None)
    print("hand-written resolver arguments (Strawberry):", CALLS.get("Branch"))
    order = CALLS["BuiltinTag"]["order"]
    print("generated resolver receives the hand-written OrderInput as:", type(order).__name__, order)
    mutation = graphql_sync(combined, CROSS_PART_MUTATION)
    print("mutation:", mutation.data, mutation.errors or "")
    print("hand-written mutation receives its input as:", CALLS.get("BranchCreate"))

    print("\n== two schemas sharing the hand-written part ==")
    second = build_generated()
    shared = [n for n, t in second.type_map.items() if combined.type_map.get(n) is t and not n.startswith("__")]
    print(f"type objects shared between the two schemas: {len(shared)}")
    print("both still execute:", graphql_sync(second, CROSS_PART_QUERY).errors is None)


if __name__ == "__main__":
    main()
