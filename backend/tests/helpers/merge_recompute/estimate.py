"""In-process derived expected-recompute estimate for the counting layer.

A node's own derived values (computed attribute, display label, human-friendly id
that read only that node's fields) are recomputed inline when the node is saved,
so they create no asynchronous recompute work. The asynchronous recompute fan-out
that the merge/rebase path pays for is the *cross-node* case: when a node that
other nodes read changes, each reader recomputes asynchronously.

Given the node events a merge emits and the schema, this predicts which derived
families fan out across a relationship for each changed node, using the same
pre-computed dependency facades the production processors consult. It counts, per
family, the number of changed nodes whose change fans out to that family. The
per-node job count is that figure times the number of readers of each changed
node, which depends on graph cardinality and is left to the authoritative timing
layer (in a one-reader-per-node dataset the two coincide).
"""

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
