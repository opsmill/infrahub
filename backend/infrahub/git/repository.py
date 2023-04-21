from __future__ import annotations

import glob
import importlib
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

import git
import jinja2
import yaml
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from pydantic import BaseModel, validator

import infrahub.config as config
from infrahub.checks import INFRAHUB_CHECK_VARIABLE_TO_IMPORT, InfrahubCheck
from infrahub.exceptions import (
    CheckError,
    CommitNotFoundError,
    Error,
    FileNotFound,
    RepositoryError,
    TransformError,
)
from infrahub.transforms import INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT
from infrahub_client import GraphQLError, InfrahubClient, ValidationError

# pylint: disable=too-few-public-methods,too-many-lines

LOGGER = logging.getLogger("infrahub.git")

COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"


def get_repositories_directory() -> str:
    """Return the absolute path to the main directory used for the repositories."""
    repos_dir = config.SETTINGS.git.repositories_directory
    if not os.path.isabs(repos_dir):
        current_dir = os.getcwd()
        repos_dir = os.path.join(current_dir, config.SETTINGS.git.repositories_directory)

    return str(repos_dir)


def initialize_repositories_directory() -> bool:
    """Check if the main repositories_directory already exist, if not create it.

    Return
        True if the directory has been created,
        False if the directory was already present.
    """
    repos_dir = get_repositories_directory()
    if not os.path.isdir(repos_dir):
        os.makedirs(repos_dir)
        LOGGER.debug(f"Initialized the repositories_directory at {repos_dir}")
        return True

    LOGGER.debug(f"Repositories_directory already present at {repos_dir}")
    return False


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
    full_filename: str, repo_directory: str, worktree_directory: str = None
) -> RepoFileInformation:
    """Extract all the relevant and required information from a filename.

    Args:
        full_filename (str): Absolute path to the file to load Example:/opt/infrahub/git/repo01/commits/71da[..]4b7/myfile.py
        root_directory: Absolute path to the root of the repository directory. Example:/opt/infrahub/git/repo01
        worktree_directory (str, optional): Absolute path to the root of the worktree directory. Defaults to None. example: /opt/infrahub/git/repo01/commits/71da[..]4b7/

    Returns:
        RepoFileInformation: Pydantic object to store all information about this file
    """
    abs_directory_name = os.path.dirname(full_filename)
    filename = os.path.basename(full_filename)
    filename_wo_ext, extension = os.path.splitext(filename)

    relative_repo_path_dir = abs_directory_name.replace(repo_directory, "")
    if relative_repo_path_dir.startswith("/"):
        relative_repo_path_dir = relative_repo_path_dir[1:]

    if worktree_directory and worktree_directory in abs_directory_name:
        path_in_repo = abs_directory_name.replace(worktree_directory, "")
        if path_in_repo.startswith("/"):
            path_in_repo = path_in_repo[1:]
    else:
        path_in_repo = abs_directory_name

    file_path = os.path.join(path_in_repo, filename)

    module_name = relative_repo_path_dir.replace("/", ".") + f".{filename_wo_ext}"

    return RepoFileInformation(
        filename=filename,
        filename_wo_ext=filename_wo_ext,
        module_name=module_name,
        absolute_path_dir=abs_directory_name,
        relative_path_dir=path_in_repo,
        relative_repo_path_dir=relative_repo_path_dir,
        extension=extension,
        relative_path_file=file_path,
    )


class Worktree(BaseModel):
    identifier: str
    directory: str
    commit: str
    branch: Optional[str]

    @classmethod
    def init(cls, text):
        lines = text.split("\n")

        full_directory = lines[0].replace("worktree ", "")

        # Extract the identifier from the directory name
        # We first need to substract the main repository_directory to get the relative path.
        repo_directory = get_repositories_directory()
        relative_directory = full_directory.replace(repo_directory, "")
        relative_paths = relative_directory.split("/")

        identifier = None
        if len(relative_paths) == 3:
            # this is the main worktree for the main branch
            identifier = relative_paths[2]
        elif len(relative_paths) == 4:
            # this is the either a commit or a branch worktree
            identifier = relative_paths[3]
        else:
            raise Error("Unexpected directory path for a worktree.")

        item = cls(
            identifier=identifier,
            directory=full_directory,
            commit=lines[1].replace("HEAD ", ""),
        )

        if lines[2] != "detached":
            item.branch = lines[1].replace("branch refs/heads", "")

        return item


