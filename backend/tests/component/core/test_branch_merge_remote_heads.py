"""When the merge of a branch reads the remote heads of its Git repositories."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.tasks import check_remote_heads_imported
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryNotSynchronizedError
from infrahub.git.merge_readiness import RemoteHeadsMergeCheck
from tests.adapters.remote_heads import HeadRead, InMemoryRemoteHeadReader

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

TRUNK_COMMIT = "a" * 40
MOVED_COMMIT = "c" * 40


@pytest.fixture
async def feature_branch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> Branch:
    """A branch synced with Git, and a repository whose remote source branch moved past the graph."""
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(
        db=db,
        name="network-repo",
        location="https://git.example.com/network-repo.git",
        commit=TRUNK_COMMIT,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )
    await repository.save(db=db)
    branch = await create_branch(branch_name="feature", db=db)
    branch.sync_with_git = True
    await branch.save(db=db)
    return branch


def remote_heads() -> InMemoryRemoteHeadReader:
    return InMemoryRemoteHeadReader(heads={"network-repo": {"feature": MOVED_COMMIT, "main": TRUNK_COMMIT}})


async def test_an_open_branch_is_checked_against_the_remote_heads(db: InfrahubDatabase, feature_branch: Branch) -> None:
    reader = remote_heads()
    message = (
        "Unable to merge branch feature, because Infrahub has not imported the latest commit of branch feature of "
        f"repository network-repo ({MOVED_COMMIT} on the remote, {TRUNK_COMMIT} in Infrahub). Merge again after the "
        "next synchronization of the repository imports it."
    )

    with pytest.raises(RepositoryNotSynchronizedError, match=rf"^{re.escape(message)}$"):
        await check_remote_heads_imported(
            db=db, branch_name="feature", check=RemoteHeadsMergeCheck(reader=reader, log=logging.getLogger(__name__))
        )

    assert reader.reads == [
        HeadRead(
            repository_name="network-repo",
            location="https://git.example.com/network-repo.git",
            branch_names=("feature", "main"),
        )
    ]


async def test_a_branch_that_is_not_open_reads_no_remote(db: InfrahubDatabase, feature_branch: Branch) -> None:
    """The merge flow skips such a branch once it holds the merge lock, so the remote read would be wasted."""
    feature_branch.status = BranchStatus.MERGED
    await feature_branch.save(db=db)
    reader = remote_heads()

    await check_remote_heads_imported(
        db=db, branch_name="feature", check=RemoteHeadsMergeCheck(reader=reader, log=logging.getLogger(__name__))
    )

    assert reader.reads == []
