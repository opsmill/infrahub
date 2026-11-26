"""The rewrite record is branch-local: no diff, no merge, and a new branch reads the record of its origin."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.models import RefClassification, RefDivergence
from infrahub.git.divergence.recorder import HistoryRewriteRecorder
from infrahub.git.divergence.store import SdkRepositoryRecordStore
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

IMPORTED = "a" * 40
REWRITTEN = "b" * 40
REWRITTEN_AGAIN = "c" * 40
READ_ONLY_COMMIT = "d" * 40
REWRITTEN_AT = datetime(2026, 10, 6, 9, 30, tzinfo=UTC)
STORED_REWRITTEN_AT = "2026-10-06T09:30:00+00:00"
RECORD_ATTRIBUTES = ("last_rewrite_previous_commit", "last_rewrite_commit", "last_rewrite_at", "rewrite_count")
NO_RECORD = {
    "last_rewrite_previous_commit": None,
    "last_rewrite_commit": None,
    "last_rewrite_at": None,
    "rewrite_count": None,
}

DIFF_UPDATE = """
mutation DiffUpdate($branch_name: String!) {
    DiffUpdate(data: { branch: $branch_name }, wait_until_completion: true) {
        ok
    }
}
"""

REWRITE_RECORD = """
query RewriteRecord($repository_id: ID!) {
    CoreGenericRepository(ids: [$repository_id]) {
        edges {
            node {
                last_rewrite_previous_commit { value }
                last_rewrite_commit { value }
                last_rewrite_at { value }
                rewrite_count { value }
            }
        }
    }
}
"""


def rewrite(branch_name: str, imported_commit: str, remote_head: str) -> RefDivergence:
    return RefDivergence(
        branch_name=branch_name,
        infrahub_branch_name=branch_name,
        imported_commit=imported_commit,
        remote_head=remote_head,
        classification=RefClassification.REWRITE,
    )


async def read_record(client: InfrahubClient, repository_id: str, branch_name: str) -> dict[str, Any]:
    response = await client.execute_graphql(
        query=REWRITE_RECORD, variables={"repository_id": repository_id}, branch_name=branch_name
    )
    node = response["CoreGenericRepository"]["edges"][0]["node"]
    return {name: node[name]["value"] for name in RECORD_ATTRIBUTES}


async def create_repository(db: InfrahubDatabase, name: str) -> Node:
    node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await node.new(
        db=db,
        name=name,
        location=f"https://git.example.com/{name}.git",
        default_branch="main",
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )
    await node.save(db=db)
    return node


async def create_read_only_repository(db: InfrahubDatabase, name: str) -> Node:
    node = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
    await node.new(
        db=db,
        name=name,
        location=f"https://git.example.com/{name}.git",
        ref="main",
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )
    await node.save(db=db)
    return node


class TestRewriteRecordBranchSafety(TestInfrahubApp):
    @pytest.fixture
    def recorder(self, client: InfrahubClient) -> HistoryRewriteRecorder:
        return HistoryRewriteRecorder(store=SdkRepositoryRecordStore(client=client), clock=lambda: REWRITTEN_AT)

    async def test_a_branch_created_after_a_record_reads_it_and_counts_on_from_it(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initialize_registry: None,
        client: InfrahubClient,
        recorder: HistoryRewriteRecorder,
    ) -> None:
        """A branch-local read falls back to the origin branch, so the record of the trunk shows on a newer branch."""
        repository = await create_repository(db=db, name="inherited-record")
        await recorder.record(
            repository_id=repository.id,
            divergence=rewrite(branch_name=default_branch.name, imported_commit=IMPORTED, remote_head=REWRITTEN),
        )
        trunk_record = {
            "last_rewrite_previous_commit": IMPORTED,
            "last_rewrite_commit": REWRITTEN,
            "last_rewrite_at": STORED_REWRITTEN_AT,
            "rewrite_count": 1,
        }
        assert await read_record(client=client, repository_id=repository.id, branch_name=default_branch.name) == (
            trunk_record
        )

        branch = await create_branch(db=db, branch_name="created-after-record")

        assert await read_record(client=client, repository_id=repository.id, branch_name=branch.name) == trunk_record

        await recorder.record(
            repository_id=repository.id,
            divergence=rewrite(branch_name=branch.name, imported_commit=REWRITTEN, remote_head=REWRITTEN_AGAIN),
        )

        assert await read_record(client=client, repository_id=repository.id, branch_name=branch.name) == {
            "last_rewrite_previous_commit": REWRITTEN,
            "last_rewrite_commit": REWRITTEN_AGAIN,
            "last_rewrite_at": STORED_REWRITTEN_AT,
            "rewrite_count": 2,
        }
        assert await read_record(client=client, repository_id=repository.id, branch_name=default_branch.name) == (
            trunk_record
        )

    async def test_a_record_is_in_no_branch_diff_and_a_merge_does_not_carry_it(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initialize_registry: None,
        client: InfrahubClient,
        recorder: HistoryRewriteRecorder,
        prefect_test_fixture: None,
    ) -> None:
        repository = await create_repository(db=db, name="record-off-the-diff")
        read_only_repository = await create_read_only_repository(db=db, name="read-only-record-off-the-diff")
        branch = await create_branch(db=db, branch_name="carries-a-record")
        for repository_id in (repository.id, read_only_repository.id):
            await recorder.record(
                repository_id=repository_id,
                divergence=rewrite(branch_name=branch.name, imported_commit=IMPORTED, remote_head=REWRITTEN),
            )
        # A branch-aware change on the same node shows that the diff reads the node at all.
        read_only_on_branch = await NodeManager.get_one(db=db, branch=branch, id=read_only_repository.id)
        read_only_on_branch.get_attribute("commit").value = READ_ONLY_COMMIT
        await read_only_on_branch.save(db=db)

        result = await client.execute_graphql(query=DIFF_UPDATE, variables={"branch_name": branch.name})
        assert result["DiffUpdate"]["ok"]

        diff_repository = await get_component_registry().get_component(DiffRepository, db=db, branch=branch)
        diff = await diff_repository.get_one(
            tracking_id=BranchTrackingId(name=branch.name), diff_branch_name=branch.name
        )
        changed_attributes = {
            node.uuid: {attribute.name for attribute in node.attributes}
            for node in diff.nodes
            if node.uuid in {repository.id, read_only_repository.id}
        }
        assert changed_attributes == {read_only_repository.id: {"commit"}}

        diff_merger = await get_component_registry().get_component(DiffMerger, db=db, branch=branch)
        await diff_merger.merge_graph(at=Timestamp())

        merged_read_only = await NodeManager.get_one(db=db, branch=default_branch, id=read_only_repository.id)
        assert merged_read_only.get_attribute("commit").value == READ_ONLY_COMMIT
        for repository_id in (repository.id, read_only_repository.id):
            assert (
                await read_record(client=client, repository_id=repository_id, branch_name=default_branch.name)
                == NO_RECORD
            )

    async def test_a_record_the_api_refuses_fails_with_the_error_of_the_api_as_its_cause(
        self, default_branch: Branch, initialize_registry: None, recorder: HistoryRewriteRecorder
    ) -> None:
        """The cause is what lets a failed record be logged with the reason the API gave."""
        repository_id = str(UUIDT())

        with pytest.raises(
            RepositoryError,
            match=rf"^Unable to access the rewrite record of repository {repository_id} on branch {default_branch.name}: ",
        ) as failure:
            await recorder.record(
                repository_id=repository_id,
                divergence=rewrite(branch_name=default_branch.name, imported_commit=IMPORTED, remote_head=REWRITTEN),
            )

        assert isinstance(failure.value.__cause__, NodeNotFoundError)