class BranchInGraph(BaseModel):
    id: str
    name: str
    is_data_only: bool
    commit: Optional[str]


class BranchInRemote(BaseModel):
    name: str
    commit: str


class BranchInLocal(BaseModel):
    name: str
    commit: str
    has_worktree: bool = False


class InfrahubRepository(BaseModel):  # pylint: disable=too-many-public-methods
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

    id: UUID
    name: str
    default_branch_name: Optional[str]
    type: Optional[str]
    location: Optional[str]
    has_origin: bool = False

    client: Optional[InfrahubClient]

    cache_repo: Optional[Repo]

    class Config:
        arbitrary_types_allowed = True

    # pylint: disable=no-self-argument
    @validator("default_branch_name", pre=True, always=True)
    def set_default_branch_name(cls, value):
        return value or config.SETTINGS.main.default_branch

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
        return os.path.join(self.directory_root, config.SETTINGS.main.default_branch)

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
        commit = str(repo.head.commit)
        if not os.path.isdir(os.path.join(self.directory_commits, commit)):
            raise RepositoryError(
                identifier=self.name, message=f"The directory for the main commit is missing for {self.name}"
            )

        return True

    async def create_locally(self) -> bool:
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
            LOGGER.warning(f"Found an existing directory at {self.directory_root}, deleted it")
        elif os.path.isfile(self.directory_root):
            os.remove(self.directory_root)
            LOGGER.warning(f"Found an existing file at {self.directory_root}, deleted it")

        # Initialize directory structure
        os.makedirs(self.directory_root)
        os.makedirs(self.directory_branches)
        os.makedirs(self.directory_commits)
        os.makedirs(self.directory_temp)

        try:
            repo = Repo.clone_from(self.location, self.directory_default)
            repo.git.checkout(self.default_branch_name)
        except GitCommandError as exc:
            if "Repository not found" in exc.stderr or "does not appear to be a git" in exc.stderr:
                raise RepositoryError(
                    identifier=self.name,
                    message=f"Unable to clone the repository {self.name}, please check the address and the credential",
                ) from exc

            if "error: pathspec" in exc.stderr:
                raise RepositoryError(
                    identifier=self.name,
                    message=f"The branch {self.default_branch_name} isn't a valid branch for the repository {self.name} at {self.location}.",
                ) from exc

            raise RepositoryError(identifier=self.name) from exc

        self.has_origin = True

        # Create a worktree for the commit in main
        # TODO Need to handle the potential exceptions coming from repo.git.worktree
        commit = str(repo.head.commit)
        self.create_commit_worktree(commit=commit)
        await self.update_commit_value(branch_name=self.default_branch_name, commit=commit)

        return True

    @classmethod
    async def new(cls, **kwargs):
        self = cls(**kwargs)
        await self.create_locally()
        LOGGER.info(f"{self.name} | Created the new project locally.")
        return self

    @classmethod
    async def init(cls, **kwargs):
        self = cls(**kwargs)
        self.validate_local_directories()
        LOGGER.debug(f"{self.name} | Initiated the object on an existing directory.")
        return self

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

        return None

    def get_commit_worktree(self, commit: str) -> Worktree:
        """Access a specific commit worktree."""

        worktrees = self.get_worktrees()

        for worktree in worktrees:
            if worktree.identifier == commit:
                return worktree

        # if not worktree exist for this commit already
        # We'll try to create one
        return self.create_commit_worktree(commit=commit)

    def get_worktrees(self) -> List[Worktree]:
        """Return the list of worktrees configured for this repository."""
        repo = self.get_git_repo_main()
        responses = repo.git.worktree("list", "--porcelain").split("\n\n")

        return [Worktree.init(response) for response in responses]

    async def get_branches_from_graph(self) -> Dict[str, BranchInGraph]:
        """Return a dict with all the branches present in the graph.
        Query the list of branches first then query the repository for each branch.
        """

        response = {}

        branches = await self.client.branch.all()

        # TODO Need to optimize this query, right now we are querying everything unnecessarily
        repositories = await self.client.get_list_repositories(branches=branches)
        repository = repositories[self.name]

        for branch_name, branch in branches.items():
            response[branch_name] = BranchInGraph(
                id=branch.id,
                name=branch.name,
                is_data_only=branch.is_data_only,
                commit=repository.branches[branch_name] or None,
            )

        return response

    def get_branches_from_remote(self) -> Dict[str, BranchInRemote]:
        """Return a dict with all the branches present on the remote."""

        git_repo = self.get_git_repo_main()

        branches = {}

        for remote_branch in git_repo.remotes.origin.refs:
            if not isinstance(remote_branch, git.refs.remote.RemoteReference):  # pylint: disable=no-member
                continue

            short_name = remote_branch.name.replace("origin/", "")

            if short_name == "HEAD":
                continue

            branches[short_name] = BranchInRemote(name=short_name, commit=str(remote_branch.commit))

        return branches

    def get_branches_from_local(self, include_worktree: bool = True) -> Dict[str, BranchInLocal]:
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

    def get_commit_value(self, branch_name, remote: bool = False) -> str:
        branches = None
        if remote:
            branches = self.get_branches_from_remote()
        else:
            branches = self.get_branches_from_local(include_worktree=False)

        if branch_name not in branches:
            raise ValueError(f"Branch {branch_name} not found.")

        return str(branches[branch_name].commit)

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        """Compare the value of the commit in the graph with the current commit on the filesystem.
        update it if they don't match.

        Returns:
            True if the commit has been updated
            False if they already had the same value
        """

        if not self.client:
            LOGGER.warning("Unable to update the value of the commit because a valid client hasn't been provided.")
            return

        LOGGER.debug(f"{self.name} | Updating commit value to {commit} for branch {branch_name}")
        await self.client.repository_update_commit(branch_name=branch_name, repository_id=self.id, commit=commit)

        return True

    async def create_branch_in_git(self, branch_name: str, push_origin: bool = True) -> bool:
        """Create new branch in the repository, assuming the branch has been created in the graph already."""

        repo = self.get_git_repo_main()

        # Check if the branch already exist locally, if it does do nothing
        local_branches = self.get_branches_from_local(include_worktree=False)
        if branch_name in local_branches:
            return False

        # TODO Catch potential exceptions coming from repo.git.branch & repo.git.worktree
        repo.git.branch(branch_name)
        self.create_branch_worktree(branch_name=branch_name)

        # If there is not remote configured, we are done
        #  Since the branch is a match for the main branch we don't need to create a commit worktree
        # If there is a remote, Check if there is an existing remote branch with the same name and if so track it.
        if not self.has_origin:
            LOGGER.debug("%s | Branch %s created in Git without tracking a remote branch.", self.name, branch_name)
            return True

        remote_branch = [br for br in repo.remotes.origin.refs if br.name == f"origin/{branch_name}"]

        if remote_branch:
            br_repo = self.get_git_repo_worktree(identifier=branch_name)
            br_repo.head.reference.set_tracking_branch(remote_branch[0])
            br_repo.remotes.origin.pull(branch_name)
            self.create_commit_worktree(str(br_repo.head.reference.commit))
            LOGGER.debug(
                "%s | Branch %s  created in Git, tracking remote branch %s.", self.name, branch_name, remote_branch[0]
            )
        else:
            LOGGER.debug(f"{self.name} | Branch {branch_name} created in Git without tracking a remote branch.")

        if push_origin:
            await self.push(branch_name)

        return True

    async def create_branch_in_graph(self, branch_name: str):
        """Create a new branch in the graph.

        NOTE We need to validate that we are not gonna end up with a race condition
        since a call to the GraphQL API will trigger a new RPC call to add a branch in this repo.
        """

        # TODO need to handle the exception properly
        await self.client.branch.create(branch_name=branch_name, background_execution=True)

        LOGGER.debug(f"{self.name} | Branch {branch_name} created in the Graph")
        return True

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
            LOGGER.debug(f"{self.name} | Commit worktree created {commit}")
            return worktree
        except GitCommandError as exc:
            if "invalid reference" in exc.stderr:
                raise CommitNotFoundError(
                    identifier=self.name,
                    commit=commit,
                ) from exc
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

    def create_branch_worktree(self, branch_name: str) -> bool:
        """Create a new worktree for a given branch."""

        # Check if the worktree already exist
        if self.has_worktree(identifier=branch_name):
            return False

        try:
            repo = self.get_git_repo_main()
            repo.git.worktree("add", os.path.join(self.directory_branches, branch_name), branch_name)
        except GitCommandError as exc:
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

        LOGGER.debug(f"{self.name} | Branch worktree created {branch_name}")
        return True

    async def calculate_diff_between_commits(
        self, first_commit: str, second_commit: str
    ) -> Tuple[List[str], List[str], List[str]]:
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

    async def push(self, branch_name: str) -> bool:
        """Push a given branch to the remote Origin repository"""

        if not self.has_origin:
            return False

        LOGGER.debug(f"{self.name} | Pushing the latest update to the remote origin for the branch '{branch_name}'")

        # TODO Catch potential exceptions coming from origin.push
        repo = self.get_git_repo_worktree(identifier=branch_name)
        repo.remotes.origin.push(branch_name)

        return True

    async def fetch(self) -> bool:
        """Fetch the latest update from the remote repository and bring a copy locally."""
        if not self.has_origin:
            return False

        LOGGER.debug(f"{self.name} | Fetching the latest updates from remote origin.")

        repo = self.get_git_repo_main()
        repo.remotes.origin.fetch()

        return True

    async def sync(self):
        """Synchronize the repository with its remote origin and with the database.

        By default the sync will focus only on the branches pulled from origin that have some differences with the local one.
        """

        LOGGER.info(f"{self.name} | Starting the synchronization.")

        await self.fetch()

        new_branches, updated_branches = await self.compare_local_remote()

        if not new_branches and not updated_branches:
            return True

        LOGGER.debug(f"{self.name} | New Branches {new_branches}, Updated Branches {updated_branches} ")

        # TODO need to handle properly the situation when a branch is not valid.
        for branch_name in new_branches:
            is_valid = await self.validate_remote_branch(branch_name=branch_name)
            if not is_valid:
                continue

            try:
                await self.create_branch_in_graph(branch_name=branch_name)
            except GraphQLError as exc:
                if "already exist" not in exc.errors[0]["message"]:
                    raise

            await self.create_branch_in_git(branch_name=branch_name)

            commit = self.get_commit_value(branch_name=branch_name, remote=False)
            self.create_commit_worktree(commit=commit)
            await self.update_commit_value(branch_name=branch_name, commit=commit)

            await self.import_objects_from_files(branch_name=branch_name)

        for branch_name in updated_branches:
            is_valid = await self.validate_remote_branch(branch_name=branch_name)
            if not is_valid:
                continue

            commit_after = await self.pull(branch_name=branch_name)
            await self.import_objects_from_files(branch_name=branch_name)

            if commit_after is True:
                LOGGER.warning(
                    f"{self.name} | An update was detected on {branch_name} but the commit remained the same after pull() ({commit_after}) ."
                )

        return True

    async def compare_local_remote(self) -> Set[List[str], List[str]]:
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
                LOGGER.info(f"New commit detected in branch {branch_name}")
                updated_branches.append(branch_name)

        return sorted(list(new_branches)), sorted(updated_branches)

    async def validate_remote_branch(self, branch_name: str) -> bool:  # pylint: disable=unused-argument
        """Validate a branch present on the remote repository.
        To check a branch we need to first create a worktree in the temporary folder then apply some checks:
        - xxx

        At the end, we need to delete the worktree in the temporary folder.
        """

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

    async def import_objects_from_files(self, branch_name: str):
        if not self.client:
            LOGGER.warning("Unable to import the objects from the files because a valid client hasn't been provided.")
            return

        await self.import_all_graphql_query(branch_name=branch_name)
        await self.import_all_yaml_files(branch_name=branch_name)
        await self.import_all_python_files(branch_name=branch_name)

    async def import_objects_rfiles(self, branch_name: str, data: dict):
        LOGGER.debug(f"{self.name} | Importing all RFiles in branch {branch_name} ")

        schema = await self.client.schema.get(kind="RFile", branch=branch_name)

        rfiles_in_repo = await self.client.filters(kind="RFile", template_repository__id=str(self.id))

        for rfile in data:
            # Insert the UUID of the repository in case they are referencing the local repo

            try:
                self.client.schema.validate_data_against_schema(schema=schema, data=rfile)
            except ValidationError as exc:
                LOGGER.error(exc.message)
                continue

            if rfile.get("template_repository") == "self" or "template_repository" not in rfile:
                rfile["template_repository"] = self.id

            current_names = [rfile.name.value for rfile in rfiles_in_repo]
            if rfile["name"] not in current_names:
                LOGGER.info(f"{self.name}: New RFile {rfile['name']!r} found on branch {branch_name!r}, creating")

                create_payload = self.client.schema.generate_payload_create(
                    schema=schema, data=rfile, source=self.id, is_protected=True
                )
                obj = await self.client.create(kind="RFile", branch=branch_name, **create_payload)
                await obj.save()
                continue

            rfile_in_repo = [item for item in rfiles_in_repo if item.name.value == rfile["name"]][0]

            description = (
                rfile.get("description") if rfile.get("description") is not None else rfile_in_repo.description.value
            )
            template_path = (
                rfile.get("template_path")
                if rfile.get("template_path") is not None
                else rfile_in_repo.template_path.value
            )

            if description != rfile_in_repo.description.value or template_path != rfile_in_repo.template_path.value:
                LOGGER.info(
                    f"{self.name}: New version of the RFile '{rfile['name']}' found on branch {branch_name}, updating"
                )
                rfile_in_repo.name.value = rfile["name"]
                rfile_in_repo.description.value = description
                rfile_in_repo.template_path.value = template_path
                await rfile_in_repo.save()

    async def import_all_graphql_query(self, branch_name: str):
        """Search for all .gql file and import them as GraphQL query."""

        LOGGER.debug(f"{self.name} | Importing all GraphQL Queries in branch {branch_name} ")

        query_files = await self.find_files(extension=["gql"], branch_name=branch_name)

        queries_in_graph = await self.client.get_list_graphql_queries(branch_name=branch_name)

        for query_file in query_files:
            filename = os.path.basename(query_file)
            query_name = os.path.splitext(filename)[0]
            query_string = Path(query_file).read_text(encoding="UTF-8")

            if query_name not in queries_in_graph.keys():
                LOGGER.info(f"{self.name} | New Graphql Query '{query_name}' found on branch {branch_name}, creating")
                await self.client.create_graphql_query(branch_name=branch_name, name=query_name, query=query_string)

            elif query_string != queries_in_graph[query_name].query:
                query = queries_in_graph[query_name]
                LOGGER.info(
                    f"{self.name} | New version of the Graphql Query '{query_name}' found on branch {branch_name}, updating"
                )
                await self.client.update_graphql_query(
                    branch_name=branch_name,
                    id=query.id,
                    name=query_name,
                    query=query_string,
                    description=query.description,
                )

        # TODO need to add traceabillity to identify where a query is coming from
        # TODO need to identify Query that are not present anymore (once lineage is available)

    async def import_python_checks_from_module(self, branch_name: str, module, file_path: str):
        # TODO add function to validate if a check is valid

        if INFRAHUB_CHECK_VARIABLE_TO_IMPORT not in dir(module):
            return False

        checks_in_graph = await self.client.get_list_checks(branch_name=branch_name)
        checks_in_repo = {key: value for key, value in checks_in_graph.items() if value.repository == str(self.id)}

        for check_class in getattr(module, INFRAHUB_CHECK_VARIABLE_TO_IMPORT):
            check_name = check_class.__name__

            if check_name not in checks_in_repo:
                LOGGER.info(f"{self.name}: New Check '{check_name}' found on branch {branch_name}, creating")
                await self.client.create_check(
                    branch_name=branch_name,
                    name=check_name,
                    repository=str(self.id),
                    query=check_class.query,
                    file_path=file_path,
                    class_name=check_name,
                    rebase=check_class.rebase,
                    timeout=check_class.timeout,
                )
                continue

            check_in_repo = checks_in_repo[check_name]

            # pylint: disable=too-many-boolean-expressions
            if (
                check_in_repo.repository != self.id
                or check_in_repo.class_name != check_name
                or check_in_repo.query != file_path
                or check_in_repo.file_path != check_class.query
                or check_in_repo.timeout != check_class.timeout
                or check_in_repo.rebase != check_class.rebase
            ):
                LOGGER.info(
                    f"{self.name}: New version of the Check '{check_name}' found on branch {branch_name}, updating"
                )
                await self.client.update_check(
                    branch_name=branch_name,
                    id=str(checks_in_repo[check_name].id),
                    name=check_name,
                    query=check_class.query,
                    file_path=file_path,
                    class_name=check_name,
                    rebase=check_class.rebase,
                    timeout=check_class.timeout,
                )

    async def import_python_transforms_from_module(self, branch_name: str, module, file_path: str):
        # TODO add function to validate if a check is valid

        if INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT not in dir(module):
            return False

        transforms_in_graph = await self.client.get_list_transform_python(branch_name=branch_name)
        transforms_in_repo = {
            key: value for key, value in transforms_in_graph.items() if value.repository == str(self.id)
        }

        for transform_class in getattr(module, INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT):
            transform = transform_class()
            transform_class_name = transform_class.__name__

            if transform.name not in transforms_in_repo:
                LOGGER.info(
                    f"{self.name}: New Python Transform '{transform.name}' found on branch {branch_name}, creating"
                )
                await self.client.create_transform_python(
                    branch_name=branch_name,
                    name=transform.name,
                    repository=str(self.id),
                    query=transform.query,
                    file_path=file_path,
                    url=transform.url,
                    class_name=transform_class_name,
                    rebase=transform.rebase,
                    timeout=transform.timeout,
                )
                continue

            transform_in_repo = transforms_in_repo[transform.name]
            # pylint: disable=too-many-boolean-expressions
            if (
                transform_in_repo.repository != self.id
                or transform_in_repo.class_name != transform.name
                or transform_in_repo.query != file_path
                or transform_in_repo.file_path != transform.query
                or transform_in_repo.timeout != transform.timeout
                or transform_in_repo.url != transform.url
                or transform_in_repo.rebase != transform.rebase
            ):
                LOGGER.info(
                    f"{self.name}: New version of the Python Transform '{transform.name}' found on branch {branch_name}, updating"
                )
                await self.client.update_transform_python(
                    branch_name=branch_name,
                    id=str(transforms_in_repo[transform.name].id),
                    name=transform.name,
                    query=transform.query,
                    file_path=file_path,
                    url=transform.url,
                    class_name=transform_class_name,
                    rebase=transform.rebase,
                    timeout=transform.timeout,
                )

    async def import_all_yaml_files(self, branch_name: str):
        yaml_files = await self.find_files(extension=["yml", "yaml"], branch_name=branch_name)

        for yaml_file in yaml_files:
            LOGGER.debug(f"{self.name} | Checking {yaml_file}")

            # ------------------------------------------------------
            # Import Yaml
            # ------------------------------------------------------
            with open(yaml_file, "r", encoding="UTF-8") as file_data:
                yaml_data = file_data.read()

            try:
                data = yaml.safe_load(yaml_data)
            except yaml.YAMLError as exc:
                LOGGER.warning(f"{self.name} | Unable to load YAML file {yaml_file} : {exc}")
                continue

            if not isinstance(data, dict):
                LOGGER.debug(f"{self.name} | {yaml_file} : payload is not a dictionnary .. SKIPPING")
                continue

            # ------------------------------------------------------
            # Search for Valid object types
            # ------------------------------------------------------
            for key, data in data.items():
                if not hasattr(self, f"import_objects_{key}"):
                    continue

                method = getattr(self, f"import_objects_{key}")
                await method(branch_name=branch_name, data=data)

    async def import_all_python_files(self, branch_name: str):
        branch_wt = self.get_worktree(identifier=branch_name)
        python_files = await self.find_files(extension=["py"], branch_name=branch_name)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        for python_file in python_files:
            LOGGER.debug(f"{self.name} | Checking {python_file}")

            file_info = extract_repo_file_information(
                full_filename=python_file, repo_directory=self.directory_root, worktree_directory=branch_wt.directory
            )

            try:
                module = importlib.import_module(file_info.module_name)
            except ModuleNotFoundError:
                LOGGER.warning(f"{self.name} | Unable to load python file {python_file}")
                continue

            await self.import_python_checks_from_module(
                branch_name=branch_name, module=module, file_path=file_info.relative_path_file
            )
            await self.import_python_transforms_from_module(
                branch_name=branch_name, module=module, file_path=file_info.relative_path_file
            )

    async def find_files(self, extension: Union[str, List[str]], branch_name: str, recursive: bool = True):
        branch_wt = self.get_worktree(identifier=branch_name)

        files = []

        if isinstance(extension, str):
            files.extend(glob.glob(f"{branch_wt.directory}/**/*.{extension}", recursive=recursive))
            files.extend(glob.glob(f"{branch_wt.directory}/**/.*.{extension}", recursive=recursive))
        elif isinstance(extension, list):
            for ext in extension:
                files.extend(glob.glob(f"{branch_wt.directory}/**/*.{ext}", recursive=recursive))
                files.extend(glob.glob(f"{branch_wt.directory}/**/.*.{ext}", recursive=recursive))
        return files

    async def render_jinja2_template(self, commit: str, location: str, data: dict):
        commit_worktree = self.get_commit_worktree(commit=commit)

        if not os.path.exists(os.path.join(commit_worktree.directory, location)):
            raise FileNotFound(repository_name=self.name, commit=commit, location=location)

        try:
            templateLoader = jinja2.FileSystemLoader(searchpath=commit_worktree.directory)
            templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
            template = templateEnv.get_template(location)
            return template.render(**data)
        except Exception as exc:
            LOGGER.critical(exc, exc_info=True)
            raise TransformError(repository_name=self.name, commit=commit, location=location, message=str(exc)) from exc

    async def execute_python_check(
        self, branch_name: str, commit: str, location: str, class_name: str, client: InfrahubClient
    ) -> InfrahubCheck:
        """Execute A Python Check stored in the repository."""

        commit_worktree = self.get_commit_worktree(commit=commit)

        # Ensure the file is present in the repository
        if not os.path.exists(os.path.join(commit_worktree.directory, location)):
            raise FileNotFound(repository_name=self.name, commit=commit, location=location)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        try:
            file_info = extract_repo_file_information(
                full_filename=os.path.join(commit_worktree.directory, location),
                repo_directory=self.directory_root,
                worktree_directory=commit_worktree.directory,
            )

            module = importlib.import_module(file_info.module_name)

            check_class = getattr(module, class_name)

            check = await check_class.init(root_directory=commit_worktree.directory, branch=branch_name, client=client)
            await check.run()

            return check

        except ModuleNotFoundError as exc:
            error_msg = f"Unable to load the check file {location} ({commit})"
            LOGGER.error(f"{self.name} | {error_msg}")
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=error_msg
            ) from exc

        except AttributeError as exc:
            error_msg = f"Unable to find the class {class_name} in {location} ({commit})"
            LOGGER.error(f"{self.name} | {error_msg}")
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=error_msg
            ) from exc

        except Exception as exc:
            LOGGER.critical(exc, exc_info=True)
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=str(exc)
            ) from exc

    async def execute_python_transform(
        self, branch_name: str, commit: str, location: str, client: InfrahubClient, data: dict = None
    ) -> InfrahubCheck:
        """Execute A Python Transform stored in the repository."""

        if "::" not in location:
            raise ValueError("Transformation location not valid, it must contains a double colons (::)")

        file_path, class_name = location.split("::")
        commit_worktree = self.get_commit_worktree(commit=commit)

        LOGGER.debug(f"Will run Python Transform from {class_name} at {location} ({commit})")

        # Ensure the file is present in the repository
        if not os.path.exists(os.path.join(commit_worktree.directory, file_path)):
            raise FileNotFound(repository_name=self.name, commit=commit, location=file_path)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        try:
            file_info = extract_repo_file_information(
                full_filename=os.path.join(commit_worktree.directory, file_path),
                repo_directory=self.directory_root,
                worktree_directory=commit_worktree.directory,
            )

            module = importlib.import_module(file_info.module_name)

            transform_class = getattr(module, class_name)

            transform = await transform_class.init(
                root_directory=commit_worktree.directory, branch=branch_name, client=client
            )
            return await transform.run(data=data)

        except ModuleNotFoundError as exc:
            error_msg = f"Unable to load the transform file {location} ({commit})"
            LOGGER.error(f"{self.name} | {error_msg}")
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=error_msg
            ) from exc

        except AttributeError as exc:
            error_msg = f"Unable to find the class {class_name} in {location} ({commit})"
            LOGGER.error(f"{self.name} | {error_msg}")
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=error_msg
            ) from exc

        except Exception as exc:
            LOGGER.critical(exc, exc_info=True)
            raise TransformError(repository_name=self.name, commit=commit, location=location, message=str(exc)) from exc
