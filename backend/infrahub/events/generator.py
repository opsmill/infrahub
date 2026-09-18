from typing import TYPE_CHECKING, cast

from infrahub.core.branch import Branch
from infrahub.core.changelog.builder import build_relationship_changelog_getter
from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.constants import DiffAction, InfrahubKind, MutationAction
from infrahub.core.mutation_context import RecordedNode
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreThread
from infrahub.events.node_action import (
    NodeDeletedEvent,
    NodeMutatedEvent,
    NodeUpdatedEvent,
    get_node_event,
)
from infrahub.groups.parsers import GroupNodeMutationParser
from infrahub.worker import WORKER_IDENTITY

from .models import EventContext, EventMeta, InfrahubEvent
from .proposed_change_action import ProposedChangeThreadCreatedEvent, ProposedChangeThreadUpdatedEvent


def _peer_changes(
    relationship: RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog,
) -> set[tuple[str, DiffAction]]:
    """Return each peer the relationship change names, with whether the change added or removed it."""
    if isinstance(relationship, RelationshipCardinalityManyChangelog):
        return {(peer.peer_id, peer.peer_status) for peer in relationship.peers}
    changes = set()
    if relationship.peer_id:
        changes.add((relationship.peer_id, DiffAction.ADDED))
    if relationship.peer_id_previous:
        changes.add((relationship.peer_id_previous, DiffAction.REMOVED))
    return changes


def _holds_relationships(changelog: NodeChangelog, relationships: NodeChangelog) -> bool:
    """Return whether the changelog already lists every relationship change of the other one, peer and direction."""
    return all(
        name in changelog.relationships and _peer_changes(relationship) <= _peer_changes(changelog.relationships[name])
        for name, relationship in relationships.relationships.items()
    )


async def generate_node_mutation_events(
    node: Node,
    deleted_nodes: list[Node],
    db: InfrahubDatabase,
    branch: Branch,
    context: EventContext,
    request_id: str,
    action: MutationAction,
    recorded_nodes: list[RecordedNode] | None = None,
) -> list[InfrahubEvent]:
    meta = EventMeta(
        account_id=context.account_id,
        initiator_id=WORKER_IDENTITY,
        request_id=request_id,
        branch=branch,
        context=context,
    )
    main_node_changed = node.has_changelog and node.node_changelog.has_changes
    main_event = (
        get_node_event(action)(
            kind=node.get_kind(),
            node_id=node.id,
            changelog=node.node_changelog,
            fields=node.node_changelog.updated_fields,
            meta=meta,
        )
        if main_node_changed
        else None
    )
    node_changelogs = (
        await build_relationship_changelog_getter(db=db, branch=branch).get_changelogs(
            primary_changelog=node.node_changelog
        )
        if main_node_changed
        else []
    )
    events: list[NodeMutatedEvent] = [main_event] if main_event else []

    def child_meta() -> EventMeta:
        if main_event:
            return EventMeta.from_parent(parent=main_event)
        # Without an event of its own for the main node, a recorded node's event has no parent to point to.
        return EventMeta(
            account_id=context.account_id,
            initiator_id=WORKER_IDENTITY,
            request_id=request_id,
            branch=branch,
            context=context,
        )

    deleted_changelogs = [deleted_node.node_changelog for deleted_node in deleted_nodes if deleted_node.id != node.id]
    recorded_events: list[NodeMutatedEvent] = [
        get_node_event(recorded.action)(
            kind=recorded.node.get_kind(),
            node_id=recorded.node.id,
            changelog=recorded.node.node_changelog,
            fields=recorded.node.node_changelog.updated_fields,
            meta=child_meta(),
        )
        for recorded in recorded_nodes or []
        if recorded.node.has_changelog and recorded.node.node_changelog.has_changes
    ]

    deleted_node_ids = {node_changelog.node_id for node_changelog in deleted_changelogs}
    own_changelogs = {recorded_event.node_id: recorded_event.changelog for recorded_event in recorded_events}

    for node_changelog in deleted_changelogs:
        delete_event = NodeDeletedEvent(
            kind=node_changelog.node_kind,
            node_id=node_changelog.node_id,
            changelog=node_changelog,
            fields=node_changelog.updated_fields,
            meta=child_meta(),
        )
        events.append(delete_event)

    for node_changelog in node_changelogs:
        own_changelog = own_changelogs.get(node_changelog.node_id)
        if node_changelog.node_id not in deleted_node_ids and not (
            own_changelog and _holds_relationships(changelog=own_changelog, relationships=node_changelog)
        ):
            update_event = NodeUpdatedEvent(
                kind=node_changelog.node_kind,
                node_id=node_changelog.node_id,
                changelog=node_changelog,
                fields=node_changelog.updated_fields,
                meta=child_meta(),
            )
            events.append(update_event)

    group_parser = GroupNodeMutationParser(db=db, branch=branch)
    group_events = await group_parser.group_events_from_node_actions(events=events + recorded_events)

    specific_events: list[InfrahubEvent] = []
    if (kind := node.get_kind()) in [
        InfrahubKind.CHANGETHREAD,
        InfrahubKind.OBJECTTHREAD,
        InfrahubKind.ARTIFACTTHREAD,
        InfrahubKind.FILETHREAD,
    ]:
        proposed_change = await cast("CoreThread", node).change.get_peer(db=db)
        if proposed_change:
            action_to_event_map = {
                MutationAction.CREATED: ProposedChangeThreadCreatedEvent,
                MutationAction.UPDATED: ProposedChangeThreadUpdatedEvent,
            }
            if action in action_to_event_map:
                specific_events.append(
                    action_to_event_map[action](
                        proposed_change_id=proposed_change.id,
                        proposed_change_name=proposed_change.name.value,
                        proposed_change_state=proposed_change.state.value,
                        thread_id=node.id,
                        thread_kind=kind,
                        meta=EventMeta.from_context(context=context),
                    )
                )

    return events + recorded_events + group_events + specific_events
