from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.schemas.objects import TERMINAL_STATES

from .models import FlowRunQueryCriteria

if TYPE_CHECKING:
    from prefect.client.schemas.filters import FlowRunFilter
    from prefect.client.schemas.objects import FlowRun

    from infrahub.log import InfrahubLogger

    from .filters import FlowRunFilterBuilder
    from .prefect_client import RetentionPrefectClient


class BranchFlowRunPurger:
    """Delete the settled flow runs tagged with a given branch."""

    def __init__(
        self,
        client: RetentionPrefectClient,
        filter_builder: FlowRunFilterBuilder,
        log: InfrahubLogger,
        batch_size: int = 100,
    ) -> None:
        self.client = client
        self.filter_builder = filter_builder
        self.log = log
        self.batch_size = batch_size

    async def _read(self, flow_run_filter: FlowRunFilter, branch_name: str) -> list[FlowRun] | None:
        """Read a page of runs, or None when the read failed (already logged)."""
        try:
            return await self.client.read_flow_runs(flow_run_filter=flow_run_filter, limit=self.batch_size)
        # Best-effort cleanup that follows a committed deletion: a read failure must not fail it.
        except Exception as exc:  # noqa: BLE001
            self.log.warning(f"Failed to read flow runs for deleted branch '{branch_name}': {exc}")
            return None

    async def purge_for_branch(self, branch_name: str) -> None:
        # Only settled runs: a run still in flight keeps the branch tag while it runs, so restricting
        # to terminal states leaves it untouched.
        flow_run_filter = self.filter_builder.build_flow_run_filter(
            criteria=FlowRunQueryCriteria(branch=branch_name, statuses=list(TERMINAL_STATES))
        )

        flow_runs = await self._read(flow_run_filter=flow_run_filter, branch_name=branch_name)
        if flow_runs is None:
            return

        purged_total = 0
        while flow_runs:
            attempted_ids = [flow_run.id for flow_run in flow_runs]
            deleted_calls = 0
            for flow_run in flow_runs:
                try:
                    await self.client.delete_flow_run(flow_run_id=flow_run.id)
                    deleted_calls += 1
                # A single failed delete must not abort the rest of the batch.
                except Exception as exc:  # noqa: BLE001
                    self.log.warning(
                        f"Failed to delete flow run {flow_run.id} for deleted branch '{branch_name}': {exc}"
                    )

            flow_runs = await self._read(flow_run_filter=flow_run_filter, branch_name=branch_name)
            if flow_runs is None:
                # The re-read that confirms removals failed, so fall back to the delete calls that
                # returned this batch rather than dropping them from the count.
                purged_total += deleted_calls
                break
            # Progress is measured by what actually left the store, not by delete calls that returned:
            # a delete can report success yet leave the run in place under eventual consistency.
            remaining_ids = {flow_run.id for flow_run in flow_runs}
            purged_total += sum(1 for flow_run_id in attempted_ids if flow_run_id not in remaining_ids)
            # None of the attempted runs are gone, so retrying would loop forever: stop and say so.
            if remaining_ids.issuperset(attempted_ids):
                self.log.warning(
                    f"Stopped purging flow runs for deleted branch '{branch_name}': "
                    f"{len(attempted_ids)} run(s) could not be removed"
                )
                break

        self.log.info(f"Purged {purged_total} flow run(s) for deleted branch '{branch_name}'")
