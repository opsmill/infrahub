from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffSummary

from infrahub.core.diff.model.diff import DiffElementType

QUERY_UNIQUE_TARGETS = """
query GetNetworkDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges {
            node {
                name { value }
                color { value }
            }
        }
    }
}
"""

QUERY_NON_UNIQUE_TARGETS = """
query GetAllNetworkDevices {
    TestNetworkDevice {
        edges {
            node {
                name { value }
                color { value }
            }
        }
    }
}
"""


def make_node_diff(
    node_id: str,
    kind: str,
    branch: str,
    field_names: list[str],
    action: str = "updated",
) -> NodeDiff:
    """Build a NodeDiff for use in diff summary cache."""
    return NodeDiff(
        branch=branch,
        action=action,
        kind=kind,
        id=node_id,
        display_label="",
        elements=[
            NodeDiffElement(
                name=field_name,
                element_type=DiffElementType.ATTRIBUTE.value,
                action="updated",
                summary=NodeDiffSummary(added=0, updated=1, removed=0),
            )
            for field_name in field_names
        ],
    )
