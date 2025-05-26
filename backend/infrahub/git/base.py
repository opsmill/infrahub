from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from uuid import UUID  # noqa: TC003

import git
from git import Blob, Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from git.refs.remote import RemoteReference
from infrahub_sdk import InfrahubClient  # noqa: TC002
from prefect import Flow, Task
from prefect.logging import get_run_logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, RepositoryOperationalStatus, RepositorySyncStatus
from infrahub.core.registry import registry
from infrahub.exceptions import (
    CommitNotFoundError,
    FileOutOfRepositoryError,
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
    RepositoryFileNotFoundError,
    RepositoryInvalidBranchError,
    RepositoryInvalidFileSystemError,
)
from infrahub.git.constants import BRANCHES_DIRECTORY_NAME, COMMITS_DIRECTORY_NAME, TEMPORARY_DIRECTORY_NAME
from infrahub.git.directory import get_repositories_directory, initialize_repositories_directory
from infrahub.git.worktree import Worktree
from infrahub.log import get_logger
from infrahub.services import InfrahubServices  # noqa: TC001

if TYPE_CHECKING:
    from infrahub_sdk.branch import BranchData

log = get_logger("infrahub.git")


class RepoFileInformation(BaseModel):
    filename: str
    """Name of the file. Example: myfile.py"""

    filename_wo_ext: str
    """Name of the file, without the extension, Example: myfile """

    module_name: str
    """Name of the module for Python, in dot notation from the root of the repository, Example: commits.71da[..]4b7.checks.myfile """

    relative_path_dir: str
    """Relative path to the directory containing the file from the root of the worktree, Example: checks/"""

    relative_repo_path_dir: str
    """Relative path to the directory containing the file from the root of repository, Example: commits/71da[..]4b7/checks/"""

    absolute_path_dir: str
    """Absolute path to the directory containing the file, Example: /opt/infrahub/git/repo01/commits/71da[..]4b7/checks/"""

    relative_path_file: str
    """Relative path to the file from the root of the worktree Example: checks/myfile.py"""

    extension: str
    """Extension of the file Example: py """


def extract_repo_file_information(
    full_filename: Path, repo_directory: Path, worktree_directory: Path | None = None
) -> RepoFileInformation:
    """Extract all the relevant and required information from a filename.

    Args:
        full_filename (Path): Absolute path to the file to load Example:/opt/infrahub/git/repo01/commits/71da[..]4b7/myfile.py
        root_directory (Path): Absolute path to the root of the repository directory. Example:/opt/infrahub/git/repo01
        worktree_directory (Path, optional): Absolute path to the root of the worktree directory. Defaults to None.
        Example: /opt/infrahub/git/repo01/commits/71da[..]4b7/

    Returns:
        RepoFileInformation: Pydantic object to store all information about this file
    """
    abs_directory = full_filename.parent.resolve()
    filename = full_filename.name
    filename_wo_ext = full_filename.stem

    relative_repo_path_dir = abs_directory.relative_to(repo_directory)

    if worktree_directory and abs_directory.is_relative_to(worktree_directory):
        path_in_repo = abs_directory.relative_to(worktree_directory)
    else:
        path_in_repo = abs_directory

    file_path = path_in_repo / filename
    module_name = str(relative_repo_path_dir).replace("/", ".") + f".{filename_wo_ext}"

    return RepoFileInformation(
        filename=filename,
        filename_wo_ext=filename_wo_ext,
        module_name=module_name,
        absolute_path_dir=str(abs_directory),
        relative_path_dir=str(path_in_repo),
        relative_repo_path_dir=str(relative_repo_path_dir),
        extension=full_filename.suffix,
        relative_path_file=str(file_path),
    )


class BranchInGraph(BaseModel):
    id: str
    name: str
    sync_with_git: bool
    commit: str | None = None


class BranchInRemote(BaseModel):
    name: str
    commit: str


class BranchInLocal(BaseModel):
    name: str
    commit: str
    has_worktree: bool = False


