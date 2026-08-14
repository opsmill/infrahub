"""The Python recompute is dispatched in batches, on a rebase as well as on a merge.

Kept out of `test_merge_recompute.py` because the rebase arm needs its own stack lifecycle and the
assertions here are about dispatch shape rather than about stored values, which parity already
covers.

The shape is the whole point. A run carrying a single object id is the per-node fan-out this
feature removes, so its absence is what is asserted, not merely that the values came out right.
The rebase arm is the only integration coverage of the rebase wiring; every measurement so far has
gone through merge.
"""

from __future__ import annotations

import os
from asyncio import sleep
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.task.models import TaskFilter, TaskState
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo, GitRepoType

from tests.helpers.fixtures import get_fixtures_dir
from tests.helpers.merge_recompute.dataset import (
    TRANSFORM_OWNER_KIND,
    TRANSFORM_PEER_KIND,
    TRANSFORM_REPO_NAME,
    build_transform_schema_dict,
)

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

CHANGED_NODES = 20
PROCESS_TRANSFORM = "computed_attribute_process_transform"


async def _drain(client: InfrahubClient, *, max_wait: int = 1800) -> None:
    while max_wait > 0:
        pending = await client.task.count(
            filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED])
        )
        if pending == 0:
            return
        await sleep(1)
        max_wait -= 1
    raise TimeoutError("background tasks did not drain within the timeout")


@pytest.mark.skipif(
    not os.environ.get("INFRAHUB_PYTHON_DISPATCH"),
    reason="on-demand dispatch-shape check; set INFRAHUB_PYTHON_DISPATCH to run",
)
class TestPythonRecomputeDispatch(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    async def seeded_peer_ids(self, client: InfrahubClient, remote_repos_dir: Path) -> list[str]:
        """Schema, transform repository and the owner/peer pairs, created once for the whole class.

        Class-scoped because the repository can only be added to the stack once; a per-test seed
        collides on its checkout directory.
        """
        await client.schema.load(schemas=[build_transform_schema_dict()], wait_until_converged=True)
        repo = GitRepo(
            type=GitRepoType.INTEGRATED,
            name=TRANSFORM_REPO_NAME,
            src_directory=get_fixtures_dir() / "repos" / TRANSFORM_REPO_NAME / "initial__main",
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        assert await repo.wait_for_sync_to_complete(client=client)

        peer_ids: list[str] = []
        for index in range(CHANGED_NODES):
            peer = await client.create(
                kind=TRANSFORM_PEER_KIND,
                data={"name": f"dispatch-color-{index:05d}", "description": f"shade {index:05d}"},
            )
            await peer.save()
            peer_ids.append(peer.id)
        for index in range(CHANGED_NODES):
            owner = await client.create(
                kind=TRANSFORM_OWNER_KIND, data={"name": f"dispatch-shirt-{index:05d}", "color": peer_ids[index]}
            )
            await owner.save()
        await _drain(client)

        seeded = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        assert sum(1 for owner in seeded if owner.pitch.value) == CHANGED_NODES, (
            "the transform had not run for every owner before the operation under test"
        )
        return peer_ids

    @staticmethod
    async def _transform_runs(client: InfrahubClient, *, branch: str) -> int:
        """How many transform runs the branch has completed.

        Fewer runs than changed nodes is what says the recompute was batched; one run per node is
        the fan-out this feature removes.
        """
        return await client.task.count(
            filters=TaskFilter(workflow=[PROCESS_TRANSFORM], branch=branch, state=[TaskState.COMPLETED])
        )

    @pytest.mark.timeout(3600)
    async def test_a_merge_dispatches_batches_not_one_run_per_node(
        self, client: InfrahubClient, seeded_peer_ids: list[str]
    ) -> None:
        before = await self._transform_runs(client, branch="main")

        branch = await client.branch.create(branch_name="python-dispatch-merge")
        for index, peer_id in enumerate(seeded_peer_ids):
            obj = await client.get(kind=TRANSFORM_PEER_KIND, id=peer_id, branch=branch.name)
            obj.description.value = f"shade {index:05d} merged"
            await obj.save()
        await _drain(client)
        assert await client.branch.merge(branch_name=branch.name)
        await _drain(client)

        dispatched = await self._transform_runs(client, branch="main") - before
        owners = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        refreshed = sum(1 for owner in owners if "merged" in (owner.pitch.value or ""))

        assert refreshed == CHANGED_NODES, "every owner reading a changed peer must refresh"
        assert 0 < dispatched < CHANGED_NODES, (
            f"expected the merge to batch its recompute, got {dispatched} runs for {CHANGED_NODES} changed nodes"
        )

    @pytest.mark.timeout(3600)
    async def test_a_rebase_dispatches_batches_not_one_run_per_node(
        self, client: InfrahubClient, seeded_peer_ids: list[str]
    ) -> None:
        """The rebase path has the same wiring and, until this, no integration coverage of it."""
        branch = await client.branch.create(branch_name="python-dispatch-rebase")
        before = await self._transform_runs(client, branch=branch.name)

        # A rebase replays what main did after the fork, so the peers change on main.
        for index, peer_id in enumerate(seeded_peer_ids):
            obj = await client.get(kind=TRANSFORM_PEER_KIND, id=peer_id, branch="main")
            obj.description.value = f"shade {index:05d} rebased"
            await obj.save()
        await _drain(client)

        await client.branch.rebase(branch_name=branch.name)
        await _drain(client)

        dispatched = await self._transform_runs(client, branch=branch.name) - before
        owners = await client.all(kind=TRANSFORM_OWNER_KIND, branch=branch.name)
        refreshed = sum(1 for owner in owners if "rebased" in (owner.pitch.value or ""))

        assert refreshed == CHANGED_NODES, "a rebase must refresh the readers on the user branch"
        assert 0 < dispatched < CHANGED_NODES, (
            f"expected the rebase to batch its recompute, got {dispatched} runs for {CHANGED_NODES} changed nodes"
        )
