from __future__ import annotations

from datetime import datetime  # noqa: TC003  # Pydantic resolves the field annotations at runtime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.constants import DiffAction

from .predicates import parse_diff_action

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff, NodeDiffElement

_UPDATED = DiffAction.UPDATED.name


class DiffChangeTimes(BaseModel):
    """When the nodes, fields and relationship peers of a branch diff last changed.

    A diff summary carries what changed against the base branch, not when. These times come from the
    same stored diff as the summary, so both describe one state of the branch.
    """

    model_config = ConfigDict(frozen=True)

    from_time: datetime
    to_time: datetime
    nodes: dict[str, datetime] = Field(default_factory=dict)
    fields: dict[str, dict[str, datetime]] = Field(default_factory=dict)
    """Keyed by node id, then by attribute or relationship name."""
    peers: dict[str, dict[str, dict[str, datetime]]] = Field(default_factory=dict)
    """Keyed by node id, then by relationship name, then by peer id."""


def changes_since(*, diff_summary: list[NodeDiff], change_times: DiffChangeTimes, since: datetime) -> list[NodeDiff]:
    """Return the entries of a diff summary that changed at or after ``since``.

    A field changed in that time counts as updated whatever its action: a value changed back to the
    value of the base branch is unchanged against that branch, yet whatever read the value in between
    is stale. A field or node with no recorded time is kept unless the diff marks it unchanged, so a
    missing time can only select more.
    """
    recent: list[NodeDiff] = []
    for node_diff in diff_summary:
        field_times = change_times.fields.get(node_diff["id"], {})
        elements = [
            _as_updated(element)
            for element in node_diff["elements"]
            if _changed_since(changed_at=field_times.get(element["name"]), since=since, action=element["action"])
        ]
        node_unchanged = _is_unchanged(node_diff["action"])
        if not elements and (
            node_unchanged
            or not _changed_since(
                changed_at=change_times.nodes.get(node_diff["id"]), since=since, action=node_diff["action"]
            )
        ):
            continue
        recent.append(
            {
                "branch": node_diff["branch"],
                "kind": node_diff["kind"],
                "id": node_diff["id"],
                "action": _UPDATED if node_unchanged else node_diff["action"],
                "display_label": node_diff["display_label"],
                "elements": elements,
            }
        )
    return recent


def peers_changed_since(
    *, change_times: DiffChangeTimes, node_id: str, relationship_name: str, since: datetime
) -> set[str]:
    """Return the peers added to or removed from a relationship of a node at or after ``since``."""
    peer_times = change_times.peers.get(node_id, {}).get(relationship_name, {})
    return {peer_id for peer_id, changed_at in peer_times.items() if changed_at >= since}


def _is_unchanged(action: str) -> bool:
    return parse_diff_action(action) == DiffAction.UNCHANGED


def _changed_since(*, changed_at: datetime | None, since: datetime, action: str) -> bool:
    if changed_at is None:
        return not _is_unchanged(action)
    return changed_at >= since


def _as_updated(element: NodeDiffElement) -> NodeDiffElement:
    if not _is_unchanged(element["action"]):
        return element
    updated: NodeDiffElement = {
        "name": element["name"],
        "element_type": element["element_type"],
        "action": _UPDATED,
        "summary": element["summary"],
    }
    if "peers" in element:
        updated["peers"] = element["peers"]
    return updated
