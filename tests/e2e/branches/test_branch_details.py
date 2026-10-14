"""Port of frontend/app/tests/e2e/branches/branch-details.spec.ts.

Branch details view for the default branch (main) and a non-default branch
(`atl1-delete-upstream`, created by the demo-data branch scenarios — hence the
data_scenario_branches dependency on the non-default tests).

Extended beyond the TS port: the Artifacts tab of a throwaway branch where one
interface of ``atl1-edge1`` differs from main, so the regenerated
``startup-config`` artifact diff hides the unchanged lines around the change
behind separators that expand them. The artifact comes from the demo-edge
repository, hence the ``demo_edge_repo`` dependency.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
from constants import ADMIN_API_TOKEN
from helpers import Deadline, generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import ScenarioBranchesHandle
    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from playwright.async_api import Page

NON_DEFAULT_BRANCH = "atl1-delete-upstream"

ARTIFACT_NAME = "startup-config"
ARTIFACT_DEVICE_NAME = "atl1-edge1"
CHANGED_INTERFACE_NAME = "Ethernet5"
CHANGED_DESCRIPTION = "e2e artifact diff"
# The config block of the interface rendered right before the changed one, more than the
# 3 context lines above the change but within the 20 lines one expand step reveals.
HIDDEN_LINE = "interface Ethernet4"


class TestBranchDetailsDefaultBranch:
    async def test_display_branch_name_and_default_badge(self, admin_page: Page) -> None:
        await admin_page.goto("/branches/main")

        # Header
        await expect(admin_page.get_by_role("heading", name="main")).to_be_visible()
        await expect(admin_page.get_by_text("default", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("button", name="View node metadata")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Copy branch name")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Refresh data")).to_be_visible()

        # Already working on main, so there is nothing to switch to
        await expect(admin_page.get_by_test_id("branch-working-notice")).to_be_visible()
        await expect(admin_page.get_by_test_id("switch-to-viewed-branch")).not_to_be_visible()

        # Tabs
        await expect(admin_page.get_by_role("navigation", name="Tabs")).not_to_be_visible()

        # Branch attributes
        await expect(admin_page.get_by_text("Name", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Sync with Git", exact=True)).to_be_visible()

        # Non-default specific attributes should NOT be visible
        await expect(admin_page.get_by_text("Schema differs from default branch")).not_to_be_visible()
        await expect(admin_page.get_by_text("Last rebase")).not_to_be_visible()

        # All action buttons should be not visible
        await expect(admin_page.get_by_role("button", name="Merge")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Rebase")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Validate")).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="Delete")).not_to_be_visible()
        await expect(admin_page.get_by_role("link", name="Propose change")).not_to_be_visible()
        await expect(admin_page.get_by_test_id("branch-tasks-card")).not_to_be_visible()

        await expect(admin_page.get_by_test_id("branch-repositories-card")).not_to_be_visible()


class TestBranchDetailsNonDefaultBranch:
    async def test_display_branch_name_and_no_default_badge(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        # Header
        await expect(admin_page.get_by_role("heading", name=NON_DEFAULT_BRANCH)).to_be_visible()
        await expect(admin_page.get_by_text("default", exact=True)).not_to_be_visible()
        await expect(admin_page.get_by_role("button", name="View node metadata")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Copy branch name")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Refresh data")).to_be_visible()

        # Branch attributes
        await expect(admin_page.get_by_text("Name", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Sync with Git", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Schema differs from default branch", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("Last rebase", exact=True)).to_be_visible()

        # Tabs navigation should be visible with all tabs
        tabs_nav = admin_page.get_by_role("navigation", name="Tabs")
        await expect(tabs_nav).to_be_visible()
        await expect(tabs_nav.get_by_text("Details")).to_be_visible()
        await expect(tabs_nav.get_by_text("Data")).to_be_visible()
        await expect(tabs_nav.get_by_text("Files")).to_be_visible()
        await expect(tabs_nav.get_by_text("Artifacts")).to_be_visible()
        await expect(tabs_nav.get_by_text("Schema")).to_be_visible()

        # All action buttons should be visible
        await expect(admin_page.get_by_role("button", name="Merge")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="Propose change")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Rebase")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Validate")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Delete", exact=True)).to_be_visible()
        await expect(admin_page.get_by_test_id("branch-tasks-card")).to_be_visible()

    async def test_navigate_between_tabs(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        tabs_nav = admin_page.get_by_role("navigation", name="Tabs")
        await tabs_nav.get_by_text("Data").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/data"))

        await tabs_nav.get_by_text("Files").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/files"))

        await tabs_nav.get_by_text("Artifacts").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/artifacts"))

        await tabs_nav.get_by_text("Schema").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}/schema"))

        # Going back to the Details tab (first tab) returns to the bare branch URL.
        await tabs_nav.get_by_text("Details").click()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{NON_DEFAULT_BRANCH}$"))

    async def test_switch_to_viewed_branch_from_mismatch_notice(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        await expect(admin_page.get_by_test_id("branch-mismatch-notice")).to_contain_text(
            f"You're viewing {NON_DEFAULT_BRANCH} but working on main"
        )

        await admin_page.get_by_test_id("switch-to-viewed-branch").click()

        await expect(admin_page.get_by_test_id("branch-working-notice")).to_be_visible()
        await expect(admin_page.get_by_test_id("branch-mismatch-notice")).not_to_be_visible()
        await expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text(NON_DEFAULT_BRANCH)

    async def test_display_node_metadata(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle
    ) -> None:
        await admin_page.goto(f"/branches/{NON_DEFAULT_BRANCH}")

        await admin_page.get_by_role("button", name="View node metadata").click()

        await expect(admin_page.get_by_text("Created at")).to_be_visible()
        await expect(admin_page.get_by_text("Created by")).to_be_visible()
        await expect(admin_page.get_by_text("Updated at")).to_be_visible()
        await expect(admin_page.get_by_text("Updated by")).to_be_visible()


class TestBranchDetailsTasks:
    @pytest.fixture
    async def fresh_branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        """A branch created for this test, so validating it leaves the shared demo branches untouched."""
        name = generate_random_branch_name("tasks-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_validate_task_row_opens_task_details(self, admin_page: Page, fresh_branch: str) -> None:
        await admin_page.goto(f"/branches/{quote(fresh_branch, safe='')}")

        await admin_page.get_by_role("button", name="Validate").click()
        await expect(admin_page.locator("#alert-success")).to_contain_text("Branch validation requested!")

        tasks_card = admin_page.get_by_test_id("branch-tasks-card")
        validate_row = tasks_card.get_by_role("row").filter(has_text="Validate")
        await expect(validate_row.first).to_be_visible()

        await validate_row.first.get_by_role("link").click()
        await expect(admin_page).to_have_url(re.compile(r"/tasks/[0-9a-f-]+"))


class TestBranchDetailsSlashName:
    @pytest.fixture
    async def slash_branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        """A branch whose name contains a slash, created via the API and removed afterwards."""
        name = generate_random_branch_name("feat/slash-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_opens_detail_page_from_branches_list(self, admin_page: Page, slash_branch: str) -> None:
        await admin_page.goto("/branches")
        await admin_page.get_by_role("link", name=slash_branch, exact=True).click()

        await expect(admin_page.get_by_role("heading", name=slash_branch)).to_be_visible()
        await expect(admin_page.get_by_role("navigation", name="Tabs")).to_be_visible()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{re.escape(quote(slash_branch, safe=''))}$"))

    async def test_navigates_to_path_based_tab(self, admin_page: Page, slash_branch: str) -> None:
        await admin_page.goto(f"/branches/{quote(slash_branch, safe='')}")

        await admin_page.get_by_role("navigation", name="Tabs").get_by_text("Data").click()

        await expect(admin_page.get_by_role("heading", name=slash_branch)).to_be_visible()
        await expect(admin_page).to_have_url(re.compile(rf"/branches/{re.escape(quote(slash_branch, safe=''))}/data"))


class TestBranchDetailsArtifactDiff:
    @pytest.fixture
    async def startup_config(self, infrahub_client: InfrahubClient, demo_edge_repo: None) -> InfrahubNode:
        """The device's startup-config artifact on main, once generated after the repository sync."""
        device = await infrahub_client.get(kind="InfraDevice", name__value=ARTIFACT_DEVICE_NAME)
        deadline = Deadline(f"the {ARTIFACT_NAME} artifact of {ARTIFACT_DEVICE_NAME} to be generated", timeout=300)
        while True:
            artifacts = await infrahub_client.filters(
                kind="CoreArtifact", name__value=ARTIFACT_NAME, object__ids=[device.id]
            )
            if artifacts and artifacts[0].status.value == "Ready":
                return artifacts[0]
            await deadline.tick(pause=2)

    @pytest.fixture
    async def artifact_branch(self, branch_api: BranchAPI, startup_config: InfrahubNode) -> AsyncGenerator[str, None]:
        """A branch cut after main's artifact exists, so the branch starts from the same content."""
        name = generate_random_branch_name("artifact-diff-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_expands_the_lines_hidden_around_a_change(
        self,
        admin_page: Page,
        infrahub_address: str,
        infrahub_client: InfrahubClient,
        startup_config: InfrahubNode,
        artifact_branch: str,
    ) -> None:
        device = await infrahub_client.get(kind="InfraDevice", name__value=ARTIFACT_DEVICE_NAME, branch=artifact_branch)
        interface = await infrahub_client.get(
            kind="InfraInterfaceL3",
            branch=artifact_branch,
            device__ids=[device.id],
            name__value=CHANGED_INTERFACE_NAME,
        )
        interface.description.value = CHANGED_DESCRIPTION
        await interface.save()

        response = await admin_page.request.post(
            f"{infrahub_address}/api/artifact/generate/{startup_config.definition.id}",
            params={"branch": artifact_branch},
            headers={"X-INFRAHUB-KEY": ADMIN_API_TOKEN},
            data={"nodes": [startup_config.id]},
        )
        assert response.ok, await response.text()

        deadline = Deadline(f"the {ARTIFACT_NAME} artifact to be regenerated on {artifact_branch}")
        while True:
            branch_artifact = await infrahub_client.get(
                kind="CoreArtifact", id=startup_config.id, branch=artifact_branch
            )
            if (
                branch_artifact.status.value == "Ready"
                and branch_artifact.checksum.value != startup_config.checksum.value
            ):
                break
            await deadline.tick(pause=1)

        await admin_page.goto(f"/branches/{artifact_branch}/artifacts")
        artifact_diff = admin_page.locator(f"id={startup_config.id}")
        await artifact_diff.get_by_text(f"{ARTIFACT_DEVICE_NAME} - {ARTIFACT_NAME}").click()

        # Only the change and its context are displayed, under a separator for the lines above
        await expect(artifact_diff.get_by_text(f"description {CHANGED_DESCRIPTION}")).to_be_visible()
        await expect(artifact_diff.get_by_text(re.compile(r"^@@ -\d+,\d+ \+\d+,\d+ @@$"))).to_be_visible()
        await expect(artifact_diff.get_by_text(HIDDEN_LINE, exact=True)).to_have_count(0)

        await artifact_diff.get_by_role("button", name="Expand 20 lines up").click()

        await expect(artifact_diff.get_by_text(HIDDEN_LINE, exact=True).first).to_be_visible()
