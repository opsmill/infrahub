from __future__ import annotations

from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffSummary


def node_diff_element(*, name: str, action: str = "UPDATED", element_type: str = "ATTRIBUTE") -> NodeDiffElement:
    """Build one diff-summary element carrying a single-update summary.

    ``action`` mirrors the uppercase GraphQL enum name the diff summary emits (e.g. "UPDATED"), not the
    lowercase ``DiffAction`` value, so a consumer's case-insensitive match runs on production-shaped data.
    """
    return NodeDiffElement(
        name=name,
        element_type=element_type,
        action=action,
        summary=NodeDiffSummary(added=0, updated=1, removed=0),
    )


def node_diff(
    *,
    node_id: str,
    kind: str,
    branch: str = "main",
    action: str = "UPDATED",
    display_label: str = "node",
    field_names: list[str] | None = None,
    element_type: str = "ATTRIBUTE",
    elements: list[NodeDiffElement] | None = None,
) -> NodeDiff:
    """Build a diff-summary node entry as ``get_diff_summary`` emits it.

    Pass ``elements`` for full control over each element, or ``field_names`` to build one updated
    element per name (sharing ``action`` and ``element_type``). ``action`` mirrors the uppercase
    GraphQL enum name the diff summary emits, not the lowercase ``DiffAction`` value.
    """
    if elements is None:
        elements = [
            node_diff_element(name=name, action=action, element_type=element_type) for name in (field_names or [])
        ]
    return NodeDiff(
        branch=branch,
        kind=kind,
        id=node_id,
        action=action,
        display_label=display_label,
        elements=elements,
    )
