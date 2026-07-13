"""End-to-end correctness of coalesced recompute across a multi-level computed-attribute chain."""

from __future__ import annotations

from asyncio import sleep, timeout
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from tests.helpers.merge_recompute.dataset import build_chain_schema_dict, chain_kind

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient


async def _wait_until(predicate: Callable[[], Awaitable[bool]], *, seconds: int = 180) -> None:
    async with timeout(seconds):
        while not await predicate():  # noqa: ASYNC110
            await sleep(2)


class TestChainCoalescedRecompute(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def chain_schema(self) -> dict:
        return build_chain_schema_dict(levels=3)

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

        await client.branch.merge(branch_name=branch.name)

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

        await client.branch.merge(branch_name=branch.name)

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
