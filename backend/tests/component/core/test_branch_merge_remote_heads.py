"""When the merge of a branch reads the remote heads of its Git repositories."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.tasks import check_remote_heads_imported
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.git.merge_readiness import RemoteHeadsMergeCheck
from tests.adapters.remote_heads import InMemoryRemoteHeadReader

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

TRUNK_COMMIT = "a" * 40


async def test_a_branch_that_is_not_open_reads_no_remote(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The merge flow skips such a branch once it holds the merge lock, so the remote read would be wasted."""
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
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)
    reader = InMemoryRemoteHeadReader(heads={"network-repo": {"feature": "c" * 40, "main": TRUNK_COMMIT}})

    await check_remote_heads_imported(
        db=db, branch_name="feature", check=RemoteHeadsMergeCheck(reader=reader, log=logging.getLogger(__name__))
    )

    assert reader.reads == []
