from __future__ import annotations

import git
import glob
import os
import asyncio
from typing import List, Dict, Optional

from uuid import UUID
from pydantic import BaseModel, validator
from git import Repo
import httpx

import infrahub.config as config


# INFRAHUB_URL = os.environ.get("INFRAHUB_GRAPHQL_URL", "http://localhost:8000")
# INFRAHUB_GRAPHQL_URL = f"{INFRAHUB_URL}/graphql"

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


def initialize_repositories_directory() -> bool:
    """Check if the main repositories_directory already exist, if not create it.

    Return
        True if the directory has been created,
        False if the directory was already present.
    """
    current_dir = os.getcwd()
    repos_dir = os.path.join(current_dir, config.SETTINGS.main.repositories_directory)
    isdir = os.path.isdir(repos_dir)
    if not isdir:
        os.makedirs(repos_dir)
        return True

    return False


class Worktree(BaseModel):
    directory: str
    commit: str
    branch: Optional[str]

    @classmethod
    def init(cls, text):
        lines = text.split("\n")

        item = cls(
            directory=lines[0].replace("worktree ", ""),
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
    has_worktree: bool


class InfrahubRepository(BaseModel):
    """
    Local version of a Git repository organized to work with Infrahub.
    The idea is that all commit that are being tracked in the graph will be checkout out
    individually as worktree under the <repo_name>/commit subdirectory

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
        return os.path.join(self.directory_root, "branches")

    @property
    def directory_commits(self) -> str:
        """Return the path to the directory where the worktrees of all the commits are stored."""
        return os.path.join(self.directory_root, "commits")

    @property
    def directory_temp(self) -> str:
        """Return the path to the directory where the temp worktrees of all the commits pending validation are stored."""
        return os.path.join(self.directory_root, "temp")

    def get_git_repo_main(self) -> Repo:
        return Repo(self.directory_default)

    def ensure_exists_locally(self) -> bool:
        """Ensure the required directory already exist in the filesystem or create them if needed.

        Returns
            True if the directory has been created,
            False if the directory was already present.
        """

        initialize_repositories_directory()

        # Check if the root, commits and branches directories are already present, create them if needed
        if not os.path.isdir(self.directory_root):
            os.makedirs(self.directory_root)

        if not os.path.isdir(self.directory_branches):
            os.makedirs(self.directory_branches)

        if not os.path.isdir(self.directory_commits):
            os.makedirs(self.directory_commits)

        if not os.path.isdir(self.directory_temp):
            os.makedirs(self.directory_temp)

        if os.path.isdir(self.directory_default):
            return False

        # if the repo doesn't exist, create it
        # Ensure the default branch in infrahub matches the default_branch configured for this repo
        if not self.location or not self.default_branch_name:
            raise Exception(
                f"Unable to initialize the repository {self.name} without the location and the default_branch"
            )

        git_repo = Repo.clone_from(self.location, self.directory_default)
        git_repo.git.checkout(self.default_branch_name)

        # Create a worktree for the commit in main
        commit = str(git_repo.head.commit)
        git_repo.git.worktree("add", os.path.join(self.directory_commits, commit), commit)

        return True

    @classmethod
    async def new(cls, **kwargs):

        self = cls(**kwargs)
        self.ensure_exists_locally()
        # await self.update_commit_value()

        return self

    def get_worktrees(self) -> List[Worktree]:
        """Return the list of worktrees configured for this repository."""
        git_repo = self.get_git_repo_main()
        responses = git_repo.git.worktree("list", "--porcelain").split("\n\n")

        return [Worktree.init(response) for response in responses]

    async def get_branches_from_graph(self) -> Dict[str, BranchInGraph]:
        """Return a dict with all the branches present in the graph.
        Query the list of branches first then query the repository for each branch.
        """

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{config.SETTINGS.main.internal_address}/graphql", json={"query": QUERY_BRANCHES})

            tasks = []
            branches = {}
            raw_branches = {branch["name"]: branch for branch in resp.json()["data"]["branch"]}
            branch_names = sorted(raw_branches.keys())

            for branch_name in branch_names:
                tasks.append(
                    client.post(
                        f"{config.SETTINGS.main.internal_address}/graphql/{branch_name}",
                        json={"query": QUERY_REPOSITORY, "variables": {"repository_name": self.name}},
                    )
                )

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # TODO add error handling
            #  No response from the API, authentification, empty response etc ..

            for branch_name, response in zip(branch_names, responses):
                data = response.json()
                repository = data["data"]["repository"]

                # if the response is empty it probably mean that this repository is not present in this branch
                if not repository:
                    continue

                branches[branch_name] = BranchInGraph(
                    id=raw_branches[branch_name]["id"],
                    name=raw_branches[branch_name]["name"],
                    is_data_only=raw_branches[branch_name]["is_data_only"],
                    commit=repository[0]["commit"]["value"],
                )

        # TODO Extend the GraphQL API to return all the commits across all branches for a given repo at once

        return branches

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

    def get_branches_from_local(self) -> Dict[str, BranchInLocal]:
        """Return a dict with all the branches present locally."""

        git_repo = self.get_git_repo_main()
        worktrees = self.get_worktrees()

        branches = {}

        for local_branch in git_repo.refs:
            if local_branch.is_remote():
                continue

            has_worktree = False

            for worktree in worktrees:
                if worktree.branch and worktree.branch == local_branch.name:
                    has_worktree = True
                    break

            branches[local_branch.name] = BranchInLocal(
                name=local_branch.name, commit=str(local_branch.commit), has_worktree=has_worktree
            )

        return branches

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        """Compare the value of the commit in the db with the current commit on the filesystem.
        update it if they don't match.

        Returns:
            True if the commit has been updated
            False if they already had the same value
        """

        variables = {"repository_id": self.id, "commt": commit}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{config.SETTINGS.main.internal_address}/graphql/{branch_name}",
                json={"query": MUTATION_COMMIT_UPDATE, "variables": variables},
            )
            resp.raise_for_status()

        return True

    def create_branch_in_git(self, branch_name: str, push_origin: bool = True) -> True:
        """Create new branch in the repository, assuming the branch has been created in the graph already."""

        repo = self.get_git_repo_main()

        repo.git.branch(branch_name)
        repo.git.worktree("add", os.path.join(self.directory_branches, branch_name), branch_name)

        # TODO add a check to ensure the repo has a remote configured
        if push_origin:
            repo.remotes.origin.push(branch_name)

        return True

    def create_branch_in_graph(self, branch_name: str):
        """Create a new branch in the graph,."""

        repo = self.get_git_repo_main()
        # TODO
        pass

    def calculate_diff_between_commits(self, first_commit: str, second_commit: str) -> List[str]:
        # TODO Add to RPC Framework

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

    def merge(self, source_branch: str, dest_branch: str = "main", push_remote: bool = True) -> bool:
        """Merge the current branch into main."""

        if source_branch == config.SETTINGS.main.default_branch:
            raise Exception("Unable to merge the default branch into itself.")

        git_repo = self.get_git_repo_main()
        # FIXME need to redesign this part to account for the new architecture

        # git_repo.git.merge(self.commit)

        # # Update the commit value in main
        # repo_main = self.get(id=self.id)
        # repo_main.commit.value = str(git_repo.head.commit)
        # repo_main.save()

        # if push_remote:
        #     for remote in git_repo.remotes:
        #         print(remote.push())

        return True

    def fetch_latest_from_remote(self):

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
