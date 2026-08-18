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
from infrahub_sdk.testing.repository import GitRepo, GitRepoType

from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
    QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from tests.helpers.fixtures import get_fixtures_dir
from tests.helpers.merge_recompute.dataset import (
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    TRANSFORM_IMPRECISE_ATTRIBUTE,
    TRANSFORM_OWNER_KIND,
    TRANSFORM_PEER_KIND,
    TRANSFORM_REPO_NAME,
    build_imprecise_transform_schema_dict,
    build_profile_schema_dict,
    build_transform_schema_dict,
)
from tests.helpers.merge_recompute.metrics import CostCenterTiming

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

# The three families the coalescing work already covers. They act as the control arm:
# already coalesced, so their count must not track the changed-node count.
RECOMPUTE_WORKFLOWS = [
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2.name,
    DISPLAY_LABELS_PROCESS_JINJA2.name,
    HFID_PROCESS.name,
]

# The Python family, which still fans out one job per changed node. This is the subject.
PYTHON_RECOMPUTE_WORKFLOWS = [
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM.name,
    QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS.name,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name,
]


async def _pending_count(client: InfrahubClient) -> int:
    return await client.task.count(
        filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED])
    )


async def _wait_idle(client: InfrahubClient, *, max_wait: int = 3600) -> None:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if await _pending_count(client) == 0:
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
            await sleep(0.25)
            after = await _recompute_count(client, branch="main")
            if after > before and await _pending_count(client) == 0:
                break
        recompute_window_s = time.monotonic() - window_start
        recompute_flow_runs = after - before

        timing = CostCenterTiming(
            merge_critical_path_s=merge_critical_path_s,
            recompute_window_s=recompute_window_s,
            recompute_flow_runs=recompute_flow_runs,
        )
        print(f"\n[merge-recompute-timing] changed_nodes={changed_nodes} {timing}")

        # Stack-relative: assert the mechanism (merge ran and the cross-node fan-out
        # recomputed), not absolute durations.
        assert merge_critical_path_s > 0
        assert recompute_flow_runs > 0


