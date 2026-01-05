from typing import Any

from graphql import (
    FieldNode,
    FragmentSpreadNode,
    GraphQLResolveInfo,
    InlineFragmentNode,
    SelectionSetNode,
)


class GraphQLFieldExtractor:
    """Class to extract fields from a GraphQL selection set."""

    def __init__(self, info: GraphQLResolveInfo):
        self.info = info
        self.fragments = info.fragments

    def get_fields(self) -> dict[str, Any]:
        """Extract fields from the GraphQL selection set."""
        fields = self._extract_fields(selection_set=self.info.field_nodes[0].selection_set)
        return fields or {}

    def _extract_fields(self, selection_set: SelectionSetNode | None) -> dict[str, dict] | None:
        """This function extract all the requested fields in a tree of Dict from a SelectionSetNode

        The goal of this function is to limit the fields that we need to query from the backend.

        Currently the function support Fields and InlineFragments but in a combined tree where the fragments are merged together
        This implementation may seam counter intuitive but in the current implementation
        it's better to have slightly more information at time passed to the query manager.

        In the future we'll probably need to redesign how we read GraphQL queries to generate better Database query.
        """

        if not selection_set:
            return None

        fields: dict[str, dict | Any] = {}
        for node in selection_set.selections:
            sub_selection_set = getattr(node, "selection_set", None)
            if isinstance(node, FieldNode):
                value = self._extract_fields(sub_selection_set)
                if node.name.value not in fields:
                    fields[node.name.value] = value
                elif isinstance(fields[node.name.value], dict) and isinstance(value, dict):
                    fields[node.name.value].update(value)

            elif isinstance(node, InlineFragmentNode):
                for sub_node in node.selection_set.selections:
                    sub_sub_selection_set = getattr(sub_node, "selection_set", None)
                    value = self._extract_fields(sub_sub_selection_set)
                    sub_node_name = getattr(sub_node, "name", "")
                    sub_node_name_value = getattr(sub_node_name, "value", "")
                    if sub_node_name_value not in fields:
                        fields[sub_node_name_value] = self._extract_fields(sub_sub_selection_set)
                    elif isinstance(fields[sub_node_name_value], dict) and isinstance(value, dict):
                        fields[sub_node_name_value].update(value)
            elif isinstance(node, FragmentSpreadNode):
                if node.name.value in self.info.fragments:
                    if fragment_fields := self._extract_fields(self.info.fragments[node.name.value].selection_set):
                        fields.update(fragment_fields)

        return fields


def extract_graphql_fields(info: GraphQLResolveInfo) -> dict[str, Any]:
    graphql_extractor = GraphQLFieldExtractor(info=info)
    return graphql_extractor.get_fields()
