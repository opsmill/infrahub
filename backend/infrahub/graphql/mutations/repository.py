from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional, cast

from graphene import Boolean, InputObjectType, Mutation, String

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository, CoreReadOnlyRepository, CoreRepository
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import ValidationError
from infrahub.graphql.types.common import IdentifierInput
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql import GraphqlContext

log = get_logger()


class InfrahubRepositoryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: Optional[NodeSchema] = None, _meta=None, **options):  # pylint: disable=arguments-differ
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
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
    ):
        context: GraphqlContext = info.context

        cleanup_payload(data)
        # Create the object in the database
        obj, result = await super().mutate_create(root, info, data, branch, at)
        obj = cast(CoreGenericRepository, obj)

        # First check the connectivity to the remote repository
        # If the connectivity is not good, we remove the repository to allow the user to add a new one
        if context.service:
            message = messages.GitRepositoryConnectivity(
                repository_name=obj.name.value,
                repository_location=obj.location.value,
            )
            response = await context.service.message_bus.rpc(
                message=message, response_class=GitRepositoryConnectivityResponse
            )

            if response.data.success is False:
                await obj.delete(db=context.db)
                raise ValidationError(response.data.message)

        # If we are in the default branch, we set the sync status to Active
        # If we are in another branch, we set the sync status to Staging
        if branch.is_default:
            obj.internal_status.value = RepositoryInternalStatus.ACTIVE.value
        else:
            obj.internal_status.value = RepositoryInternalStatus.STAGING.value
        await obj.save(db=context.db)

        # Create the new repository in the filesystem.
        log.info("create_repository", name=obj.name.value)
        authenticated_user = None
        if context.account_session and context.account_session.authenticated:
            authenticated_user = context.account_session.account_id
        if obj.get_kind() == InfrahubKind.READONLYREPOSITORY:
            obj = cast(CoreReadOnlyRepository, obj)
            message = messages.GitRepositoryAddReadOnly(
                repository_id=obj.id,
                repository_name=obj.name.value,
                location=obj.location.value,
                ref=obj.ref.value,
                infrahub_branch_name=branch.name,
                internal_status=obj.internal_status.value,
                created_by=authenticated_user,
            )
        else:
            obj = cast(CoreRepository, obj)
            message = messages.GitRepositoryAdd(
                repository_id=obj.id,
                repository_name=obj.name.value,
                location=obj.location.value,
                default_branch_name=obj.default_branch.value,
                infrahub_branch_name=branch.name,
                internal_status=obj.internal_status.value,
                created_by=authenticated_user,
            )

        if context.service:
            await context.service.send(message=message)

        # TODO Validate that the creation of the repository went as expected

        return obj, result

    @classmethod
    async def mutate_update(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ):
        context: GraphqlContext = info.context

        cleanup_payload(data)
        if not node:
            node: CoreReadOnlyRepository | CoreRepository = await NodeManager.get_one_by_id_or_default_filter(
                db=context.db,
                kind=cls._meta.schema.kind,
                id=data.get("id"),
                branch=branch,
                at=at,
                include_owner=True,
                include_source=True,
            )
        if node.get_kind() != InfrahubKind.READONLYREPOSITORY:
            return await super().mutate_update(root, info, data, branch, at, database=context.db, node=node)

        node = cast(CoreReadOnlyRepository, node)
        current_commit = node.commit.value
        current_ref = node.ref.value
        new_commit = None
        if data.commit and data.commit.value:
            new_commit = data.commit.value
        new_ref = None
        if data.ref and data.ref.value:
            new_ref = data.ref.value

        obj, result = await super().mutate_update(root, info, data, branch, at, database=context.db, node=node)
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

        message = messages.GitRepositoryPullReadOnly(
            repository_id=obj.id,
            repository_name=obj.name.value,
            location=obj.location.value,
            ref=obj.ref.value,
            commit=new_commit,
            infrahub_branch_name=branch.name,
        )
        if context.service:
            await context.service.send(message=message)
        return obj, result


def cleanup_payload(data: InputObjectType | dict[str, Any]) -> None:
    """If the input payload contains an http URL that doesn't end in .git it will be added to the payload"""
    http_without_dotgit = r"^(https?://)(?!.*\.git$).*"
    if (
        data.get("location")
        and data["location"].get("value")
        and re.match(http_without_dotgit, data["location"]["value"])
    ):
        data["location"]["value"] = f'{data["location"]["value"]}.git'


class ProcessRepository(Mutation):
    class Arguments:
        data = IdentifierInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: IdentifierInput,
    ) -> dict[str, bool]:
        context: GraphqlContext = info.context
        branch = context.branch
        repository_id = str(data.id)
        repo: CoreReadOnlyRepository | CoreRepository = await NodeManager.get_one_by_id_or_default_filter(
            db=context.db,
            kind=InfrahubKind.GENERICREPOSITORY,
            id=str(data.id),
            branch=branch,
        )

        message = messages.GitRepositoryImportObjects(
            repository_id=repository_id,
            repository_name=str(repo.name.value),
            repository_kind=repo.get_kind(),
            commit=str(repo.commit.value),
            infrahub_branch_name=branch.name,
        )
        if context.service:
            await context.service.send(message=message)
        return {"ok": True}


class ValidateRepositoryConnectivity(Mutation):
    class Arguments:
        data = IdentifierInput(required=True)

    ok = Boolean(required=True)
    message = String(required=True)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: IdentifierInput,
    ) -> dict[str, Any]:
        context: GraphqlContext = info.context
        branch = context.branch
        repository_id = str(data.id)
        repo: CoreReadOnlyRepository | CoreRepository = await NodeManager.get_one_by_id_or_default_filter(
            db=context.db,
            kind=InfrahubKind.GENERICREPOSITORY,
            id=repository_id,
            branch=branch,
        )

        message = messages.GitRepositoryConnectivity(
            repository_name=str(repo.name.value),
            repository_location=str(repo.location.value),
        )
        if context.service:
            response = await context.service.message_bus.rpc(
                message=message, response_class=GitRepositoryConnectivityResponse
            )

        return {"ok": response.data.success, "message": response.data.message}
