from dataclasses import dataclass

from infrahub.core.branch import Branch
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.events.group_action import GroupMemberAddedEvent, GroupMemberRemovedEvent, GroupMutatedEvent
from infrahub.events.models import EventMeta, EventNode, InfrahubEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeMutatedEvent, NodeUpdatedEvent
from infrahub.exceptions import SchemaNotFoundError

from .ancestors import collect_ancestors


@dataclass
class ApplicableEvent:
    event: NodeMutatedEvent
    node_schema: NodeSchema
    relationship: RelationshipCardinalityManyChangelog


class GroupNodeMutationParser:
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self._db = db
        self._branch = branch

    def _get_schema(self, kind: str) -> NodeSchema | None:
        try:
            node_schema = self._db.schema.get_node_schema(name=kind, branch=self._branch, duplicate=False)
        except (ValueError, SchemaNotFoundError):
            return None
        return node_schema

    def _get_applicable_events(self, events: list[NodeMutatedEvent]) -> list[ApplicableEvent]:
        applicable: list[ApplicableEvent] = []
        for event in events:
            if event_kind := self._get_schema(kind=event.kind):
                if (
                    InfrahubKind.GENERICGROUP in event_kind.inherit_from
                    and "members" in event.changelog.relationships
                    and isinstance(
                        event.changelog.relationships["members"],
                        RelationshipCardinalityManyChangelog,
                    )
                ):
                    applicable.append(
                        ApplicableEvent(
                            event=event,
                            node_schema=event_kind,
                            relationship=event.changelog.relationships["members"],
                        )
                    )
        return applicable

    async def group_events_from_node_actions(self, events: list[NodeMutatedEvent]) -> list[InfrahubEvent]:
        group_events: list[InfrahubEvent] = []

        for applicable_event in self._get_applicable_events(events=events):
            added_peers = [
                EventNode(id=peer.peer_id, kind=peer.peer_kind)
                for peer in applicable_event.relationship.peers
                if peer.peer_status == DiffAction.ADDED
            ]
            removed_peers = [
                EventNode(id=peer.peer_id, kind=peer.peer_kind)
                for peer in applicable_event.relationship.peers
                if peer.peer_status == DiffAction.REMOVED
            ]
            if added_peers:
                group_events.append(
                    await self._define_group_event(
                        event_type=GroupMemberAddedEvent, parent=applicable_event.event, peers=added_peers
                    )
                )

            if removed_peers:
                group_events.append(
                    await self._define_group_event(
                        event_type=GroupMemberRemovedEvent, parent=applicable_event.event, peers=removed_peers
                    )
                )

        return group_events

    async def _define_group_event(
        self,
        event_type: type[GroupMemberAddedEvent | GroupMemberRemovedEvent],
        parent: NodeMutatedEvent,
        peers: list[EventNode],
    ) -> GroupMutatedEvent:
        event_meta = EventMeta.from_parent(parent=parent)
        group_event = event_type(
            meta=event_meta,
            kind=parent.kind,
            node_id=parent.node_id,
            members=peers,
        )
        if isinstance(parent, NodeCreatedEvent | NodeUpdatedEvent):
            # Avoid trying to find ancestors for deleted nodes
            group_event.ancestors = await collect_ancestors(
                db=self._db,
                branch=self._branch,
                node_kind=parent.kind,
                node_id=parent.node_id,
            )
        return group_event
