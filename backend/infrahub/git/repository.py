from __future__ import annotations

from typing import Any, Optional, Union

from git.exc import BadName, GitCommandError
from infrahub_sdk.exceptions import GraphQLError
from pydantic import Field

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.exceptions import RepositoryError
from infrahub.git.integrator import InfrahubRepositoryIntegrator
from infrahub.log import get_logger
from infrahub.services import InfrahubServices

log = get_logger()


class InfrahubRepository(InfrahubRepositoryIntegrator):
    """
    Primary type of Git repository, with deep integration within Infrahub.

    Eventually we should rename this class InfrahubIntegratedRepository
    """

    @classmethod
    async def init(cls, service: Optional[InfrahubServices] = None, **kwargs: Any) -> InfrahubRepository:
        service = service or InfrahubServices()
        self = cls(service=service, **kwargs)
        self.validate_local_directories()
        log.debug("Initiated the object on an existing directory.", repository=self.name)
        return self

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        branches = {}
        if remote:
            branches = self.get_branches_from_remote()
        else:
            branches = self.get_branches_from_local(include_worktree=False)

        if branch_name not in branches:
            raise ValueError(f"Branch {branch_name} not found.")

        return str(branches[branch_name].commit)

    async def create_branch_in_git(
        self, branch_name: str, branch_id: Optional[str] = None, push_origin: bool = True
    ) -> bool:
        """Create new branch in the repository, assuming the branch has been created in the graph already."""

        repo = self.get_git_repo_main()

        # Check if the branch already exists locally, if it does do nothing
        local_branches = self.get_branches_from_local(include_worktree=False)
        if branch_name in local_branches:
            return False

        # TODO Catch potential exceptions coming from repo.git.branch & repo.git.worktree
        repo.git.branch(branch_name)
        self.create_branch_worktree(branch_name=branch_name, branch_id=branch_id or branch_name)

        # If there is not remote configured, we are done
        #  Since the branch is a match for the main branch we don't need to create a commit worktree
        # If there is a remote, Check if there is an existing remote branch with the same name and if so track it.
        if not self.has_origin:
            log.debug(
                f"Branch {branch_name} created in Git without tracking a remote branch.",
                repository=self.name,
                branch=branch_name,
            )
            return True

        remote_branch = [br for br in repo.remotes.origin.refs if br.name == f"origin/{branch_name}"]

        if remote_branch:
            br_repo = self.get_git_repo_worktree(identifier=branch_name)
            br_repo.head.reference.set_tracking_branch(remote_branch[0])
            br_repo.remotes.origin.pull(branch_name)
            self.create_commit_worktree(str(br_repo.head.reference.commit))
            log.debug(
                f"Branch {branch_name} created in Git, tracking remote branch {remote_branch[0]}.",
                repository=self.name,
                branch=branch_name,
            )
        else:
            log.debug(f"Branch {branch_name} created in Git without tracking a remote branch.", repository=self.name)

        if push_origin:
            await self.push(branch_name)

        return True

    async def sync(self, staging_branch: str | None = None) -> None:
        """Synchronize the repository with its remote origin and with the database.

        By default the sync will focus only on the branches pulled from origin that have some differences with the local one.
        """

        log.info("Starting the synchronization.", repository=self.name)

        await self.fetch()

        new_branches, updated_branches = await self.compare_local_remote()

        if not new_branches and not updated_branches:
            return

        log.debug(f"New Branches {new_branches}, Updated Branches {updated_branches}", repository=self.name)

        # TODO need to handle properly the situation when a branch is not valid.
        if self.internal_status == RepositoryInternalStatus.ACTIVE.value:
            for branch_name in new_branches:
                is_valid = await self.validate_remote_branch(branch_name=branch_name)
                if not is_valid:
                    continue

                infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)
                try:
                    branch = await self.create_branch_in_graph(branch_name=infrahub_branch)
                except GraphQLError as exc:
                    if "already exist" not in exc.errors[0]["message"]:
                        raise
                    branch = await self.sdk.branch.get(branch_name=infrahub_branch)

                await self.create_branch_in_git(branch_name=branch.name, branch_id=branch.id)

                commit = self.get_commit_value(branch_name=branch_name, remote=False)
                self.create_commit_worktree(commit=commit)
                await self.update_commit_value(branch_name=infrahub_branch, commit=commit)

                await self.import_objects_from_files(infrahub_branch_name=infrahub_branch, commit=commit)

            for branch_name in updated_branches:
                is_valid = await self.validate_remote_branch(branch_name=branch_name)
                if not is_valid:
                    continue

                infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)

                commit_after = await self.pull(branch_name=branch_name)
                if isinstance(commit_after, str):
                    await self.import_objects_from_files(infrahub_branch_name=infrahub_branch, commit=commit_after)

                elif commit_after is True:
                    log.warning(
                        f"An update was detected but the commit remained the same after pull() ({commit_after}).",
                        repository=self.name,
                        branch=branch_name,
                    )

        await self._sync_staging(staging_branch=staging_branch, updated_branches=updated_branches)

    async def _sync_staging(self, staging_branch: str | None, updated_branches: list[str]) -> None:
        if (
            self.internal_status == RepositoryInternalStatus.STAGING.value
            and staging_branch
            and self.default_branch in updated_branches
        ):
            commit_after = await self.pull(branch_name=self.default_branch)
            if isinstance(commit_after, str):
                await self.import_objects_from_files(
                    git_branch_name=self.default_branch, infrahub_branch_name=staging_branch, commit=commit_after
                )

            elif commit_after is True:
                log.warning(
                    f"An update was detected but the commit remained the same after pull() ({commit_after}).",
                    repository=self.name,
                    branch=self.default_branch,
                )

    async def push(self, branch_name: str) -> bool:
        """Push a given branch to the remote Origin repository"""

        if not self.has_origin:
            return False

        log.debug(
            f"Pushing the latest update to the remote origin for the branch '{branch_name}'", repository=self.name
        )

        # TODO Catch potential exceptions coming from origin.push
        repo = self.get_git_repo_worktree(identifier=branch_name)
        remote_branch = self._get_mapped_remote_branch(branch_name=branch_name)
        repo.remotes.origin.push(remote_branch)

        return True

    async def merge(self, source_branch: str, dest_branch: str, push_remote: bool = True) -> bool:
        """Merge the source branch into the destination branch.

        After the rebase we need to resync the data
        """
        repo = self.get_git_repo_worktree(identifier=dest_branch)
        if not repo:
            raise ValueError(f"Unable to identify the worktree for the branch : {dest_branch}")

        commit_before = str(repo.head.commit)
        commit = self.get_commit_value(branch_name=source_branch, remote=False)

        try:
            repo.git.merge(commit)
        except GitCommandError as exc:
            repo.git.merge("--abort")
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

        commit_after = str(repo.head.commit)

        if commit_after == commit_before:
            return False

        self.create_commit_worktree(commit_after)
        await self.update_commit_value(branch_name=dest_branch, commit=commit_after)
        if self.has_origin and push_remote:
            await self.push(branch_name=dest_branch)

        return str(commit_after)

    async def rebase(self, branch_name: str, source_branch: str = "main", push_remote: bool = True) -> bool:
        """Rebase the current branch with main.

        Technically we are not doing a Git rebase because it will change the git history
        We'll merge the content of the source_branch into branch_name instead to keep the history clear.

        TODO need to see how we manage conflict

        After the rebase we need to resync the data
        """

        response = await self.merge(dest_branch=branch_name, source_branch=source_branch, push_remote=push_remote)

        return response

    @classmethod
    async def new(cls, service: Optional[InfrahubServices] = None, **kwargs: Any) -> InfrahubRepository:
        service = service or InfrahubServices()
        self = cls(service=service, **kwargs)
        await self.create_locally(infrahub_branch_name=self.infrahub_branch_name)
        log.info("Created the new project locally.", repository=self.name)
        return self


