from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Never
from unittest.mock import patch

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.graph_merger import GraphMerger
from infrahub.core.merge.rollback_handler import MergeRollbackHandler, PreMergeState
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.database.validation import verify_graph
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient

    from infrahub.core.diff.merger.exclusion_plan import MergeExclusionPlan
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.message_bus import BusSimulator


async def _count_branch_edges_at(db: InfrahubDatabase, branch_name: str, at: str) -> int:
    result = await db.execute_query(
        query="MATCH ()-[r {from: $at, branch: $branch}]->() RETURN count(r) AS c",
        params={"at": at, "branch": branch_name},
    )
    return result[0].get("c")


async def _get_node_metadata(db: InfrahubDatabase, node_uuid: str) -> dict[str, str | None]:
    result = await db.execute_query(
        query=(
            "MATCH (n:Node {uuid: $uuid}) "
            "RETURN n.updated_at AS updated_at, n.previous_updated_at AS previous_updated_at"
        ),
        params={"uuid": node_uuid},
    )
    return {
        "updated_at": result[0].get("updated_at"),
        "previous_updated_at": result[0].get("previous_updated_at"),
    }


BRANCH_MERGE = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""


class BrokenGraphMerger:
    def __init__(self, *args, **kwargs) -> None:
        self.real_merger = GraphMerger(*args, **kwargs)
        self.real_merge_graph = self.real_merger.diff_merger.merge_graph
        self.real_merger.diff_merger.merge_graph = self.merge_graph  # type: ignore

    async def merge(self, at: Timestamp, user_id: str = SYSTEM_USER_ID) -> None:
        await self.real_merger.merge(at=at)

    async def merge_graph(self, at: Timestamp) -> Never:
        await self.real_merge_graph(at=at)
        raise ValueError("This is broken on purpose")


class MidMergeFailureGraphMerger:
    """Fails partway through the bulk merge phase, after the earlier bulk queries have committed."""

    def __init__(self, *args, **kwargs) -> None:
        self.real_merger = GraphMerger(*args, **kwargs)
        self.real_merger.diff_merger._bulk_merge_relationship_property_edges = self._fail_bulk_merge  # type: ignore

    async def merge(self, at: Timestamp, user_id: str = SYSTEM_USER_ID) -> None:
        await self.real_merger.merge(at=at)

    async def _fail_bulk_merge(self, at: Timestamp, plan: MergeExclusionPlan) -> Never:
        raise ValueError("This is broken on purpose")


class EdgeCountingRollbackHandler(MergeRollbackHandler):
    """Counts the merge-stamped edges on the destination branch at the moment the rollback fires.

    A count above zero proves the merge failed partway through the graph write phase with partial
    data committed; zero means the merge failed before writing anything.
    """

    edge_count_before_rollback: ClassVar[int | None] = None

    async def rollback(
        self,
        *,
        merge_started_at: Timestamp,
        pre_merge_state: PreMergeState,
        user_id: str,
    ) -> bool:
        type(self).edge_count_before_rollback = await _count_branch_edges_at(
            db=self.db, branch_name=self.destination_branch.name, at=merge_started_at.to_string()
        )
        return await super().rollback(
            merge_started_at=merge_started_at,
            pre_merge_state=pre_merge_state,
            user_id=user_id,
        )


