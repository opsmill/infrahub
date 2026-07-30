"""End-to-end correctness of the coalesced merge and rebase recompute."""

from __future__ import annotations

from asyncio import sleep, timeout
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.branch import BranchStatus
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from tests.helpers.merge_recompute.dataset import (
    DEVICE_KIND,
    INTERFACE_KIND,
    METRO_KIND,
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    RACK_KIND,
    SITE_KIND,
    build_chain_schema_dict,
    build_interface_hfid_schema_dict,
    build_location_cascade_schema_dict,
    build_profile_schema_dict,
    chain_kind,
)
from tests.helpers.schema.color import COLOR
from tests.helpers.schema.tshirt import TSHIRT

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient

COLOR_KIND = "TestingColor"
TSHIRT_KIND = "TestingTShirt"


async def _wait_until(predicate: Callable[[], Awaitable[bool]], *, seconds: int = 180) -> None:
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


async def _wait_until_merged(*, client: InfrahubClient, branch_name: str, seconds: int = 120) -> None:
    """Wait until the branch reaches the MERGED status, so the test asserts on a merge that applied."""

    async def _merged() -> bool:
        branch = await client.branch.get(branch_name=branch_name)
        return branch.status == BranchStatus.MERGED

    await _wait_until(_merged, seconds=seconds)


