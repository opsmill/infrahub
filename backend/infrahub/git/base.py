from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID  # noqa: TCH003

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from git.refs.remote import RemoteReference
from infrahub_sdk import InfrahubClient  # noqa: TCH002
from infrahub_sdk.task_report import InfrahubTaskReportLogger  # noqa: TCH002
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.exceptions import (
    CommitNotFoundError,
    FileOutOfRepositoryError,
    InitializationError,
    RepositoryError,
    RepositoryFileNotFoundError,
)
from infrahub.git.constants import BRANCHES_DIRECTORY_NAME, COMMITS_DIRECTORY_NAME, TEMPORARY_DIRECTORY_NAME
from infrahub.git.directory import initialize_repositories_directory
from infrahub.git.worktree import Worktree
from infrahub.log import get_logger
from infrahub.services import InfrahubServices  # noqa: TCH001

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
    full_filename: str, repo_directory: str, worktree_directory: Optional[str] = None
) -> RepoFileInformation:
    """Extract all the relevant and required information from a filename.

    Args:
        full_filename (str): Absolute path to the file to load Example:/opt/infrahub/git/repo01/commits/71da[..]4b7/myfile.py
        root_directory: Absolute path to the root of the repository directory. Example:/opt/infrahub/git/repo01
        worktree_directory (str, optional): Absolute path to the root of the worktree directory. Defaults to None.
        Example: /opt/infrahub/git/repo01/commits/71da[..]4b7/

    Returns:
        RepoFileInformation: Pydantic object to store all information about this file
    """
    full_path = Path(full_filename)
    abs_directory = full_path.parent.resolve()

    filename = full_path.name
    filename_wo_ext = full_path.stem

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
        extension=full_path.suffix,
        relative_path_file=str(file_path),
    )


class BranchInGraph(BaseModel):
    id: str
    name: str
    sync_with_git: bool
    commit: Optional[str] = None


class BranchInRemote(BaseModel):
    name: str
    commit: str


class BranchInLocal(BaseModel):
    name: str
    commit: str
    has_worktree: bool = False


