from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.schemas.objects import TERMINAL_STATES

from infrahub.workflows.constants import WorkflowTag

from .models import FlowRunQueryCriteria

if TYPE_CHECKING:
    from prefect.client.schemas.filters import FlowRunFilter
    from prefect.client.schemas.objects import FlowRun

    from infrahub.log import InfrahubLogger

    from .filters import FlowRunFilterBuilder
    from .prefect_client import BranchCleanupPrefectClient


class BranchFlowRunDetacher:
    """Move the settled flow runs of a deleted branch off its branch tag, keeping every run readable by id."""

    def __init__(
        self,
        client: BranchCleanupPrefectClient,
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
        except Exception as exc:
            self.log.warning(f"Failed to read flow runs for deleted branch '{branch_name}': {exc}")
            return None

    def _detached_tags(self, tags: list[str], branch_tag: str, added_tags: list[str]) -> list[str]:
        kept = [tag for tag in tags if tag != branch_tag]
        return kept + [tag for tag in added_tags if tag not in kept]

    async def detach_for_branch(self, branch_name: str, branch_id: str | None = None) -> None:
        # Only settled runs: a run still in flight keeps the branch tag while it runs, so restricting
        # to terminal states leaves it untouched.
        flow_run_filter = self.filter_builder.build_flow_run_filter(
            criteria=FlowRunQueryCriteria(branch=branch_name, statuses=list(TERMINAL_STATES))
        )
        branch_tag = WorkflowTag.BRANCH.render(identifier=branch_name)
        added_tags = [WorkflowTag.DELETED_BRANCH.render(identifier=branch_name)]
        if branch_id:
            added_tags.append(WorkflowTag.DELETED_BRANCH_ID.render(identifier=branch_id))

        flow_runs = await self._read(flow_run_filter=flow_run_filter, branch_name=branch_name)
        if flow_runs is None:
            return

        detached_total = 0
        while flow_runs:
            attempted_ids = [flow_run.id for flow_run in flow_runs]
            updated_calls = 0
            for flow_run in flow_runs:
                try:
                    await self.client.update_flow_run(
                        flow_run_id=flow_run.id,
                        tags=self._detached_tags(tags=flow_run.tags, branch_tag=branch_tag, added_tags=added_tags),
                    )
                    updated_calls += 1
                # A single failed update must not abort the rest of the batch.
                except Exception as exc:
                    self.log.warning(
                        f"Failed to detach flow run {flow_run.id} from deleted branch '{branch_name}': {exc}"
                    )

            flow_runs = await self._read(flow_run_filter=flow_run_filter, branch_name=branch_name)
            if flow_runs is None:
                # The re-read that confirms the detach failed, so fall back to the update calls that
                # returned this batch rather than dropping them from the count.
                detached_total += updated_calls
                break
            # Progress is measured by what actually left the branch filter, not by update calls that
            # returned: an update can report success yet leave the tag in place under eventual consistency.
            remaining_ids = {flow_run.id for flow_run in flow_runs}
            detached_total += sum(1 for flow_run_id in attempted_ids if flow_run_id not in remaining_ids)
            # None of the attempted runs left the filter, so retrying would loop forever: stop and say so.
            if remaining_ids.issuperset(attempted_ids):
                self.log.warning(
                    f"Stopped detaching flow runs from deleted branch '{branch_name}': "
                    f"{len(attempted_ids)} run(s) kept the branch tag"
                )
                break

        self.log.info(f"Detached {detached_total} flow run(s) from deleted branch '{branch_name}'")
