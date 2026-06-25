"""Timing layer for the merge recompute profile (full distributed stack).

On-demand and gated: set ``INFRAHUB_PROFILE_TIMING`` to run it. It drives a real
merge on the running stack with a real task worker and attributes wall-clock
across the merge critical path and the trailing recompute window, and counts the
executed recompute runs (the authoritative recompute count). Scale is set with
``INFRAHUB_PROFILE_SCALE`` (changed-node count, default 100).

The executed-recompute count uses a branch + recompute-deployment filter measured
as a before/after delta on the default branch; the merge runs on a dedicated
branch with the stack otherwise idle, so the delta isolates this merge's recompute
(a seeded-node-id-set filter is not supported by the flow-run query). Timings are
reported with no hard thresholds because they are stack-relative.
"""

from __future__ import annotations

import os
import time
from asyncio import sleep
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.task.models import TaskFilter, TaskState
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE,
    DISPLAY_LABEL_JINJA2_UPDATE_VALUE,
    HFID_UPDATE_VALUE,
)
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, PROFILE_PEER_KIND, build_profile_schema_dict
from tests.helpers.merge_recompute.metrics import CostCenterTiming

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

RECOMPUTE_WORKFLOWS = [
    COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name,
    DISPLAY_LABEL_JINJA2_UPDATE_VALUE.name,
    HFID_UPDATE_VALUE.name,
]


async def _wait_idle(client: InfrahubClient, *, max_wait: int = 2400) -> None:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        pending = await client.task.count(
            filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED])
        )
        if pending == 0:
            return
        await sleep(1)
    raise TimeoutError("background tasks did not drain within the timeout")


async def _recompute_count(client: InfrahubClient, *, branch: str) -> int:
    return await client.task.count(filters=TaskFilter(workflow=RECOMPUTE_WORKFLOWS, branch=branch))


@pytest.mark.skipif(
    not os.environ.get("INFRAHUB_PROFILE_TIMING"),
    reason="on-demand merge timing profile; set INFRAHUB_PROFILE_TIMING to run",
)
class TestMergeRecomputeTiming(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.mark.timeout(5400)
    async def test_merge_timing(self, client: InfrahubClient) -> None:
        changed_nodes = int(os.environ.get("INFRAHUB_PROFILE_SCALE", "100"))

        await client.schema.load(schemas=[build_profile_schema_dict()], wait_until_converged=True)

        # Baseline on the default branch: each main reads its own peer. The merge
        # payload is a change to the peers, so the dependent mains recompute. (A
        # node's own derived values recompute inline on save and create no async
        # work; the merge recompute cost is this cross-node fan-out.)
        peers = []
        peer_batch = await client.create_batch()
        for index in range(changed_nodes):
            peer = await client.create(kind=PROFILE_PEER_KIND, data={"name": f"timing-peer-{index:05d}"})
            peer_batch.add(task=peer.save, node=peer)
            peers.append(peer)
        async for _, _ in peer_batch.execute():
            pass

        main_batch = await client.create_batch()
        for index in range(changed_nodes):
            main = await client.create(
                kind=PROFILE_NODE_KIND, data={"name": f"timing-node-{index:05d}", "peer": peers[index]}
            )
            main_batch.add(task=main.save, node=main)
        async for _, _ in main_batch.execute():
            pass

        # Let baseline recompute settle so only the merge's recompute is measured.
        await _wait_idle(client)

        # Change the peers on a dedicated branch; this is the merge payload.
        branch = await client.branch.create(branch_name="merge-recompute-timing")
        update_batch = await client.create_batch()
        for index, peer in enumerate(peers):
            obj = await client.get(kind=PROFILE_PEER_KIND, id=peer.id, branch=branch.name)
            obj.name.value = f"timing-peer-{index:05d}-edited"
            update_batch.add(task=obj.save, node=obj)
        async for _, _ in update_batch.execute():
            pass

        await _wait_idle(client)
        before = await _recompute_count(client, branch="main")

        # Merge critical path: the synchronous, in-transaction cost.
        start = time.monotonic()
        merged = await client.branch.merge(branch_name=branch.name)
        merge_critical_path_s = time.monotonic() - start
        assert merged

        # Trailing recompute window. Recompute is dispatched asynchronously by the
        # event-to-automation engine after the merge returns, so poll until it rises
        # above the pre-merge baseline and the queue drains in the same pass.
        window_start = time.monotonic()
        deadline = time.monotonic() + 2400
        after = before
        while time.monotonic() < deadline:
            await sleep(2)
            await _wait_idle(client)
            after = await _recompute_count(client, branch="main")
            if after > before:
                break
        recompute_window_s = time.monotonic() - window_start
        recompute_flow_runs = after - before

        timing = CostCenterTiming(
            merge_critical_path_s=merge_critical_path_s,
            recompute_total_s=recompute_window_s,
            recompute_window_s=recompute_window_s,
            recompute_flow_runs=recompute_flow_runs,
            schema_migration_s=None,
            db_commit_s=None,
        )
        print(f"\n[merge-recompute-timing] changed_nodes={changed_nodes} {timing}")

        # Stack-relative: assert the mechanism (merge ran and the cross-node fan-out
        # recomputed), not absolute durations.
        assert merge_critical_path_s > 0
        assert recompute_flow_runs > 0
