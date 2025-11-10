from __future__ import annotations

from dataclasses import dataclass, field

from prefect import task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow

from .models import HFIDTriggerDefinition


@dataclass
class BranchScope:
    name: str
    out_of_scope: list[str] = field(default_factory=list)


@task(
    name="gather-trigger-hfid",
    cache_policy=NONE,
)
async def gather_trigger_hfid(
    db: InfrahubDatabase | None = None,  # noqa: ARG001 Needed to have a common function signature for gathering functions
) -> list[HFIDTriggerDefinition]:
    log = get_run_logger()

    # Build a list of all branches to process based on which branch is different from main
    branches_with_diff_from_main = registry.get_altered_schema_branches()
    branches_to_process: list[BranchScope] = [BranchScope(name=branch) for branch in branches_with_diff_from_main]
    branches_to_process.append(BranchScope(name=registry.default_branch, out_of_scope=branches_with_diff_from_main))

    triggers: list[HFIDTriggerDefinition] = []

    for branch in branches_to_process:
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        branch_triggers = HFIDTriggerDefinition.from_schema_hfids(
            branch=branch.name,
            hfids=schema_branch.hfids,
            branches_out_of_scope=branch.out_of_scope,
        )
        log.info(f"Generating {len(branch_triggers)} HFID trigger for {branch.name} (except {branch.out_of_scope})")

        triggers.extend(branch_triggers)

    return triggers
