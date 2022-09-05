from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import graphql

from infrahub.core import get_branch
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node


def extract_global_kwargs(kwargs) -> Tuple[Timestamp, Branch, Node]:
    """Extract the timestamp, the branch and the account from the kwargs from GraphQL"""
    at = Timestamp(kwargs.get("at", None))

    branch = get_branch(kwargs.get("branch"))
    rebase = kwargs.get("rebase", False)
    branch.ephemeral_rebase = rebase

    account = kwargs.get("account", None)

    return at, branch, account


def selected_field_names_naive(selection_set: graphql.SelectionSetNode):
    """Get the list of field names that are selected at the current level. Does not include nested names.

    Limitations:
    * Does not resolve fragments; throws RuntimeError
    * Does not take directives into account. A field might be disabled, and this function wouldn't know

    As a result:
    * It will give a RuntimeError if a fragment is provided
    * It may give false positives in case directives are used
    * It is 20x faster than the alternative

    Benefits:
    * Fast!

    Args:
        selection_set: the selected fields

    Code copied from https://github.com/graphql-python/graphene/issues/57#issuecomment-774227086
        This link also includes a more powerful and complexe alternative.
    """
    assert isinstance(selection_set, graphql.SelectionSetNode)

    field_names = []

    for node in selection_set.selections:
        # Field
        if isinstance(node, graphql.FieldNode):
            field_names.append(node.name.value)
        # Fragment spread (`... fragmentName`)
        elif isinstance(node, (graphql.FragmentSpreadNode, graphql.InlineFragmentNode)):
            raise NotImplementedError("Fragments are not supported by this simplistic function")
        # Something new
        else:
            raise NotImplementedError(str(type(node)))

    return field_names


async def extract_fields(selection_set):  # -> dict[str, Selection_Set]

    if not selection_set:
        return None

    fields = {}
    for field in getattr(selection_set, "selections", []):
        sub_selection_set = getattr(field, "selection_set", None)
        fields[field.name.value] = await extract_fields(sub_selection_set)

    return fields


def print_query(info):
    """Traverse the query"""
    initial_selection_set = info.field_nodes[0].selection_set
    print_selection_set(initial_selection_set, 1)


def print_selection_set(selection_set, level: int = 1) -> int:
    # max_depth = level
    tab = "  "
    for field in getattr(selection_set, "selections", []):
        # print(f"in print_selection_set loop {field}")
        # The field we are at is already a lever deeper, even if it doesn't have its own selection set.
        # max_depth = max(max_depth, level + 1)
        print(f"{level*tab}{field.name.value}")
        if selection_set := getattr(field, "selection_set", None):
            # max_depth = max(max_depth, self._get_query_depth(selection_set, level + 1))
            print_selection_set(selection_set, level + 1)

    """
    MATCH (d:Device)
    WHERE (d)-[]-(:Attribute {name: "name"})-[]-(:AttributeValue {value: "spine1"})
    MAT36CH (d)-[:IS_RELATED]-(r1:Relationship{type: "device_interface"})-[:IS_RELATED]-(n1)
    WHERE (n1)-[]-(:Attribute {name: "enabled"})-[]-(:AttributeValue {value: false})
    OPTIONAL MATCH (d)-[:IS_RELATED]-(r1)-[:IS_RELATED]-(n1)-[:IS_RELATED]-(r2:Relationship {type: "interface_ip"})-[:IS_RELATED]-(n2)
    RETURN d,n1,r1,n2,r2
    """
