from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Self

from graphene import Boolean, InputField, InputObjectType, List, Mutation, String
from infrahub_sdk.utils import compare_lists

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.changelog.models import NodeChangelog, RelationshipChangelogGetter
from infrahub.core.constants import (
    InfrahubKind,
    MetadataOptions,
    PermissionAction,
    PermissionDecision,
    RelationshipCardinality,
)
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeGetKindQuery
from infrahub.core.query.relationship import (
    RelationshipGetPeerQuery,
    RelationshipPeerData,
)
from infrahub.core.relationship import Relationship
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.events import EventMeta
from infrahub.events.group_action import GroupMemberAddedEvent, GroupMemberRemovedEvent
from infrahub.events.models import EventNode
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.groups.ancestors import collect_ancestors
from infrahub.permissions import get_global_permission_for_kind
from infrahub.profiles.node_applier import NodeProfilesApplier

from ..types import RelatedNodeInput

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship import RelationshipManager
    from infrahub.core.schema.relationship_schema import RelationshipSchema

    from ..initialization import GraphqlContext


RELATIONSHIP_PEERS_TO_IGNORE = [InfrahubKind.NODE]


class GroupUpdateType(StrEnum):
    NONE = "none"
    MEMBERS = "members"
    MEMBER_OF_GROUPS = "member_of_groups"


class RelationshipNodesInput(InputObjectType):
    id = InputField(String(required=True), description="ID of the node at the source of the relationship")
    name = InputField(String(required=True), description="Name of the relationship to add or remove nodes")
    nodes = InputField(
        List(of_type=RelatedNodeInput), description="List of nodes to add or remove to the relationships"
    )


async def _emit_relationship_add_events(
    *,
    graphql_context: GraphqlContext,
    group_event_type: GroupUpdateType,
    source: Node,
    peers: list[EventNode],
    node_changelog: NodeChangelog,
    relationship_name: str,
) -> None:
    """Schedule background events for an add-relationship mutation.

    Dispatches a single event shape based on ``group_event_type``:
    - ``MEMBERS``: one ``GroupMemberAddedEvent`` for the source group.
    - ``MEMBER_OF_GROUPS``: one ``GroupMemberAddedEvent`` per peer group.
    - otherwise: a ``NodeUpdatedEvent`` for the source plus one per
      downstream relationship changelog.

    No-op when the GraphQL context lacks background/service/account_session
    or when ``node_changelog`` has no changes.
    """
    if not (
        graphql_context.background
        and graphql_context.account_session
        and graphql_context.service
        and node_changelog.has_changes
    ):
        return

    event_context = graphql_context.to_event_context()

    if group_event_type == GroupUpdateType.MEMBERS:
        ancestors = await collect_ancestors(
            db=graphql_context.db,
            branch=graphql_context.branch,
            node_kind=source.get_schema().kind,
            node_id=source.id,
        )
        group_add_event = GroupMemberAddedEvent(
            node_id=source.id,
            kind=source.get_schema().kind,
            members=peers,
            ancestors=ancestors,
            meta=EventMeta(branch=graphql_context.branch, context=event_context),
        )
        graphql_context.background.add_task(graphql_context.active_service.event.send, group_add_event)
        return

    if group_event_type == GroupUpdateType.MEMBER_OF_GROUPS:
        group_ids = [node.id for node in peers]
        async with graphql_context.db.start_session() as db:
            node_kind_query = await NodeGetKindQuery.init(db=db, branch=graphql_context.branch, ids=group_ids)
            await node_kind_query.execute(db=db)
            node_kind_map = await node_kind_query.get_node_kind_map()

            for node_id, node_kind in node_kind_map.items():
                ancestors = await collect_ancestors(
                    db=graphql_context.db, branch=graphql_context.branch, node_kind=node_kind, node_id=node_id
                )
                group_add_event = GroupMemberAddedEvent(
                    node_id=node_id,
                    kind=node_kind,
                    ancestors=ancestors,
                    members=[EventNode(id=source.get_id(), kind=source.get_kind())],
                    meta=EventMeta(branch=graphql_context.branch, context=event_context),
                )
                graphql_context.background.add_task(graphql_context.active_service.event.send, group_add_event)
        return

    main_event = NodeUpdatedEvent(
        kind=source.get_schema().kind,
        node_id=source.id,
        changelog=node_changelog,
        fields=[relationship_name],
        meta=EventMeta(branch=graphql_context.branch, context=event_context),
    )
    relationship_changelogs = RelationshipChangelogGetter(db=graphql_context.db, branch=graphql_context.branch)
    node_changelogs = await relationship_changelogs.get_changelogs(primary_changelog=node_changelog)

    events: list[NodeUpdatedEvent] = [main_event]
    for downstream_changelog in node_changelogs:
        events.append(
            NodeUpdatedEvent(
                kind=downstream_changelog.node_kind,
                node_id=downstream_changelog.node_id,
                changelog=downstream_changelog,
                fields=downstream_changelog.updated_fields,
                meta=EventMeta.from_parent(parent=main_event),
            )
        )

    for event in events:
        graphql_context.background.add_task(graphql_context.active_service.event.send, event)


