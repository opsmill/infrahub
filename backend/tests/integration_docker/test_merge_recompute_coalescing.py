"""End-to-end correctness of the coalesced merge and rebase recompute."""

from __future__ import annotations

from asyncio import sleep, timeout
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, PROFILE_PEER_KIND, build_profile_schema_dict

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient


async def _wait_until(predicate: Callable[[], Awaitable[bool]], *, seconds: int = 120) -> None:
    async with timeout(seconds):
        while not await predicate():  # noqa: ASYNC110
            await sleep(2)


async def _became_true(predicate: Callable[[], Awaitable[bool]], *, seconds: int = 60) -> bool:
    """Return True if the predicate becomes true within the timeout, False if it never does."""
    try:
        await _wait_until(predicate, seconds=seconds)
    except TimeoutError:
        return False
    return True


class TestMergeCoalescedRecompute(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def profile_schema(self) -> dict:
        return build_profile_schema_dict()

    async def test_merge_recomputes_destination_only_reader(self, client: InfrahubClient, profile_schema: dict) -> None:
        loaded = await client.schema.load(schemas=[profile_schema], wait_until_converged=True)
        assert loaded.schema_updated

        peer = await client.create(kind=PROFILE_PEER_KIND, data={"name": "alpha"})
        await peer.save()
        node1 = await client.create(kind=PROFILE_NODE_KIND, data={"name": "node1", "peer": peer})
        await node1.save()

        async def _node1_initial() -> bool:
            node = await client.get(kind=PROFILE_NODE_KIND, id=node1.id)
            return node.summary.value == "node1 on alpha"

        await _wait_until(_node1_initial)

        branch = await client.branch.create(branch_name="coalesce-merge-correctness")

        # Cross-node change on the branch only: rename the peer the nodes read.
        peer_on_branch = await client.get(kind=PROFILE_PEER_KIND, id=peer.id, branch=branch.name)
        peer_on_branch.name.value = "omega"
        await peer_on_branch.save()

        # A reader created on the destination after the fork. The branch never sees it, so the
        # branch's own recompute cannot refresh it; only the coalesced post-merge recompute can.
        node2 = await client.create(kind=PROFILE_NODE_KIND, data={"name": "node2", "peer": peer})
        await node2.save()

        async def _node2_initial() -> bool:
            node = await client.get(kind=PROFILE_NODE_KIND, id=node2.id)
            return node.summary.value == "node2 on alpha"

        await _wait_until(_node2_initial)

        await client.branch.merge(branch_name=branch.name)

        async def _both_recomputed() -> bool:
            refreshed_node1 = await client.get(kind=PROFILE_NODE_KIND, id=node1.id)
            refreshed_node2 = await client.get(kind=PROFILE_NODE_KIND, id=node2.id)
            return (
                refreshed_node1.summary.value == "node1 on omega" and refreshed_node2.summary.value == "node2 on omega"
            )

        await _wait_until(_both_recomputed)

        final_node1 = await client.get(kind=PROFILE_NODE_KIND, id=node1.id)
        final_node2 = await client.get(kind=PROFILE_NODE_KIND, id=node2.id)

        # The computed attribute and display label read the peer across the relationship: both refresh.
        assert final_node1.summary.value == "node1 on omega"
        assert final_node2.summary.value == "node2 on omega"
        assert final_node1.display_label == "node1 via omega"
        assert final_node2.display_label == "node2 via omega"
        # The human-friendly id reads only the local name, so the peer change must leave it unchanged.
        assert final_node1.hfid == ["node1"]
        assert final_node2.hfid == ["node2"]

    async def test_rebase_recomputes_user_branch_only_reader(
        self, client: InfrahubClient, profile_schema: dict
    ) -> None:
        await client.schema.load(schemas=[profile_schema], wait_until_converged=True)

        peer = await client.create(kind=PROFILE_PEER_KIND, data={"name": "ralpha"})
        await peer.save()

        branch = await client.branch.create(branch_name="coalesce-rebase-correctness")

        # Change the peer on the default branch; the rebase replays this onto the user branch.
        peer.name.value = "romega"
        await peer.save()

        # A reader created only on the user branch. The default branch never sees it, so the
        # default's recompute cannot refresh it; only the coalesced rebase recompute can.
        node = await client.create(kind=PROFILE_NODE_KIND, data={"name": "rnode", "peer": peer}, branch=branch.name)
        await node.save()

        async def _node_initial() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id, branch=branch.name)
            return refreshed.summary.value == "rnode on ralpha"

        await _wait_until(_node_initial)

        await client.branch.rebase(branch_name=branch.name)

        async def _node_recomputed() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id, branch=branch.name)
            return refreshed.summary.value == "rnode on romega"

        await _wait_until(_node_recomputed)

        final = await client.get(kind=PROFILE_NODE_KIND, id=node.id, branch=branch.name)
        # The rebase recomputes on the user branch: the user-branch-only reader refreshes.
        assert final.summary.value == "rnode on romega"
        assert final.display_label == "rnode via romega"
        assert final.hfid == ["rnode"]

    async def test_merge_recomputes_created_reader(self, client: InfrahubClient, profile_schema: dict) -> None:
        """A node created on the branch must carry every derived family, correct, after merge."""
        await client.schema.load(schemas=[profile_schema], wait_until_converged=True)

        peer = await client.create(kind=PROFILE_PEER_KIND, data={"name": "gamma"})
        await peer.save()

        branch = await client.branch.create(branch_name="coalesce-merge-create")
        # Creation fans out to every derived family on the new node, including the human-friendly id.
        node = await client.create(kind=PROFILE_NODE_KIND, data={"name": "cnode", "peer": peer}, branch=branch.name)
        await node.save()

        async def _created_on_branch() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id, branch=branch.name)
            return (
                refreshed.summary.value == "cnode on gamma"
                and refreshed.display_label == "cnode via gamma"
                and refreshed.hfid == ["cnode"]
            )

        await _wait_until(_created_on_branch)

        await client.branch.merge(branch_name=branch.name)

        async def _on_destination() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id)
            return (
                refreshed.summary.value == "cnode on gamma"
                and refreshed.display_label == "cnode via gamma"
                and refreshed.hfid == ["cnode"]
            )

        await _wait_until(_on_destination)

        final = await client.get(kind=PROFILE_NODE_KIND, id=node.id)
        assert final.summary.value == "cnode on gamma"
        assert final.display_label == "cnode via gamma"
        assert final.hfid == ["cnode"]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "the recompute locates readers with a reverse relationship query that returns nothing "
            "once the deleted peer's edges are closed, so the reader keeps a value that still names "
            "the deleted peer"
        ),
    )
    async def test_deleting_read_peer_refreshes_reader_after_merge(self, client: InfrahubClient) -> None:
        """After a read peer is deleted and merged, the reader's derived values should stop naming it."""
        schema = build_profile_schema_dict()
        node_schema = schema["nodes"][1]
        node_schema["relationships"][0]["optional"] = True
        # Self-only display label so the scenario exercises the stale computed value, not the separate
        # missing-peer diff crash that is fixed on its own path.
        node_schema["display_label"] = "{{ name__value }}"
        await client.schema.load(schemas=[schema], wait_until_converged=True)

        peer = await client.create(kind=PROFILE_PEER_KIND, data={"name": "beta"})
        await peer.save()
        node = await client.create(kind=PROFILE_NODE_KIND, data={"name": "node2", "peer": peer})
        await node.save()

        async def _reader_initial() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id)
            return refreshed.summary.value == "node2 on beta"

        await _wait_until(_reader_initial)

        branch = await client.branch.create(branch_name="delete-peer-refresh")
        peer_on_branch = await client.get(kind=PROFILE_PEER_KIND, id=peer.id, branch=branch.name)
        await peer_on_branch.delete()

        await client.branch.merge(branch_name=branch.name)

        async def _reader_no_longer_names_peer() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id)
            return refreshed.summary.value != "node2 on beta"

        assert await _became_true(_reader_no_longer_names_peer, seconds=60)