@pytest.mark.skipif(
    not os.environ.get("INFRAHUB_PROFILE_TIMING"),
    reason="on-demand merge timing profile; set INFRAHUB_PROFILE_TIMING to run",
)
class TestPythonMergeRecomputeTiming(TestInfrahubDockerClient):
    """Baseline for the Python-transform family, which still fans out per changed node.

    The merge payload is a change to the peers the transform's query reads, so every owner
    that reads a changed peer has to recompute. The kinds carry no display label and no
    human-friendly id, so the only derived value in play is the Python one and the counts
    below are attributable to it.
    """

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.mark.timeout(5400)
    async def test_python_merge_timing(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        changed_nodes = int(os.environ.get("INFRAHUB_PROFILE_SCALE", "100"))

        await client.schema.load(schemas=[build_transform_schema_dict()], wait_until_converged=True)

        repo = GitRepo(
            type=GitRepoType.INTEGRATED,
            name=TRANSFORM_REPO_NAME,
            src_directory=get_fixtures_dir() / "repos" / TRANSFORM_REPO_NAME / "initial__main",
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        assert await repo.wait_for_sync_to_complete(client=client)

        peers = []
        peer_batch = await client.create_batch()
        for index in range(changed_nodes):
            peer = await client.create(
                kind=TRANSFORM_PEER_KIND,
                data={"name": f"timing-color-{index:05d}", "description": f"shade {index:05d}"},
            )
            peer_batch.add(task=peer.save, node=peer)
            peers.append(peer)
        async for _, _ in peer_batch.execute():
            pass

        owner_batch = await client.create_batch()
        for index in range(changed_nodes):
            owner = await client.create(
                kind=TRANSFORM_OWNER_KIND,
                data={"name": f"timing-shirt-{index:05d}", "color": peers[index]},
            )
            owner_batch.add(task=owner.save, node=owner)
        async for _, _ in owner_batch.execute():
            pass

        await _wait_idle(client)

        # The transform has to have run once per owner before the merge, or there is nothing to
        # measure: no run means no query group membership, so the merge finds no reader to refresh
        # and the whole measurement silently reports an empty population. Registering the Python
        # automations races with these creations, so assert the baseline rather than assume it.
        seeded = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        computed = sum(1 for owner in seeded if owner.pitch.value)
        assert computed == changed_nodes, (
            f"only {computed}/{changed_nodes} owners had a computed value before the merge; "
            "the recompute automations were probably not registered yet when the owners were created"
        )

        branch = await client.branch.create(branch_name="python-merge-recompute-timing")
        update_batch = await client.create_batch()
        for index, peer in enumerate(peers):
            obj = await client.get(kind=TRANSFORM_PEER_KIND, id=peer.id, branch=branch.name)
            obj.description.value = f"shade {index:05d} edited"
            update_batch.add(task=obj.save, node=obj)
        async for _, _ in update_batch.execute():
            pass

        await _wait_idle(client)
        before = await client.task.count(filters=TaskFilter(workflow=PYTHON_RECOMPUTE_WORKFLOWS, branch="main"))
        control_before = await _recompute_count(client, branch="main")

        start = time.monotonic()
        merged = await client.branch.merge(branch_name=branch.name)
        merge_critical_path_s = time.monotonic() - start
        assert merged

        window_start = time.monotonic()
        deadline = time.monotonic() + 3600
        after = before
        while time.monotonic() < deadline:
            await sleep(0.25)
            after = await client.task.count(filters=TaskFilter(workflow=PYTHON_RECOMPUTE_WORKFLOWS, branch="main"))
            if after > before and await _pending_count(client) == 0:
                break
        recompute_window_s = time.monotonic() - window_start

        owners = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        refreshed = sum(1 for owner in owners if "edited" in (owner.pitch.value or ""))

        timing = CostCenterTiming(
            merge_critical_path_s=merge_critical_path_s,
            recompute_window_s=recompute_window_s,
            recompute_flow_runs=after - before,
            recompute_nodes_written=refreshed,
        )
        control_runs = await _recompute_count(client, branch="main") - control_before
        print(
            f"\n[python-merge-recompute-timing] changed_nodes={changed_nodes} "
            f"control_family_runs={control_runs} {timing}"
        )

        assert merge_critical_path_s > 0
        assert refreshed == changed_nodes, "every owner reading a changed peer must refresh"


@pytest.mark.skipif(
    not os.environ.get("INFRAHUB_PROFILE_TIMING"),
    reason="on-demand merge timing profile; set INFRAHUB_PROFILE_TIMING to run",
)
class TestImpreciseReadSetDoesNotWiden(TestInfrahubDockerClient):
    """An attribute whose read set cannot be mapped to fields must still be narrowed by its readers.

    Reading a display label makes the read set imprecise. The pass has to answer that by asking who
    reads the changed nodes, not by refreshing every node of the kind.
    """

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.mark.timeout(3600)
    async def test_an_imprecise_attribute_does_not_refresh_its_whole_kind(
        self, client: InfrahubClient, remote_repos_dir: Path
    ) -> None:
        changed_nodes = int(os.environ.get("INFRAHUB_PROFILE_SCALE", "20"))

        await client.schema.load(schemas=[build_imprecise_transform_schema_dict()], wait_until_converged=True)
        repo = GitRepo(
            type=GitRepoType.INTEGRATED,
            name=TRANSFORM_REPO_NAME,
            src_directory=get_fixtures_dir() / "repos" / TRANSFORM_REPO_NAME / "initial__main",
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        assert await repo.wait_for_sync_to_complete(client=client)

        peers = []
        for index in range(changed_nodes):
            peer = await client.create(
                kind=TRANSFORM_PEER_KIND,
                data={"name": f"imprecise-color-{index:05d}", "description": f"shade {index:05d}"},
            )
            await peer.save()
            peers.append(peer)
        for index in range(changed_nodes):
            owner = await client.create(
                kind=TRANSFORM_OWNER_KIND, data={"name": f"imprecise-shirt-{index:05d}", "color": peers[index]}
            )
            await owner.save()

        await _wait_idle(client)
        seeded = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        assert sum(1 for owner in seeded if getattr(owner, TRANSFORM_IMPRECISE_ATTRIBUTE).value) == changed_nodes, (
            "the imprecise transform had not run for every owner before the merge"
        )

        widened_before = await client.task.count(
            filters=TaskFilter(workflow=[TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name])
        )
        batches_before = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM.name])
        )

        branch = await client.branch.create(branch_name="imprecise-read-set")
        for index, peer in enumerate(peers):
            obj = await client.get(kind=TRANSFORM_PEER_KIND, id=peer.id, branch=branch.name)
            obj.description.value = f"shade {index:05d} edited"
            await obj.save()
        await _wait_idle(client)
        assert await client.branch.merge(branch_name=branch.name)
        await _wait_idle(client)

        widened = (
            await client.task.count(filters=TaskFilter(workflow=[TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name]))
            - widened_before
        )
        batches = (
            await client.task.count(filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM.name]))
            - batches_before
        )
        print(f"\n[imprecise-read-set] changed_nodes={changed_nodes} widened={widened} batches={batches}")

        assert widened == 0, f"the pass widened {widened} time(s) instead of resolving the readers"
        assert batches < changed_nodes, f"{batches} batches for {changed_nodes} changed nodes is per-node fan-out"
