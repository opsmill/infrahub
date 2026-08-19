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
