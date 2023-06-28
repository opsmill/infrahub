from typing import TYPE_CHECKING

from graphene import Boolean, InputField, InputObjectType, List, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core.manager import NodeManager
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.exceptions import NodeNotFound

from ..types import RelatedNodeInput

if TYPE_CHECKING:
    from neo4j import AsyncSession


# pylint: disable=unused-argument


class RelationshipNodesInput(InputObjectType):
    id = InputField(String(required=True), description="ID of the node at the source of the relationship")
    name = InputField(String(required=True), description="Name of the relationship to add or remove nodes")
    nodes = InputField(
        List(of_type=RelatedNodeInput), description="List of nodes to add or remove to the relationships"
    )


class RelationshipMixin:
    @classmethod
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data,
    ):
        session: AsyncSession = info.context.get("infrahub_session")
        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")

        if not (
            source := await NodeManager.get_one(
                session=session, id=data.get("id"), branch=branch, at=at, include_owner=True, include_source=True
            )
        ):
            raise NodeNotFound(branch, None, data.get("id"))

        # Check if the name of the relationship provided exist for this node and is of type Many
        if data.get("name") not in source._schema.relationship_names:
            raise ValueError(f"'{data.get('name')}' is not a valid relationship for '{source.get_kind()}'")

        rel_schema = source._schema.get_relationship(name=data.get("name"))

        # The nodes that are already present in the db
        query = await RelationshipGetPeerQuery.init(
            session=session,
            source=source,
            at=at,
            rel=Relationship(schema=rel_schema, branch=branch, node=source),
        )
        await query.execute(session=session)
        existing_peers = {peer.peer_id: peer for peer in query.get_peers()}

        if cls.__name__ == "RelationshipAdd":
            for node_data in data.get("nodes"):
                if node_data.get("id") not in existing_peers.keys():
                    rel = Relationship(schema=rel_schema, branch=branch, at=at, node=source)
                    await rel.new(session=session, data=node_data)
                    await rel.save(session=session)

        elif cls.__name__ == "RelationshipRemove":
            for node_data in data.get("nodes"):
                if node_data.get("id") in existing_peers.keys():
                    rel = Relationship(schema=rel_schema, branch=branch, at=at, node=source)
                    await rel.load(session=session, data=existing_peers[node_data.get("id")])
                    await rel.delete(session=session)

        return cls(ok=True)


class RelationshipAdd(RelationshipMixin, Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)

    ok = Boolean()


class RelationshipRemove(RelationshipMixin, Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)

    ok = Boolean()
