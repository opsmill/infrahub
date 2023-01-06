from __future__ import annotations

import git
import glob
import os
import asyncio
import shutil
import logging
from typing import List, Dict, Set, Optional

from uuid import UUID
from pydantic import BaseModel, validator
from git import Repo
from git.exc import InvalidGitRepositoryError, GitCommandError

from infrahub_client import InfrahubClient

import infrahub.config as config
from infrahub.exceptions import RepositoryError
from infrahub.message_bus.events import InfrahubGitRPC, InfrahubRPCResponse, GitMessageAction, RPCStatusCode

LOGGER = logging.getLogger("infrahub.git")

COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

QUERY_BRANCHES = """
query {
    branch {
        id
        name
        is_data_only
    }
}
"""

QUERY_REPOSITORY = """
query ($repository_name: String) {
    repository(name__value: $repository_name) {
        id
        name {
            value
        }
        location {
            value
        }
        commit {
            value
        }
    }
}
"""

MUTATION_COMMIT_UPDATE = """
mutation ($repository_id: String!, $commit: String!) {
    repository_update(data: { id: $repository_id, commit: { value: $commit } }) {
        ok
        object {
            commit {
                value
            }
        }
    }
}
"""

MUTATION_BRANCH_CREATE = """
mutation ($branch_name: String!) {
    branch_create(data: { name: $branch_name, is_data_only: false }) {
        ok
        object {
            id
            name
        }
    }
}
"""


