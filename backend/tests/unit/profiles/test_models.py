from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.profiles.models import ProfileRefreshTriggerDefinition
from infrahub.trigger.models import TriggerType
from infrahub.workflows.catalogue import PROFILE_REFRESH_PROCESS


async def test_profile_refresh_trigger_definition_from_profile_schema(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_attributes: SchemaRoot
) -> None:
    """Test creating a ProfileRefreshTriggerDefinition from a profile schema."""
    trigger_fields = ["description", "status"]

    trigger = ProfileRefreshTriggerDefinition.from_profile_schema(
        branch=default_branch.name,
        profile_kind="ProfileTestDevice",
        trigger_fields=trigger_fields,
        workflow=PROFILE_REFRESH_PROCESS,
    )

    assert trigger.name == "ProfileTestDevice::refresh"
    assert trigger.branch == default_branch.name
    assert trigger.profile_kind == "ProfileTestDevice"
    assert trigger.type == TriggerType.PROFILE

    assert trigger.generate_name() == "profile::main::ProfileTestDevice::refresh"

    assert trigger.trigger.events == {NodeUpdatedEvent.event_name}
    assert trigger.trigger.match == {"infrahub.node.kind": "ProfileTestDevice"}

    assert "prefect.resource.role" in trigger.trigger.match_related
    assert trigger.trigger.match_related["prefect.resource.role"] == [
        "infrahub.node.attribute_update",
        "infrahub.node.relationship_update",
    ]
    assert "infrahub.field.name" in trigger.trigger.match_related
    assert trigger.trigger.match_related["infrahub.field.name"] == trigger_fields

    assert "infrahub.branch.name" not in trigger.trigger.match


async def test_profile_refresh_trigger_definition_with_branch_scoping(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_attributes: SchemaRoot
) -> None:
    """Test creating a trigger with branch scoping for non-default branch."""
    trigger_fields = ["description", "status"]

    trigger = ProfileRefreshTriggerDefinition.from_profile_schema(
        branch="feature-branch",
        profile_kind="ProfileTestDevice",
        trigger_fields=trigger_fields,
        workflow=PROFILE_REFRESH_PROCESS,
    )

    assert trigger.branch == "feature-branch"
    assert trigger.generate_name() == "profile::feature-branch::ProfileTestDevice::refresh"

    assert "infrahub.branch.name" in trigger.trigger.match
    assert trigger.trigger.match["infrahub.branch.name"] == "feature-branch"


async def test_profile_refresh_trigger_definition_with_branches_out_of_scope(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_attributes: SchemaRoot
) -> None:
    """Test creating a trigger with branches out of scope."""
    trigger_fields = ["description", "status"]

    trigger = ProfileRefreshTriggerDefinition.from_profile_schema(
        branch=default_branch.name,
        profile_kind="ProfileTestDevice",
        trigger_fields=trigger_fields,
        workflow=PROFILE_REFRESH_PROCESS,
        branches_out_of_scope=["branch1", "branch2"],
    )

    assert "infrahub.branch.name" in trigger.trigger.match
    assert trigger.trigger.match["infrahub.branch.name"] == ["!branch1", "!branch2"]


async def test_profile_refresh_trigger_definition_actions(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_attributes: SchemaRoot
) -> None:
    """Test that the trigger has the correct workflow action."""
    trigger_fields = ["description", "status"]

    trigger = ProfileRefreshTriggerDefinition.from_profile_schema(
        branch=default_branch.name,
        profile_kind="ProfileTestDevice",
        trigger_fields=trigger_fields,
        workflow=PROFILE_REFRESH_PROCESS,
    )

    assert len(trigger.actions) == 1

    action = trigger.actions[0]
    assert action.workflow == PROFILE_REFRESH_PROCESS

    assert "branch_name" in action.parameters
    assert "profile_kind" in action.parameters
    assert "profile_id" in action.parameters
    assert "context" in action.parameters

    assert action.parameters["profile_kind"] == "ProfileTestDevice"
    assert action.parameters["branch_name"] == "{{ event.resource['infrahub.branch.name'] }}"
    assert action.parameters["profile_id"] == "{{ event.resource['infrahub.node.id'] }}"
