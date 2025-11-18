from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Self, cast

import httpx
from graphene import Boolean, Field, InputObjectType, Mutation, String

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub.core.schema import NodeSchema
from infrahub.git.models import (
    GitRepositoryImportObjects,
    GitRepositoryPullReadOnly,
)
from infrahub.graphql.types.common import IdentifierInput
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse
from infrahub.repositories.create_repository import RepositoryFinalizer
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_IMPORT_OBJECTS,
    GIT_REPOSITORIES_PULL_READ_ONLY,
)

from ...core.node.create import create_node
from ..types.task import TaskInfo
from .main import InfrahubMutationMixin, InfrahubMutationOptions, build_graphql_response

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


class InfrahubRepositoryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema | None = None, _meta=None, **options) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        cleanup_payload(data)
        db = database or graphql_context.db
        create_data = dict(data)
        create_data.update(override_data or {})
        obj = await create_node(data=create_data, db=db, branch=branch, schema=cls._meta.active_schema)

        await RepositoryFinalizer(
            account_session=graphql_context.active_account_session,
            services=graphql_context.active_service,
            context=graphql_context.get_context(),
        ).post_create(
            obj=obj,  # type: ignore
            branch=branch,
            db=db,
        )

        graphql_response = await build_graphql_response(info=info, db=db, obj=obj)
        return obj, cls(**graphql_response)

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        node: Node | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        cleanup_payload(data)
        if not node:
            node: CoreReadOnlyRepository | CoreRepository = await NodeManager.get_one_by_id_or_default_filter(
                db=graphql_context.db,
                kind=cls._meta.schema.kind,
                id=data.get("id"),
                branch=branch,
                include_owner=True,
                include_source=True,
            )
        if node.get_kind() != InfrahubKind.READONLYREPOSITORY:
            return await super().mutate_update(info, data, branch, database=graphql_context.db, node=node)

        node = cast(CoreReadOnlyRepository, node)
        current_commit = node.commit.value
        current_ref = node.ref.value
        new_commit = None
        if data.commit and data.commit.value:
            new_commit = data.commit.value
        new_ref = None
        if data.ref and data.ref.value:
            new_ref = data.ref.value

        obj, result = await super().mutate_update(info, data, branch, database=graphql_context.db, node=node)
        obj = cast(CoreReadOnlyRepository, obj)

        send_update_message = (new_commit and new_commit != current_commit) or (new_ref and new_ref != current_ref)
        if not send_update_message:
            return obj, result

        log.info(
            "update read-only repository commit",
            name=obj.name.value,
            commit=data.commit.value if data.commit else None,
            ref=data.ref.value if data.ref else None,
        )

        model = GitRepositoryPullReadOnly(
            repository_id=obj.id,
            repository_name=obj.name.value,
            location=obj.location.value,
            ref=obj.ref.value,
            commit=new_commit,
            infrahub_branch_name=branch.name,
            infrahub_branch_id=str(branch.get_uuid()),
        )
        if graphql_context.service:
            await graphql_context.service.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_PULL_READ_ONLY,
                context=graphql_context.get_context(),
                parameters={"model": model},
            )
        return obj, result


def cleanup_payload(data: InputObjectType | dict[str, Any]) -> None:
    """If the input payload contains an http URL that doesn't end in .git it will be added to the payload"""
    http_without_dotgit = r"^(https?://)(?!.*\.git$).*"
    if (
        data.get("location")
        and data["location"].get("value")
        and re.match(http_without_dotgit, data["location"]["value"])
    ):
        url = httpx.URL(data["location"]["value"])
        if url.host in config.SETTINGS.git.append_git_suffix:
            data["location"]["value"] = f"{data['location']['value']}.git"


class ProcessRepository(Mutation):
    class Arguments:
        data = IdentifierInput(required=True)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: IdentifierInput,
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context
        branch = graphql_context.branch
        repository_id = str(data.id)
        repo: CoreReadOnlyRepository | CoreRepository = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db,
            kind=InfrahubKind.GENERICREPOSITORY,
            id=str(data.id),
            branch=branch,
        )

        model = GitRepositoryImportObjects(
            repository_id=repository_id,
            repository_name=str(repo.name.value),
            repository_kind=repo.get_kind(),
            commit=str(repo.commit.value),
            infrahub_branch_name=branch.name,
        )
        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=GIT_REPOSITORIES_IMPORT_OBJECTS, context=graphql_context.get_context(), parameters={"model": model}
        )
        task = {"id": workflow.id}
        return cls(ok=True, task=task)


class ValidateRepositoryConnectivity(Mutation):
    class Arguments:
        data = IdentifierInput(required=True)

    ok = Boolean(required=True)
    message = String(required=True)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: IdentifierInput,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context
        branch = graphql_context.branch
        repository_id = str(data.id)
        repo: CoreReadOnlyRepository | CoreRepository = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db,
            kind=InfrahubKind.GENERICREPOSITORY,
            id=repository_id,
            branch=branch,
        )

        message = messages.GitRepositoryConnectivity(
            repository_name=str(repo.name.value),
            repository_location=str(repo.location.value),
        )
        if graphql_context.service:
            response = await graphql_context.service.message_bus.rpc(
                message=message, response_class=GitRepositoryConnectivityResponse
            )

        return {"ok": response.data.success, "message": response.data.message}
