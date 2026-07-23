"""A human-friendly id reading a peer across the relationship is recomputed on merge and rebase.

When the id reads only the node's own name a peer rename never touches it. When the id reads the
peer across the relationship the peer rename has to schedule an HFID recompute like the other two
families. These assert the latter, the case a self-only id never exercises.
"""

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
from tests.helpers.merge_recompute.dataset import load_profile_schema, seed_branch

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_merge_submits_hfid_recompute_when_hfid_crosses_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db, cross_relationship_hfid=True)

    changed_nodes = 8
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="coalesced_merge_hfid",
        changed_nodes=changed_nodes,
        mutate_target="branch",
        mutate_kind="peer",
    )

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

    # The peer rename reaches the human-friendly id because the id reads the peer across the
    # relationship, so the merge coalesces one HFID recompute alongside the other two families.
    assert len(computed) == 1
    assert len(display) == 1
    assert len(hfid) == 1

    # A merge recomputes on the destination branch.
    assert computed[0]["parameters"]["branch_name"] == default_branch.name
    assert display[0]["parameters"]["branch_name"] == default_branch.name
    assert hfid[0]["parameters"]["branch_name"] == default_branch.name


async def test_rebase_submits_hfid_recompute_when_hfid_crosses_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db, cross_relationship_hfid=True)

    changed_nodes = 6
    # Rebase replays the default branch's intervening changes, so the peers are mutated on default.
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="coalesced_rebase_hfid",
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
    assert len(hfid) == 1

    # A rebase recomputes on the user branch, not the destination.
    assert computed[0]["parameters"]["branch_name"] == seeded.branch_name
    assert display[0]["parameters"]["branch_name"] == seeded.branch_name
    assert hfid[0]["parameters"]["branch_name"] == seeded.branch_name
