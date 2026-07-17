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


async def _drive_branch_to_merge_failed(
    client: InfrahubClient,
    infrahub_compose: InfrahubDockerCompose,
    branch_name: str,
) -> None:
    """Take a fresh branch all the way to MERGE_FAILED by killing its merge worker mid-flight.

    Creates the branch with enough changes that the merge stays in MERGING long enough to be caught,
    fires the merge without awaiting it (it runs on a task worker), SIGKILLs the worker(s) while the
    merge is in flight so the global merge lock stays held by a now-dead worker, restarts the
    worker(s), and stays idle until the recurring merge-watcher scan flips the branch to MERGE_FAILED.
    """
    await client.branch.create(branch_name=branch_name)
    for index in range(20):
        node = await client.create(kind="BuiltinTag", name=f"{branch_name}-tag-{index}", branch=branch_name)
        await node.save()

    # Fire the merge without awaiting completion; we kill the worker while it is in flight, so awaiting
    # here would hang.
    merge_task = asyncio.create_task(
        client.execute_graphql(
            query=f'mutation {{ BranchMerge(data: {{name: "{branch_name}"}}) {{ ok }} }}',
            branch_name="main",
        )
    )
    try:
        # Wait until the merge is genuinely in flight, then SIGKILL the worker(s) so the merge dies
        # mid-flight with the global merge lock still held by the now-dead worker.
        assert await _wait_for_status(client, branch_name, "MERGING", MERGING_TIMEOUT_SECONDS) == "MERGING", (
            "merge never reached MERGING; cannot exercise the mid-merge kill"
        )
        base_cmd = list(infrahub_compose.compose_command_property)
        infrahub_compose._run_command(cmd=[*base_cmd, "kill", "-s", "SIGKILL", "task-worker"])

        # Bring the worker(s) back so the recurring merge-watcher can run; issue no writes — the flip
        # must come from the idle scan alone. A restarted worker has a fresh identity, so the dead lock
        # holder is no longer in the active set.
        infrahub_compose.start_container("task-worker")

        status = await _wait_for_status(client, branch_name, "MERGE_FAILED", DETECTION_TIMEOUT_SECONDS)
        assert status == "MERGE_FAILED", f"branch {branch_name} was not flagged MERGE_FAILED (status={status})"
    finally:
        merge_task.cancel()
        try:
            await merge_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            # The mutation legitimately errors once its worker is SIGKILLed mid-flight; retrieve the
            # exception so an unrelated early failure (validation, connectivity) surfaces in the
            # captured test output instead of being lost as an unretrieved-task warning.
            print(f"merge mutation task raised: {exc!r}")


@pytest.mark.skip(reason="test takes too long")
class TestMergeKillRecovery(TestInfrahubDockerClient):
    """End-to-end cross-process detection and recovery from a killed merge.

    First the detection half: SIGKILL a merge worker mid-flight and stay idle until the recurring
    merge-watcher scan flips the branch to MERGE_FAILED. Then the recovery half: running the recover
    command rolls back the partial merge, reopens the branch, restores default-branch writes, and lets
    the branch merge again. Detection is a strict prerequisite of recovery, so one flow covers both.
    """

    async def test_killed_merge_is_detected_then_recovered(
        self,
        client: InfrahubClient,
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        branch_name = "merge_kill_recovery"
        await _drive_branch_to_merge_failed(client=client, infrahub_compose=infrahub_compose, branch_name=branch_name)

        # Recover from inside the stack: the CLI process reads its configuration from the same
        # environment the server container runs with, so it operates on the stack's database. It exits
        # non-zero on a failed recovery, which _run_command surfaces as a raised error.
        infrahub_compose.exec_in_container(
            command=["infrahub", "recover", "merge", "--yes"],
            service_name="infrahub-server",
        )

        assert await _branch_status(client, branch_name) == "OPEN", "branch was not reopened after recovery"

        # Writes to the default branch are unblocked again once the protection is lifted.
        recovered_write = await client.create(kind="BuiltinTag", name="post-recovery-tag", branch="main")
        await recovered_write.save()

        # The reopened branch merges cleanly the second time.
        remerge = await client.execute_graphql(
            query=f'mutation {{ BranchMerge(data: {{name: "{branch_name}"}}) {{ ok }} }}',
            branch_name="main",
        )
        assert remerge["BranchMerge"]["ok"] is True
        status = await _wait_for_status(client, branch_name, "MERGED", MERGING_TIMEOUT_SECONDS)
        assert status == "MERGED", f"branch {branch_name} did not reach MERGED after re-merge (status={status})"