class InfrahubRepositoryBase(BaseModel, ABC):
    """
    Local version of a Git repository organized to work with Infrahub.
    The idea is that all commits that are being tracked in the graph will be checkout out
    individually as worktree under the <repo_name>/commits subdirectory

    Directory organization
    <repo_directory>/
        <repo_name>/main       Primary directory with the complete clone
        <repo_name>/branch     Directory for worktrees of all branches
        <repo_name>/commit     Directory for worktrees of individual commits
    """

    id: UUID = Field(..., description="Internal UUID of the repository")
    name: str = Field(..., description="Primary name of the repository")
    default_branch_name: str | None = Field(None, description="Default branch to use when pulling the repository")
    type: str | None = None
    location: str | None = Field(None, description="Location of the remote repository")
    has_origin: bool = Field(
        False, description="Flag to indicate if a remote repository (named origin) is present in the config."
    )

    client: InfrahubClient | None = Field(
        default=None,
        description="Infrahub Client, used to query the Repository and Branch information in the graph and to update the commit.",
    )

    cache_repo: Repo | None = Field(None, description="Internal cache of the GitPython Repo object")
    service: InfrahubServices = Field(
        ..., description="Service object with access to the message queue, the database etc.."
    )
    is_read_only: bool = Field(False, description="If true, changes will not be synced to remote")

    internal_status: str = Field("active", description="Internal status: Active, Inactive, Staging")
    infrahub_branch_name: str | None = Field(None, description="Infrahub branch on which to sync the remote repository")
    model_config = ConfigDict(arbitrary_types_allowed=True, ignored_types=(Flow, Task))

    def get_client(self) -> InfrahubClient:
        if self.client is None:
            raise ValueError("Client is not set")
        return self.client

    @property
    def sdk(self) -> InfrahubClient:
        if self.client:
            return self.client

        return self.service.client

    @property
    def default_branch(self) -> str:
        return self.default_branch_name or registry.default_branch

    @property
    def legacy_directory_root(self) -> Path:
        """Return the legacy path to the root directory for this repository."""
        return get_repositories_directory() / self.name

    @property
    def directory_root(self) -> Path:
        """Return the path to the root directory for this repository."""
        return get_repositories_directory() / str(self.id)

    @property
    def directory_default(self) -> Path:
        """Return the path to the directory of the main branch."""
        return self.directory_root / "main"

    @property
    def directory_branches(self) -> Path:
        """Return the path to the directory where the worktrees of all the branches are stored."""
        return self.directory_root / BRANCHES_DIRECTORY_NAME

    @property
    def directory_commits(self) -> Path:
        """Return the path to the directory where the worktrees of all the commits are stored."""
        return self.directory_root / COMMITS_DIRECTORY_NAME

    @property
    def directory_temp(self) -> Path:
        """Return the path to the directory where the temp worktrees of all the commits pending validation are stored."""
        return self.directory_root / TEMPORARY_DIRECTORY_NAME

    async def _update_operational_status(self, status: RepositoryOperationalStatus) -> None:
        update_status = """
        mutation UpdateRepositoryStatus(
            $repo_id: String!,
            $status: String!,
        ) {
            CoreGenericRepositoryUpdate(
                data: {
                    id: $repo_id,
                    operational_status: { value: $status },
                }
            ) {
                ok
            }
        }
        """

        await self.sdk.execute_graphql(
            branch_name=self.infrahub_branch_name or registry.default_branch,
            query=update_status,
            variables={"repo_id": str(self.id), "status": status.value},
            tracker="mutation-repository-update-operational-status",
        )

    async def _update_sync_status(self, branch_name: str, status: RepositorySyncStatus) -> None:
        update_status = """
        mutation UpdateRepositoryStatus(
            $repo_id: String!,
            $status: String!,
        ) {
            CoreGenericRepositoryUpdate(
                data: {
                    id: $repo_id,
                    sync_status: { value: $status },
                }
            ) {
                ok
            }
        }
        """

        await self.sdk.execute_graphql(
            branch_name=branch_name,
            query=update_status,
            variables={"repo_id": str(self.id), "status": status.value},
            tracker="mutation-repository-update-admin-status",
        )

    def get_git_repo_main(self) -> Repo:
        """Return Git Repo object of the main repository.

        Returns:
            Repo: git object of the main repository

        Raises:
            git.exc.InvalidGitRepositoryError if the default directory is not a valid Git repository.
        """

        if not self.cache_repo:
            self.cache_repo = Repo(self.directory_default)

        return self.cache_repo

    def get_git_repo_worktree(self, identifier: str) -> Repo:
        """Return Git Repo object of the given worktree.

        Returns:
            Repo: git object of the main repository

        """
        if worktree := self.get_worktree(identifier=identifier):
            return Repo(worktree.directory)

        raise RepositoryError(identifier=self.name, message=f"Unable to find the worktree {identifier}.")

    def relocate_directory_root(self) -> None:
        """Move an old repository directory based on its name to a directory based on its ID.

        This method will also take care of removing the legacy directory if:
        1. The regular directory exists
        2. The regular directory does not exist but will be created after renaming the legacy one
        """
        legacy = self.legacy_directory_root
        current = self.directory_root

        if not legacy.exists():
            return

        if not legacy.is_dir():
            log.error("A file named after the repository should not exist", repository=self.name)
            return

        if current.is_dir():
            log.warning(
                f"Found legacy directory at {self.legacy_directory_root} but {self.directory_root} exists, deleting legacy directory",
                repository=self.name,
            )
            shutil.rmtree(self.legacy_directory_root)
        else:
            log.warning(
                f"Found legacy directory at {self.legacy_directory_root}, moving it to {self.directory_root}",
                repository=self.name,
            )
            legacy.rename(self.directory_root)

    def validate_local_directories(self) -> bool:
        """Check if the local directories structure to ensure that the repository has been properly initialized.

        Returns True if everything is correct
        Raises a RepositoryError exception if something is not correct
        """

        directories_to_validate = [
            self.directory_root,
            self.directory_branches,
            self.directory_commits,
            self.directory_temp,
            self.directory_default,
        ]

        for directory in directories_to_validate:
            if not directory.is_dir():
                raise RepositoryInvalidFileSystemError(
                    identifier=self.name,
                    directory=directory,
                )

        # Validate that a worktree for the commit in main is present
        try:
            repo = self.get_git_repo_main()
            if "origin" in repo.remotes:
                self.has_origin = True

        except InvalidGitRepositoryError as exc:
            raise RepositoryError(
                identifier=self.name, message=f"The data on disk is not a valid Git repository for {self.name}."
            ) from exc

        # Validate that at least one worktree for the active commit in main has been created
        try:
            commit = str(repo.head.commit)
        except ValueError as exc:
            raise RepositoryError(
                identifier=self.name, message="The initial commit is missing for {self.name}"
            ) from exc

        if not (self.directory_commits / commit).is_dir():
            raise RepositoryError(
                identifier=self.name, message=f"The directory for the main commit is missing for {self.name}"
            )

        return True

    async def create_locally(
        self, checkout_ref: str | None = None, infrahub_branch_name: str | None = None, update_commit_value: bool = True
    ) -> bool:
        """Ensure the required directory already exist in the filesystem or create them if needed.

        Returns
            True if the directory has been created,
            False if the directory was already present.
        """
        initialize_repositories_directory()

        if not self.location:
            raise RepositoryError(
                identifier=self.name,
                message=f"Unable to initialize the repository {self.name} without a remote location.",
            )

        # Check if the root, commits and branches directories are already present, create them if needed
        if self.directory_root.is_dir():
            shutil.rmtree(self.directory_root)
            log.warning(f"Found an existing directory at {self.directory_root}, deleted it", repository=self.name)
        elif self.directory_root.is_file():
            self.directory_root.unlink()
            log.warning(f"Found an existing file at {self.directory_root}, deleted it", repository=self.name)

        # Initialize directory structure
        self.directory_root.mkdir(parents=True)
        self.directory_branches.mkdir(parents=True)
        self.directory_commits.mkdir(parents=True)
        self.directory_temp.mkdir(parents=True)

        try:
            repo = Repo.clone_from(self.location, self.directory_default)
            repo.git.checkout(checkout_ref or self.default_branch)
        except GitCommandError as exc:
            await self._raise_enriched_error(error=exc)

        self.has_origin = True

        # Create a worktree for the commit in the default branch
        # TODO Need to handle the potential exceptions coming from repo.git.worktree
        commit = str(repo.head.commit)
        self.create_commit_worktree(commit=commit)
        if update_commit_value:
            await self.update_commit_value(branch_name=infrahub_branch_name or self.default_branch, commit=commit)

        return True

    def has_worktree(self, identifier: str) -> bool:
        """Return True if a worktree with a given identifier already exist."""

        worktrees = self.get_worktrees()

        for worktree in worktrees:
            if worktree.identifier == identifier:
                return True

        return False

    def get_worktree(self, identifier: str) -> Worktree:
        """Access a specific worktree by its identifier."""

        worktrees = self.get_worktrees()
        for worktree in worktrees:
            if worktree.identifier == identifier:
                return worktree

        raise RepositoryError(identifier=identifier, message=f"Unable to get worktree : {identifier}")

    def get_commit_worktree(self, commit: str) -> Worktree:
        """Access a specific commit worktree."""

        worktrees = self.get_worktrees()

        for worktree in worktrees:
            if worktree.identifier == commit:
                return worktree

        # if not worktree exist for this commit already
        # We'll try to create one
        return self.create_commit_worktree(commit=commit)

    def get_worktrees(self) -> list[Worktree]:
        """Return the list of worktrees configured for this repository."""
        repo = self.get_git_repo_main()
        responses = repo.git.worktree("list", "--porcelain").split("\n\n")

        return [Worktree.init(response) for response in responses]

    def get_location(self) -> str:
        if self.location:
            return self.location
        raise ValueError(f"location hasn't been provided for this repository ({self.name})")

    async def get_branches_from_graph(self) -> dict[str, BranchInGraph]:
        """Return a dict with all the branches present in the graph.
        Query the list of branches first then query the repository for each branch.
        """

        response = {}

        branches = await self.sdk.branch.all()

        # TODO Need to optimize this query, right now we are querying everything unnecessarily
        repositories = await self.sdk.get_list_repositories(branches=branches, kind=InfrahubKind.REPOSITORY)
        repository = repositories[self.name]

        for branch_name, branch in branches.items():
            response[branch_name] = BranchInGraph(
                id=branch.id,
                name=branch.name,
                sync_with_git=branch.sync_with_git,
                commit=repository.branches[branch_name] or None,
            )

        return response

    def get_branches_from_remote(self) -> dict[str, BranchInRemote]:
        """Return a dict with all the branches present on the remote."""

        git_repo = self.get_git_repo_main()

        branches = {}

        for remote_branch in git_repo.remotes.origin.refs:
            if not isinstance(remote_branch, RemoteReference):
                continue

            short_name = remote_branch.name.replace("origin/", "")

            if short_name == "HEAD":
                continue

            branches[short_name] = BranchInRemote(name=short_name, commit=str(remote_branch.commit))

        return branches

    def get_branches_from_local(self, include_worktree: bool = True) -> dict[str, BranchInLocal]:
        """Return a dict with all the branches present locally."""

        git_repo = self.get_git_repo_main()

        if include_worktree:
            worktrees = self.get_worktrees()

        branches = {}

        for local_branch in git_repo.refs:
            if local_branch.is_remote():
                continue

            has_worktree = False

            if include_worktree:
                for worktree in worktrees:
                    if worktree.branch and worktree.branch == local_branch.name:
                        has_worktree = True
                        break

            branches[local_branch.name] = BranchInLocal(
                name=local_branch.name, commit=str(local_branch.commit), has_worktree=has_worktree
            )

        return branches

    @abstractmethod
    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        raise NotImplementedError()

    def has_conflicting_changes(self, target_branch: str, source_branch: str) -> bool:
        """Use merge tree to spot conflicts and tell if there is any."""
        repo = self.get_git_repo_main()

        if repo.remotes:
            # Ensure we have the latest changes from the remote
            info = repo.remotes.origin.fetch(source_branch)

            target = repo.branches[target_branch]
            source = repo.commit(info[0].ref)

            merge_base = repo.merge_base(target.commit, source)[0]
            merge_tree_output = repo.git.merge_tree(merge_base.hexsha, target.commit.hexsha, source.hexsha)
        else:
            target = repo.branches[target_branch]
            source = repo.branches[source_branch]

            merge_base = repo.merge_base(target.commit, source)[0]
            merge_tree_output = repo.git.merge_tree(merge_base.hexsha, target.commit.hexsha, source.commit.hexsha)

        log.debug(
            f"Merging {source_branch} into {target_branch} will bring changes",
            repository=self.name,
            source=source_branch,
            target=target_branch,
            merge_structure=merge_tree_output,
        )

        return any(marker in merge_tree_output for marker in ("<<<<<<<", "=======", ">>>>>>>"))

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        """Compare the value of the commit in the graph with the current commit on the filesystem.
        update it if they don't match.

        Returns:
            True if the commit has been updated
            False if they already had the same value
        """

        infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)
        log.debug(
            f"Updating commit value to {commit} for branch {branch_name}", repository=self.name, branch=infrahub_branch
        )
        await self.sdk.repository_update_commit(
            branch_name=infrahub_branch, repository_id=self.id, commit=commit, is_read_only=self.is_read_only
        )

        return True

    async def create_branch_in_graph(self, branch_name: str) -> BranchData:
        """Create a new branch in the graph.

        NOTE We need to validate that we are not gonna end up with a race condition
        since a call to the GraphQL API will trigger a new RPC call to add a branch in this repo.
        """

        # TODO need to handle the exception properly
        branch = await self.sdk.branch.create(branch_name=branch_name)

        log.debug(f"Branch {branch_name} created in the Graph", repository=self.name, branch=branch_name)
        return branch

    async def create_branch_in_git(self, branch_name: str, branch_id: str | None = None) -> bool:
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
            try:
                br_repo.remotes.origin.pull(branch_name)
            except GitCommandError as exc:
                await self._raise_enriched_error(error=exc, branch_name=branch_name)
            self.create_commit_worktree(str(br_repo.head.reference.commit))
            log.debug(
                f"Branch {branch_name} created in Git, tracking remote branch {remote_branch[0]}.",
                repository=self.name,
                branch=branch_name,
            )
        else:
            log.debug(f"Branch {branch_name} created in Git without tracking a remote branch.", repository=self.name)

        return True

    def create_commit_worktree(self, commit: str) -> bool | Worktree:
        """Create a new worktree for a given commit."""

        # Check of the worktree already exist
        if self.has_worktree(identifier=commit):
            return False

        directory = self.directory_commits / commit
        worktree = Worktree(identifier=commit, directory=str(directory), commit=commit)

        repo = self.get_git_repo_main()
        try:
            repo.git.worktree("add", directory, commit)
            log.debug(f"Commit worktree created {commit}", repository=self.name)
            return worktree
        except GitCommandError as exc:
            if "invalid reference" in exc.stderr:
                raise CommitNotFoundError(
                    identifier=self.name,
                    commit=commit,
                ) from exc
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

    def create_branch_worktree(self, branch_name: str, branch_id: str) -> bool:
        """Create a new worktree for a given branch."""

        # Check if the worktree already exist
        if self.has_worktree(identifier=branch_name):
            return False

        try:
            repo = self.get_git_repo_main()
            repo.git.worktree("add", self.directory_branches / branch_id, branch_name)
        except GitCommandError as exc:
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

        log.debug(f"Branch worktree created {branch_name}", repository=self.name)
        return True

    async def calculate_diff_between_commits(
        self, first_commit: str, second_commit: str
    ) -> tuple[list[str], list[str], list[str]]:
        """TODO need to refactor this function to return more information.
        Like :
          - What has changed inside the files
          - Are there some conflicts between the files.
        """

        git_repo = self.get_git_repo_main()

        commit_to_compare = git_repo.commit(second_commit)
        commit_in_branch = git_repo.commit(first_commit)

        changed_files = []
        removed_files = []
        added_files = []

        for x in commit_in_branch.diff(commit_to_compare, create_patch=True):
            if x.a_blob and not x.b_blob and x.a_blob.path not in added_files:
                added_files.append(x.a_blob.path)
            elif x.a_blob and x.b_blob and x.a_blob.path not in changed_files:
                changed_files.append(x.a_blob.path)
            elif not x.a_blob and x.b_blob and x.b_blob.path not in removed_files:
                removed_files.append(x.b_blob.path)

        return changed_files, added_files, removed_files

    async def list_all_files(self, commit: str) -> list[str]:
        git_repo = self.get_git_repo_main()
        return [str(entry.path) for entry in git_repo.commit(commit).tree.traverse() if isinstance(entry, Blob)]

    async def fetch(self) -> bool:
        """Fetch the latest update from the remote repository and bring a copy locally."""
        if not self.has_origin:
            return False

        log.debug("Fetching the latest updates from remote origin.", repository=self.name)

        self.relocate_directory_root()

        repo = self.get_git_repo_main()
        try:
            repo.remotes.origin.fetch()
        except GitCommandError as exc:
            await self._raise_enriched_error(error=exc)

        await self._update_operational_status(status=RepositoryOperationalStatus.ONLINE)

        return True

    async def compare_local_remote(self) -> tuple[list[str], list[str]]:
        """
        Returns:
            List[str] New Branches in Remote
            List[str] Branches with different commit in Remote
        """
        if not self.has_origin:
            return [], []

        # TODO move this section into a dedicated function to compare and bring in sync the remote repo with the local one.
        # It can be useful just after a clone etc ...
        local_branches = self.get_branches_from_local()
        remote_branches = self.get_branches_from_remote()

        new_branches = set(remote_branches.keys()) - set(local_branches.keys())
        existing_branches = set(local_branches.keys()) - new_branches

        updated_branches = []

        for branch_name in existing_branches:
            if (
                branch_name in remote_branches
                and branch_name in local_branches
                and remote_branches[branch_name].commit != local_branches[branch_name].commit
            ):
                log.info("New commit detected", repository=self.name, branch=branch_name)
                updated_branches.append(branch_name)

        return sorted(new_branches), sorted(updated_branches)

    def validate_remote_branch(self, branch_name: str) -> bool:
        """Process a remote branch to validate that we can use it safely.

        - Make sure that the branch name won't conflict with infrahub's default branch
        - Make sure that a representation if the branch can be created in the database
        - Make sure that there are no conflicts that would prevent it from being merged
        """
        if branch_name == registry.default_branch and branch_name != self.default_branch:
            # If the default branch of Infrahub and the git repository differs we map the repository
            # default branch to that of Infrahub. In that scenario we can't import a branch from the
            # repository if it matches the default branch of Infrahub
            log.warning("Ignoring import of mismatched default branch", branch=branch_name, repository=self.name)
            return False

        try:
            # Check if the branch can be created in the database
            Branch(name=branch_name)
        except PydanticValidationError as e:
            log.warning(
                "Git branch failed validation.", branch_name=branch_name, errors=[error["msg"] for error in e.errors()]
            )
            return False

        # Make sure the branch won't conflict on merge
        if self.has_conflicting_changes(target_branch=self.default_branch, source_branch=branch_name):
            get_run_logger().warning(
                f"Remote branch {branch_name} will cause conflicts, they need to be resolved before importing the branch into Infrahub"
            )
            return False

        # Find the commit on the remote branch
        # Check out the commit in a worktree
        # Validate

        return True

    async def pull(
        self,
        branch_name: str,
        branch_id: str | None = None,
        create_if_missing: bool = False,
        update_commit_value: bool = True,
    ) -> bool | str:
        """Pull the latest update from the remote repository on a given branch."""

        if not self.has_origin:
            return False
        identifier = branch_name
        if branch_name == self.default_branch and branch_name != registry.default_branch:
            identifier = "main"

        repo: Repo | None = None
        try:
            repo = self.get_git_repo_worktree(identifier=identifier)
        except RepositoryError as exc:
            if not create_if_missing:
                raise ValueError(f"Unable to identify the worktree for the branch : {branch_name}") from exc

        if repo:
            try:
                commit_before = str(repo.head.commit)
                repo.remotes.origin.pull(branch_name)
            except GitCommandError as exc:
                await self._raise_enriched_error(error=exc, branch_name=branch_name)

            commit_after = str(repo.head.commit)

            if commit_after == commit_before:
                return True

            self.create_commit_worktree(commit=commit_after)
            infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)

        elif branch_id:
            await self.create_branch_in_git(branch_name=branch_name, branch_id=branch_id)
            repo = self.get_git_repo_worktree(identifier=branch_name)
            commit_after = str(repo.head.commit)
        else:
            raise ValueError(
                f"Unable to identify the worktree for the branch : {branch_name} "
                "and unable to pull the branch because the branch)id is missing"
            )

        if update_commit_value:
            await self.update_commit_value(branch_name=infrahub_branch, commit=commit_after)

        return commit_after

    async def get_conflicts(self, source_branch: str, dest_branch: str) -> list[str]:
        repo = self.get_git_repo_worktree(identifier=dest_branch)
        if not repo:
            raise ValueError(f"Unable to identify the worktree for the branch : {dest_branch}")

        commit = self.get_commit_value(branch_name=source_branch, remote=False)
        git_status = ""
        try:
            repo.git.merge(["--no-commit", "--no-ff", commit])
            repo.git.merge("--abort")
        except GitCommandError:
            git_status = repo.git.status("-s")
            if git_status:
                repo.git.merge("--abort")

        changed_files = git_status.splitlines()
        conflict_files = [filename[3:] for filename in changed_files if filename.startswith("UU ")]

        return conflict_files

    async def find_files(
        self,
        extension: str | list[str],
        branch_name: str | None = None,
        commit: str | None = None,
        directory: Path | None = None,
    ) -> list[Path]:
        """Return the path of all files matching a specific extension in a given Branch or Commit."""
        if not branch_name and not commit:
            raise ValueError("Either branch_name or commit must be provided.")
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        search_dir = Path(branch_wt.directory)
        if directory:
            search_dir /= directory

        files: list[Path] = []
        if isinstance(extension, str):
            files.extend(list(search_dir.glob(f"**/*.{extension}")))
            files.extend(list(search_dir.glob(f"**/.*.{extension}")))
        elif isinstance(extension, list):
            for ext in extension:
                files.extend(list(search_dir.glob(f"**/*.{ext}")))
                files.extend(list(search_dir.glob(f"**/.*.{ext}")))
        return files

    async def get_file(self, commit: str, location: str) -> str:
        commit_worktree = self.get_commit_worktree(commit=commit)
        path = self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=location)

        return path.read_text(encoding="UTF-8")

    def validate_location(self, commit: str, worktree_directory: Path, file_path: str) -> Path:
        """Validate that a file is found inside a repository and return a corresponding `pathlib.Path` object for it."""
        path = (worktree_directory / file_path).resolve()

        if not path.is_relative_to(worktree_directory):
            raise FileOutOfRepositoryError(repository_name=self.name, commit=commit, location=file_path)

        if not path.exists():
            raise RepositoryFileNotFoundError(repository_name=self.name, commit=commit, location=file_path)

        return path

    @classmethod
    def check_connectivity(cls, name: str, url: str) -> None:
        cmd = git.cmd.Git()
        try:
            cmd.ls_remote("--tags", url)
        except GitCommandError as exc:
            cls._raise_enriched_error_static(name=name, location=url, error=exc)

    async def _raise_enriched_error(self, error: GitCommandError, branch_name: str | None = None) -> NoReturn:
        try:
            self._raise_enriched_error_static(
                error=error, name=self.name, location=self.location, branch_name=branch_name or self.default_branch
            )
        except RepositoryError as exc:
            await self._update_operational_status(
                status={
                    RepositoryConnectionError: RepositoryOperationalStatus.ERROR_CONNECTION,
                    RepositoryCredentialsError: RepositoryOperationalStatus.ERROR_CRED,
                }.get(type(exc), RepositoryOperationalStatus.ERROR)
            )
            raise

    @staticmethod
    def _raise_enriched_error_static(
        error: GitCommandError, name: str, location: str, branch_name: str | None = None
    ) -> NoReturn:
        if "Repository not found" in error.stderr or "does not appear to be a git" in error.stderr:
            raise RepositoryConnectionError(identifier=name) from error

        if "error: pathspec" in error.stderr:
            raise RepositoryInvalidBranchError(identifier=name, branch_name=branch_name, location=location) from error

        if "SSL certificate problem" in error.stderr or "server certificate verification failed" in error.stderr:
            raise RepositoryConnectionError(
                identifier=name, message=f"SSL verification failed for {name}, please validate the certificate chain."
            ) from error

        if "authentication failed for" in error.stderr.lower():
            raise RepositoryCredentialsError(identifier=name) from error

        if "fatal: could not read Username for" in error.stderr and "terminal prompts disable" in error.stderr:
            raise RepositoryCredentialsError(
                identifier=name, message=f"Unable to correctly lookup credentials for repository {name} ({location})."
            ) from error

        if any(err in error.stderr for err in ("Need to specify how to reconcile", "because you have unmerged files")):
            raise RepositoryError(
                identifier=name,
                message=f"Unable to pull the branch {branch_name} for repository {name}, there are conflicts that must be resolved.",
            ) from error

        raise RepositoryError(identifier=name, message=error.stderr) from error

    def _get_mapped_remote_branch(self, branch_name: str) -> str:
        """Returns the remote branch for Git Repositories."""
        if branch_name != self.default_branch and branch_name == registry.default_branch:
            return self.default_branch
        return branch_name

    def _get_mapped_target_branch(self, branch_name: str) -> str:
        """Returns the target branch within Infrahub."""
        if branch_name == self.default_branch and branch_name != registry.default_branch:
            return registry.default_branch
        return branch_name
