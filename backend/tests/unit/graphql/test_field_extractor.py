from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from graphql import FragmentDefinitionNode, OperationDefinitionNode, parse

from infrahub.graphql.field_extractor import extract_graphql_fields

if TYPE_CHECKING:
    from graphql import FieldNode, GraphQLResolveInfo


@dataclass(frozen=True)
class _ResolveInfoStub:
    """The only two members the extractor reads from the resolve info of a root field."""

    field_nodes: list[FieldNode]
    """Every node the document selects under the response key being resolved."""

    fragments: dict[str, FragmentDefinitionNode]
    """The fragment definitions of the document, keyed by name."""


def _extract(query: str) -> dict[str, Any]:
    """Extract the selection of the document's first root field, as its resolver would see it."""
    document = parse(query)
    operation = next(node for node in document.definitions if isinstance(node, OperationDefinitionNode))
    fragments = {node.name.value: node for node in document.definitions if isinstance(node, FragmentDefinitionNode)}
    field_nodes = [cast("FieldNode", selection) for selection in operation.selection_set.selections]

    info = _ResolveInfoStub(field_nodes=field_nodes, fragments=fragments)
    return extract_graphql_fields(info=cast("GraphQLResolveInfo", info))


def test_a_fragment_spread_inside_an_inline_fragment_is_expanded() -> None:
    """A spread nested in an inline fragment contributes the fragment's fields, not its name."""
    fields = _extract("""
        query {
          InfrahubRepositoryCommits(repository_id: "x") {
            ... on RepositoryCommits {
              ...CommitState
            }
          }
        }

        fragment CommitState on RepositoryCommits {
          condition
        }
    """)

    # Resolves to {'CommitState': None} today.
    assert fields == {"condition": None}


def test_an_inline_fragment_inside_an_inline_fragment_is_expanded() -> None:
    """A nested inline fragment contributes the fields it selects, under their own names."""
    fields = _extract("""
        query {
          InfrahubRepositoryCommits(repository_id: "x") {
            ... on RepositoryCommits {
              ... on RepositoryCommits {
                condition
              }
            }
          }
        }
    """)

    # Resolves to {'': {'condition': None}} today.
    assert fields == {"condition": None}


def test_sibling_fragment_spreads_contribute_both_selections() -> None:
    """Two spreads selecting the same field keep the sub-selections of both."""
    fields = _extract("""
        query {
          BuiltinTag {
            ...TagName
            ...TagId
          }
        }

        fragment TagName on BuiltinTag {
          edges { node { name } }
        }

        fragment TagId on BuiltinTag {
          edges { node { id } }
        }
    """)

    # Resolves to {'edges': {'node': {'id': None}}} today.
    assert fields == {"edges": {"node": {"name": None, "id": None}}}


def test_a_field_selected_twice_keeps_both_nested_selections() -> None:
    """A field repeated under one response key keeps the sub-selections of every occurrence."""
    fields = _extract("""
        query {
          BuiltinTag {
            edges { node { name } }
            edges { node { id } }
          }
        }
    """)

    # Resolves to {'edges': {'node': {'id': None}}} today.
    assert fields == {"edges": {"node": {"name": None, "id": None}}}


def test_sibling_inline_fragments_keep_both_nested_selections() -> None:
    """Two inline fragments selecting the same field keep the sub-selections of both."""
    fields = _extract("""
        query {
          BuiltinTag {
            ... on BuiltinTag {
              edges { node { name } }
            }
            ... on BuiltinTag {
              edges { node { id } }
            }
          }
        }
    """)

    # Resolves to {'edges': {'node': {'id': None}}} today.
    assert fields == {"edges": {"node": {"name": None, "id": None}}}