class RelationshipAdd(Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="relationship_add")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: RelationshipNodesInput,
        context: ContextInput | None = None,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        relationship_name = str(data.name)

        source = await _validate_node(info=info, data=data)
        nodes = await _validate_peers(info=info, data=data)
        await _validate_permissions(info=info, source_node=source, peers=nodes)
        await _validate_peer_types(info=info, data=data, source_node=source, peers=nodes)
        await _validate_peer_parents(info=info, data=data, source_node=source, peers=nodes)

        # This has to be done after validating the permissions
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        rel_schema = source.get_schema().get_relationship(name=relationship_name)
        display_label = await source.get_display_label(db=graphql_context.db)
        node_changelog = NodeChangelog(
            node_id=source.get_id(), node_kind=source.get_kind(), display_label=display_label
        )

        existing_peers = await _collect_current_peers(info=info, data=data, source_node=source)
        _validate_cardinality_add(data=data, rel_schema=rel_schema, existing_peers=existing_peers)

        group_event_type = _get_group_event_type(
            node=source, relationship_schema=rel_schema, relationship_name=relationship_name
        )

        async with graphql_context.db.start_transaction() as db:
            peers: list[EventNode] = []
            relationship_modified = False
            for node_data in data.get("nodes"):
                # Instantiate and resolve a relationship
                # This will take care of allocating a node from a pool if needed
                rel = Relationship(
                    schema=rel_schema, branch=graphql_context.branch, source_kind=source.get_kind(), node=source
                )
                await rel.new(db=db, data=node_data)
                await rel.resolve(db=db, user_id=graphql_context.assigned_user_id)
                # Save it only if it does not exist
                if rel.get_peer_id() not in existing_peers.keys():
                    if group_event_type != GroupUpdateType.NONE:
                        peers.append(EventNode(id=rel.get_peer_id(), kind=nodes[rel.get_peer_id()].get_kind()))
                    node_changelog.create_relationship(relationship=rel)
                    await rel.save(db=db, user_id=graphql_context.assigned_user_id)
                    relationship_modified = True

            # peers that need to have their profile source cleared
            profile_sourced_peers = [peer for peer in existing_peers.values() if peer.is_from_profile]
            await _apply_profiles_after_relationship_change(
                db=db,
                branch=graphql_context.branch,
                source=source,
                related_peers=nodes,
                relationship_name=relationship_name,
                rel_schema=rel_schema,
                relationship_modified=relationship_modified,
                profile_sourced_peers=profile_sourced_peers,
                user_id=graphql_context.assigned_user_id,
            )

        await _emit_relationship_add_events(
            graphql_context=graphql_context,
            group_event_type=group_event_type,
            source=source,
            peers=peers,
            node_changelog=node_changelog,
            relationship_name=relationship_name,
        )

        return cls(ok=True)


