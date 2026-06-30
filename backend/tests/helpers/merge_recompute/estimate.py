"""In-process derived expected-recompute estimate for the counting layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.events.node_action import NodeDeletedEvent, NodeMutatedEvent

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

COMPUTED_ATTRIBUTE = "computed_attribute"
DISPLAY_LABEL = "display_label"
HFID = "hfid"


def _related_trigger_fires(triggers: dict, *, changed_kind: str, changed_fields: set[str]) -> bool:
    """A cross-node derived value recomputes when a related kind it reads changes."""
    relationship_triggers = triggers.get(changed_kind)
    if relationship_triggers is None:
        return False
    return bool(set(relationship_triggers.attributes) & changed_fields)


def derive_expected_recompute(*, schema_branch: SchemaBranch, events: list) -> dict[str, int]:
    counts = {COMPUTED_ATTRIBUTE: 0, DISPLAY_LABEL: 0, HFID: 0}

    display_triggers = schema_branch.display_labels.get_related_trigger_nodes()
    hfid_triggers = schema_branch.hfids.get_related_trigger_nodes()

    for event in events:
        if not isinstance(event, NodeMutatedEvent) or isinstance(event, NodeDeletedEvent):
            continue
        kind: str = event.kind
        changed_fields: set[str] = set(event.fields or [])

        impacted_targets = schema_branch.computed_attributes.get_impacted_jinja2_targets(
            kind=kind, updates=sorted(changed_fields)
        )
        if any(resolved.target.kind != kind for resolved in impacted_targets):
            counts[COMPUTED_ATTRIBUTE] += 1

        if _related_trigger_fires(display_triggers, changed_kind=kind, changed_fields=changed_fields):
            counts[DISPLAY_LABEL] += 1

        if _related_trigger_fires(hfid_triggers, changed_kind=kind, changed_fields=changed_fields):
            counts[HFID] += 1

    return counts
