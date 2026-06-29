"""Timing layer for the merge and rebase recompute (full distributed stack).

On-demand and gated: set ``INFRAHUB_PROFILE_TIMING`` to run it. It drives a real merge and rebase on
the running stack with a real task worker and reports, per operation:

- the merge/rebase critical path (synchronous, in-transaction cost),
- the trailing recompute window (merge return to queue drained),
- the executed per-reader recompute runs (``*-update-value`` flows), and
- the recompute process-flow dispatches (``*-process`` flows).

The process-flow dispatch count is the coalescing signal: the per-node path dispatched one process
flow per changed node per family (about ``2 * changed_nodes`` here), while the coalesced path
dispatches one per affected derived value (about two), independent of the changed-node count. Scale
is set with ``INFRAHUB_PROFILE_SCALE`` (changed-node count, default 100). Timings are reported with
no hard thresholds because they are stack-relative; only the structural bound is asserted.
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
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABEL_JINJA2_UPDATE_VALUE,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
    HFID_UPDATE_VALUE,
)
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, PROFILE_PEER_KIND, build_profile_schema_dict

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

# Per-reader value writes: roughly the same count old or new, since every affected reader is written.
RECOMPUTE_WORKFLOWS = [
    COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name,
    DISPLAY_LABEL_JINJA2_UPDATE_VALUE.name,
    HFID_UPDATE_VALUE.name,
]
# Process-flow dispatches: the coalescing signal (one per affected derived value, not per node).
PROCESS_WORKFLOWS = [
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2.name,
    DISPLAY_LABELS_PROCESS_JINJA2.name,
    HFID_PROCESS.name,
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


async def _count(client: InfrahubClient, *, workflows: list[str], branch: str) -> int:
    return await client.task.count(filters=TaskFilter(workflow=workflows, branch=branch))


@pytest.mark.skipif(
    not os.environ.get("INFRAHUB_PROFILE_TIMING"),
    reason="on-demand merge/rebase timing profile; set INFRAHUB_PROFILE_TIMING to run",
)
class TestMergeRecomputeTiming(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    async def _seed(self, client: InfrahubClient, *, changed_nodes: int, prefix: str) -> list:
        """Create ``changed_nodes`` peers and one main per peer (each main reads its peer)."""
        peers = []
        peer_batch = await client.create_batch()
        for index in range(changed_nodes):
            peer = await client.create(kind=PROFILE_PEER_KIND, data={"name": f"{prefix}-peer-{index:05d}"})
            peer_batch.add(task=peer.save, node=peer)
            peers.append(peer)
        async for _, _ in peer_batch.execute():
            pass

        main_batch = await client.create_batch()
        for index in range(changed_nodes):
            main = await client.create(
                kind=PROFILE_NODE_KIND, data={"name": f"{prefix}-node-{index:05d}", "peer": peers[index]}
            )
            main_batch.add(task=main.save, node=main)
        async for _, _ in main_batch.execute():
            pass

        await _wait_idle(client)
        return peers

    async def _mutate_peers(self, client: InfrahubClient, *, peers: list, prefix: str, branch: str) -> None:
        batch = await client.create_batch()
        for index, peer in enumerate(peers):
            obj = await client.get(kind=PROFILE_PEER_KIND, id=peer.id, branch=branch)
            obj.name.value = f"{prefix}-peer-{index:05d}-edited"
            batch.add(task=obj.save, node=obj)
        async for _, _ in batch.execute():
            pass
        await _wait_idle(client)

    async def _measure_window(self, client: InfrahubClient, *, branch: str, before_updates: int) -> float:
        """Poll until the per-reader recompute rises above the baseline and the queue drains."""
        window_start = time.monotonic()
        deadline = time.monotonic() + 2400
        while time.monotonic() < deadline:
            await sleep(2)
            await _wait_idle(client)
            if await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch=branch) > before_updates:
                break
        return time.monotonic() - window_start

    @pytest.mark.timeout(5400)
    async def test_merge_timing(self, client: InfrahubClient) -> None:
        changed_nodes = int(os.environ.get("INFRAHUB_PROFILE_SCALE", "100"))
        await client.schema.load(schemas=[build_profile_schema_dict()], wait_until_converged=True)

        peers = await self._seed(client, changed_nodes=changed_nodes, prefix="merge")
        branch = await client.branch.create(branch_name="merge-recompute-timing")
        await self._mutate_peers(client, peers=peers, prefix="merge", branch=branch.name)

        before_updates = await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch="main")
        before_process = await _count(client, workflows=PROCESS_WORKFLOWS, branch="main")

        start = time.monotonic()
        merged = await client.branch.merge(branch_name=branch.name)
        critical_path_s = time.monotonic() - start
        assert merged

        window_s = await self._measure_window(client, branch="main", before_updates=before_updates)
        update_runs = await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch="main") - before_updates
        process_runs = await _count(client, workflows=PROCESS_WORKFLOWS, branch="main") - before_process

        print(
            f"\n[merge-recompute-timing] changed_nodes={changed_nodes} "
            f"critical_path_s={critical_path_s:.2f} window_s={window_s:.2f} "
            f"process_flows={process_runs} update_value_runs={update_runs}"
        )
        assert critical_path_s > 0
        assert update_runs > 0
        # Coalescing: process-flow dispatch is bounded by the affected derived values, not the
        # changed-node count. The per-node path would dispatch about 2 * changed_nodes.
        assert process_runs < changed_nodes

    @pytest.mark.timeout(5400)
    async def test_rebase_timing(self, client: InfrahubClient) -> None:
        changed_nodes = int(os.environ.get("INFRAHUB_PROFILE_SCALE", "100"))
        await client.schema.load(schemas=[build_profile_schema_dict()], wait_until_converged=True)

        peers = await self._seed(client, changed_nodes=changed_nodes, prefix="rebase")
        branch = await client.branch.create(branch_name="rebase-recompute-timing")
        # Rebase replays the default branch's intervening changes, so mutate the peers on default.
        await self._mutate_peers(client, peers=peers, prefix="rebase", branch="main")

        before_updates = await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch=branch.name)
        before_process = await _count(client, workflows=PROCESS_WORKFLOWS, branch=branch.name)

        start = time.monotonic()
        await client.branch.rebase(branch_name=branch.name)
        critical_path_s = time.monotonic() - start

        window_s = await self._measure_window(client, branch=branch.name, before_updates=before_updates)
        update_runs = await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch=branch.name) - before_updates
        process_runs = await _count(client, workflows=PROCESS_WORKFLOWS, branch=branch.name) - before_process

        print(
            f"\n[rebase-recompute-timing] changed_nodes={changed_nodes} "
            f"critical_path_s={critical_path_s:.2f} window_s={window_s:.2f} "
            f"process_flows={process_runs} update_value_runs={update_runs}"
        )
        assert critical_path_s > 0
        assert update_runs > 0
        assert process_runs < changed_nodes
