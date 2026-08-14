"""The coalesced Python recompute writes what the per-node path writes.

The feature replaces one recompute per changed node with a single coalesced pass. Speed is
measured elsewhere; what this checks is that the two paths leave the graph in the same state,
because a faster merge that refreshes fewer nodes is a regression dressed as an improvement.

Run it twice, once per mode, and the second run compares itself against the first:

    INFRAHUB_PARITY=1 INFRAHUB_TESTING_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE=false \\
        pytest backend/tests/integration_docker/test_merge_recompute_parity.py -s
    INFRAHUB_PARITY=1 \\
        pytest backend/tests/integration_docker/test_merge_recompute_parity.py -s

Each mode needs its own stack because the switch is read when the container starts, so the two
runs cannot share one. That is also why the comparison is keyed on node name rather than node id:
the ids are freshly minted per stack, while the names are seeded deterministically.
"""

from __future__ import annotations

import json
import os
from asyncio import sleep
from pathlib import Path
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
    from infrahub_sdk import InfrahubClient

CHANGED_NODES = int(os.environ.get("INFRAHUB_PARITY_SCALE", "50"))
SNAPSHOT_DIR = Path(os.environ.get("INFRAHUB_PARITY_DIR", "/tmp/infrahub-parity"))  # noqa: S108


def _snapshot_path(*, coalesced: bool) -> Path:
    return SNAPSHOT_DIR / f"parity_{'on' if coalesced else 'off'}_{CHANGED_NODES}.json"


def _coalescing_enabled() -> bool:
    return os.environ.get("INFRAHUB_TESTING_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE", "true").lower() != "false"


async def _drain(client: InfrahubClient, *, max_wait: int = 3600) -> None:
    deadline = max_wait
    while deadline > 0:
        pending = await client.task.count(
            filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED])
        )
        if pending == 0:
            return
        await sleep(1)
        deadline -= 1
    raise TimeoutError("background tasks did not drain within the timeout")


@pytest.mark.skipif(not os.environ.get("INFRAHUB_PARITY"), reason="on-demand parity check; set INFRAHUB_PARITY to run")
class TestPythonMergeRecomputeParity(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.mark.timeout(5400)
    async def test_both_paths_write_the_same_values(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        coalesced = _coalescing_enabled()

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
        for index in range(CHANGED_NODES):
            peer = await client.create(
                kind=TRANSFORM_PEER_KIND,
                data={"name": f"parity-color-{index:05d}", "description": f"shade {index:05d}"},
            )
            await peer.save()
            peers.append(peer)
        for index in range(CHANGED_NODES):
            owner = await client.create(
                kind=TRANSFORM_OWNER_KIND, data={"name": f"parity-shirt-{index:05d}", "color": peers[index]}
            )
            await owner.save()

        await _drain(client)

        # Without this the run compares two empty populations and passes for the wrong reason.
        seeded = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        assert sum(1 for owner in seeded if owner.pitch.value) == CHANGED_NODES, (
            "the transform had not run for every owner before the merge"
        )

        branch = await client.branch.create(branch_name="python-parity")
        for index, peer in enumerate(peers):
            obj = await client.get(kind=TRANSFORM_PEER_KIND, id=peer.id, branch=branch.name)
            obj.description.value = f"shade {index:05d} edited"
            await obj.save()

        await _drain(client)
        assert await client.branch.merge(branch_name=branch.name)
        await _drain(client)

        owners = await client.all(kind=TRANSFORM_OWNER_KIND, branch="main")
        written = {owner.name.value: owner.pitch.value for owner in owners}
        assert len(written) == CHANGED_NODES
        assert all("edited" in (value or "") for value in written.values()), (
            "every owner reading a changed peer must end up with the edited value"
        )

        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        _snapshot_path(coalesced=coalesced).write_text(json.dumps(written, sort_keys=True), encoding="utf-8")

        other = _snapshot_path(coalesced=not coalesced)
        if not other.exists():
            pytest.skip(f"recorded the {'coalesced' if coalesced else 'per-node'} side; run the other mode to compare")

        baseline = json.loads(other.read_text(encoding="utf-8"))
        # Compare the mappings, not their sizes: a path that refreshed the wrong nodes, or refreshed
        # the right count with a stale value, has to fail here.
        assert written == baseline
