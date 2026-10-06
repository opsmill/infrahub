from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind, RepositoryDeliveryFailureCause, RepositoryDeliveryStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.proposed_change.constants import ProposedChangeState
from tests.helpers.graphql import graphql

from .conftest import (
    DELIVERED_COMMIT,
    DELIVERY_ATTRIBUTES,
    ERROR,
    FAILURE_CAUSE,
    HELD_REGENERATION,
    LAST_ABANDONMENT,
    LAST_DELIVERED_COMMIT,
    PROGRESS,
    QUEUE,
    REVERTED,
    STATUS,
    pending_merge,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.database import InfrahubDatabase

    from .conftest import StoreUnderTest

BRANCH_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"

BRANCH_VALUES: dict[str, Any] = {
    STATUS: RepositoryDeliveryStatus.ACTION_REQUIRED.value,
    FAILURE_CAUSE: RepositoryDeliveryFailureCause.PERMISSION.value,
    ERROR: "remote: written on a branch",
    QUEUE: {"version": 7, "entries": [], "written_on": "branch"},
    HELD_REGENERATION: {"next_hold_seq": 7, "written_on": "branch"},
    LAST_ABANDONMENT: {"written_on": "branch"},
    LAST_DELIVERED_COMMIT: BRANCH_COMMIT,
    REVERTED: {"written_on": "branch"},
    PROGRESS: {"written_on": "branch"},
}

PROPOSED_CHANGE_DIFF_QUERY = """
query ($branch: String, $proposed_change_id: String) {
    DiffTree(branch: $branch, proposed_change_id: $proposed_change_id) {
        num_conflicts
        nodes {
            uuid
            attributes { name }
            relationships { name }
        }
    }
}
"""


async def _create_tag(db: InfrahubDatabase, branch: Branch, name: str) -> Node:
    tag = await Node.init(db=db, schema=InfrahubKind.TAG, branch=branch)
    await tag.new(db=db, name=name)
    await tag.save(db=db)
    return tag


async def _open_proposed_change(db: InfrahubDatabase, default_branch: Branch, source_branch: Branch) -> Node:
    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE, branch=default_branch)
    await proposed_change.new(
        db=db,
        name=f"merge {source_branch.name}",
        source_branch=source_branch.name,
        destination_branch=default_branch.name,
        state=ProposedChangeState.OPEN.value,
    )
    await proposed_change.save(db=db)
    return proposed_change


async def _get_repository(db: InfrahubDatabase, branch: Branch, repository_id: str) -> Node:
    return await NodeManager.get_one(
        db=db, id=repository_id, kind=InfrahubKind.REPOSITORY, branch=branch, raise_on_error=True
    )


async def _write_on_branch(db: InfrahubDatabase, branch: Branch, repository_id: str, tag: Node) -> None:
    """Write every delivery attribute on the branch, with a tag as an ordinary change that a diff and a merge carry."""
    repository = await _get_repository(db=db, branch=branch, repository_id=repository_id)
    for name, value in BRANCH_VALUES.items():
        repository.get_attribute(name=name).value = value
    await repository.get_relationship(name="tags").update(db=db, data=[tag])
    await repository.save(db=db)


async def _delivery_values(db: InfrahubDatabase, branch: Branch, repository_id: str) -> dict[str, Any]:
    repository = await _get_repository(db=db, branch=branch, repository_id=repository_id)
    return {name: repository.get_attribute(name=name).value for name in DELIVERY_ATTRIBUTES}


def _changed_fields(diff: EnrichedDiffRoot) -> dict[str, set[str]]:
    return {
        node.uuid: {attribute.name for attribute in node.attributes}
        | {relationship.name for relationship in node.relationships}
        for node in diff.nodes
    }


