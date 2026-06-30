"""The merge and rebase post-process submit one coalesced recompute, not per-node fan-out."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch.tasks import merge_branch, rebase_branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.dependencies.registry import get_component_registry
from infrahub.workers.dependencies import build_cache, build_database, build_event_service, build_workflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, load_profile_schema, seed_branch

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_merge_submits_one_coalesced_recompute_per_target(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    changed_nodes = 8
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="coalesced_merge",
        changed_nodes=changed_nodes,
        mutate_target="branch",
        mutate_kind="peer",
    )

    # The merge flow loads the tracked diff, so it must be enriched under the branch tracking id first.
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=seeded.branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=seeded.branch)

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
    ):
        await merge_branch(branch=seeded.branch_name, context=context)

    computed = workflow_recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
    display = workflow_recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    hfid = workflow_recorder.get_submit_calls_for(HFID_PROCESS)

    # The mains' computed attribute and display label recompute once each over the union of changed
    # peers; the human-friendly id reads only the local name, so a peer change does not fan out to it.
    assert len(computed) == 1
    assert len(display) == 1
    assert hfid == []

    assert computed[0]["parameters"]["computed_attribute_kind"] == PROFILE_NODE_KIND
    assert computed[0]["parameters"]["computed_attribute_name"] == "summary"
    assert sorted(computed[0]["parameters"]["object_ids"]) == sorted(seeded.peer_ids)

    assert display[0]["parameters"]["target_kind"] == PROFILE_NODE_KIND
    assert sorted(display[0]["parameters"]["object_ids"]) == sorted(seeded.peer_ids)


async def test_rebase_submits_one_coalesced_recompute_per_target(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    changed_nodes = 6
    # Rebase replays the default branch's intervening changes, so the peers are mutated on default.
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="coalesced_rebase",
        changed_nodes=changed_nodes,
        mutate_target="default",
        mutate_kind="peer",
    )

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
    ):
        await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    computed = workflow_recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
    display = workflow_recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    hfid = workflow_recorder.get_submit_calls_for(HFID_PROCESS)

    assert len(computed) == 1
    assert len(display) == 1
    assert hfid == []

    # Rebase recomputes on the user branch, not the destination.
    assert computed[0]["parameters"]["branch_name"] == seeded.branch_name
    assert computed[0]["parameters"]["computed_attribute_kind"] == PROFILE_NODE_KIND
    assert sorted(computed[0]["parameters"]["object_ids"]) == sorted(seeded.peer_ids)

    assert display[0]["parameters"]["branch_name"] == seeded.branch_name
    assert display[0]["parameters"]["target_kind"] == PROFILE_NODE_KIND
    assert sorted(display[0]["parameters"]["object_ids"]) == sorted(seeded.peer_ids)
