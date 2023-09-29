from typing import Dict, List, Optional

from infrahub import lock
from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.events import ArtifactMessageAction, InfrahubArtifactRPC
from infrahub.message_bus.rpc import InfrahubRpcClient


async def execute_task_in_pool(task, semaphore, *args, **kwargs):
    async with semaphore:
        return await task(*args, **kwargs)


class CoreArtifactDefinition(Node):
    @staticmethod
    async def generate_one_artifact(
        db: InfrahubDatabase,
        rpc_client: InfrahubRpcClient,
        schema: NodeSchema,
        definition: Node,
        repository: Node,
        query: Node,
        target: Node,
        transformation: Node,
    ) -> None:
        # only one generation task for the same target/definition combo concurrently
        async with lock.registry.get(f"{target.id}-{definition.id}", namespace="artifact"):
            artifacts = await registry.manager.query(
                db=db, schema=schema, filters={"definition__ids": [definition.id], "object__ids": [target.id]}
            )

            if len(artifacts) == 0:
                artifact = await Node.init(db=db, schema=schema, branch=definition._branch)
                await artifact.new(
                    db=db,
                    name=definition.artifact_name.value,
                    status="Pending",
                    content_type=definition.content_type.value,
                    object=target.id,
                    definition=definition.id,
                )
                await artifact.save(db=db)
            else:
                artifact = artifacts[0]

            message = InfrahubArtifactRPC(
                action=ArtifactMessageAction.GENERATE,
                repository=repository,
                artifact=await artifact.to_graphql(db=db),
                target=await target.to_graphql(db=db),
                definition=await definition.to_graphql(db=db),
                branch_name=definition._branch.name,
                query=await query.to_graphql(db=db),
                transformation=await transformation.to_graphql(db=db),
            )

            await rpc_client.call(message=message, wait_for_response=False)

    async def generate(
        self,
        db: InfrahubDatabase,
        rpc_client: InfrahubRpcClient,
        nodes: Optional[List[str]] = None,
        # max_concurrent_execution: int = 5,
    ) -> List[str]:
        # pylint: disable=no-member
        transformation: Node = await self.transformation.get_peer(db=db)  # type: ignore[attr-defined]
        query: Node = await transformation.query.get_peer(db=db)  # type: ignore[attr-defined]
        repository: Node = await transformation.repository.get_peer(db=db)  # type: ignore[attr-defined]

        # TODO Check payload and do an intersection with the list of nodes provided if any
        group: Node = await self.targets.get_peer(db=db)  # type: ignore[attr-defined]
        members_dict: Dict[str, Node] = await group.members.get_peers(db=db)  # type: ignore[attr-defined]
        members = list(members_dict.values())

        if nodes is None:
            nodes = []
        # group_filter = {"member_of_groups__ids": [group.id]}
        # if nodes:
        #     group_filter["ids"] = nodes

        # node_schema = registry.schema.get(name="CoreNode", branch=self._branch)
        # members = await registry.manager.query(
        #     db=db,
        #     schema=node_schema,
        #     filters=group_filter,
        #     branch=self._branch,
        #     prefetch_relationships=True,
        # )

        artifact_schema = registry.schema.get(name="CoreArtifact", branch=self._branch)

        # tasks = []
        # limit_concurrent_execution = asyncio.Semaphore(max_concurrent_execution)

        # TODO need to revisit this part to avoid pulling all members in the first place
        targets = [member for member in members if len(nodes) != 0 and member.id in nodes or len(nodes) == 0]

        for target in targets:
            # TODO Execute these tasks in a Pool
            await self.generate_one_artifact(
                db=db,
                rpc_client=rpc_client,
                schema=artifact_schema,
                definition=self,
                repository=repository,
                target=target,
                query=query,
                transformation=transformation,
            )

        return [target.id for target in targets]