class RelationshipRemove(Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="relationship_remove")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: RelationshipNodesInput,
        context: ContextInput | None = None,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        relationship_name = str(data.name)

        source = await _validate_node(info=info, data=data)
        nodes = await _validate_peers(info=info, data=data)
        await _validate_permissions(info=info, source_node=source, peers=nodes)
        await _validate_peer_types(info=info, data=data, source_node=source, peers=nodes)

        # This has to be done after validating the permissions
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        rel_schema = source.get_schema().get_relationship(name=relationship_name)
        display_label: str = await source.get_display_label(db=graphql_context.db) or ""
        node_changelog = NodeChangelog(
            node_id=source.get_id(), node_kind=source.get_kind(), display_label=display_label
        )

        existing_peers = await _collect_current_peers(info=info, data=data, source_node=source)
        _validate_optional_remove(data=data, rel_schema=rel_schema, existing_peers=existing_peers)
        group_event_type = _get_group_event_type(
            node=source, relationship_schema=rel_schema, relationship_name=relationship_name
        )

        async with graphql_context.db.start_transaction() as db:
            peers: list[EventNode] = []
            relationship_modified = False
            removed_peer_ids: set[str] = set()

            for node_data in data.get("nodes"):
                if node_data.get("id") in existing_peers.keys():
                    # TODO once https://github.com/opsmill/infrahub/issues/792 has been fixed
                    # we should use RelationshipDeleteQuery to delete the relationship
                    # it would be more query efficient
                    rel = Relationship(
                        schema=rel_schema, branch=graphql_context.branch, source_kind=source.get_kind(), node=source
                    )
                    rel.load(db=db, data=existing_peers[node_data.get("id")])
                    if group_event_type != GroupUpdateType.NONE:
                        peers.append(EventNode(id=rel.get_peer_id(), kind=nodes[rel.get_peer_id()].get_kind()))
                    node_changelog.delete_relationship(relationship=rel)
                    await rel.delete(db=db, user_id=graphql_context.assigned_user_id)
                    removed_peer_ids.add(str(node_data.get("id")))
                    relationship_modified = True

            # remaining peers that need to have their profile source cleared
            profile_sourced_peers = [
                peer
                for peer_id, peer in existing_peers.items()
                if peer.is_from_profile and peer_id not in removed_peer_ids
            ]
            await _apply_profiles_after_relationship_change(
                db=db,
                branch=graphql_context.branch,
                source=source,
                related_peers=nodes,
                relationship_name=relationship_name,
                rel_schema=rel_schema,
                relationship_modified=relationship_modified,
                profile_sourced_peers=profile_sourced_peers,
                user_id=graphql_context.assigned_user_id,
            )

        if (
            graphql_context.background
            and graphql_context.account_session
            and graphql_context.service
            and node_changelog.has_changes
        ):
            event_context = graphql_context.to_event_context()
            if group_event_type == GroupUpdateType.MEMBERS:
                ancestors = await collect_ancestors(
                    db=graphql_context.db,
                    branch=graphql_context.branch,
                    node_kind=source.get_schema().kind,
                    node_id=source.id,
                )
                group_remove_event = GroupMemberRemovedEvent(
                    node_id=source.id,
                    kind=source.get_schema().kind,
                    members=peers,
                    ancestors=ancestors,
                    meta=EventMeta(branch=graphql_context.branch, context=event_context),
                )
                graphql_context.background.add_task(graphql_context.active_service.event.send, group_remove_event)
            elif group_event_type == GroupUpdateType.MEMBER_OF_GROUPS:
                group_ids = [node.id for node in peers]
                async with graphql_context.db.start_session() as db:
                    node_kind_query = await NodeGetKindQuery.init(db=db, branch=graphql_context.branch, ids=group_ids)
                    await node_kind_query.execute(db=db)
                    node_kind_map = await node_kind_query.get_node_kind_map()

                    for node_id, node_kind in node_kind_map.items():
                        ancestors = await collect_ancestors(
                            db=graphql_context.db, branch=graphql_context.branch, node_kind=node_kind, node_id=node_id
                        )
                        group_remove_event = GroupMemberRemovedEvent(
                            node_id=node_id,
                            kind=node_kind,
                            members=[EventNode(id=source.get_id(), kind=source.get_kind())],
                            meta=EventMeta(branch=graphql_context.branch, context=event_context),
                        )
                        graphql_context.background.add_task(
                            graphql_context.active_service.event.send, group_remove_event
                        )
            else:
                main_event = NodeUpdatedEvent(
                    kind=source.get_schema().kind,
                    node_id=source.id,
                    changelog=node_changelog,
                    fields=[relationship_name],
                    meta=EventMeta(branch=graphql_context.branch, context=event_context),
                )

                relationship_changelogs = RelationshipChangelogGetter(
                    db=graphql_context.db, branch=graphql_context.branch
                )
                node_changelogs = await relationship_changelogs.get_changelogs(primary_changelog=node_changelog)

                events = [main_event]

                for node_changelog in node_changelogs:
                    meta = EventMeta.from_parent(parent=main_event)
                    event = NodeUpdatedEvent(
                        kind=node_changelog.node_kind,
                        node_id=node_changelog.node_id,
                        changelog=node_changelog,
                        fields=node_changelog.updated_fields,
                        meta=meta,
                    )
                    events.append(event)

                for event in events:
                    graphql_context.background.add_task(graphql_context.active_service.event.send, event)

        return cls(ok=True)


