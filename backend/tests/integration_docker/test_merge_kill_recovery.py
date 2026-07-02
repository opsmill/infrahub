from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_testcontainers.container import InfrahubDockerCompose

# The test stack runs with a ~1s merge-failure grace period (set in docker-compose.test.yml), so once
# a merge's lock holder is gone the next merge-watcher scan (cron, every minute) flips it quickly.
MERGING_TIMEOUT_SECONDS = 90
DETECTION_TIMEOUT_SECONDS = 180
POLL_INTERVAL_SECONDS = 3


async def _branch_status(client: InfrahubClient, branch_name: str) -> str | None:
    branches = await client.branch.all()
    branch = branches.get(branch_name)
    return branch.status if branch is not None else None


async def _wait_for_status(client: InfrahubClient, branch_name: str, target: str, timeout_seconds: float) -> str | None:
    deadline = time.monotonic() + timeout_seconds
    status: str | None = None
    while time.monotonic() < deadline:
        status = await _branch_status(client, branch_name)
        if status == target:
            return status
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    return status


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
        # Enough changes that the merge stays in MERGING long enough to be caught and killed
        # mid-flight rather than completing before the SIGKILL lands.
        for index in range(20):
            node = await client.create(kind="BuiltinTag", name=f"merge-kill-tag-{index}", branch=branch_name)
            await node.save()

        # Fire the merge without awaiting completion (it runs on a task worker); we kill the worker
        # while it is in flight, so awaiting here would hang.
        merge_task = asyncio.create_task(
            client.execute_graphql(
                query=f'mutation {{ BranchMerge(data: {{name: "{branch_name}"}}) {{ ok }} }}',
                branch_name="main",
            )
        )
        try:
            # Wait until the merge is genuinely in flight, then SIGKILL the worker(s) so the merge
            # dies mid-flight with the global merge lock still held by the now-dead worker.
            assert await _wait_for_status(client, branch_name, "MERGING", MERGING_TIMEOUT_SECONDS) == "MERGING", (
                "merge never reached MERGING; cannot exercise the mid-merge kill"
            )
            base_cmd = list(infrahub_compose.compose_command_property)
            infrahub_compose._run_command(cmd=[*base_cmd, "kill", "-s", "SIGKILL", "task-worker"])

            # Bring the worker(s) back so the recurring merge-watcher can run; issue no writes — the
            # flip must come from the idle scan alone. A restarted worker has a fresh identity, so the
            # dead lock holder is no longer in the active set.
            infrahub_compose.start_container("task-worker")

            status = await _wait_for_status(client, branch_name, "MERGE_FAILED", DETECTION_TIMEOUT_SECONDS)
            assert status == "MERGE_FAILED", f"branch {branch_name} was not flagged MERGE_FAILED (status={status})"
        finally:
            merge_task.cancel()

    @pytest.mark.skip(reason="Recovery half is not implemented yet.")
    async def test_recover_after_kill_remerges(self, client: InfrahubClient) -> None:  # pragma: no cover
        ...
