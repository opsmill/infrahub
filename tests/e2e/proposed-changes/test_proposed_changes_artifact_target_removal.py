"""Artifact cleanup when a target leaves the group of its artifact definition.

Reproduction scenario (API-driven, no browser):

1. The demo-edge repository defines the "Startup Config for Edge devices"
   artifact definition targeting the ``edge_router`` group. ``atl1-core1`` is a
   core router, so it is not a member and has no startup-config artifact.
2. A first proposed change adds ``atl1-core1`` to ``edge_router`` and is merged:
   the post-merge artifact pipeline generates a startup-config artifact for the
   device on ``main``.
3. A second proposed change removes ``atl1-core1`` from ``edge_router`` and is
   merged: the device is no longer a target, so its startup-config artifact must
   be removed from ``main``.

The final assertion currently fails: the post-merge artifact regeneration only
iterates the group's current members, so the artifact of a removed member is
left behind on ``main`` as a stale copy.

The test merges two proposed changes into main (data-taxonomy class (d)); the
two merges cancel each other out membership-wise, but the leftover artifact and
the merged proposed changes remain on main.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

DEVICE_NAME = "atl1-core1"
TARGET_GROUP_NAME = "edge_router"
ARTIFACT_NAME = "startup-config"

# The proposed-change merge mutation runs the whole merge synchronously within
# the GraphQL request, so it needs a far larger client timeout than the default.
MERGE_TIMEOUT_SECONDS = 900


async def _get_target_group(client: InfrahubClient, branch: str) -> InfrahubNode:
    return await client.get(
        kind="CoreStandardGroup",
        name__value=TARGET_GROUP_NAME,
        branch=branch,
        include=["members"],
    )


async def _target_group_member_ids(client: InfrahubClient, branch: str) -> set[str]:
    group = await _get_target_group(client, branch)
    return {peer.id for peer in group.members.peers}


async def _startup_config_artifacts(client: InfrahubClient, device_id: str) -> list[InfrahubNode]:
    """The startup-config artifacts attached to the device on main."""
    artifacts = await client.filters(kind="CoreArtifact", object__ids=[device_id])
    return [artifact for artifact in artifacts if artifact.name.value == ARTIFACT_NAME]


async def _open_proposed_change(client: InfrahubClient, name: str, source_branch: str) -> InfrahubNode:
    proposed_change = await client.create(
        kind="CoreProposedChange",
        data={"name": name, "source_branch": source_branch, "destination_branch": "main"},
    )
    await proposed_change.save()
    return proposed_change


async def _wait_for_checks_to_pass(client: InfrahubClient, proposed_change: InfrahubNode) -> None:
    """Wait until the proposed change's validators all completed, and assert none failed.

    The checks pipeline creates its validators asynchronously after the proposed
    change is created, so completion alone is not enough: an early poll could see
    only the first validators. The set must also be identical between two
    consecutive polls before it is trusted.
    """
    deadline = Deadline(f"all checks of proposed change '{proposed_change.name.value}' to complete", timeout=600)
    previous_ids: set[str] | None = None
    while True:
        validators = await client.filters(kind="CoreValidator", proposed_change__ids=[proposed_change.id])
        current_ids = {validator.id for validator in validators}
        if (
            validators
            and current_ids == previous_ids
            and all(validator.state.value == "completed" for validator in validators)
        ):
            break
        previous_ids = current_ids
        await deadline.tick(pause=5)

    # Mirror the merge gate: every validator except data integrity must succeed.
    failed = {
        validator.label.value: validator.conclusion.value
        for validator in validators
        if validator.typename != "CoreDataValidator" and validator.conclusion.value != "success"
    }
    assert not failed, f"proposed change '{proposed_change.name.value}' has failing checks: {failed}"


async def _merge_proposed_change(client: InfrahubClient, proposed_change: InfrahubNode) -> None:
    await client.execute_graphql(
        query="""
        mutation MergeProposedChange($id: String!) {
            CoreProposedChangeUpdate(data: { id: $id, state: { value: "merged" } }) {
                ok
            }
        }
        """,
        variables={"id": proposed_change.id},
        timeout=MERGE_TIMEOUT_SECONDS,
    )
    merged = await client.get(kind="CoreProposedChange", id=proposed_change.id)
    assert merged.state.value == "merged"


async def _propose_and_merge_membership_change(
    client: InfrahubClient, *, device_id: str, prefix: str, action: str
) -> None:
    """Change the device's target-group membership on a branch and merge it via a proposed change."""
    branch_name = generate_random_branch_name(prefix)
    await client.branch.create(branch_name=branch_name, sync_with_git=False)

    group = await _get_target_group(client, branch_name)
    if action == "add":
        await group.add_relationships(relation_to_update="members", related_nodes=[device_id])
    else:
        await group.remove_relationships(relation_to_update="members", related_nodes=[device_id])

    proposed_change = await _open_proposed_change(client, name=branch_name, source_branch=branch_name)
    await _wait_for_checks_to_pass(client, proposed_change)
    await _merge_proposed_change(client, proposed_change)


@pytest.mark.usefixtures("demo_edge_repo")
class TestArtifactTargetRemoval:
    async def test_artifact_is_removed_from_main_when_target_leaves_the_group(
        self, infrahub_client: InfrahubClient
    ) -> None:
        client = infrahub_client
        device = await client.get(kind="InfraDevice", name__value=DEVICE_NAME)

        # sanity: the core router is not an artifact target and has no startup-config artifact
        assert device.id not in await _target_group_member_ids(client, "main")
        assert not await _startup_config_artifacts(client, device.id)

        # proposed change 1: make the device an artifact target -> merged into main
        await _propose_and_merge_membership_change(client, device_id=device.id, prefix="pc-artifact-add-", action="add")
        assert device.id in await _target_group_member_ids(client, "main")

        # the post-merge pipeline generates the startup-config artifact for the new target on main
        deadline = Deadline(f"the {ARTIFACT_NAME} artifact of {DEVICE_NAME} to be generated on main", timeout=300)
        while not any(
            artifact.status.value == "Ready" for artifact in await _startup_config_artifacts(client, device.id)
        ):
            await deadline.tick(pause=5)

        # proposed change 2: the device is no longer an artifact target -> merged into main
        await _propose_and_merge_membership_change(
            client, device_id=device.id, prefix="pc-artifact-remove-", action="remove"
        )
        assert device.id not in await _target_group_member_ids(client, "main")

        # the artifact of the removed target must be cleaned up from main
        deadline = Deadline(
            f"the {ARTIFACT_NAME} artifact of {DEVICE_NAME} to be removed from main "
            f"after the device left the {TARGET_GROUP_NAME} group",
            timeout=300,
        )
        while await _startup_config_artifacts(client, device.id):
            await deadline.tick(pause=5)