async def _validate_node(info: GraphQLResolveInfo, data: RelationshipNodesInput) -> Node:
    graphql_context: GraphqlContext = info.context
    input_id = str(data.id)
    relationship_name = str(data.name)

    if not (
        source := await NodeManager.get_one(
            db=graphql_context.db,
            id=input_id,
            branch=graphql_context.branch,
            include_metadata=MetadataOptions.NONE,
        )
    ):
        raise NodeNotFoundError(node_type="node", identifier=input_id, branch_name=graphql_context.branch.name)

    if relationship_name not in source.get_schema().relationship_names:
        raise ValidationError({"name": f"'{relationship_name}' is not a valid relationship for '{source.get_kind()}'"})

    rel_schema = source.get_schema().get_relationship(name=relationship_name)
    if rel_schema.read_only:
        # These mutations should never be allowed to update read-only relationships, as those typically
        # have custom code tied to them such as the approved_by relationship of a CoreProposedChange.
        raise ValidationError({source.get_kind(): f"'{relationship_name}' is a read-only relationship"})

    return source


async def _validate_peers(info: GraphQLResolveInfo, data: RelationshipNodesInput) -> dict[str, Node]:
    graphql_context: GraphqlContext = info.context

    # Query the node in the database and validate that all of them exist and are if the correct kind
    node_ids: list[str] = [node_data["id"] for node_data in data.get("nodes") if "id" in node_data]
    nodes = await NodeManager.get_many(
        db=graphql_context.db, ids=node_ids, fields={"display_label": None}, branch=graphql_context.branch
    )
    _, _, in_list2 = compare_lists(list1=list(nodes.keys()), list2=node_ids)
    if in_list2:
        for node_id in in_list2:
            raise ValidationError(f"{node_id!r}: Unable to find the node in the database.")
    return nodes


