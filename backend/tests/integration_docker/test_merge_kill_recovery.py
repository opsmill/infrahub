from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_testcontainers.container import InfrahubDockerCompose

# A killed worker leaves the branch MERGING; the merge-watcher cron (every minute) must flip it to
# MERGE_FAILED once the lock holder is gone and the grace period (default 180s) has elapsed.
DETECTION_TIMEOUT_SECONDS = 360
POLL_INTERVAL_SECONDS = 5


async def _branch_status(client: InfrahubClient, branch_name: str) -> str | None:
    branches = await client.branch.all()
    branch = branches.get(branch_name)
    return branch.status if branch is not None else None


class TestMergeKillDetection(TestInfrahubDockerClient):
    """Cross-process detection: SIGKILL a worker mid-merge, stay idle, expect MERGE_FAILED.

    This is the detection half of the kill/recovery integration scenario. The recovery half
    (`infrahub recover` re-merges) is added with the recovery increment in the same file.
    """

    async def test_killed_merge_is_flagged_failed_while_idle(
        self,
        client: InfrahubClient,
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        branch_name = "merge_kill_detection"
        await client.branch.create(branch_name=branch_name)
        node = await client.create(kind="BuiltinTag", name="merge-kill-tag", branch=branch_name)
        await node.save()

        # Submit the merge so it runs on a task worker, then SIGKILL the workers before it can reach
        # the MERGED transition. The merge lock holder is now a dead worker and the branch is stuck
        # in MERGING.
        await client.execute_graphql(
            query=f'mutation {{ BranchMerge(data: {{name: "{branch_name}"}}) {{ ok }} }}',
            branch_name="main",
        )
        base_cmd = list(infrahub_compose.compose_command_property)
        infrahub_compose._run_command(cmd=[*base_cmd, "kill", "-s", "SIGKILL", "task-worker"])

        # Bring the workers back so the recurring merge-watcher can run, but issue no writes — the
        # flip must happen from the idle scan alone.
        infrahub_compose.start_container("task-worker")

        deadline = time.monotonic() + DETECTION_TIMEOUT_SECONDS
        status: str | None = None
        while time.monotonic() < deadline:
            status = await _branch_status(client, branch_name)
            if status == "MERGE_FAILED":
                break
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        assert status == "MERGE_FAILED", f"branch {branch_name} was not flagged MERGE_FAILED (status={status})"

    @pytest.mark.skip(reason="Recovery half is not implemented yet.")
    async def test_recover_after_kill_remerges(self, client: InfrahubClient) -> None:  # pragma: no cover
        ...
