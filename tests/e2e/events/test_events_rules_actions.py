"""Port of frontend/app/tests/e2e/events/events-rules-actions.spec.ts.

Create and configure an Event with a Group Action: a Group action targeting the
`arista_devices` group, then a Node trigger on Device creation wired to that
action, plus a trigger match on the `Arista EOS` platform. The active test is
`test.fixme` in the source and is preserved as skipped; the second test was
fully commented out in the source and is not ported. Depends on data_topology
(it fills the `arista_devices` group membership; the `Arista EOS` platform
comes transitively).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import TopologyHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestEventRulesAndActions:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_topology: TopologyHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("events-rules-actions")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    @pytest.mark.skip(reason="fixme in the source; preserved as skipped.")
    async def test_create_and_configure_an_event_with_a_group_action(self, admin_page: Page, branch: str) -> None:
        # Create a Group action
        # Navigate to the Actions page
        await admin_page.goto(f"/objects/CoreAction?branch={branch}")
        # Configure Group action
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Group Action").click()
        await admin_page.get_by_role("textbox", name="Name *").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("add-to-group-arista_devices")
        await admin_page.get_by_role("combobox", name="Kind").click()
        await admin_page.get_by_role("option", name="Standard Group Core").click()
        await admin_page.get_by_role("combobox", name="Standard Group *").click()
        await admin_page.get_by_placeholder("Filter...").fill("arista")
        await admin_page.get_by_text("arista_devices").click()
        # Save screenshot Form
        await save_screenshot_for_docs(admin_page, "guides/events/grp_actions-form-creation")
        await admin_page.get_by_role("button", name="Save").click()
        await admin_page.get_by_role("link", name="add-to-group-arista_devices").click()
        # Save screenshot Details
        await expect(admin_page.get_by_text("Activities")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "guides/events/grp_actions-details")

        # Create a Node trigger
        # Navigate to the Triggers page
        await admin_page.goto(f"/objects/CoreTriggerRule?branch={branch}")
        # Configure Node trigger
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Node Trigger").click()
        await admin_page.get_by_role("textbox", name="Name *").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("new-arista-devices")
        await admin_page.get_by_role("combobox", name="Node Kind *").click()
        await admin_page.get_by_placeholder("Filter...").fill("device")
        await admin_page.get_by_text("Device Infra").click()
        await admin_page.get_by_role("combobox", name="Mutation Action *").click()
        await admin_page.get_by_role("option", name="created").click()
        await admin_page.get_by_role("combobox", name="Kind", exact=True).click()
        await admin_page.get_by_role("option", name="Group Action Core").click()
        await admin_page.get_by_role("combobox", name="Group Action *").click()
        await admin_page.get_by_text("add-to-group-arista_devices").click()
        # Save screenshot Form
        await save_screenshot_for_docs(admin_page, "guides/events/node-trigger-form-creation")
        await admin_page.get_by_role("button", name="Save").click()
        # Add Match to Node trigger
        await admin_page.get_by_role("link", name="new-arista-devices").click()
        await admin_page.get_by_role("link", name="Matches").click()
        await admin_page.get_by_test_id("open-relationship-form-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_text("Node Trigger Relationship").click()
        await admin_page.get_by_role("combobox", name="Relationship Name *").click()
        await admin_page.get_by_text("Platform").click()
        await admin_page.get_by_role("combobox", name="Peer").click()
        await admin_page.get_by_text("Arista EOS").click()
        # Save screenshot Match Form
        await save_screenshot_for_docs(admin_page, "guides/events/node-trigger-matches-form-creation")
        await admin_page.get_by_role("button", name="Save").click()