async def _validate_permissions(info: GraphQLResolveInfo, source_node: Node, peers: dict[str, Node]) -> None:
    graphql_context: GraphqlContext = info.context

    if graphql_context.account_session:
        impacted_schemas = {node.get_schema() for node in [source_node] + list(peers.values())}
        required_permissions: list[GlobalPermission | ObjectPermission] = []
        decision = (
            PermissionDecision.ALLOW_DEFAULT.value
            if graphql_context.branch.is_default
            else PermissionDecision.ALLOW_OTHER.value
        )

        for impacted_schema in impacted_schemas:
            global_action = get_global_permission_for_kind(schema=impacted_schema)

            if global_action:
                required_permissions.append(GlobalPermission(action=global_action, decision=decision))
            else:
                required_permissions.append(
                    ObjectPermission(
                        namespace=impacted_schema.namespace,
                        name=impacted_schema.name,
                        action=PermissionAction.UPDATE.value,
                        decision=decision,
                    )
                )

        graphql_context.active_permissions.raise_for_permissions(permissions=required_permissions)


async def _validate_peer_types(
    info: GraphQLResolveInfo, data: RelationshipNodesInput, source_node: Node, peers: dict[str, Node]
) -> None:
    graphql_context: GraphqlContext = info.context
    relationship_name = str(data.name)
    input_id = str(data.id)
    rel_schema = source_node.get_schema().get_relationship(name=relationship_name)
    for node_id, node in peers.items():
        if rel_schema.peer in RELATIONSHIP_PEERS_TO_IGNORE:
            continue
        if rel_schema.peer not in node.get_labels():
            raise ValidationError(f"{node_id!r} {node.get_kind()!r} is not a valid peer for '{rel_schema.peer}'")

        peer_relationships = [rel for rel in node.get_schema().relationships if rel.identifier == rel_schema.identifier]
        if (
            rel_schema.identifier
            and len(peer_relationships) == 1
            and peer_relationships[0].cardinality == RelationshipCardinality.ONE
        ):
            peer_relationship: RelationshipManager = getattr(node, peer_relationships[0].name)
            if peer := await peer_relationship.get_peer(db=graphql_context.db):
                if peer.id != input_id:
                    raise ValidationError(
                        f"{node_id!r} {node.get_kind()!r} is already related to another peer on '{peer_relationships[0].name}'"
                    )


async def _validate_peer_parents(
    info: GraphQLResolveInfo, data: RelationshipNodesInput, source_node: Node, peers: dict[str, Node]
) -> None:
    relationship_name = str(data.name)
    rel_schema = source_node.get_schema().get_relationship(name=relationship_name)
    if not rel_schema.common_parent:
        return

    graphql_context: GraphqlContext = info.context

    source_node_parent = await source_node.get_parent_relationship_peer(
        db=graphql_context.db, name=rel_schema.common_parent
    )
    if not source_node_parent:
        # If the schema is properly validated we are not expecting this to happen
        raise ValidationError(f"Node {source_node.id} ({source_node.get_kind()!r}) does not have a parent peer")

    parents: set[str] = {source_node_parent.id}
    for peer in peers.values():
        peer_parent = await peer.get_parent_relationship_peer(db=graphql_context.db, name=rel_schema.common_parent)
        if not peer_parent:
            # If the schema is properly validated we are not expecting this to happen
            raise ValidationError(f"Peer {peer.id} ({peer.get_kind()!r}) does not have a parent peer")
        parents.add(peer_parent.id)

    if len(parents) > 1:
        raise ValidationError(
            f"Cannot relate {source_node.id!r} to '{relationship_name}' peers that do not have the same parent"
        )


async def _collect_current_peers(
    info: GraphQLResolveInfo, data: RelationshipNodesInput, source_node: Node
) -> dict[str, RelationshipPeerData]:
    graphql_context: GraphqlContext = info.context
    relationship_name = str(data.name)

    rel_schema = source_node.get_schema().get_relationship(name=relationship_name)

    # The nodes that are already present in the db
    # include SOURCE metadata for handling profile-sourcing updates if necessary
    query = await RelationshipGetPeerQuery.init(
        db=graphql_context.db,
        source=source_node,
        rel=Relationship(
            schema=rel_schema, branch=graphql_context.branch, source_kind=source_node.get_kind(), node=source_node
        ),
        include_metadata=MetadataOptions.SOURCE,
    )
    await query.execute(db=graphql_context.db)
    return {str(peer.peer_id): peer for peer in query.get_peers()}