class InfrahubReadOnlyRepository(InfrahubRepositoryIntegrator):
    """
    Repository with only read-only access to the remote repo
    """

    is_read_only: bool = True
    ref: Optional[str] = Field(None, description="Ref to track on the external repository")

    @classmethod
    async def init(cls, service: Optional[InfrahubServices] = None, **kwargs: Any) -> InfrahubReadOnlyRepository:
        service = service or InfrahubServices()
        self = cls(service=service, **kwargs)
        self.validate_local_directories()
        log.debug("Initiated the object on an existing directory.", repository=self.name)
        return self

    @classmethod
    async def new(cls, service: Optional[InfrahubServices] = None, **kwargs: Any) -> InfrahubReadOnlyRepository:
        service = service or InfrahubServices()

        if "ref" not in kwargs or "infrahub_branch_name" not in kwargs:
            raise ValueError("ref and infrahub_branch_name are mandatory to initialize a new Read-Only repository")

        self = cls(service=service, **kwargs)
        await self.create_locally(checkout_ref=self.ref, infrahub_branch_name=self.infrahub_branch_name)
        log.info("Created the new project locally.", repository=self.name)
        return self

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        """Always get the latest commit for this repository's ref on the remote"""
        git_repo = self.get_git_repo_main()
        git_repo.remotes.origin.fetch()

        refs = (f"origin/{self.ref}", self.ref)
        commit = None
        for possible_ref in refs:
            try:
                commit = git_repo.commit(possible_ref)
                break
            except BadName:
                ...
        if not commit:
            log.error(f"No object found for refs {refs} on repository {self.name}")
            raise ValueError(f"Ref {self.ref} not found.")

        return str(commit)

    async def sync_from_remote(self, commit: Optional[str] = None) -> None:
        if not commit:
            commit = self.get_commit_value(branch_name=self.ref, remote=True)
        local_branches = self.get_branches_from_local()
        if self.ref in local_branches and commit == local_branches[self.ref].commit:
            return
        self.create_commit_worktree(commit=commit)
        await self.import_objects_from_files(infrahub_branch_name=self.infrahub_branch_name, commit=commit)
        await self.update_commit_value(branch_name=self.infrahub_branch_name, commit=commit)


async def get_initialized_repo(
    repository_id: str, name: str, service: InfrahubServices, repository_kind: str
) -> Union[InfrahubReadOnlyRepository, InfrahubRepository]:
    if repository_kind == InfrahubKind.REPOSITORY:
        return await InfrahubRepository.init(id=repository_id, name=name, client=service._client, service=service)

    if repository_kind == InfrahubKind.READONLYREPOSITORY:
        return await InfrahubReadOnlyRepository.init(
            id=repository_id, name=name, client=service._client, service=service
        )

    raise NotImplementedError(f"The repository kind {repository_kind} has not been implemented")
