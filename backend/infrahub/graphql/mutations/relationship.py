from __future__ import annotations

from typing import TYPE_CHECKING, Self

from graphene import Boolean, InputField, InputObjectType, List, Mutation, String
from infrahub_sdk.utils import compare_lists

from infrahub import config
from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import InfrahubKind, MutationAction, RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.query.relationship import (
    RelationshipGetPeerQuery,
    RelationshipPeerData,
)
from infrahub.core.relationship import Relationship
from infrahub.database import retry_db_transaction
from infrahub.events import EventMeta, NodeMutatedEvent
from infrahub.events.group_action import GroupMemberAddedEvent, GroupMemberRemovedEvent
from infrahub.events.models import EventNode
from infrahub.exceptions import NodeNotFoundError, ValidationError

from ..types import RelatedNodeInput

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.relationship import RelationshipManager

    from ..initialization import GraphqlContext


RELATIONSHIP_PEERS_TO_IGNORE = [InfrahubKind.NODE]


class RelationshipNodesInput(InputObjectType):
    id = InputField(String(required=True), description="ID of the node at the source of the relationship")
    name = InputField(String(required=True), description="Name of the relationship to add or remove nodes")
    nodes = InputField(
        List(of_type=RelatedNodeInput), description="List of nodes to add or remove to the relationships"
    )


class RelationshipMixin:
    @classmethod
    async def mutate(  # noqa: PLR0915
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: RelationshipNodesInput,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        input_id = str(data.id)
        relationship_name = str(data.name)

        if not (
            source := await NodeManager.get_one(
                db=graphql_context.db,
                id=input_id,
                branch=graphql_context.branch,
                include_owner=False,
                include_source=False,
            )
        ):
            raise NodeNotFoundError(node_type="node", identifier=input_id, branch_name=graphql_context.branch.name)

        # Check if the name of the relationship provided exist for this node and is of cardinality Many
        if relationship_name not in source._schema.relationship_names:
            raise ValidationError(
                {"name": f"'{relationship_name}' is not a valid relationship for '{source.get_kind()}'"}
            )

        rel_schema = source._schema.get_relationship(name=relationship_name)
        if rel_schema.cardinality != RelationshipCardinality.MANY:
            raise ValidationError({"name": f"'{relationship_name}' must be a relationship of cardinality Many"})

        is_group_event = rel_schema.identifier == "group_member" and "CoreGroup" in source._schema.inherit_from

        # Query the node in the database and validate that all of them exist and are if the correct kind
        node_ids: list[str] = [node_data["id"] for node_data in data.get("nodes") if "id" in node_data]
        nodes = await NodeManager.get_many(
            db=graphql_context.db, ids=node_ids, fields={"display_label": None}, branch=graphql_context.branch
        )

        _, _, in_list2 = compare_lists(list1=list(nodes.keys()), list2=node_ids)
        if in_list2:
            for node_id in in_list2:
                raise ValidationError(f"{node_id!r}: Unable to find the node in the database.")

        for node_id, node in nodes.items():
            if rel_schema.peer in RELATIONSHIP_PEERS_TO_IGNORE:
                continue
            if rel_schema.peer not in node.get_labels():
                raise ValidationError(f"{node_id!r} {node.get_kind()!r} is not a valid peer for '{rel_schema.peer}'")

            peer_relationships = [rel for rel in node._schema.relationships if rel.identifier == rel_schema.identifier]
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

        display_label: str = await source.render_display_label(db=graphql_context.db)
        node_changelog = NodeChangelog(
            node_id=source.get_id(), node_kind=source.get_kind(), display_label=display_label
        )

        # The nodes that are already present in the db
        query = await RelationshipGetPeerQuery.init(
            db=graphql_context.db,
            source=source,
            rel=Relationship(schema=rel_schema, branch=graphql_context.branch, node=source),
        )
        await query.execute(db=graphql_context.db)
        existing_peers: dict[str, RelationshipPeerData] = {str(peer.peer_id): peer for peer in query.get_peers()}
        async with graphql_context.db.start_transaction() as db:
            members = []
            if cls.__name__ == "RelationshipAdd":
                for node_data in data.get("nodes"):
                    # Instantiate and resolve a relationship
                    # This will take care of allocating a node from a pool if needed
                    rel = Relationship(schema=rel_schema, branch=graphql_context.branch, node=source)
                    await rel.new(db=db, data=node_data)
                    await rel.resolve(db=db)
                    # Save it only if it does not exist
                    if rel.get_peer_id() not in existing_peers.keys():
                        members.append(EventNode(id=rel.get_peer_id(), kind=rel.get_peer_kind()))
                        node_changelog.create_relationship(relationship=rel)
                        await rel.save(db=db)

            elif cls.__name__ == "RelationshipRemove":
                for node_data in data.get("nodes"):
                    if node_data.get("id") in existing_peers.keys():
                        # TODO once https://github.com/opsmill/infrahub/issues/792 has been fixed
                        # we should use RelationshipDataDeleteQuery to delete the relationship
                        # it would be more query efficient
                        rel = Relationship(schema=rel_schema, branch=graphql_context.branch, node=source)
                        await rel.load(db=db, data=existing_peers[node_data.get("id")])
                        members.append(EventNode(id=rel.get_peer_id(), kind=rel.get_peer_kind()))
                        node_changelog.delete_relationship(relationship=rel)
                        await rel.delete(db=db)

        if config.SETTINGS.broker.enable and graphql_context.background:
            event = NodeMutatedEvent(
                kind=source._schema.kind,
                node_id=source.id,
                data=node_changelog,
                action=MutationAction.UPDATED,
                fields=[relationship_name],
                meta=EventMeta(
                    branch=graphql_context.branch,
                ),
            )
            graphql_context.background.add_task(graphql_context.active_service.event.send, event)
            if is_group_event:
                if cls.__name__ == "RelationshipAdd":
                    group_add_event = GroupMemberAddedEvent(
                        node_id=source.id, kind=source._schema.kind, members=members
                    )
                    graphql_context.background.add_task(graphql_context.active_service.event.send, group_add_event)
                elif cls.__name__ == "RelationshipRemove":
                    group_remove_event = GroupMemberRemovedEvent(
                        node_id=source.id, kind=source._schema.kind, members=members
                    )
                    graphql_context.background.add_task(graphql_context.active_service.event.send, group_remove_event)

        return cls(ok=True)  # type: ignore[call-arg]


class RelationshipAdd(RelationshipMixin, Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="relationship_add")
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: RelationshipNodesInput,
    ) -> Self:
        return await super().mutate(root=root, info=info, data=data)


class RelationshipRemove(RelationshipMixin, Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="relationship_remove")
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: RelationshipNodesInput,
    ) -> Self:
        return await super().mutate(root=root, info=info, data=data)
