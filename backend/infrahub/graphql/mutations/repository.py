from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Self, cast

import httpx
from graphene import Boolean, Field, InputObjectType, Mutation, String

from infrahub import config
from infrahub.core.constants import InfrahubKind, MetadataOptions, PermissionAction
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import ValidationError
from infrahub.git.divergence.suppression import RetargetMarkers
from infrahub.git.models import (
    GitReadOnlyRepositoryImportCommit,
    GitRepositoryImportObjects,
    GitRepositoryPullReadOnly,
)
from infrahub.graphql.types.common import IdentifierInput
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse
from infrahub.permissions.types import define_object_permission_from_branch
from infrahub.repositories.create_repository import RepositoryFinalizer
from infrahub.workflows.catalogue import (
    GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
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
    from infrahub.core.protocols import CoreRepository
    from infrahub.database import InfrahubDatabase
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
        repo_node = node or await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db,
            kind=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            include_metadata=MetadataOptions.LINKED_NODES,
        )
        return await super().mutate_update(info, data, branch, database=graphql_context.db, node=repo_node)

    @classmethod
    async def _call_mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> tuple[Node, Self]:
        """Update the repository, and pull and import the new target of a re-pointed read-only repository.

        The workflows start only after the update commits, because a submitted workflow still runs when the
        transaction rolls back. This holds only when the database handed in is not already a transaction.
        """
        if obj.get_kind() != InfrahubKind.READONLYREPOSITORY:
            return await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=db, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

        # Read from the database, because a retried update hands back the node an earlier attempt changed.
        stored = await NodeManager.get_one(
            db=db, id=obj.get_id(), kind=CoreReadOnlyRepository, branch=branch, raise_on_error=True
        )
        current_ref = stored.ref.value
        current_commit = stored.commit.value

        obj, result = await super()._call_mutate_update(
            info=info, data=data, branch=branch, db=db, obj=obj, skip_uniqueness_check=skip_uniqueness_check
        )

        new_ref = obj.get_attribute("ref").value
        new_commit = data.commit.value if data.commit and data.commit.value else None
        # A cleared commit is a change too, because the repository then follows the head of its ref.
        if new_ref != current_ref or obj.get_attribute("commit").value != current_commit:
            log.info(
                "update read-only repository commit",
                name=obj.get_attribute("name").value,
                commit=new_commit,
                ref=new_ref,
            )
            await cls._pull_new_read_only_target(info=info, branch=branch, repository=obj, commit=new_commit)
        return obj, result

    @classmethod
    async def _pull_new_read_only_target(
        cls, info: GraphQLResolveInfo, branch: Branch, repository: Node, commit: str | None
    ) -> None:
        graphql_context: GraphqlContext = info.context
        if not graphql_context.service:
            return

        name = str(repository.get_attribute("name").value)
        ref = str(repository.get_attribute("ref").value)
        await graphql_context.service.workflow.submit_workflow(
            workflow=GIT_REPOSITORIES_PULL_READ_ONLY,
            context=graphql_context.get_context(),
            parameters={
                "model": GitRepositoryPullReadOnly(
                    repository_id=repository.get_id(),
                    repository_name=name,
                    location=str(repository.get_attribute("location").value),
                    ref=ref,
                    commit=commit,
                    infrahub_branch_name=branch.name,
                    infrahub_branch_id=str(branch.get_uuid()),
                    target_changed=True,
                )
            },
        )
        await graphql_context.service.workflow.submit_workflow(
            workflow=GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
            context=graphql_context.get_context(),
            parameters={
                "model": GitReadOnlyRepositoryImportCommit(
                    repository_id=repository.get_id(),
                    repository_name=name,
                    repository_kind=repository.get_kind(),
                    infrahub_branch_name=branch.name,
                    ref=ref,
                    target_changed=True,
                )
            },
        )

    @classmethod
    async def mutate_update_object(
        cls,
        db: InfrahubDatabase,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> Node:
        """Update the repository, and mark a change of the default branch of a read-write repository.

        The marker is written before the transaction commits, so no sync reads the new default branch without
        it. Without the marker, the next sync reports the switch to another git branch as a trunk rewrite.
        """
        if obj.get_kind() != InfrahubKind.REPOSITORY:
            return await super().mutate_update_object(
                db=db, info=info, data=data, branch=branch, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

        # Read from the database, because a retried update hands back the node an earlier attempt changed.
        stored = await NodeManager.get_one(
            db=db, id=obj.get_id(), kind=InfrahubKind.REPOSITORY, branch=branch, raise_on_error=True
        )
        current_default_branch = stored.get_attribute("default_branch").value

        obj = await super().mutate_update_object(
            db=db, info=info, data=data, branch=branch, obj=obj, skip_uniqueness_check=skip_uniqueness_check
        )

        new_default_branch = obj.get_attribute("default_branch").value
        if new_default_branch != current_default_branch:
            graphql_context: GraphqlContext = info.context
            await RetargetMarkers(cache=graphql_context.active_service.cache).mark(
                repository_id=obj.get_id(), target=str(new_default_branch)
            )
        return obj


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
