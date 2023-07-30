from typing import Dict, List, Optional

from neo4j import AsyncSession

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.message_bus.events import ArtifactMessageAction, InfrahubArtifactRPC
from infrahub.message_bus.rpc import InfrahubRpcClient


async def execute_task_in_pool(task, semaphore, *args, **kwargs):
    async with semaphore:
        return await task(*args, **kwargs)


class CoreArtifactDefinition(Node):
    @staticmethod
    async def generate_one_artifact(
        session: AsyncSession,
        rpc_client: InfrahubRpcClient,
        schema: NodeSchema,
        definition: Node,
        repository: Node,
        query: Node,
        object: Node,
        transformation: Node,
        artifact: Optional[Node] = None,
    ) -> None:
        if not artifact:
            artifact = await Node.init(session=session, schema=schema, branch=definition._branch)
            await artifact.new(
                session=session,
                name=definition.artifact_name.value,
                status="Pending",
                content_type=definition.content_type.value,
                object=object.id,
                definition=definition.id,
            )
            await artifact.save(session=session)

        message = InfrahubArtifactRPC(
            action=ArtifactMessageAction.GENERATE,
            repository=repository,
            artifact=await artifact.to_graphql(session=session),
            target=await object.to_graphql(session=session),
            definition=await definition.to_graphql(session=session),
            branch_name=definition._branch.name,
            query=await query.to_graphql(session=session),
            transformation=await transformation.to_graphql(session=session),
        )

        await rpc_client.call(message=message, wait_for_response=False)

    async def generate(
        self,
        session: AsyncSession,
        rpc_client: InfrahubRpcClient,
        nodes: Optional[List[str]] = None,
        max_concurrent_execution: int = 5,
    ) -> List[Node]:
        transformation: Node = await self.transformation.get_peer(session=session)  # type: ignore[attr-defined]
        query: Node = await transformation.query.get_peer(session=session)  # type: ignore[attr-defined]
        repository: Node = await transformation.repository.get_peer(session=session)  # type: ignore[attr-defined]

        # TODO Check payload and do an intersection with the list of nodes provided if any
        group: Node = await self.targets.get_peer(session=session)  # type: ignore[attr-defined]
        members: Dict[str, Node] = await group.members.get_peers(session=session)  # type: ignore[attr-defined]

        artifact_schema = registry.schema.get(name="CoreArtifact", branch=self._branch)
        artifacts = await registry.manager.query(
            session=session,
            schema=artifact_schema,
            filters={"definition__id": self.id},
            branch=self._branch,
            at=self._at,
            prefetch_relationships=True,
        )

        artifacts_by_member = {artifact.object.id: artifact for artifact in artifacts}

        # tasks = []
        # limit_concurrent_execution = asyncio.Semaphore(max_concurrent_execution)

        for member_id, member in members.items():
            # TODO Execute these tasks in a Pool
            await self.generate_one_artifact(
                session=session,
                rpc_client=rpc_client,
                schema=artifact_schema,
                definition=self,
                repository=repository,
                object=member,
                query=query,
                transformation=transformation,
                artifact=artifacts_by_member.get(member_id, None),
            )

        return list(members.keys())
