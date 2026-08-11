"""Derive the human-friendly-id targets a data change affects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.schema.schema_branch_hfid import HFIDs


@dataclass(frozen=True)
class HFIDRecomputeTarget:
    """A human-friendly-id target to recompute, with the filter that locates its nodes.

    ``filter_key`` is ``"ids"`` when the changed node is itself the target and
    ``"<relationship>__ids"`` when other nodes read the changed node across a
    relationship.
    """

    target_kind: str
    filter_key: str
    reads_across_relationship: bool


def derive_hfid_targets(
    *,
    hfids: HFIDs,
    kind: str,
    changed_fields: Iterable[str] | None,
    include_self: bool,
    include_cross: bool,
) -> list[HFIDRecomputeTarget]:
    """Map a changed ``kind`` to the human-friendly-id targets it affects.

    ``include_self`` covers the changed node's own id, used for a creation.
    ``include_cross`` covers other nodes that read this kind across a relationship,
    used for an update or a deletion; a self-only id contributes nothing here.
    ``changed_fields`` of ``None`` means every field, which is what a deletion needs.
    """
    fields = None if changed_fields is None else frozenset(changed_fields)
    targets: dict[tuple[str, str], HFIDRecomputeTarget] = {}

    if include_self and hfids.targets_node(kind):
        targets[kind, "ids"] = HFIDRecomputeTarget(target_kind=kind, filter_key="ids", reads_across_relationship=False)

    if include_cross:
        relationship_triggers = hfids.get_related_trigger_nodes().get(kind)
        if relationship_triggers is not None:
            for attribute, identifiers in relationship_triggers.attributes.items():
                if fields is not None and attribute not in fields:
                    continue
                for identifier in identifiers:
                    targets[identifier.kind, identifier.filter_key] = HFIDRecomputeTarget(
                        target_kind=identifier.kind,
                        filter_key=identifier.filter_key,
                        reads_across_relationship=True,
                    )

    return list(targets.values())
