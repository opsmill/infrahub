"""Port of frontend/app/tests/e2e/objects/artifact-definition.spec.ts.

/objects/CoreArtifactDefinition page (as Admin): navigate to the demo-edge
repo's "Startup Config for Edge devices" artifact definition via the breadcrumb
and trigger artifact generation. The artifact definitions come from the
demo-edge Git repository, so this depends on the `demo_edge_repo` fixture (which
pulls in infrastructure_data). The TS spec ran with storageState ADMIN ->
admin_page.

Extended beyond the TS port: before generating, ``atl1-core1`` (a core router,
not an artifact target) is added to the definition's ``edge_router`` target
group, so the same Generate pass must produce an artifact for the new member;
the device is then removed from the group and a second Generate pass must
delete its artifact instead of leaving it behind as a stale copy. Group
membership is net unchanged when the test completes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import Deadline
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from playwright.async_api import Page

DEVICE_NAME = "atl1-core1"
TARGET_GROUP_NAME = "edge_router"
ARTIFACT_NAME = "startup-config"


async def _startup_config_artifacts(client: InfrahubClient, device_id: str) -> list[InfrahubNode]:
    artifacts = await client.filters(kind="CoreArtifact", object__ids=[device_id])
    return [artifact for artifact in artifacts if artifact.name.value == ARTIFACT_NAME]


@pytest.mark.usefixtures("demo_edge_repo")
class TestArtifactDefinitionPage:
    async def test_should_generate_artifacts_successfully(
        self, admin_page: Page, infrahub_client: InfrahubClient
    ) -> None:
        # make a device that is not an edge router an artifact target, so this
        # Generate pass also has a new member to produce an artifact for
        device = await infrahub_client.get(kind="InfraDevice", name__value=DEVICE_NAME)
        group = await infrahub_client.get(kind="CoreStandardGroup", name__value=TARGET_GROUP_NAME, include=["members"])
        assert device.id not in {peer.id for peer in group.members.peers}
        assert not await _startup_config_artifacts(infrahub_client, device.id)
        await group.add_relationships(relation_to_update="members", related_nodes=[device.id])

        await admin_page.goto("/objects/CoreArtifactDefinition")
        breadcrumb = admin_page.get_by_test_id("breadcrumb-navigation")
        await expect(breadcrumb.get_by_role("link", name="Artifact Definition")).to_be_visible()

        await admin_page.get_by_role("link", name="Startup Config for Edge devices").click()
        await expect(breadcrumb.get_by_role("link", name="Artifact Definition")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Startup Config for Edge devices")).to_be_visible()

        await expect(admin_page.get_by_role("button", name="Generate")).not_to_be_disabled()
        await admin_page.get_by_role("button", name="Generate").click()
        await expect(admin_page.get_by_text("Artifacts generated")).to_be_visible()

        # the generation pass produces an artifact for the group's new member
        deadline = Deadline(f"the {ARTIFACT_NAME} artifact of {DEVICE_NAME} to be generated")
        while not any(
            artifact.status.value == "Ready" for artifact in await _startup_config_artifacts(infrahub_client, device.id)
        ):
            await deadline.tick()

        # once the device leaves the group, a generation pass deletes its
        # artifact instead of leaving a stale copy behind
        await group.remove_relationships(relation_to_update="members", related_nodes=[device.id])
        await admin_page.get_by_role("button", name="Generate").click()
        await expect(admin_page.get_by_text("Artifacts generated").first).to_be_visible()

        deadline = Deadline(
            f"the {ARTIFACT_NAME} artifact of {DEVICE_NAME} to be deleted "
            f"after the device left the {TARGET_GROUP_NAME} group"
        )
        while await _startup_config_artifacts(infrahub_client, device.id):
            await deadline.tick()
