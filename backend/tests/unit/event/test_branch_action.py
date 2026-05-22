from __future__ import annotations

import uuid

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.events.branch_action import BranchDeletedEvent, BranchMergedEvent
from infrahub.events.models import EventMeta


def _make_meta() -> EventMeta:
    branch = Branch(name="test-branch-action-events", uuid=uuid.uuid4())
    return EventMeta(
        branch=branch,
        context=InfrahubContext.init(
            branch=branch,
            account=AccountSession(auth_type=AuthType.NONE, authenticated=False, account_id=""),
        ).to_event_context(),
    )


def test_branch_deleted_resource_without_proposed_change() -> None:
    event = BranchDeletedEvent(
        meta=_make_meta(),
        branch_name="feature",
        branch_id="branch-123",
        sync_with_git=True,
    )

    resource = event.get_resource()

    assert resource["prefect.resource.id"] == "infrahub.branch.feature"
    assert resource["infrahub.branch.id"] == "branch-123"
    assert resource["infrahub.branch.name"] == "feature"
    assert "infrahub.node.id" not in resource
    assert "infrahub.node.kind" not in resource
    assert "infrahub.branch.proposed_change_id" not in resource


def test_branch_deleted_resource_with_proposed_change_sets_primary_node() -> None:
    event = BranchDeletedEvent(
        meta=_make_meta(),
        branch_name="feature",
        branch_id="branch-123",
        sync_with_git=True,
        proposed_change_id="pc-456",
    )

    resource = event.get_resource()

    assert resource["infrahub.node.id"] == "pc-456"
    assert resource["infrahub.node.kind"] == InfrahubKind.PROPOSEDCHANGE
    assert resource["infrahub.branch.proposed_change_id"] == "pc-456"


def test_branch_deleted_related_excludes_proposed_change() -> None:
    event = BranchDeletedEvent(
        meta=_make_meta(),
        branch_name="feature",
        branch_id="branch-123",
        sync_with_git=True,
        proposed_change_id="pc-456",
    )

    related = event.get_related()

    pc_entries = [r for r in related if r.get("prefect.resource.id") == "pc-456"]
    assert pc_entries == []


def test_branch_merged_resource_without_proposed_change() -> None:
    event = BranchMergedEvent(
        meta=_make_meta(),
        branch_name="feature",
        branch_id="branch-123",
    )

    resource = event.get_resource()

    assert resource["prefect.resource.id"] == "infrahub.branch.feature"
    assert "infrahub.node.id" not in resource
    assert "infrahub.node.kind" not in resource


def test_branch_merged_resource_with_proposed_change_sets_primary_node() -> None:
    event = BranchMergedEvent(
        meta=_make_meta(),
        branch_name="feature",
        branch_id="branch-123",
        proposed_change_id="pc-456",
    )

    resource = event.get_resource()

    assert resource["infrahub.node.id"] == "pc-456"
    assert resource["infrahub.node.kind"] == InfrahubKind.PROPOSEDCHANGE


def test_branch_merged_related_excludes_proposed_change() -> None:
    event = BranchMergedEvent(
        meta=_make_meta(),
        branch_name="feature",
        branch_id="branch-123",
        proposed_change_id="pc-456",
    )

    related = event.get_related()

    pc_entries = [r for r in related if r.get("prefect.resource.id") == "pc-456"]
    assert pc_entries == []