def _validate_cardinality_add(
    data: RelationshipNodesInput, rel_schema: RelationshipSchema, existing_peers: dict[str, RelationshipPeerData]
) -> None:
    if rel_schema.cardinality != RelationshipCardinality.ONE:
        return
    if existing_peers:
        raise ValidationError(f"'{rel_schema.name}' is a cardinality-one relationship and already has a peer")
    if len(data.get("nodes")) > 1:
        raise ValidationError(
            f"'{rel_schema.name}' is a cardinality-one relationship and cannot be assigned more than one peer"
        )


def _validate_optional_remove(
    data: RelationshipNodesInput,
    rel_schema: RelationshipSchema,
    existing_peers: dict[str, RelationshipPeerData],
) -> None:
    if rel_schema.optional is True:
        return
    peers_to_remove = {node_data.get("id") for node_data in data.get("nodes") if node_data.get("id")}
    remaining = set(existing_peers.keys()) - peers_to_remove
    if not remaining:
        raise ValidationError({"name": f"'{rel_schema.name}' is a mandatory relationship and cannot be fully removed"})


def _get_group_event_type(
    node: Node, relationship_schema: RelationshipSchema, relationship_name: str
) -> GroupUpdateType:
    group_event_type = GroupUpdateType.NONE
    if relationship_schema.identifier == "group_member":
        if "CoreGroup" in node.get_schema().inherit_from and relationship_name == "members":
            # Updating members of a group
            group_event_type = GroupUpdateType.MEMBERS

        elif relationship_name == "member_of_groups":
            # Modifying the membership of the current node
            group_event_type = GroupUpdateType.MEMBER_OF_GROUPS
    return group_event_type


async def _apply_profiles(node: Node, db: InfrahubDatabase, branch: Branch) -> None:
    refreshed_node = await NodeManager.get_one(db=db, id=node.get_id(), branch=branch)
    node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_profiles_applier.apply_profiles(node=refreshed_node)
    if updated_fields:
        await refreshed_node.save(db=db, fields=updated_fields)


async def _detach_relationship_from_profiles(
    db: InfrahubDatabase,
    branch: Branch,
    source: Node,
    rel_schema: RelationshipSchema,
    profile_sourced_peers: list[RelationshipPeerData],
    user_id: str,
) -> None:
    """Detach a relationship from its profile by clearing the source from its profile-sourced peers.

    A relationship is either entirely profile-sourced or entirely user-defined. A user modification to a
    profile-sourced relationship turns it into a user-defined one: the peers are kept and only their
    profile source is cleared (the relationships are not deleted).

    The peers are passed in already loaded (with source metadata) by the caller so the relationships are
    not re-read.
    """
    for peer_data in profile_sourced_peers:
        rel = Relationship(schema=rel_schema, branch=branch, source_kind=source.get_kind(), node=source)
        rel.load(db=db, data=peer_data)
        rel.clear_source()
        await rel.update(db=db, properties_to_update=["source"], data=peer_data, user_id=user_id)


async def _apply_profiles_after_relationship_change(
    db: InfrahubDatabase,
    branch: Branch,
    source: Node,
    related_peers: dict[str, Node],
    relationship_name: str,
    rel_schema: RelationshipSchema,
    relationship_modified: bool,
    profile_sourced_peers: list[RelationshipPeerData],
    user_id: str,
) -> None:
    if relationship_name == "profiles":
        await _apply_profiles(node=source, db=db, branch=branch)
    elif source.get_schema().is_profile_schema and relationship_name == "related_nodes":
        for node in related_peers.values():
            await _apply_profiles(node=node, db=db, branch=branch)
    elif relationship_modified and rel_schema.support_profiles:
        await _detach_relationship_from_profiles(
            db=db,
            branch=branch,
            source=source,
            rel_schema=rel_schema,
            profile_sourced_peers=profile_sourced_peers,
            user_id=user_id,
        )