class TestMergeRecompute(TestInfrahubDockerClient):
    """Post-merge and post-rebase recompute across single-hop, chained, and delete-peer scenarios."""

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def profile_schema(self) -> dict:
        return build_profile_schema_dict()

    @pytest.fixture(scope="class")
    def chain_schema(self) -> dict:
        return build_chain_schema_dict(levels=3)

    @pytest.fixture(scope="class")
    def interface_hfid_schema(self) -> dict:
        return build_interface_hfid_schema_dict()

    @pytest.fixture(scope="class")
    def location_cascade_schema(self) -> dict:
        return build_location_cascade_schema_dict()

    @pytest.fixture(scope="class")
    def delete_peer_schema(self) -> dict:
        """Reuse the TShirt and Color helpers, dropping the transform-python attribute (it needs a transform repo) and making color optional."""
        tshirt = TSHIRT.duplicate()
        tshirt.generate_template = False
        tshirt.attributes = [attribute for attribute in tshirt.attributes if attribute.name != "pitch"]
        for relationship in tshirt.relationships:
            if relationship.name == "color":
                relationship.optional = True
        return {"version": "1.0", "nodes": [COLOR.model_dump(), tshirt.model_dump()]}

    # Single-hop: a node reads a peer across one relationship.

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

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

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

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

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

    # Cross-relationship human-friendly id: the reader's identity reads a peer across the relationship,
    # so a peer rename must reindex the stored hfid that backs get_one_by_hfid. These assert the stored
    # value through the id lookup, not the id the SDK recomputes client-side from the loaded peer.

    async def test_merge_recomputes_cross_relationship_hfid(
        self, client: InfrahubClient, interface_hfid_schema: dict
    ) -> None:
        """A merged peer rename reindexes the reader: it resolves under the new hfid and not the old one."""
        loaded = await client.schema.load(schemas=[interface_hfid_schema], wait_until_converged=True)
        assert loaded.schema_updated

        device = await client.create(kind=DEVICE_KIND, data={"name": "device-a"})
        await device.save()
        interface = await client.create(kind=INTERFACE_KIND, data={"name": "eth1", "device": device})
        await interface.save()

        async def _resolves(hfid: list[str]) -> bool:
            return await client.get(kind=INTERFACE_KIND, hfid=hfid, raise_when_missing=False) is not None

        await _wait_until(lambda: _resolves(["eth1", "device-a"]))

        branch = await client.branch.create(branch_name="hfid-merge-correctness")
        device_on_branch = await client.get(kind=DEVICE_KIND, id=device.id, branch=branch.name)
        device_on_branch.name.value = "device-b"
        await device_on_branch.save()

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

        assert await _became_true(lambda: _resolves(["eth1", "device-b"]), seconds=90)
        assert (await client.get(kind=INTERFACE_KIND, hfid=["eth1", "device-b"])).id == interface.id
        assert not await _resolves(["eth1", "device-a"])

    async def test_rebase_recomputes_cross_relationship_hfid(
        self, client: InfrahubClient, interface_hfid_schema: dict
    ) -> None:
        """A rebase that replays a peer rename reindexes a user-branch reader under its new hfid."""
        await client.schema.load(schemas=[interface_hfid_schema], wait_until_converged=True)

        device = await client.create(kind=DEVICE_KIND, data={"name": "rdevice-a"})
        await device.save()

        branch = await client.branch.create(branch_name="hfid-rebase-correctness")

        # Rename the device on the default branch; the rebase replays this onto the user branch.
        device.name.value = "rdevice-b"
        await device.save()

        # The interface lives only on the user branch, so only the rebase recompute can refresh it.
        interface = await client.create(
            kind=INTERFACE_KIND, data={"name": "reth1", "device": device}, branch=branch.name
        )
        await interface.save()

        async def _resolves(hfid: list[str]) -> bool:
            found = await client.get(kind=INTERFACE_KIND, hfid=hfid, branch=branch.name, raise_when_missing=False)
            return found is not None

        await _wait_until(lambda: _resolves(["reth1", "rdevice-a"]))

        await client.branch.rebase(branch_name=branch.name)

        assert await _became_true(lambda: _resolves(["reth1", "rdevice-b"]), seconds=90)
        assert (
            await client.get(kind=INTERFACE_KIND, hfid=["reth1", "rdevice-b"], branch=branch.name)
        ).id == interface.id
        assert not await _resolves(["reth1", "rdevice-a"])

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

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

        async def _reader_no_longer_names_peer() -> bool:
            refreshed = await client.get(kind=PROFILE_NODE_KIND, id=node.id)
            return refreshed.summary.value != "node2 on beta"

        assert await _became_true(_reader_no_longer_names_peer, seconds=60)

    # Multi-level chain: level i reads level i-1 across the source relationship.

    async def test_merge_recomputes_full_chain(self, client: InfrahubClient, chain_schema: dict) -> None:
        """A root edit made on the branch must leave every level correct on the destination after merge."""
        loaded = await client.schema.load(schemas=[chain_schema], wait_until_converged=True)
        assert loaded.schema_updated
        l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)

        root = await client.create(kind=l1, data={"name": "root"})
        await root.save()
        mid = await client.create(kind=l2, data={"name": "mid", "source": root})
        await mid.save()
        tip = await client.create(kind=l3, data={"name": "tip", "source": mid})
        await tip.save()

        async def _chain_is(value: str) -> bool:
            mid_node = await client.get(kind=l2, id=mid.id)
            tip_node = await client.get(kind=l3, id=tip.id)
            return mid_node.summary.value == value and tip_node.summary.value == value

        await _wait_until(lambda: _chain_is("root"))

        branch = await client.branch.create(branch_name="chain-merge-correctness")
        root_on_branch = await client.get(kind=l1, id=root.id, branch=branch.name)
        root_on_branch.name.value = "root-edited"
        await root_on_branch.save()

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

        await _wait_until(lambda: _chain_is("root-edited"))

        final_mid = await client.get(kind=l2, id=mid.id)
        final_tip = await client.get(kind=l3, id=tip.id)
        # The whole chain reads across the relationship, so every level reflects the new root value.
        assert final_mid.summary.value == "root-edited"
        assert final_tip.summary.value == "root-edited"

    async def test_merge_recomputes_destination_only_chain_tip(
        self, client: InfrahubClient, chain_schema: dict
    ) -> None:
        """A tip created only on the destination must still be refreshed by the merge's recompute."""
        await client.schema.load(schemas=[chain_schema], wait_until_converged=True)
        l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)

        root = await client.create(kind=l1, data={"name": "droot"})
        await root.save()
        mid = await client.create(kind=l2, data={"name": "dmid", "source": root})
        await mid.save()

        async def _mid_is(value: str) -> bool:
            mid_node = await client.get(kind=l2, id=mid.id)
            return mid_node.summary.value == value

        await _wait_until(lambda: _mid_is("droot"))

        branch = await client.branch.create(branch_name="chain-merge-destination-only")
        root_on_branch = await client.get(kind=l1, id=root.id, branch=branch.name)
        root_on_branch.name.value = "droot-edited"
        await root_on_branch.save()

        # The tip exists only on the destination. The branch never saw it, so its branch-side
        # recompute cannot refresh it; only the coalesced post-merge recompute can.
        tip = await client.create(kind=l3, data={"name": "dtip", "source": mid})
        await tip.save()

        async def _tip_is(value: str) -> bool:
            tip_node = await client.get(kind=l3, id=tip.id)
            return tip_node.summary.value == value

        await _wait_until(lambda: _tip_is("droot"))

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

        async def _chain_is(value: str) -> bool:
            return await _mid_is(value) and await _tip_is(value)

        await _wait_until(lambda: _chain_is("droot-edited"))

        final_mid = await client.get(kind=l2, id=mid.id)
        final_tip = await client.get(kind=l3, id=tip.id)
        assert final_mid.summary.value == "droot-edited"
        assert final_tip.summary.value == "droot-edited"

    async def test_rebase_recomputes_full_chain(self, client: InfrahubClient, chain_schema: dict) -> None:
        """A root edit replayed by a rebase must leave every level correct on the user branch."""
        await client.schema.load(schemas=[chain_schema], wait_until_converged=True)
        l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)

        root = await client.create(kind=l1, data={"name": "rroot"})
        await root.save()

        branch = await client.branch.create(branch_name="chain-rebase-correctness")
        # The chain readers live only on the user branch.
        mid = await client.create(kind=l2, data={"name": "rmid", "source": root}, branch=branch.name)
        await mid.save()
        tip = await client.create(kind=l3, data={"name": "rtip", "source": mid}, branch=branch.name)
        await tip.save()

        async def _chain_on_branch_is(value: str) -> bool:
            mid_node = await client.get(kind=l2, id=mid.id, branch=branch.name)
            tip_node = await client.get(kind=l3, id=tip.id, branch=branch.name)
            return mid_node.summary.value == value and tip_node.summary.value == value

        await _wait_until(lambda: _chain_on_branch_is("rroot"))

        # The rebase replays the default branch's root change onto the user branch.
        root.name.value = "rroot-edited"
        await root.save()

        await client.branch.rebase(branch_name=branch.name)

        await _wait_until(lambda: _chain_on_branch_is("rroot-edited"))

        final_mid = await client.get(kind=l2, id=mid.id, branch=branch.name)
        final_tip = await client.get(kind=l3, id=tip.id, branch=branch.name)
        assert final_mid.summary.value == "rroot-edited"
        assert final_tip.summary.value == "rroot-edited"

    # Display-label cascade: a rename two hops up must refresh display labels down the chain.

    async def test_merge_recomputes_two_level_display_label_cascade(
        self, client: InfrahubClient, location_cascade_schema: dict
    ) -> None:
        """A top-level rename must refresh both levels' display labels below it after merge."""
        loaded = await client.schema.load(schemas=[location_cascade_schema], wait_until_converged=True)
        assert loaded.schema_updated

        metro = await client.create(kind=METRO_KIND, data={"name": "metro-a"})
        await metro.save()
        site = await client.create(kind=SITE_KIND, data={"name": "site1", "metro": metro})
        await site.save()
        rack = await client.create(kind=RACK_KIND, data={"name": "rack1", "site": site})
        await rack.save()

        async def _labels_are(metro_name: str) -> bool:
            site_node = await client.get(kind=SITE_KIND, id=site.id)
            rack_node = await client.get(kind=RACK_KIND, id=rack.id)
            return (
                site_node.display_label == f"{metro_name}-site1"
                and rack_node.display_label == f"{metro_name}-site1 :: rack1"
            )

        await _wait_until(lambda: _labels_are("metro-a"))

        branch = await client.branch.create(branch_name="cascade-merge-correctness")
        metro_on_branch = await client.get(kind=METRO_KIND, id=metro.id, branch=branch.name)
        metro_on_branch.name.value = "metro-b"
        await metro_on_branch.save()

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

        await _wait_until(lambda: _labels_are("metro-b"))

        final_site = await client.get(kind=SITE_KIND, id=site.id)
        final_rack = await client.get(kind=RACK_KIND, id=rack.id)
        # First hop: the site reads the metro across its relationship. Second hop: the rack reads the
        # site's short name, which only moves once the site's recompute writes it, so the rack
        # refreshes only if the recompute chains from the site's write to the rack.
        assert final_site.shortname.value == "metro-b-site1"
        assert final_site.display_label == "metro-b-site1"
        assert final_rack.display_label == "metro-b-site1 :: rack1"

    async def test_rebase_recomputes_two_level_display_label_cascade(
        self, client: InfrahubClient, location_cascade_schema: dict
    ) -> None:
        """A rebase that replays a top-level rename must refresh both levels' display labels on the user branch."""
        await client.schema.load(schemas=[location_cascade_schema], wait_until_converged=True)

        metro = await client.create(kind=METRO_KIND, data={"name": "rmetro-a"})
        await metro.save()

        branch = await client.branch.create(branch_name="cascade-rebase-correctness")
        # The site and rack live only on the user branch, so only the rebase recompute can refresh them.
        site = await client.create(kind=SITE_KIND, data={"name": "rsite1", "metro": metro}, branch=branch.name)
        await site.save()
        rack = await client.create(kind=RACK_KIND, data={"name": "rrack1", "site": site}, branch=branch.name)
        await rack.save()

        async def _labels_on_branch_are(metro_name: str) -> bool:
            site_node = await client.get(kind=SITE_KIND, id=site.id, branch=branch.name)
            rack_node = await client.get(kind=RACK_KIND, id=rack.id, branch=branch.name)
            return (
                site_node.display_label == f"{metro_name}-rsite1"
                and rack_node.display_label == f"{metro_name}-rsite1 :: rrack1"
            )

        await _wait_until(lambda: _labels_on_branch_are("rmetro-a"))

        # The rebase replays the default branch's metro rename onto the user branch.
        metro.name.value = "rmetro-b"
        await metro.save()

        await client.branch.rebase(branch_name=branch.name)

        await _wait_until(lambda: _labels_on_branch_are("rmetro-b"))

        final_site = await client.get(kind=SITE_KIND, id=site.id, branch=branch.name)
        final_rack = await client.get(kind=RACK_KIND, id=rack.id, branch=branch.name)
        assert final_site.shortname.value == "rmetro-b-rsite1"
        assert final_site.display_label == "rmetro-b-rsite1"
        assert final_rack.display_label == "rmetro-b-rsite1 :: rrack1"

    # Delete a read peer: the merge must complete instead of erroring on the missing peer.

    async def test_merge_survives_deleting_a_read_peer(self, client: InfrahubClient, delete_peer_schema: dict) -> None:
        """Merging a branch that deleted a read peer completes instead of erroring on the missing peer."""
        loaded = await client.schema.load(schemas=[delete_peer_schema], wait_until_converged=True)
        assert loaded.schema_updated

        color = await client.create(kind=COLOR_KIND, data={"name": "red", "description": "the red one"})
        await color.save()
        tshirt = await client.create(kind=TSHIRT_KIND, data={"name": "tee", "color": color})
        await tshirt.save()

        async def _reader_initial() -> bool:
            refreshed = await client.get(kind=TSHIRT_KIND, id=tshirt.id)
            return refreshed.display_label == "tee red"

        await _wait_until(_reader_initial)

        branch = await client.branch.create(branch_name="delete-peer-survives")
        color_on_branch = await client.get(kind=COLOR_KIND, id=color.id, branch=branch.name)
        await color_on_branch.delete()

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged
        await _wait_until_merged(client=client, branch_name=branch.name)

        refreshed = await client.get(kind=TSHIRT_KIND, id=tshirt.id)
        assert refreshed.name.value == "tee"
