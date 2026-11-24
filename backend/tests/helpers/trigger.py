from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from prefect.server.events.schemas.automations import EventTrigger as PrefectServerEventTrigger
from prefect.server.events.schemas.events import RelatedResource, Resource

from infrahub.core.branch import Branch
from infrahub.core.changelog.models import AttributeChangelog, NodeChangelog
from infrahub.events.node_action import NodeUpdatedEvent
from tests.helpers.events import dummy_event_meta

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.events.models import InfrahubEvent
    from infrahub.trigger.models import TriggerDefinition


def _node_updated_event(kind: str, field: str, branch_name: str) -> NodeUpdatedEvent:
    """Build the event a live edit of one attribute on one node emits."""
    changelog = NodeChangelog(node_id=str(uuid4()), node_kind=kind, display_label="node01")
    changelog.attributes[field] = AttributeChangelog(name=field, value="value01", value_previous=None, kind="Text")
    return NodeUpdatedEvent(
        kind=changelog.node_kind,
        node_id=changelog.node_id,
        changelog=changelog,
        fields=changelog.updated_fields,
        meta=dummy_event_meta(branch=Branch(name=branch_name, uuid=uuid4())),
    )


def _automation_covers_event(trigger_definition: TriggerDefinition, event: InfrahubEvent) -> bool:
    """Report whether the automation built from this definition selects the event.

    Uses `EventTrigger.covers_resources`, the entry point the task manager calls to route an
    event to an automation, so this tracks a server-side signature that an upgrade could move.
    """
    server_trigger = PrefectServerEventTrigger.model_validate(trigger_definition.trigger.get_prefect().model_dump())
    return server_trigger.covers_resources(
        resource=Resource(root=event.get_resource()),
        related=[RelatedResource(root=item) for item in event.get_related()],
    )


def branches_covered_by(
    triggers_by_scope: Mapping[str, TriggerDefinition], kind: str, field: str, branch_names: list[str]
) -> dict[str, list[str]]:
    """Map each branch to the scopes of the automations that fire for a live edit on it."""
    return {
        branch_name: sorted(
            scope
            for scope, trigger in triggers_by_scope.items()
            if _automation_covers_event(
                trigger_definition=trigger,
                event=_node_updated_event(kind=kind, field=field, branch_name=branch_name),
            )
        )
        for branch_name in branch_names
    }
