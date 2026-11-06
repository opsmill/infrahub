from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from graphql import ExecutionResult, GraphQLResolveInfo, build_schema, execute, parse

from infrahub.graphql.field_extractor import extract_graphql_fields_for_request

SCHEMA = build_schema(
    """
    type Query {
        items: [Item]
    }

    type Item {
        name: String
        child: Item
    }
    """
)

QUERY = "{ items { child { name child { name } } } }"


class Item:
    def __init__(self, name: str, extracted: list[dict[str, Any]]) -> None:
        self.name = name
        self._extracted = extracted

    def child(self, info: GraphQLResolveInfo) -> Item:
        list_index = info.path.prev
        if list_index is not None and list_index.prev is not None and list_index.prev.key == "items":
            # Only the outer `child` field, directly under an item of the list, records what it extracts.
            self._extracted.append(extract_graphql_fields_for_request(info))
        return Item(name=f"{self.name}/child", extracted=self._extracted)


def run(query: str, context: Any) -> tuple[ExecutionResult, list[dict[str, Any]]]:
    extracted: list[dict[str, Any]] = []
    root = {"items": [Item(name=name, extracted=extracted) for name in ("a", "b", "c")]}
    result = execute(SCHEMA, parse(query), root_value=root, context_value=context)
    assert isinstance(result, ExecutionResult)
    assert result.errors is None
    return result, extracted


def test_field_is_extracted_once_per_request() -> None:
    _, extracted = run(QUERY, context=SimpleNamespace(extracted_fields={}))

    assert extracted[0] == {"name": None, "child": {"name": None}}
    assert len(extracted) == 3
    assert all(fields is extracted[0] for fields in extracted)


def test_each_request_extracts_its_own_fields() -> None:
    _, first = run(QUERY, context=SimpleNamespace(extracted_fields={}))
    _, second = run(QUERY, context=SimpleNamespace(extracted_fields={}))

    assert first[0] == second[0]
    assert first[0] is not second[0]


def test_context_without_a_cache_extracts_on_each_call() -> None:
    _, extracted = run(QUERY, context=SimpleNamespace())

    assert all(fields == {"name": None, "child": {"name": None}} for fields in extracted)
    assert len({id(fields) for fields in extracted}) == 3


def test_fields_from_a_fragment_are_extracted() -> None:
    _, extracted = run(
        "fragment F on Item { name } { items { child { ...F } } }", context=SimpleNamespace(extracted_fields={})
    )

    assert extracted == [{"name": None}] * 3
