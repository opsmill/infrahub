from __future__ import annotations

import glob
import json
import os
from typing import List, Optional

from uuid import UUID
from pydantic import BaseModel, validator
from git import Repo

from gql import Client, gql

import infrahub.config as config

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

class GitRepository(BaseModel):

    id: UUID
    name: str
    branch_name: str
    default_branch_name: Optional[str]
    type: Optional[str]
    location: Optional[str]
    commit_value: Optional[str]
    client: Optional[Client]


    class Config:
        arbitrary_types_allowed = True

    # {"name": "name", "kind": "String", "unique": True},
    # {"name": "description", "kind": "String", "optional": True},
    # {"name": "location", "kind": "String"},
    # {"name": "type", "kind": "String", "default_value": "LOCAL"},
    # {"name": "default_branch", "kind": "String", "default_value": "main"},
    # {"name": "commit", "kind": "String", "optional": True},

    @validator("default_branch_name", pre=True, always=True)
    def set_default_branch_name(cls, value):
        return value or config.SETTINGS.main.default_branch

    @property
    def directory_root(self) -> str:

        current_dir = os.getcwd()
        repositories_directory = config.SETTINGS.main.repositories_directory
        if not os.path.isabs(repositories_directory):
            repositories_directory = os.path.join(current_dir, config.SETTINGS.main.repositories_directory)

        return os.path.join(repositories_directory, self.name)

    @property
    def directory_default(self) -> str:
        return os.path.join(self.directory_root, config.SETTINGS.main.default_branch)

    @property
    def directory_branch(self) -> str:
        return os.path.join(self.directory_root, self.branch_name)

    def get_active_directory(self) -> str:
        """Return the path of the current active directory dependending on the branch."""
        if os.path.isdir(self.directory_branch):
            return self.directory_branch

        return self.directory_default

    def get_git_repo_main(self) -> Repo:
        return Repo(self.directory_default)

    def get_git_repo_branch(self) -> Repo:
        # Check if the worktree already exist and create it if needed
        return Repo(self.directory_branch)

    def get_account(self):
        # FIXME Need to revisit this one
        return None

        # return self.account.get()

    def ensure_exists_locally(self) -> bool:
        """Ensure the required directory already exist in the filesystem or create them if needed.

        Returns
            True if the directory has been created,
            False if the directory was already present.
        """

        initialize_repositories_directory()

        # Check if the root directory is already present, create it if needed
        if not os.path.isdir(self.directory_root):
            os.makedirs(self.directory_root)

        if os.path.isdir(self.directory_default):
            return False

        # if the repo doesn't exist, create it
        # Ensure the default branch in infrahub matches the default_branch configured for this repo
        repo = Repo.clone_from(self.location, self.directory_default)
        repo.git.checkout(self.default_branch_name)

        # If we are currently on a new branch
        # Create a new worktree for the branch for this repo
        if self.branch_name != config.SETTINGS.main.default_branch:
            repo.git.branch(self.branch_name)
            repo.git.worktree("add", self.directory_branch, self.branch_name)

        return True

    @classmethod
    async def new(cls, **kwargs):

        self = cls(**kwargs)
        self.ensure_exists_locally()
        await self.update_commit_value()

        return self

    async def update_commit_value(self) -> bool:
        """Compare the value of the commit in the db with the current commit on the filesystem.
        update it if they don't match.

        Returns:
            True if the commit has been updated
            False if they already had the same value
        """

        # query = gql("""
        # repository_update($commit: [String]) {
        #     { data: { commit: $commit } }
        # }
        # """)

        # result = await self.client.execute(query)

        # previous_commit = self.commit.value if self.commit else None

        # git_repo = self.get_git_repo_branch()
        # self.commit.value = str(git_repo.head.commit)

        # if self.commit.value == previous_commit:
        #     return False

        return True

    def add_branch(self, branch_name: str, push_origin: bool = True):

        repo = self.get_git_repo_main()

        repo.git.branch(branch_name)
        repo.git.worktree("add", os.path.join(self.directory_root, branch_name), branch_name)

        # TODO add a check to ensure the repo has a remote configured
        if push_origin:
            repo.remotes.origin.push(branch_name)

    def calculate_diff_with_commit(self, commit: str) -> List[str]:
        # TODO Add to RPC Framework

        git_repo = self.get_git_repo_main()

        commit_to_compare = git_repo.commit(commit)
        commit_in_branch = git_repo.commit(self.commit.value)

        changed_files = []

        for x in commit_in_branch.diff(commit_to_compare):
            if x.a_blob and x.a_blob.path not in changed_files:
                changed_files.append(x.a_blob.path)

            if x.b_blob is not None and x.b_blob.path not in changed_files:
                changed_files.append(x.b_blob.path)

        return changed_files or None

    def merge(self, push_remote: bool = True) -> bool:
        """Merge the current branch into main."""

        if self.name == config.SETTINGS.main.default_branch:
            raise Exception("Unable to merge the default branch into itself.")

        git_repo = self.get_git_repo_main()
        git_repo.git.merge(self.commit)

        # Update the commit value in main
        repo_main = self.get(id=self.id)
        repo_main.commit.value = str(git_repo.head.commit)
        repo_main.save()

        if push_remote:
            for remote in git_repo.remotes:
                print(remote.push())

        return True

    def find_files(self, extension, recursive=True):
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