async def test_a_delivery_state_written_on_either_branch_stays_out_of_the_diff_and_the_proposed_change(
    db: InfrahubDatabase, default_branch: Branch, subject: StoreUnderTest
) -> None:
    tag = await _create_tag(db=db, branch=default_branch, name="branch-tag")
    branch = await create_branch(db=db, branch_name="delivery-diff")
    proposed_change = await _open_proposed_change(db=db, default_branch=default_branch, source_branch=branch)
    await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
    await _write_on_branch(db=db, branch=branch, repository_id=subject.repository_id, tag=tag)

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    branch_diff = await diff_repository.get_one(diff_branch_name=branch.name, diff_id=diff_metadata.uuid)
    base_diff = await diff_repository.get_one(diff_branch_name=default_branch.name, diff_id=diff_metadata.partner_uuid)

    assert (await subject.read()).status == RepositoryDeliveryStatus.PENDING
    assert await _delivery_values(db=db, branch=branch, repository_id=subject.repository_id) == BRANCH_VALUES
    assert diff_metadata.proposed_change_id == proposed_change.id
    assert _changed_fields(branch_diff) == {subject.repository_id: {"tags"}}
    assert _changed_fields(base_diff) == {}
    assert branch_diff.get_all_conflicts() == {}

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=PROPOSED_CHANGE_DIFF_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": branch.name, "proposed_change_id": proposed_change.id},
    )

    assert result.errors is None
    assert result.data == {
        "DiffTree": {
            "num_conflicts": 0,
            "nodes": [{"uuid": subject.repository_id, "attributes": [], "relationships": [{"name": "tags"}]}],
        }
    }


async def test_a_delivery_state_written_on_a_branch_is_never_merged(
    db: InfrahubDatabase, default_branch: Branch, subject: StoreUnderTest
) -> None:
    await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
    default_state = await subject.read()
    default_values = await _delivery_values(db=db, branch=default_branch, repository_id=subject.repository_id)
    tag = await _create_tag(db=db, branch=default_branch, name="merged-tag")
    branch = await create_branch(db=db, branch_name="delivery-merge")
    await _write_on_branch(db=db, branch=branch, repository_id=subject.repository_id, tag=tag)

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await diff_merger.merge_graph(at=Timestamp())

    merged = await _get_repository(db=db, branch=default_branch, repository_id=subject.repository_id)
    assert {
        relationship.peer_id for relationship in await merged.get_relationship(name="tags").get_relationships(db=db)
    } == {tag.id}
    assert default_values[STATUS] == RepositoryDeliveryStatus.PENDING.value
    assert await _delivery_values(db=db, branch=default_branch, repository_id=subject.repository_id) == default_values
    assert await subject.read() == default_state
    assert await _delivery_values(db=db, branch=branch, repository_id=subject.repository_id) == BRANCH_VALUES


async def test_a_branch_created_while_a_push_is_pending_reads_a_copy_that_the_store_never_returns(
    db: InfrahubDatabase, default_branch: Branch, subject: StoreUnderTest
) -> None:
    await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
    branch = await create_branch(db=db, branch_name="delivery-copy")
    copy_at_fork = await _delivery_values(db=db, branch=branch, repository_id=subject.repository_id)

    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    await subject.store.settle_delivery(
        repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=DELIVERED_COMMIT
    )
    copy_after_delivery = await _delivery_values(db=db, branch=branch, repository_id=subject.repository_id)
    branch_repository = await _get_repository(db=db, branch=branch, repository_id=subject.repository_id)
    branch_repository.get_attribute(name=STATUS).value = RepositoryDeliveryStatus.ACTION_REQUIRED.value
    await branch_repository.save(db=db, fields=[STATUS])

    for copy in (copy_at_fork, copy_after_delivery):
        assert (copy[STATUS], [entry["entry_id"] for entry in copy[QUEUE]["entries"]], copy[LAST_DELIVERED_COMMIT]) == (
            RepositoryDeliveryStatus.PENDING.value,
            ["e1"],
            None,
        )
    changed_copy = await _delivery_values(db=db, branch=branch, repository_id=subject.repository_id)
    assert changed_copy[STATUS] == RepositoryDeliveryStatus.ACTION_REQUIRED.value
    delivered = await subject.read()
    assert (delivered.status, delivered.queue.entries, delivered.last_delivered_commit) == (
        RepositoryDeliveryStatus.NONE,
        (),
        DELIVERED_COMMIT,
    )
    assert await subject.store.pending_repository_ids() == frozenset()
