"""Derive the display-label targets a data change affects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.schema.schema_branch_display import DisplayLabels


@dataclass(frozen=True)
class DisplayLabelRecomputeTarget:
    """A display-label target to recompute, with the filter that locates its nodes.

    ``filter_key`` is ``"ids"`` when the changed node is itself the target (located
    by its own id) and ``"<relationship>__ids"`` when other nodes read the changed
    node across a relationship (located by that relationship filter).
    """

    target_kind: str
    filter_key: str
    reads_across_relationship: bool


def derive_display_label_targets(
    *,
    display_labels: DisplayLabels,
    kind: str,
    changed_fields: Iterable[str] | None,
    include_self: bool,
    include_cross: bool,
) -> list[DisplayLabelRecomputeTarget]:
    """Map a changed ``kind`` to the display-label targets it affects.

    ``include_self`` covers the changed node's own display label, used for a
    creation. ``include_cross`` covers the display labels of other nodes that read
    this kind across a relationship, used for an update or a deletion. A same-node
    update needs neither here: its value recomputes inline on save. ``changed_fields``
    of ``None`` means every field, which is what a deletion needs because any read of
    the removed node is now stale.
    """
    fields = None if changed_fields is None else frozenset(changed_fields)
    targets: dict[tuple[str, str], DisplayLabelRecomputeTarget] = {}

    if include_self and display_labels.targets_node(kind):
        targets[kind, "ids"] = DisplayLabelRecomputeTarget(
            target_kind=kind, filter_key="ids", reads_across_relationship=False
        )

    if include_cross:
        relationship_triggers = display_labels.get_related_trigger_nodes().get(kind)
        if relationship_triggers is not None:
            for attribute, identifiers in relationship_triggers.attributes.items():
                if fields is not None and attribute not in fields:
                    continue
                for identifier in identifiers:
                    targets[identifier.kind, identifier.filter_key] = DisplayLabelRecomputeTarget(
                        target_kind=identifier.kind,
                        filter_key=identifier.filter_key,
                        reads_across_relationship=True,
                    )

    return list(targets.values())
