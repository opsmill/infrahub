"""Names of the Profile and Template kinds generated from a node.

A generated kind's name is fully determined by the kind it derives from, so callers that
only need to look one up do not have to walk the schema.
"""

from __future__ import annotations

from infrahub.core.constants import PROFILE_NAMESPACE, TEMPLATE_NAMESPACE


def get_profile_kind(node_kind: str) -> str:
    return f"{PROFILE_NAMESPACE}{node_kind}"


def get_object_template_kind(node_kind: str) -> str:
    return f"{TEMPLATE_NAMESPACE}{node_kind}"


def get_kind_with_derived_kinds(node_kind: str) -> tuple[str, str, str]:
    """Return the kind with the Profile and Template kinds generated from it."""
    return (node_kind, get_profile_kind(node_kind=node_kind), get_object_template_kind(node_kind=node_kind))
