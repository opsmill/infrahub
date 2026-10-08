from __future__ import annotations

import re
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Self, cast

import httpx
from graphene import Boolean, Field, InputObjectType, Int, Mutation, String

from infrahub import config, lock
from infrahub.core.constants import (
    GlobalPermissions,
    InfrahubKind,
    MetadataOptions,
    PermissionAction,
    RepositoryInternalStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository, CoreReadOnlyRepository
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import DeliveryQueueChangedError, NothingPendingError, ValidationError
from infrahub.git.models import (
    GitReadOnlyRepositoryImportCommit,
    GitRepositoryDeliveryAbandon,
    GitRepositoryDeliveryRetry,
    GitRepositoryImportObjects,
    GitRepositoryPullReadOnly,
)
from infrahub.git.writeback.runs import delivery_run_tags
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.graphql.types.common import IdentifierInput
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse
from infrahub.permissions.globals import define_global_permission_from_branch
from infrahub.permissions.types import define_object_permission_from_branch
from infrahub.repositories.create_repository import RepositoryFinalizer
from infrahub.workflows.catalogue import (
    GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
    GIT_REPOSITORIES_IMPORT_OBJECTS,
    GIT_REPOSITORIES_PULL_READ_ONLY,
    GIT_REPOSITORY_DELIVERY_ABANDON,
    GIT_REPOSITORY_DELIVERY_RETRY,
)

from ...core.node.create import create_node
from ..types.task import TaskInfo
from .main import InfrahubMutationMixin, InfrahubMutationOptions, build_graphql_response

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreRepository
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import WritebackIntent
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


class InfrahubRepositoryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema | None = None, _meta: InfrahubMutationOptions | None = None, **options: Any
    ) -> None:
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
        repo_node: CoreReadOnlyRepository | CoreRepository | Node | None = node
        if not repo_node:
            repo_node = await NodeManager.get_one_by_id_or_default_filter(
                db=graphql_context.db,
                kind=cls._meta.schema.kind,
                id=data.get("id"),
                branch=branch,
                include_metadata=MetadataOptions.LINKED_NODES,
            )
        if repo_node.get_kind() != InfrahubKind.READONLYREPOSITORY:
            return await super().mutate_update(info, data, branch, database=graphql_context.db, node=repo_node)

        repo_node = cast("CoreReadOnlyRepository", repo_node)
        current_commit = repo_node.commit.value
        current_ref = repo_node.ref.value
        new_commit = None
        if data.commit and data.commit.value:
            new_commit = data.commit.value
        new_ref = None
        if data.ref and data.ref.value:
            new_ref = data.ref.value

        obj, result = await super().mutate_update(info, data, branch, database=graphql_context.db, node=repo_node)
        obj = cast("CoreReadOnlyRepository", obj)

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
        git_read_only_repo_import_commit_model = GitReadOnlyRepositoryImportCommit(
            repository_id=obj.id,
            repository_name=str(obj.name.value),
            repository_kind=obj.get_kind(),
            infrahub_branch_name=branch.name,
            ref=str(obj.ref.value),
        )
        if graphql_context.service:
            await graphql_context.service.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_PULL_READ_ONLY,
                context=graphql_context.get_context(),
                parameters={"model": model},
            )
            await graphql_context.service.workflow.submit_workflow(
                workflow=GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
                context=graphql_context.get_context(),
                parameters={"model": git_read_only_repo_import_commit_model},
            )
        return obj, result


def cleanup_payload(data: InputObjectType | dict[str, Any]) -> None:
    """If the input payload contains an http URL that doesn't end in .git it will be added to the payload."""
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
            workflow=GIT_REPOSITORIES_IMPORT_OBJECTS,
            context=graphql_context.get_context(),
            parameters={"model": model},
        )
        task = {"id": workflow.id}
        return cls(ok=True, task=task)


class ReadOnlyRepositoryImportLastCommit(Mutation):
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
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        branch = graphql_context.branch
        repository_id = str(data.id)

        schema = registry.get_node_schema(name=InfrahubKind.READONLYREPOSITORY, branch=branch.name, duplicate=False)
        permission = define_object_permission_from_branch(
            schema=schema, action=PermissionAction.UPDATE, branch_name=branch.name
        )
        graphql_context.active_permissions.raise_for_permission(permission=permission)

        repo = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db,
            kind=CoreReadOnlyRepository,
            id=str(data.id),
            branch=branch,
        )

        if repo.get_kind() != InfrahubKind.READONLYREPOSITORY:
            raise ValidationError(
                f"Node {data.id} is a {repo.get_kind()}, not a {InfrahubKind.READONLYREPOSITORY}. "
                "Import latest commit is only supported for read-only repositories."
            )

        model = GitReadOnlyRepositoryImportCommit(
            repository_id=repository_id,
            repository_name=str(repo.name.value),
            repository_kind=repo.get_kind(),
            infrahub_branch_name=branch.name,
            ref=str(repo.ref.value),
        )
        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
            context=graphql_context.get_context(),
            parameters={"model": model},
        )
        task = {"id": workflow.id}
        return cls(ok=True, task=task)


class RepositoryDeliveryRetryInput(InputObjectType):
    id = String(required=True, description="The id of the CoreRepository")


