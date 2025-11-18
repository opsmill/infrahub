from __future__ import annotations

from typing import TYPE_CHECKING, cast

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.constants.infrahubkind import READONLYREPOSITORY, REPOSITORY
from infrahub.core.protocols import CoreGenericRepository, CoreReadOnlyRepository, CoreRepository
from infrahub.exceptions import ValidationError
from infrahub.git.models import GitRepositoryAdd, GitRepositoryAddReadOnly
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse
from infrahub.workflows.catalogue import GIT_REPOSITORY_ADD, GIT_REPOSITORY_ADD_READ_ONLY

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

log = get_logger()


class RepositoryFinalizer:
    def __init__(
        self,
        account_session: AccountSession,
        services: InfrahubServices,
        context: InfrahubContext,
    ) -> None:
        self.account_session = account_session
        self.services = services
        self.context = context

    async def post_create(
        self,
        obj: CoreGenericRepository,
        branch: Branch,
        db: InfrahubDatabase,
        delete_on_connectivity_failure: bool = True,
    ) -> None:
        """
        Method meant to be called after a repository has been created in the database.
        It mainly checks the connectivity to the remote repository and submit the workflow to create the repository in the local filesystem.
        """

        # If the connectivity is not good, we remove the repository to allow the user to add a new one
        if delete_on_connectivity_failure:
            message = messages.GitRepositoryConnectivity(
                repository_name=obj.name.value,
                repository_location=obj.location.value,
            )
            response = await self.services.message_bus.rpc(
                message=message, response_class=GitRepositoryConnectivityResponse
            )

            if response.data.success is False:
                await obj.delete(db=db)
                raise ValidationError(response.data.message)

        # If we are in the default branch, we set the sync status to Active
        # If we are in another branch, we set the sync status to Staging
        if branch.is_default:
            obj.internal_status.value = RepositoryInternalStatus.ACTIVE.value
        else:
            obj.internal_status.value = RepositoryInternalStatus.STAGING.value
        await obj.save(db=db)

        # Create the new repository in the filesystem.
        log.info("create_repository", name=obj.name.value)
        authenticated_user = None
        if self.account_session and self.account_session.authenticated:
            authenticated_user = self.account_session.account_id

        if obj.get_kind() == READONLYREPOSITORY:
            obj = cast(CoreReadOnlyRepository, obj)
            model = GitRepositoryAddReadOnly(
                repository_id=obj.id,
                repository_name=obj.name.value,
                location=obj.location.value,
                ref=obj.ref.value,
                infrahub_branch_name=branch.name,
                infrahub_branch_id=str(branch.get_uuid()),
                internal_status=obj.internal_status.value,
                created_by=authenticated_user,
            )
            await self.services.workflow.submit_workflow(
                workflow=GIT_REPOSITORY_ADD_READ_ONLY,
                context=self.context,
                parameters={"model": model},
            )

        elif obj.get_kind() == REPOSITORY:
            obj = cast(CoreRepository, obj)
            git_repo_add_model = GitRepositoryAdd(
                repository_id=obj.id,
                repository_name=obj.name.value,
                location=obj.location.value,
                default_branch_name=obj.default_branch.value,
                infrahub_branch_name=branch.name,
                infrahub_branch_id=str(branch.get_uuid()),
                internal_status=obj.internal_status.value,
                created_by=authenticated_user,
            )

            await self.services.workflow.submit_workflow(
                workflow=GIT_REPOSITORY_ADD,
                context=self.context,
                parameters={"model": git_repo_add_model},
            )
        else:
            raise ValueError(f"Unknown repository kind: {obj.get_kind()}")
