from __future__ import annotations

import git
import glob
import os
import yaml
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Set, Union, Optional

import jinja2

from uuid import UUID
from pydantic import BaseModel, validator
from git import Repo
from git.exc import InvalidGitRepositoryError, GitCommandError

from infrahub_client import InfrahubClient

import infrahub.config as config
from infrahub.lock import registry as lock_registry
from infrahub.exceptions import RepositoryError, TransformError, TransformNotFoundError
from infrahub.message_bus.events import (
    InfrahubGitRPC,
    InfrahubRPCResponse,
    GitMessageAction,
    InfrahubTransformRPC,
    TransformMessageAction,
    RPCStatusCode,
)

LOGGER = logging.getLogger("infrahub.git")

COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"


async def handle_git_rpc_message(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:

    LOGGER.debug(f"Will process Git RPC message : {message.action}, {message.repository_name} : {message.params}")

    if message.action == GitMessageAction.REPO_ADD.value:

        async with lock_registry.get(message.repository_name):
            try:
                repo = await InfrahubRepository.new(
                    id=message.repository_id, name=message.repository_name, location=message.location, client=client
                )
                await repo.import_objects_from_files(branch_name=repo.default_branch_name)
                await repo.sync()

            except RepositoryError as exc:
                return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST, errors=[exc.message])

            return InfrahubRPCResponse(status=RPCStatusCode.CREATED.value)

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    if message.action == GitMessageAction.BRANCH_ADD.value:

        async with lock_registry.get(message.repository_name):
            try:
                await repo.create_branch_in_git(branch_name=message.params["branch_name"])
            except RepositoryError as exc:
                return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])

            return InfrahubRPCResponse(status=RPCStatusCode.OK.value)

    elif message.action == GitMessageAction.DIFF.value:

        # Calculate the diff between 2 timestamps / branches
        files_changed = repo.calculate_diff_between_commits(
            first_commit=message.params["first_commit"], second_commit=message.params["second_commit"]
        )
        return InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"files_changed": files_changed})

    elif message.action == GitMessageAction.MERGE.value:
        async with lock_registry.get(message.repository_name):
            repo.merge(source_branch=message.params["branch_name"])
            return InfrahubRPCResponse(status=RPCStatusCode.OK.value)

    elif message.action == GitMessageAction.REBASE.value:
        # async with lock_registry.get(message.repository_name):
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    elif message.action == GitMessageAction.PUSH.value:
        # async with lock_registry.get(message.repository_name):
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    elif message.action == GitMessageAction.PULL.value:
        # async with lock_registry.get(message.repository_name):
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST.value)


async def handle_git_transform_message(message: InfrahubTransformRPC, client: InfrahubClient) -> InfrahubRPCResponse:

    LOGGER.debug(
        f"Will process Transform RPC message : {message.action}, {message.repository_name} : {message.transform_location}"
    )

    if message.action == TransformMessageAction.JINJA2.value:

        repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

        try:
            rendered_template = await repo.render_jinja2_template(
                commit=message.commit, location=message.transform_location, data=message.data or {}
            )
            return InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"rendered_template": rendered_template})

        except TransformError as exc:
            return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR.value, errors=[exc.message])

    elif message.action == TransformMessageAction.PYTHON.value:
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST.value)


def get_repositories_directory() -> str:
    current_dir = os.getcwd()
    repos_dir = os.path.join(current_dir, config.SETTINGS.main.repositories_directory)
    return str(repos_dir)


def initialize_repositories_directory() -> bool:
    """Check if the main repositories_directory already exist, if not create it.

    Return
        True if the directory has been created,
        False if the directory was already present.
    """
    repos_dir = get_repositories_directory()
    isdir = os.path.isdir(repos_dir)
    if not isdir:
        os.makedirs(repos_dir)
        return True

    return False


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
            raise Exception("Unexpected directory path for a worktree.")

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