class RepositoryDeliveryRetry(Mutation):
    class Arguments:
        data = RepositoryDeliveryRetryInput(required=True)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: RepositoryDeliveryRetryInput,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        branch = graphql_context.branch
        # The default-branch permission checker acts only on requests that name the default branch.
        if branch.name != registry.default_branch:
            raise ValidationError(
                f"Send this request on the default branch {registry.default_branch}; the pending pushes live there."
            )

        schema = registry.get_node_schema(name=InfrahubKind.REPOSITORY, branch=branch.name, duplicate=False)
        for permission in (
            define_object_permission_from_branch(
                schema=schema, action=PermissionAction.UPDATE, branch_name=branch.name
            ),
            define_global_permission_from_branch(
                permission=GlobalPermissions.MANAGE_REPOSITORIES, branch_name=branch.name
            ),
            define_global_permission_from_branch(
                permission=GlobalPermissions.EDIT_DEFAULT_BRANCH, branch_name=branch.name
            ),
        ):
            graphql_context.active_permissions.raise_for_permission(permission=permission)

        repo = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db, kind=CoreGenericRepository, id=str(data.id), branch=branch
        )
        repository_name = repo.name.value
        if repo.get_kind() != InfrahubKind.REPOSITORY:
            raise ValidationError(f"Repository {repository_name} is read-only and never pushes to its remote.")
        if repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
            raise ValidationError(
                f"Repository {repository_name} is staging; its changes are pushed when its proposed change merges."
            )

        store = WritebackIntentStore(
            db=graphql_context.db, lock_registry=lock.registry, default_branch=branch, clock=partial(datetime.now, UTC)
        )
        intent = await store.read(repository_id=repo.id)
        if not intent.queue.entries:
            raise NothingPendingError(repository_name=repository_name)

        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=GIT_REPOSITORY_DELIVERY_RETRY,
            context=graphql_context.get_context(),
            parameters={"model": GitRepositoryDeliveryRetry(repository_id=repo.id, repository_name=repository_name)},
            tags=delivery_run_tags(repository_id=repo.id),
        )
        return cls(ok=True, task={"id": workflow.id})


def _check_delivery_permissions(graphql_context: GraphqlContext) -> None:
    """Refuse a request off the default branch, or from an account that cannot edit repositories there.

    Raises:
        ValidationError: The request is not on the default branch.
        PermissionDeniedError: The account lacks one of the permissions.

    """
    branch = graphql_context.branch
    if branch.name != registry.default_branch:
        raise ValidationError(
            f"Send this request on the default branch {registry.default_branch}; the pending pushes live there."
        )

    schema = registry.get_node_schema(name=InfrahubKind.REPOSITORY, branch=branch.name, duplicate=False)
    for permission in (
        define_object_permission_from_branch(schema=schema, action=PermissionAction.UPDATE, branch_name=branch.name),
        define_global_permission_from_branch(permission=GlobalPermissions.MANAGE_REPOSITORIES, branch_name=branch.name),
        define_global_permission_from_branch(permission=GlobalPermissions.EDIT_DEFAULT_BRANCH, branch_name=branch.name),
    ):
        graphql_context.active_permissions.raise_for_permission(permission=permission)


async def _read_pending_delivery(
    graphql_context: GraphqlContext, repository_id: str
) -> tuple[CoreGenericRepository, WritebackIntent]:
    """Return the repository and its delivery state, refusing a repository that has nothing to push.

    Raises:
        NodeNotFoundError: No repository has this id.
        ValidationError: The repository is read-only or staging.
        NothingPendingError: The queue is empty.

    """
    repository = await NodeManager.get_one_by_id_or_default_filter(
        db=graphql_context.db, kind=CoreGenericRepository, id=repository_id, branch=graphql_context.branch
    )
    name = repository.name.value
    if repository.get_kind() != InfrahubKind.REPOSITORY:
        raise ValidationError(f"Repository {name} is read-only and never pushes to its remote.")
    if repository.internal_status.value == RepositoryInternalStatus.STAGING.value:
        raise ValidationError(f"Repository {name} is staging; its changes are pushed when its proposed change merges.")

    intent = await WritebackIntentStore(
        db=graphql_context.db,
        lock_registry=lock.registry,
        default_branch=await registry.get_branch(db=graphql_context.db),
        clock=partial(datetime.now, UTC),
    ).read(repository_id=repository.id)
    if not intent.queue.entries:
        raise NothingPendingError(repository_name=name)
    return repository, intent


class RepositoryDeliveryAbandonInput(InputObjectType):
    id = String(required=True, description="The id of the CoreRepository")
    queue_version = Int(
        required=True,
        description="The version of the delivery queue the user saw. The request is refused if the queue changed since.",
    )


class RepositoryDeliveryAbandon(Mutation):
    class Arguments:
        data = RepositoryDeliveryAbandonInput(required=True)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: RepositoryDeliveryAbandonInput,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        _check_delivery_permissions(graphql_context=graphql_context)
        repository, intent = await _read_pending_delivery(graphql_context=graphql_context, repository_id=str(data.id))

        name = repository.name.value
        queue_version: int = data["queue_version"]
        if queue_version != intent.queue.version:
            raise DeliveryQueueChangedError(repository_name=name, queue_version=queue_version)

        model = GitRepositoryDeliveryAbandon(
            repository_id=repository.id, repository_name=name, queue_version=queue_version
        )
        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=GIT_REPOSITORY_DELIVERY_ABANDON,
            context=graphql_context.get_context(),
            parameters={"model": model},
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
            # A read-write repository must be push-able; a read-only one never pushes.
            requires_write=repo.get_kind() == InfrahubKind.REPOSITORY,
        )
        if graphql_context.service:
            response = await graphql_context.service.message_bus.rpc(
                message=message, response_class=GitRepositoryConnectivityResponse
            )
            # Persist the outcome so the repository's operational status reflects the connectivity
            # check rather than remaining stuck on its last-known value.
            repo.operational_status.value = response.data.operational_status
            # Scope the write to operational_status: the node was loaded before the connectivity
            # RPC, so persisting every field could clobber concurrent edits with stale values.
            await cast("Node", repo).save(db=graphql_context.db, fields=["operational_status"])

        return {"ok": response.data.success, "message": response.data.message}