async def handle_git_rpc_message(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:

    if message.action == GitMessageAction.REPO_ADD.value:

        try:
            repo = await InfrahubRepository.new(
                id=message.repository_id, name=message.repository_name, location=message.location, client=client
            )
            await repo.sync()

        except RepositoryError as exc:
            return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST, errors=[exc.message])

        return InfrahubRPCResponse(status=RPCStatusCode.CREATED.value)

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    if message.action == GitMessageAction.BRANCH_ADD.value:
        try:
            ok = await repo.create_branch_in_git(branch_name=message.params["branch_name"])
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
        ok = repo.merge(source_branch=message.params["branch_name"])
        return InfrahubRPCResponse(status=RPCStatusCode.OK.value)

    elif message.action == GitMessageAction.REBASE.value:
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    elif message.action == GitMessageAction.PUSH.value:
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    elif message.action == GitMessageAction.PULL.value:
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    return InfrahubRPCResponse(status=RPCStatusCode.NOT_FOUND.value)


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

    def create_locally(self) -> bool:
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

        return True

    @classmethod
    async def new(cls, **kwargs):

        self = cls(**kwargs)
        self.create_locally()

        return self

    @classmethod
    async def init(cls, **kwargs):

        self = cls(**kwargs)
        self.validate_local_directories()

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

    def get_commit_value(self, branch_name, remote: bool = False):

        branches = None
        if remote:
            branches = self.get_branches_from_remote()
        else:
            branches = self.get_branches_from_local(include_worktree=False)

        if not branch_name in branches:
            raise ValueError(f"Branch {branch_name} not found.")

        return branches[branch_name].commit

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        """Compare the value of the commit in the graph with the current commit on the filesystem.
        update it if they don't match.

        Returns:
            True if the commit has been updated
            False if they already had the same value
        """

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
            return True

        remote_branch = [br for br in repo.remotes.origin.refs if br.name == f"origin/{branch_name}"]

        if remote_branch:
            br_repo = self.get_git_repo_worktree(identifier=branch_name)
            br_repo.head.reference.set_tracking_branch(remote_branch[0])
            br_repo.remotes.origin.pull(branch_name)
            await self.create_commit_worktree(str(br_repo.head.reference.commit))

        if push_origin:
            await self.push(branch_name)

        return True

    async def create_branch_in_graph(self, branch_name: str):
        """Create a new branch in the graph.

        NOTE We need to validate that we are not gonna end up with a race condition
        since a call to the GraphQL API will trigger a new RPC call to add a branch in this repo.
        """

        await self.client.create_branch(branch_name=branch_name)

        return True

    async def create_commit_worktree(self, commit: str) -> bool:
        """Create a new worktree for a given commit."""

        # Check of the worktree already exist
        if self.has_worktree(identifier=commit):
            return False

        repo = self.get_git_repo_main()
        repo.git.worktree("add", os.path.join(self.directory_commits, commit), commit)

        return True

    async def create_branch_worktree(self, branch_name: str) -> bool:
        """Create a new worktree for a given branch."""

        # Check if the worktree already exist
        if self.has_worktree(identifier=branch_name):
            return False

        repo = self.get_git_repo_main()
        repo.git.worktree("add", os.path.join(self.directory_branches, branch_name), branch_name)

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

        # TODO Catch potential exceptions coming from origin.push
        repo = self.get_git_repo_main()
        repo.remotes.origin.push(branch_name)

        return True

    async def fetch(self) -> bool:
        """Fetch the latest update from the remote repository and bring a copy locally."""
        if not self.has_origin:
            return False

        repo = self.get_git_repo_main()
        repo.remotes.origin.fetch()

        return True

    async def sync(self):

        await self.fetch()

        new_branches, updated_branches = await self.compare_local_remote()

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

        for branch_name in updated_branches:
            is_valid = await self.validate_remote_branch(branch_name=branch_name)
            if not is_valid:
                continue

            self.pull()
            commit = self.get_commit_value(branch_name=branch_name, remote=False)
            await self.update_commit_value(branch_name=branch_name, commit=commit)

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

    async def pull(self, branch_name: str) -> bool:
        """Pull the latest update from the remote repository on a given branch."""

        repo = self.get_git_repo_main()
        repo.remotes.origin.pull(branch_name)

        return True

    async def merge(self, source_branch: str, dest_branch: str, push_remote: bool = True) -> bool:
        """Merge the current branch into main.

        After the rebase we need to resync the data
        """

        if source_branch == config.SETTINGS.main.default_branch:
            raise Exception("Unable to merge the default branch into itself.")

        repo = self.get_git_repo_main()

        # FIXME need to redesign this part to account for the new architecture

        # git_repo.git.merge(self.commit)

        return True

    async def rebase(self, branch_name: str, source_branch: str = "main", push_remote: bool = True) -> bool:
        """Rebase the current branch with main.

        Technically we are not doing a Git rebase because it will change the git history
        We'll merge the content of the source_branch into branch_name instead to keep the history clear.

        TODO need to see how we manage conflict

        After the rebase we need to resync the data
        """

        if source_branch == config.SETTINGS.main.default_branch:
            raise Exception("Unable to rebase the default branch into itself.")

        git_repo = self.get_git_repo_main()
        # FIXME need to redesign this part to account for the new architecture

        return True

    async def fetch_latest_from_remote(self):

        # Fetch the latest updates from the remote repository
        # Check all the branches to see of the commit are matching or not,
        #   - if a new commit is present on a remote branch
        #     - Create a new worktree in the temp directory for validation
        #     - If the branch is valid:
        #        - delete the temp worktree
        #        - create a new worktree in the proper directory
        #        - update the graph
        #     - If the branch is not valid:
        #        - ??? TODO we need to track that somewhere.

        git_repo = self.get_git_repo_main()
        git_repo.remotes.origin.fetch()

    #             # Pull the latest update from the remote repo
    #             git_repo.remotes.origin.fetch()
    #             git_repo.remotes.origin.pull()
    #             if str(git_repo.head.commit) != str(repo.commit.value):
    #                 log.info(
    #                     f"{repo.name.value}: Commit on branch {repo._branch.name} ({repo.commit.value}) do not match the local value ({git_repo.head.commit})"
    #                 )

    #                 repo.commit.value = str(git_repo.head.commit)
    #                 repo.save()

    #             # Remove stale branches from the remote repo
    #             for stale_branch in git_repo.remotes.origin.stale_refs:
    #                 if not isinstance(stale_branch, git.refs.remote.RemoteReference):
    #                     continue

    #                 log.debug(f"{repo.name.value}: Cleaning branch {stale_branch.name} no longer present on remote.")
    #                 type(stale_branch).delete(git_repo, stale_branch)

    #             # Got over all branches in the remote and check if they already exist locally
    #             # If not, create a new branch locally in the database and in Git and track the remote branch
    #             for remote_branch in git_repo.remotes.origin.refs:
    #                 if not isinstance(remote_branch, git.refs.remote.RemoteReference):
    #                     continue
    #                 short_name = remote_branch.name.replace("origin/", "")

    #                 if short_name == "HEAD" or short_name in db_branche_names:
    #                     continue

    #                 log.info(f"{repo.name.value}: Found new branch {short_name}")

    #                 # Create the new branch in the database
    #                 # Don't do more for now because we'll process all other repos in the next section
    #                 new_branch = Branch(name=short_name, description=f"Created from Repository: {repo.name.value}")
    #                 new_branch.save()

    #                 # Create the new Branch locally in Git too
    #                 local_branch_names = [br.name for br in git_repo.refs if not br.is_remote()]
    #                 if short_name not in local_branch_names:
    #                     git_repo.git.branch(short_name)

    def find_files(self, extension: str, recursive: bool = True):
        return glob.glob(f"{self.get_active_directory()}/**/*.{extension}", recursive=recursive)

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