class InfrahubRepository(BaseModel):
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

    @validator("default_branch_name", pre=True, always=True)
    def set_default_branch_name(cls, value):
        return value or config.SETTINGS.main.default_branch

    @property
    def directory_root(self) -> str:
        """Return the path to the root directory for this repository."""
        current_dir = os.getcwd()
        repositories_directory = config.SETTINGS.main.repositories_directory
        if not os.path.isabs(repositories_directory):
            repositories_directory = os.path.join(current_dir, config.SETTINGS.main.repositories_directory)

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

        except InvalidGitRepositoryError:
            raise RepositoryError(
                identifier=self.name, message=f"The data on disk is not a valid Git repository for {self.name}."
            )

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
                )

            if "error: pathspec" in exc.stderr:
                raise RepositoryError(
                    identifier=self.name,
                    message=f"The branch {self.default_branch_name} isn't a valid branch for the repository {self.name} at {self.location}.",
                )

            raise RepositoryError(identifier=self.name)

        self.has_origin = True

        # Create a worktree for the commit in main
        # TODO Need to handle the potential exceptions coming from repo.git.worktree
        commit = str(repo.head.commit)
        repo.git.worktree("add", os.path.join(self.directory_commits, commit), commit)

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
        LOGGER.info(f"{self.name} | Initiated the object on an existing directory.")
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

        branches = await self.client.get_list_branches()

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
            if not isinstance(remote_branch, git.refs.remote.RemoteReference):
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
        if branch_name in local_branches.keys():
            return False

        # TODO Catch potential exceptions coming from repo.git.branch & repo.git.worktree
        repo.git.branch(branch_name)
        await self.create_branch_worktree(branch_name=branch_name)

        # If there is not remote configured, we are done
        #  Since the branch is a match for the main branch we don't need to create a commit worktree
        # If there is a remote, Check if there is an existing remote branch with the same name and if so track it.
        if not self.has_origin:
            LOGGER.debug(f"{self.name} | Branch {branch_name} created in Git without tracking a remote branch.")
            return True

        remote_branch = [br for br in repo.remotes.origin.refs if br.name == f"origin/{branch_name}"]

        if remote_branch:
            br_repo = self.get_git_repo_worktree(identifier=branch_name)
            br_repo.head.reference.set_tracking_branch(remote_branch[0])
            br_repo.remotes.origin.pull(branch_name)
            await self.create_commit_worktree(str(br_repo.head.reference.commit))
            LOGGER.debug(
                f"{self.name} | Branch {branch_name} created in Git, tracking remote branch {remote_branch[0]}."
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
        await self.client.create_branch(branch_name=branch_name, background_execution=True)

        LOGGER.debug(f"{self.name} | Branch {branch_name} created in the Graph")
        return True

    async def create_commit_worktree(self, commit: str) -> bool:
        """Create a new worktree for a given commit."""

        # Check of the worktree already exist
        if self.has_worktree(identifier=commit):
            return False

        repo = self.get_git_repo_main()
        repo.git.worktree("add", os.path.join(self.directory_commits, commit), commit)

        LOGGER.debug(f"{self.name} | Commit worktree created {commit}")
        return True

    async def create_branch_worktree(self, branch_name: str) -> bool:
        """Create a new worktree for a given branch."""

        # Check if the worktree already exist
        if self.has_worktree(identifier=branch_name):
            return False

        repo = self.get_git_repo_main()
        repo.git.worktree("add", os.path.join(self.directory_branches, branch_name), branch_name)

        LOGGER.debug(f"{self.name} | Branch worktree created {branch_name}")
        return True

    async def calculate_diff_between_commits(self, first_commit: str, second_commit: str) -> List[str]:
        """TODO need to refactor this function to return more information.
        Like :
          - What has changed inside the files
          - Are there some conflicts between the files.
        """

        git_repo = self.get_git_repo_main()

        commit_to_compare = git_repo.commit(second_commit)
        commit_in_branch = git_repo.commit(first_commit)

        changed_files = []

        for x in commit_in_branch.diff(commit_to_compare):
            if x.a_blob and x.a_blob.path not in changed_files:
                changed_files.append(x.a_blob.path)

            if x.b_blob is not None and x.b_blob.path not in changed_files:
                changed_files.append(x.b_blob.path)

        return changed_files or None

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

            await self.create_branch_in_graph(branch_name=branch_name)
            await self.create_branch_in_git(branch_name=branch_name)

            commit = self.get_commit_value(branch_name=branch_name, remote=False)
            await self.create_commit_worktree(commit=commit)
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

    async def validate_remote_branch(self, branch_name: str) -> bool:
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
                )
            raise RepositoryError(identifier=self.name, message=exc.stderr)

        commit_after = str(repo.head.commit)

        if commit_after == commit_before:
            return True

        await self.create_commit_worktree(commit=commit_after)
        await self.update_commit_value(branch_name=branch_name, commit=commit_after)

        return commit_after

    async def merge(self, source_branch: str, dest_branch: str, push_remote: bool = True) -> bool:
        """Merge the current branch into main.

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
            raise RepositoryError(identifier=self.name, message=exc.stderr)

        commit_after = str(repo.head.commit)

        if commit_after == commit_before:
            return False

        await self.create_commit_worktree(commit_after)
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

    async def import_objects_rfiles(self, branch_name: str, data: dict):

        LOGGER.debug(f"{self.name} | Importing all RFiles in branch {branch_name} ")

        # For now we query all repositories and we filter down to this one
        # We'll need to revisit that once we have a better client library
        rfiles_in_graph = await self.client.get_list_rfiles(branch_name=branch_name)
        rfiles_in_repo = {
            key: value for key, value in rfiles_in_graph.items() if value.template_repository == str(self.id)
        }

        for rfile_name, rfile in data.items():

            # Insert the UUID of the repository in case they are referencing the local repo
            for key in rfile.keys():
                if "repository" in key:
                    if rfile[key] == "self":
                        rfile[key] = self.id

            if rfile_name not in rfiles_in_repo:
                LOGGER.info(f"{self.name}: New RFile '{rfile_name}' found on branch {branch_name}, creating")
                await self.client.create_rfile(
                    branch_name=branch_name,
                    name=rfile_name,
                    description=rfile.get("description", ""),
                    query=rfile.get("query"),
                    template_path=rfile.get("template_path"),
                    template_repository=str(rfile.get("template_repository")),
                )
                continue

            rfile_in_repo = rfiles_in_repo[rfile_name]

            need_to_update = False
            for field_name in ["template_path", "description"]:
                attr = getattr(rfile_in_repo, field_name)
                if field_name in rfile and rfile[field_name] != attr:
                    need_to_update = True

                if need_to_update:
                    LOGGER.info(
                        f"{self.name}: New version of the RFile '{rfile_name}' found on branch {branch_name}, updating"
                    )
                    await self.client.update_rfile(
                        branch_name=branch_name,
                        id=str(rfile_in_repo.id),
                        name=rfile_name,
                        description=rfile["description"],
                        template_path=rfile["template_path"],
                    )

    async def import_all_graphql_query(self, branch_name: str):
        """Search for all .gql file and import them as GraphQL query."""

        LOGGER.debug(f"{self.name} | Importing all GraphQL Queries in branch {branch_name} ")

        query_files = await self.find_files(extension=["gql"], branch_name=branch_name)

        queries_in_graph = await self.client.get_list_graphql_queries(branch_name=branch_name)

        for query_file in query_files:

            filename = os.path.basename(query_file)
            query_name = os.path.splitext(filename)[0]
            query_string = Path(query_file).read_text()

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

    async def import_all_yaml_files(self, branch_name: str):

        yaml_files = await self.find_files(extension=["yml", "yaml"], branch_name=branch_name)

        for yaml_file in yaml_files:

            LOGGER.debug(f"{self.name} | Checking {yaml_file}")

            # ------------------------------------------------------
            # Import Yaml
            # ------------------------------------------------------
            with open(yaml_file, "r") as file_data:
                yaml_data = file_data.read()

            try:
                data = yaml.safe_load(yaml_data)
            except yaml.YAMLError as exc:
                LOGGER.warning(f"{self.name} | Unable to load YAML file {yaml_file} : {exc.message}")
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

        commit_worktree = self.get_worktree(identifier=commit)

        if not os.path.exists(os.path.join(commit_worktree.directory, location)):
            raise TransformNotFoundError(repository_name=self.name, commit=commit, location=location)

        try:
            templateLoader = jinja2.FileSystemLoader(searchpath=commit_worktree.directory)
            templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
            template = templateEnv.get_template(location)
            return template.render(**data)
        except Exception as exc:
            LOGGER.critical(exc, exc_info=True)
            raise TransformError(repository_name=self.name, commit=commit, location=location, message=exc.message)

    # def run_checks(self, rebase: bool = True) -> set(bool, List[str]):
    #     """Execute the checks for this repository using the infrahub cli.

    #     The execution is done using the CLI to decouple the checks from the server, mainly for security reasons.

    #     The interface is very simple for now, this is something that need to be revisited.
    #     """

    #     # CHeck will fail if there is any log message with the severity ERROR
    #     result = True
    #     messages = []

    #     command = f"infrahub check run {self.get_active_directory()} --branch {self._branch.name} --format-json"
    #     if rebase:
    #         command += " --rebase"

    #     stream = os.popen(command)
    #     output = stream.read()
    #     output_lines = output.split("\n")

    #     for line in output_lines:
    #         if not line:
    #             continue

    #         log_message = json.loads(line)
    #         if log_message.get("level") == "ERROR":
    #             result = False
    #             messages.append(log_message.get("message"))

    #     return result, messages
