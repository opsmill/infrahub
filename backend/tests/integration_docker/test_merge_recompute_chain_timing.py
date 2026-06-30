"""On-demand chain recompute timing (set INFRAHUB_PROFILE_TIMING; scale via INFRAHUB_PROFILE_SCALE).

Profiles how deep the coalescing reaches over a multi-level computed-attribute chain. The chain
depth is set with INFRAHUB_PROFILE_CHAIN_LEVELS (default 3). The printed ``process_flows`` is the
signal: one coalesced dispatch per derived value the merge diff reaches, versus the per-node path
that would dispatch on the order of ``(levels - 1) * changed_nodes``.
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
)
from tests.helpers.merge_recompute.dataset import build_chain_schema_dict, chain_kind

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

# Per-reader value writes: roughly one per affected node per reader level, old or new.
RECOMPUTE_WORKFLOWS = [COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name]
# Process-flow dispatches: the coalescing signal, one per derived value the diff reaches.
PROCESS_WORKFLOWS = [COMPUTED_ATTRIBUTE_PROCESS_JINJA2.name]


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
    reason="on-demand chain recompute timing profile; set INFRAHUB_PROFILE_TIMING to run",
)
class TestChainRecomputeTiming(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    async def _seed_chain(
        self, client: InfrahubClient, *, count: int, levels: int, prefix: str
    ) -> list[list[InfrahubNode]]:
        """Create ``count`` independent chains, each ``levels`` deep (level i reads level i-1)."""
        by_level: list[list[InfrahubNode]] = []

        roots: list[InfrahubNode] = []
        batch = await client.create_batch()
        for index in range(count):
            root = await client.create(kind=chain_kind(1), data={"name": f"{prefix}-l1-{index:05d}"})
            batch.add(task=root.save, node=root)
            roots.append(root)
        async for _, _ in batch.execute():
            pass
        by_level.append(roots)

        for level in range(2, levels + 1):
            previous = by_level[-1]
            nodes: list[InfrahubNode] = []
            batch = await client.create_batch()
            for index in range(count):
                node = await client.create(
                    kind=chain_kind(level),
                    data={"name": f"{prefix}-l{level}-{index:05d}", "source": previous[index]},
                )
                batch.add(task=node.save, node=node)
                nodes.append(node)
            async for _, _ in batch.execute():
                pass
            by_level.append(nodes)

        await _wait_idle(client)
        return by_level

    async def _mutate_roots(
        self, client: InfrahubClient, *, roots: list[InfrahubNode], prefix: str, branch: str
    ) -> None:
        batch = await client.create_batch()
        for index, root in enumerate(roots):
            obj = await client.get(kind=chain_kind(1), id=root.id, branch=branch)
            obj.name.value = f"{prefix}-l1-{index:05d}-edited"
            batch.add(task=obj.save, node=obj)
        async for _, _ in batch.execute():
            pass
        await _wait_idle(client)

    async def _measure_window(self, client: InfrahubClient, *, branch: str, before_updates: int) -> float:
        window_start = time.monotonic()
        deadline = time.monotonic() + 2400
        while time.monotonic() < deadline:
            await sleep(2)
            await _wait_idle(client)
            if await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch=branch) > before_updates:
                break
        return time.monotonic() - window_start

    @pytest.mark.timeout(5400)
    async def test_merge_chain_timing(self, client: InfrahubClient) -> None:
        changed_nodes = int(os.environ.get("INFRAHUB_PROFILE_SCALE", "100"))
        levels = int(os.environ.get("INFRAHUB_PROFILE_CHAIN_LEVELS", "3"))
        await client.schema.load(schemas=[build_chain_schema_dict(levels=levels)], wait_until_converged=True)

        by_level = await self._seed_chain(client, count=changed_nodes, levels=levels, prefix="merge")
        branch = await client.branch.create(branch_name="chain-merge-timing")
        await self._mutate_roots(client, roots=by_level[0], prefix="merge", branch=branch.name)

        before_updates = await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch="main")
        before_process = await _count(client, workflows=PROCESS_WORKFLOWS, branch="main")

        start = time.monotonic()
        merged = await client.branch.merge(branch_name=branch.name)
        critical_path_s = time.monotonic() - start
        assert merged

        window_s = await self._measure_window(client, branch="main", before_updates=before_updates)
        update_runs = await _count(client, workflows=RECOMPUTE_WORKFLOWS, branch="main") - before_updates
        process_runs = await _count(client, workflows=PROCESS_WORKFLOWS, branch="main") - before_process

        per_node_dispatch = (levels - 1) * changed_nodes
        print(
            f"\n[chain-merge-timing] levels={levels} changed_nodes={changed_nodes} "
            f"critical_path_s={critical_path_s:.2f} window_s={window_s:.2f} "
            f"process_flows={process_runs} update_value_runs={update_runs} "
            f"per_node_baseline={per_node_dispatch}"
        )
        assert critical_path_s > 0
        assert update_runs > 0
        # Coalescing reaches at least the first hop, so the dispatch stays below the per-node path,
        # which would fan out on the order of (levels - 1) * changed_nodes.
        assert process_runs < per_node_dispatch