class InfrahubRepositoryBase(BaseModel, ABC):  # pylint: disable=too-many-public-methods
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
    default_branch_name: Optional[str] = Field(None, description="Default branch to use when pulling the repository")
    type: Optional[str] = None
    location: Optional[str] = Field(None, description="Location of the remote repository")
    has_origin: bool = Field(
        False, description="Flag to indicate if a remote repository (named origin) is present in the config."
    )

    client: Optional[InfrahubClient] = Field(
        default=None,
        description="Infrahub Client, used to query the Repository and Branch information in the graph and to update the commit.",
    )

    cache_repo: Optional[Repo] = Field(None, description="Internal cache of the GitPython Repo object")
    service: InfrahubServices = Field(
        ..., description="Service object with access to the message queue, the database etc.."
    )
    is_read_only: bool = Field(False, description="If true, changes will not be synced to remote")
    task_report: Optional[InfrahubTaskReportLogger] = Field(default=None)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def sdk(self) -> InfrahubClient:
        if self.client:
            return self.client

        return self.service.client

    @property
    def default_branch(self) -> str:
        return self.default_branch_name or registry.default_branch

    @property
    def log(self) -> InfrahubTaskReportLogger:
        if self.task_report:
            return self.task_report
        raise InitializationError("The repository has not been initialized with a TaskReport")

    @property
    def directory_root(self) -> str:
        """Return the path to the root directory for this repository."""
        current_dir = os.getcwd()
        repositories_directory = config.SETTINGS.git.repositories_directory
        if not os.path.isabs(repositories_directory):
            repositories_directory = os.path.join(current_dir, config.SETTINGS.git.repositories_directory)

        return os.path.join(repositories_directory, self.name)

    @property
    def directory_default(self) -> str:
        """Return the path to the directory of the main branch."""
        return os.path.join(self.directory_root, registry.default_branch)

    @property
    def directory_branches(self) -> str:
        """Return the path to the directory where the worktrees of all the branches are stored."""
        return os.path.join(self.directory_root, BRANCHES_DIRECTORY_NAME)

    @property
    def directory_commits(self) -> str:
        """Return the path to the directory where the worktrees of all the commits are stored."""
        return os.path.join(self.directory_root, COMMITS_DIRECTORY_NAME)

    @property
    def directory_temp(self) -> str:
        """Return the path to the directory where the temp worktrees of all the commits pending validation are stored."""
        return os.path.join(self.directory_root, TEMPORARY_DIRECTORY_NAME)

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

        return None

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
            if not os.path.isdir(directory):
                raise RepositoryError(
                    identifier=self.name,
                    message=f"Invalid file system for {self.name}, Local directory {directory} missing.",
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

        if not os.path.isdir(os.path.join(self.directory_commits, commit)):
            raise RepositoryError(
                identifier=self.name, message=f"The directory for the main commit is missing for {self.name}"
            )

        return True

    async def create_locally(
        self, checkout_ref: Optional[str] = None, infrahub_branch_name: Optional[str] = None
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
        if os.path.isdir(self.directory_root):
            shutil.rmtree(self.directory_root)
            log.warning(f"Found an existing directory at {self.directory_root}, deleted it", repository=self.name)
        elif os.path.isfile(self.directory_root):
            os.remove(self.directory_root)
            log.warning(f"Found an existing file at {self.directory_root}, deleted it", repository=self.name)

        # Initialize directory structure
        os.makedirs(self.directory_root)
        os.makedirs(self.directory_branches)
        os.makedirs(self.directory_commits)
        os.makedirs(self.directory_temp)

        try:
            repo = Repo.clone_from(self.location, self.directory_default)
            repo.git.checkout(checkout_ref or self.default_branch)
        except GitCommandError as exc:
            if "Repository not found" in exc.stderr or "does not appear to be a git" in exc.stderr:
                raise RepositoryError(
                    identifier=self.name,
                    message=f"Unable to clone the repository {self.name}, please check the address and the credential",
                ) from exc

            if "error: pathspec" in exc.stderr:
                raise RepositoryError(
                    identifier=self.name,
                    message=f"The branch {self.default_branch} isn't a valid branch for the repository {self.name} at {self.location}.",
                ) from exc

            if "authentication failed for" in exc.stderr.lower():
                raise RepositoryError(
                    identifier=self.name,
                    message=f"Authentication failed for {self.name}, please validate the credentials.",
                ) from exc
            raise RepositoryError(identifier=self.name) from exc

        self.has_origin = True

        # Create a worktree for the commit in main
        # TODO Need to handle the potential exceptions coming from repo.git.worktree
        commit = str(repo.head.commit)
        self.create_commit_worktree(commit=commit)
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

        raise RepositoryError(identifier=identifier, message="Unble to get worktree")

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

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        """Compare the value of the commit in the graph with the current commit on the filesystem.
        update it if they don't match.

        Returns:
            True if the commit has been updated
            False if they already had the same value
        """

        log.debug(
            f"Updating commit value to {commit} for branch {branch_name}", repository=self.name, branch=branch_name
        )
        await self.sdk.repository_update_commit(
            branch_name=branch_name, repository_id=self.id, commit=commit, is_read_only=self.is_read_only
        )

        return True

    async def create_branch_in_graph(self, branch_name: str) -> BranchData:
        """Create a new branch in the graph.

        NOTE We need to validate that we are not gonna end up with a race condition
        since a call to the GraphQL API will trigger a new RPC call to add a branch in this repo.
        """

        # TODO need to handle the exception properly
        branch = await self.sdk.branch.create(branch_name=branch_name, background_execution=True)

        log.debug(f"Branch {branch_name} created in the Graph", repository=self.name, branch=branch_name)
        return branch

    def create_commit_worktree(self, commit: str) -> Union[bool, Worktree]:
        """Create a new worktree for a given commit."""

        # Check of the worktree already exist
        if self.has_worktree(identifier=commit):
            return False

        directory = os.path.join(self.directory_commits, commit)
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
            repo.git.worktree("add", os.path.join(self.directory_branches, branch_id), branch_name)
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

    async def fetch(self) -> bool:
        """Fetch the latest update from the remote repository and bring a copy locally."""
        if not self.has_origin:
            return False

        log.debug("Fetching the latest updates from remote origin.", repository=self.name)

        repo = self.get_git_repo_main()
        repo.remotes.origin.fetch()

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

        return sorted(list(new_branches)), sorted(updated_branches)

    async def validate_remote_branch(self, branch_name: str) -> bool:  # pylint: disable=unused-argument
        """Validate a branch present on the remote repository.
        To check a branch we need to first create a worktree in the temporary folder then apply some checks:
        - xxx

        At the end, we need to delete the worktree in the temporary folder.
        """
        try:
            # Check if the branch can be created in the database
            Branch(name=branch_name)
        except PydanticValidationError as e:
            log.warning(
                "Git branch failed validation.", branch_name=branch_name, errors=[error["msg"] for error in e.errors()]
            )
            return False

        # Find the commit on the remote branch
        # Check out the commit in a worktree
        # Validate

        return True

    async def pull(self, branch_name: str) -> Union[bool, str]:
        """Pull the latest update from the remote repository on a given branch."""

        if not self.has_origin:
            return False

        repo = self.get_git_repo_worktree(identifier=branch_name)
        if not repo:
            raise ValueError(f"Unable to identify the worktree for the branch : {branch_name}")

        try:
            commit_before = str(repo.head.commit)
            repo.remotes.origin.pull(branch_name)
        except GitCommandError as exc:
            if "Need to specify how to reconcile" in exc.stderr:
                raise RepositoryError(
                    identifier=self.name,
                    message=f"Unable to pull the branch {branch_name} for repository {self.name}, there is a conflict that must be resolved.",
                ) from exc
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

        commit_after = str(repo.head.commit)

        if commit_after == commit_before:
            return True

        self.create_commit_worktree(commit=commit_after)
        await self.update_commit_value(branch_name=branch_name, commit=commit_after)

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
        extension: Union[str, list[str]],
        branch_name: Optional[str] = None,
        commit: Optional[str] = None,
        directory: Optional[str] = None,
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

    def validate_location(self, commit: str, worktree_directory: str, file_path: str) -> Path:
        """Validate that a file is found inside a repository and return a corresponding `pathlib.Path` object for it."""
        path = Path(worktree_directory, file_path).resolve()

        if not str(path).startswith(worktree_directory):
            raise FileOutOfRepositoryError(repository_name=self.name, commit=commit, location=file_path)

        if not path.exists():
            raise RepositoryFileNotFoundError(repository_name=self.name, commit=commit, location=file_path)

        return path
