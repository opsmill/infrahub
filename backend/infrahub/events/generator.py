from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.changelog.models import RelationshipChangelogGetter
from infrahub.core.constants import MutationAction
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeDeletedEvent, NodeMutatedEvent, NodeUpdatedEvent, get_node_event
from infrahub.groups.parsers import GroupNodeMutationParser
from infrahub.worker import WORKER_IDENTITY

from .models import EventMeta, InfrahubEvent


async def generate_node_mutation_events(
    node: Node,
    deleted_nodes: list[Node],
    db: InfrahubDatabase,
    branch: Branch,
    context: InfrahubContext,
    request_id: str,
    action: MutationAction,
) -> list[InfrahubEvent]:
    meta = EventMeta(
        account_id=context.account.account_id,
        initiator_id=WORKER_IDENTITY,
        request_id=request_id,
        branch=branch,
        context=context,
    )
    node_event_class = get_node_event(action)
    main_event = node_event_class(
        kind=node.get_kind(),
        node_id=node.id,
        changelog=node.node_changelog,
        fields=node.node_changelog.updated_fields,
        meta=meta,
    )
    relationship_changelogs = RelationshipChangelogGetter(db=db, branch=branch)
    node_changelogs = await relationship_changelogs.get_changelogs(primary_changelog=node.node_changelog)

    events: list[NodeMutatedEvent] = [main_event]

    deleted_changelogs = [deleted_node.node_changelog for deleted_node in deleted_nodes if deleted_node.id != node.id]
    deleted_ids = {deleted_node.node_id for deleted_node in deleted_changelogs}

    for node_changelog in deleted_changelogs:
        meta = EventMeta.from_parent(parent=main_event)
        delete_event = NodeDeletedEvent(
            kind=node_changelog.node_kind,
            node_id=node_changelog.node_id,
            changelog=node_changelog,
            fields=node_changelog.updated_fields,
            meta=meta,
        )
        events.append(delete_event)

    for node_changelog in node_changelogs:
        if node_changelog.node_id not in deleted_ids:
            meta = EventMeta.from_parent(parent=main_event)
            update_event = NodeUpdatedEvent(
                kind=node_changelog.node_kind,
                node_id=node_changelog.node_id,
                changelog=node_changelog,
                fields=node_changelog.updated_fields,
                meta=meta,
            )
            events.append(update_event)

    group_parser = GroupNodeMutationParser(db=db, branch=branch)
    group_events = await group_parser.group_events_from_node_actions(events=events)
    return events + group_events
