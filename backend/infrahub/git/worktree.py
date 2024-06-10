from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from infrahub.exceptions import Error
from infrahub.git.constants import BRANCHES_DIRECTORY_NAME, COMMITS_DIRECTORY_NAME
from infrahub.git.directory import get_repositories_directory


class Worktree(BaseModel):
    identifier: str
    directory: str
    commit: str
    branch: Optional[str] = None

    @classmethod
    def init(cls, text: str) -> Worktree:
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

        elif len(relative_paths) == 4 and relative_paths[2] == COMMITS_DIRECTORY_NAME:
            # this is the either a commit or a branch worktree
            identifier = relative_paths[3]
        elif len(relative_paths) == 4 and relative_paths[2] == BRANCHES_DIRECTORY_NAME and lines[2] != "detached":
            identifier = lines[2].replace("branch refs/heads/", "")
        else:
            raise Error("Unexpected path for a worktree.")

        item = cls(
            identifier=identifier,
            directory=full_directory,
            commit=lines[1].replace("HEAD ", ""),
        )

        if lines[2] != "detached":
            item.branch = lines[2].replace("branch refs/heads/", "")

        return item
