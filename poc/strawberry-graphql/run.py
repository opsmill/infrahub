"""Compares SDL parity, schema build time and execution time across the three builders."""

from __future__ import annotations

import argparse
import asyncio
import difflib
import gc
import statistics
import time
from typing import Any

from graphql import (
    GraphQLSchema,
    execute,
    get_introspection_query,
    graphql_sync,
    parse,
    print_schema,
    validate,
)
from graphql.utilities import lexicographic_sort_schema

import build_core
import build_graphene
import build_strawberry
from spec import build_spec, make_query, make_rows

ROWS: dict[str, list[dict]] = {}
REL_ROW = {"node": {"__typename": "TestNode0", "id": "peer", "display_label": "peer"}}


def list_resolver(root: Any, info: Any, **kwargs: Any) -> dict:
    rows = ROWS[info.field_name]
    return {"count": len(rows), "edges": [{"node": r} for r in rows]}


async def async_list_resolver(root: Any, info: Any, **kwargs: Any) -> dict:
    return list_resolver(root, info, **kwargs)


def one_resolver(root: Any, info: Any, **kwargs: Any) -> dict:
    return REL_ROW


async def async_one_resolver(root: Any, info: Any, **kwargs: Any) -> dict:
    return REL_ROW


def many_resolver(root: Any, info: Any, **kwargs: Any) -> dict:
    return {"count": 0, "edges": []}


SYNC = {"list": list_resolver, "one": one_resolver, "many": many_resolver}
ASYNC = {"list": async_list_resolver, "one": async_one_resolver, "many": many_resolver}


def core_schema(name: str, schema: Any) -> GraphQLSchema:
    if name == "graphene":
        return schema.graphql_schema
    if name == "strawberry":
        return schema._schema
    return schema


def timeit(fn, repeat: int) -> float:
    samples = []
    for _ in range(repeat):
        gc.collect()
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=200)
    parser.add_argument("--generics", type=int, default=20)
    parser.add_argument("--attrs", type=int, default=8)
    parser.add_argument("--rels", type=int, default=6)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()

    spec = build_spec(args.nodes, args.generics, args.attrs, args.rels)
    target = next(k for k in spec if not k.is_generic)
    ROWS[target.name] = make_rows(target, args.rows)
    query = make_query(target)
    document = parse(query)

    builders = {
        "graphene": build_graphene.build,
        "strawberry": build_strawberry.build,
        "graphql-core": build_core.build,
    }

    schemas: dict[str, GraphQLSchema] = {}
    print(f"spec: {args.nodes} nodes, {args.generics} generics, {args.attrs} attrs, {args.rels} rels, {args.rows} rows")
    print("\n== schema build (seconds, median) ==")
    for name, builder in builders.items():

        def run_build() -> None:
            schemas[name] = core_schema(name, builder(spec, SYNC))

        print(f"{name:13s} {timeit(run_build, max(1, args.repeat // 2)):.3f}")

    print("\n== SDL parity with graphene ==")
    reference = print_schema(lexicographic_sort_schema(schemas["graphene"]))
    print(f"graphene SDL: {len(reference.splitlines())} lines, {len(schemas['graphene'].type_map)} types")
    for name in ("strawberry", "graphql-core"):
        sdl = print_schema(lexicographic_sort_schema(schemas[name]))
        diff = list(difflib.unified_diff(reference.splitlines(), sdl.splitlines(), "graphene", name, lineterm="", n=1))
        print(f"{name:13s} identical={not diff} diff_lines={len(diff)}")
        for line in diff[:30]:
            print("   ", line)

    print("\n== validate + execute query (ms, median) ==")
    results = {}
    for mode, resolvers in (("sync", SYNC), ("async", ASYNC)):
        for name, builder in builders.items():
            schema = core_schema(name, builder(spec, resolvers))
            assert not validate(schema, document)

            def run_exec() -> None:
                result = execute(schema, document)
                if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                    result = asyncio.run(result)
                assert not result.errors, result.errors
                results[(mode, name)] = result.data

            print(f"{mode:5s} {name:13s} {timeit(run_exec, args.repeat) * 1000:8.1f}")
    assert results[("sync", "graphene")] == results[("sync", "strawberry")] == results[("sync", "graphql-core")]
    print("query results identical across builders: True")

    print("\n== introspection query (ms, median) ==")
    introspection = get_introspection_query(descriptions=True)
    for name, schema in schemas.items():
        print(f"{name:13s} {timeit(lambda: graphql_sync(schema, introspection), max(1, args.repeat // 2)) * 1000:8.1f}")

    print("\n== mutation input handling ==")
    mutation = 'mutation { TestCreate(data: {name: "a", extra: {k: [1, 2]}}) { ok } }'
    for name, schema in schemas.items():
        result = graphql_sync(schema, mutation)
        print(f"{name:13s} {result.data} {result.errors or ''}")


if __name__ == "__main__":
    main()
