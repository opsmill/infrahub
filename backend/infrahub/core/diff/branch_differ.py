from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING

from typing_extensions import Self

from infrahub.core.constants import (
    DiffAction,
    InfrahubKind,
)
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import DiffFromRequiredOnDefaultBranchError, DiffRangeValidationError

from ...git.models import GitDiffNamesOnly
from ...workflows.catalogue import GIT_REPOSITORIES_DIFF_NAMES_ONLY
from .model.diff import (
    FileDiffElement,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

    from ..branch import Branch
    from ..node import Node


class BranchDiffer:
    diff_from: Timestamp
    diff_to: Timestamp

    def __init__(
        self,
        branch: Branch,
        origin_branch: Branch | None = None,
        branch_only: bool = False,
        diff_from: str | Timestamp | None = None,
        diff_to: str | Timestamp | None = None,
        db: InfrahubDatabase | None = None,
        service: InfrahubServices | None = None,
    ):
        """_summary_

        Args:
            branch (Branch): Main branch this diff is caculated from
            origin_branch (Branch): Storing the origin branch the main branch started from for convenience.
            branch_only (bool, optional): When True, only consider the changes in the branch, ignore the changes in main. Defaults to False.
            diff_from (Union[str, Timestamp], optional): Time from when the diff is calculated. Defaults to None.
            diff_to (Union[str, Timestamp], optional): Time to when the diff is calculated. Defaults to None.

        Raises:
            ValueError: if diff_from and diff_to are not correct
        """

        self.branch = branch
        self.branch_only = branch_only
        self.origin_branch = origin_branch

        self._db = db
        self._service = service

        if not diff_from and self.branch.is_default:
            raise DiffFromRequiredOnDefaultBranchError(
                f"diff_from is mandatory when diffing on the default branch `{self.branch.name}`."
            )

        # If diff from hasn't been provided, we'll use the creation of the branch as the starting point
        if diff_from:
            self.diff_from = Timestamp(diff_from)
        else:
            self.diff_from = Timestamp(self.branch.created_at)

        # If diff_to hasn't been provided, we will use the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise DiffRangeValidationError("diff_to must be later than diff_from")

        # Results organized by Branch
        self._results: dict[str, dict] = defaultdict(lambda: {"nodes": {}, "rels": defaultdict(dict), "files": {}})
        self._calculated_diff_files_at: Timestamp | None = None

    @property
    def service(self) -> InfrahubServices:
        if not self._service:
            raise ValueError("BranchDiffer object was not initialized with InfrahubServices")
        return self._service

    @property
    def db(self) -> InfrahubDatabase:
        if not self._db:
            raise ValueError("BranchDiffer object was not initialized with InfrahubDatabase")
        return self._db

    @classmethod
    async def init(
        cls,
        db: InfrahubDatabase,
        branch: Branch,
        branch_only: bool = False,
        diff_from: str | Timestamp | None = None,
        diff_to: str | Timestamp | None = None,
        service: InfrahubServices | None = None,
    ) -> Self:
        origin_branch = branch.get_origin_branch()

        return cls(
            branch=branch,
            origin_branch=origin_branch,
            branch_only=branch_only,
            diff_from=diff_from,
            diff_to=diff_to,
            db=db,
            service=service,
        )

    async def get_files(self) -> dict[str, list[FileDiffElement]]:
        if not self._calculated_diff_files_at:
            await self._calculated_diff_files()

        return {
            branch_name: data["files"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculated_diff_files(self) -> None:
        self._results[self.branch.name]["files"] = await self.get_files_repositories_for_branch(branch=self.branch)

        if self.origin_branch:
            self._results[self.origin_branch.name]["files"] = await self.get_files_repositories_for_branch(
                branch=self.origin_branch
            )

        self._calculated_diff_files_at = Timestamp()

    async def get_files_repository(
        self,
        branch_name: str,
        repository: Node,
        commit_from: str,
        commit_to: str,
    ) -> list[FileDiffElement]:
        """Return all the files that have added, changed or removed for a given repository between 2 commits."""

        files = []

        model = GitDiffNamesOnly(
            repository_id=repository.id,
            repository_name=repository.name.value,  # type: ignore[attr-defined]
            repository_kind=repository.get_kind(),
            first_commit=commit_from,
            second_commit=commit_to,
        )

        diff = await self.service.workflow.execute_workflow(
            workflow=GIT_REPOSITORIES_DIFF_NAMES_ONLY, parameters={"model": model}
        )

        actions = {
            "files_changed": DiffAction.UPDATED,
            "files_added": DiffAction.ADDED,
            "files_removed": DiffAction.REMOVED,
        }

        for action_name, diff_action in actions.items():
            for filename in getattr(diff, action_name, []):
                files.append(
                    FileDiffElement(
                        branch=branch_name,
                        location=filename,
                        repository=repository,
                        action=diff_action,
                        commit_to=commit_to,
                        commit_from=commit_from,
                    )
                )

        return files

    async def get_files_repositories_for_branch(self, branch: Branch) -> list[FileDiffElement]:
        tasks = []
        files = []

        repos_to = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema=InfrahubKind.GENERICREPOSITORY, db=self.db, branch=branch, at=self.diff_to
            )
        }
        repos_from = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema=InfrahubKind.GENERICREPOSITORY, db=self.db, branch=branch, at=self.diff_from
            )
        }

        # For now we are ignoring the repos that are either not present at to time or at from time.
        # These repos will be identified in the graph already
        repo_ids_common = set(repos_to.keys()) & set(repos_from.keys())

        for repo_id in repo_ids_common:
            if repos_to[repo_id].commit.value == repos_from[repo_id].commit.value:  # type: ignore[attr-defined]
                continue

            tasks.append(
                self.get_files_repository(
                    branch_name=branch.name,
                    repository=repos_to[repo_id],
                    commit_from=repos_from[repo_id].commit.value,  # type: ignore[attr-defined]
                    commit_to=repos_to[repo_id].commit.value,  # type: ignore[attr-defined]
                )
            )

        responses = await asyncio.gather(*tasks)

        for response in responses:
            if isinstance(response, list):
                files.extend(response)

        return files