class TestBranchMergeRollback(TestInfrahubApp):
    @pytest.fixture(autouse=True)
    async def clear_merge_protection(self, service: InfrahubServices) -> AsyncGenerator[None, None]:
        """Clear the merge-protection key around this test.

        This test deliberately fails a merge, and the merge flow holds the shared merge:protected key
        on an incomplete rollback so recovery can take over. The integration suite runs against a real
        shared cache with no key expiry, so a leaked key would block writes in every later test.
        Clearing it on setup and teardown keeps this test from inheriting or leaking that state.
        """
        blocker = MergeWriteBlocker(cache=service.cache)
        await blocker.delete()
        yield
        await blocker.delete()

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, Node]:
        await load_schema(db, schema=CAR_SCHEMA)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        kara = await Node.init(schema=TestKind.PERSON, db=db)
        await kara.new(db=db, name="Kara Thrace", height=165, description="Starbuck")
        await kara.save(db=db)
        murphy = await Node.init(schema=TestKind.PERSON, db=db)
        await murphy.new(db=db, name="Alex Murphy", height=185, description="Robocop")
        await murphy.save(db=db)
        omnicorp = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await omnicorp.new(db=db, name="Omnicorp", customers=[murphy])
        await omnicorp.save(db=db)
        cyberdyne = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await cyberdyne.new(db=db, name="Cyberdyne")
        await cyberdyne.save(db=db)

        t_800 = await Node.init(schema=TestKind.CAR, db=db)
        await t_800.new(
            db=db,
            name="Cyberdyne systems model 101",
            color="Chrome",
            description="killing machine with secret heart of gold",
            owner=john,
            manufacturer=cyberdyne,
        )
        await t_800.save(db=db)
        ed_209 = await Node.init(schema=TestKind.CAR, db=db)
        await ed_209.new(
            db=db,
            name="ED-209",
            color="Chrome",
            description="still working on doing stairs",
            owner=murphy,
            manufacturer=omnicorp,
        )
        await ed_209.save(db=db)

        return {
            "john": john,
            "kara": kara,
            "murphy": murphy,
            "omnicorp": omnicorp,
            "cyberdyne": cyberdyne,
            "t_800": t_800,
            "ed_209": ed_209,
        }

    @pytest.fixture(scope="class")
    async def branch1(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch1")

    @pytest.fixture(scope="class")
    async def branch1_data(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch1: Branch
    ) -> dict[str, Node]:
        kara_branch = await NodeManager.get_one(db=db, branch=branch1, id=initial_dataset["kara"].id)
        await kara_branch.delete(db=db)

        sarah = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1)
        await sarah.new(db=db, name="Sarah", height=161, description="no fate")
        await sarah.save(db=db)

        t_800_branch = await NodeManager.get_one(db=db, branch=branch1, id=initial_dataset["t_800"].id)
        await t_800_branch.owner.update(db=db, data=sarah)
        await t_800_branch.save(db=db)

        ocp_branch = await NodeManager.get_one(db=db, branch=branch1, id=initial_dataset["omnicorp"].id)
        ocp_branch.name.value = "Omni Consumer Products"
        await ocp_branch.save(db=db)

        return {"sarah": sarah}

    async def test_merge_branch_rollback(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, Node],
        branch1: Branch,
        branch1_data: dict[str, Node],
    ) -> None:
        # Capture the branch's pre-merge `branched_from` so we can verify rollback restored it.
        pre_merge_branched_from = branch1.branched_from

        with patch("infrahub.core.merge.builder.GraphMerger", new=BrokenGraphMerger):
            with pytest.raises(GraphQLError) as exc:
                await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch1.name})

            assert exc
            assert f"Failed to merge branch '{branch1.name}'" in exc.value.message

        # check that the changes on the branch have all been rolled back
        kara_main = await NodeManager.get_one(db=db, id=initial_dataset["kara"].id)
        assert kara_main.id

        sarah = await NodeManager.get_one(db=db, id=branch1_data["sarah"].id)
        assert sarah is None

        t_800_main = await NodeManager.get_one(db=db, id=initial_dataset["t_800"].id)
        owner_peer = await t_800_main.owner.get_peer(db=db)
        assert owner_peer.id == initial_dataset["john"].id

        ocp_main = await NodeManager.get_one(db=db, id=initial_dataset["omnicorp"].id)
        assert ocp_main.name.value == "Omnicorp"

        await verify_graph(db=db)

        # Verify the branch is back to OPEN with branched_from restored to its pre-merge value.
        reloaded_branch = await Branch.get_by_name(db=db, name=branch1.name)
        assert reloaded_branch.status.value == "OPEN"
        assert reloaded_branch.branched_from == pre_merge_branched_from

    async def test_merge_branch_rollback_mid_bulk_merge(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, Node],
        branch1: Branch,
        branch1_data: dict[str, Node],
    ) -> None:
        """A failure partway through the bulk merge phase must roll back the partially committed data.

        The earlier bulk merge queries have already committed on the destination branch when a later
        one fails, so the rollback fired by the merge flow must remove that partial data.
        """
        EdgeCountingRollbackHandler.edge_count_before_rollback = None
        with (
            patch("infrahub.core.merge.builder.GraphMerger", new=MidMergeFailureGraphMerger),
            patch("infrahub.core.merge.builder.MergeRollbackHandler", new=EdgeCountingRollbackHandler),
        ):
            with pytest.raises(GraphQLError) as exc:
                await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch1.name})

            assert f"Failed to merge branch '{branch1.name}'" in exc.value.message

        assert EdgeCountingRollbackHandler.edge_count_before_rollback is not None, "The rollback must have fired"
        assert EdgeCountingRollbackHandler.edge_count_before_rollback > 0, (
            "The bulk queries that ran before the failure must have committed edges"
        )

        # the merge timestamp is recorded on the branch when the merge starts and survives the rollback
        reloaded_branch = await Branch.get_by_name(db=db, name=branch1.name)
        assert reloaded_branch.merge_started_at is not None

        edges_after = await _count_branch_edges_at(
            db=db, branch_name=registry.default_branch, at=reloaded_branch.merge_started_at
        )
        assert edges_after == 0, "The rollback must remove every edge committed by the partial merge"

        # check that the changes on the branch have all been rolled back
        kara_main = await NodeManager.get_one(db=db, id=initial_dataset["kara"].id)
        assert kara_main.id

        sarah = await NodeManager.get_one(db=db, id=branch1_data["sarah"].id)
        assert sarah is None

        ocp_main = await NodeManager.get_one(db=db, id=initial_dataset["omnicorp"].id)
        assert ocp_main.get_attribute("name").value == "Omnicorp"

        await verify_graph(db=db)

        assert reloaded_branch.status.value == "OPEN"

    async def test_failed_merge_rollback_preserves_metadata_of_earlier_merge(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, Node],
        branch1: Branch,
        branch1_data: dict[str, Node],
    ) -> None:
        """A failed merge must not rewind updated_at/by metadata written by an earlier successful merge.

        previous_updated_at/by snapshots survive successful merges, so the rollback of a later failed
        merge over the same nodes must only restore metadata stamped with its own merge timestamp.
        """
        # the overlap merge changes an attribute branch1 does not touch, so branch1's later merge
        # fails on the induced error rather than on an unresolved conflict
        overlap_branch = await create_branch(db=db, branch_name="overlap-merged-first")
        ocp_overlap = await NodeManager.get_one(
            db=db, branch=overlap_branch, id=initial_dataset["omnicorp"].id, raise_on_error=True
        )
        ocp_overlap.get_attribute("description").value = "consumer products megacorp"
        await ocp_overlap.save(db=db)
        await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": overlap_branch.name})

        metadata_before = await _get_node_metadata(db=db, node_uuid=initial_dataset["omnicorp"].id)
        assert metadata_before["previous_updated_at"] is not None, (
            "The successful merge must leave a previous_updated_at snapshot in place"
        )

        EdgeCountingRollbackHandler.edge_count_before_rollback = None
        with (
            patch("infrahub.core.merge.builder.GraphMerger", new=MidMergeFailureGraphMerger),
            patch("infrahub.core.merge.builder.MergeRollbackHandler", new=EdgeCountingRollbackHandler),
        ):
            with pytest.raises(GraphQLError) as exc:
                await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch1.name})

            assert f"Failed to merge branch '{branch1.name}'" in exc.value.message

        assert EdgeCountingRollbackHandler.edge_count_before_rollback is not None, "The rollback must have fired"
        assert EdgeCountingRollbackHandler.edge_count_before_rollback > 0, (
            "The merge must reach the graph write phase before failing"
        )

        metadata_after = await _get_node_metadata(db=db, node_uuid=initial_dataset["omnicorp"].id)
        assert metadata_after["updated_at"] == metadata_before["updated_at"], (
            "The failed merge's rollback must not rewind updated_at written by the earlier successful merge"
        )
        assert metadata_after["previous_updated_at"] == metadata_before["previous_updated_at"], (
            "The failed merge's rollback must not consume the earlier merge's previous_updated_at snapshot"
        )
