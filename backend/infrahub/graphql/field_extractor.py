from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from graphql import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    SelectionSetNode,
)


class GraphQLFieldExtractionInfo(Protocol):
    """The parts of a GraphQL resolve info that field extraction reads."""

    @property
    def field_nodes(self) -> Sequence[FieldNode]: ...

    @property
    def fragments(self) -> Mapping[str, FragmentDefinitionNode]: ...


class GraphQLFieldExtractor:
    """Class to extract fields from a GraphQL selection set."""

    def __init__(self, info: GraphQLFieldExtractionInfo) -> None:
        self.info = info
        self.fragments = info.fragments

    def get_fields(self) -> dict[str, Any]:
        """Extract fields from the GraphQL selection set."""
        fields = self._extract_fields(selection_set=self.info.field_nodes[0].selection_set)
        return fields or {}

    def _extract_fields(self, selection_set: SelectionSetNode | None) -> dict[str, Any] | None:
        """Collect the union of every field a selection set requests, as a tree of nested dicts.

        The goal is to limit the fields we read from the backend. A field's sub-selection becomes a
        nested dict; a leaf field maps to ``None``. Fragment spreads and inline fragments contribute
        their own selections, recursively and to any depth.

        Inline fragments are collected across every branch without resolving their type condition:
        the extraction runs before the concrete type is known, so it deliberately over-collects
        rather than risk under-fetching for an interface or union field.
        """
        if not selection_set:
            return None

        fields: dict[str, Any] = {}
        for node in selection_set.selections:
            if isinstance(node, FieldNode):
                self._merge_fields(target=fields, source={node.name.value: self._extract_fields(node.selection_set)})
            elif isinstance(node, InlineFragmentNode):
                self._merge_fields(target=fields, source=self._extract_fields(node.selection_set) or {})
            elif isinstance(node, FragmentSpreadNode) and node.name.value in self.info.fragments:
                fragment = self.info.fragments[node.name.value]
                self._merge_fields(target=fields, source=self._extract_fields(fragment.selection_set) or {})

        return fields

    @classmethod
    def _merge_fields(cls, target: dict[str, Any], source: dict[str, Any]) -> None:
        """Merge ``source`` into ``target`` in place, taking the union of overlapping sub-selections."""
        for name, value in source.items():
            existing = target.get(name)
            if isinstance(existing, dict) and isinstance(value, dict):
                cls._merge_fields(target=existing, source=value)
            elif name not in target or existing is None:
                target[name] = value


def extract_graphql_fields(info: GraphQLFieldExtractionInfo) -> dict[str, Any]:
    graphql_extractor = GraphQLFieldExtractor(info=info)
    return graphql_extractor.get_fields()
