"""Port of frontend/app/tests/e2e/triggers/triggers.spec.ts.

Node Trigger flow (serial): create a Node Trigger Rule (with a nested Group
Action + Standard Group created inline), then add an attribute match and a
relationship match to it.

Serial handling: the flow shares one branch (a class-scoped fixture) and the
trigger rule it creates in the first test. Every test depends on the SAME
fixtures (admin_page + branch) and the chain relies on pytest's default
definition-order collection (see the README's serial-specs gotcha). The suite
runs single-process.

Data dependency: the relationship-match step references the `atl1` site (seeded
by data_sites) and the skipped update step references the `AS174` ASN (seeded
via its org_registry dependency), so the branch fixture depends on `data_sites`.

The legacy spec navigated with a `?brach=` (sic) query param, so its objects —
including an ACTIVE node trigger wired to a group action — silently landed on
main and outlived the test. The typo is fixed here so the whole flow stays on
the throwaway branch and is removed with it.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestNodeTrigger:
    @pytest.fixture(scope="class")
    async def branch(
        self,
        infrahub_client: InfrahubClient,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("triggers-")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_should_create_a_node_trigger(self, admin_page: Page, branch: str) -> None:
        # access form
        await admin_page.goto(f"/objects/CoreTriggerRule?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        # fill and validate form
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Node Trigger Rule Core").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test node trigger rule")
        await admin_page.get_by_role("combobox", name="Node Kind *").click()
        await admin_page.get_by_role("option", name="Device Infra").click()
        await admin_page.get_by_role("combobox", name="Mutation Action *").click()
        await admin_page.get_by_role("option", name="created").click()
        await admin_page.get_by_role("combobox", name="Kind", exact=True).click()
        await admin_page.get_by_role("option", name="Group Action Core").click()
        await admin_page.get_by_role("combobox", name="Group Action *").click()
        await admin_page.get_by_role("button", name="+ Add new Group Action").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test group action")
        await admin_page.get_by_role("combobox", name="Kind").click()
        await admin_page.get_by_role("option", name="Standard Group Core").click()
        await admin_page.get_by_role("combobox", name="Standard Group *").click()
        await admin_page.get_by_role("button", name="+ Add new Standard Group").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test standard group")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("StandardGroup created")).to_be_visible()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("GroupAction created")).to_be_visible()
        await admin_page.get_by_role("button", name="Save").click()

        # ensure the creation is correct
        await expect(admin_page.get_by_text("NodeTriggerRule created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test node trigger rule")).to_be_visible()

    async def test_should_create_new_matches(self, admin_page: Page, branch: str) -> None:
        # access list view
        await admin_page.goto(f"/objects/CoreTriggerRule?branch={branch}")

        # access the matches
        await expect(admin_page.get_by_role("link", name="test node trigger rule")).to_be_visible()
        await admin_page.get_by_role("link", name="test node trigger rule").click()
        await expect(admin_page.get_by_text("Nametest node trigger rule")).to_be_visible()
        await admin_page.get_by_role("link", name="Matches").click()
        await expect(admin_page.get_by_text("No Node Trigger Match found")).to_be_visible()

        # create an attribute match
        await admin_page.get_by_test_id("open-relationship-form-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_role("option", name="Node Trigger Attribute Match").click()
        await admin_page.get_by_role("combobox", name="Attribute Name *").click()
        await admin_page.get_by_role("option", name="Name").locator("div").nth(1).click()
        await expect(admin_page.get_by_role("combobox").filter(has_text="test node trigger rule")).to_be_visible()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Node attribute match created!")).to_be_visible()

        # create a relationship match
        await admin_page.get_by_test_id("open-relationship-form-button").click()
        await admin_page.get_by_role("combobox", name="Select an object type").click()
        await admin_page.get_by_text("Node Trigger Relationship Match Core").click()
        await admin_page.get_by_role("combobox", name="Relationship Name *").click()
        await admin_page.get_by_role("option", name="Site").click()
        await admin_page.get_by_role("combobox", name="Peer").click()
        await admin_page.get_by_role("option", name="atl1").click()
        await expect(admin_page.get_by_role("combobox").filter(has_text="test node trigger rule")).to_be_visible()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Node relationship match created!")).to_be_visible()

    @pytest.mark.skip(reason="`should update the matches` is test.fixme in the source; preserved as skipped.")
    async def test_should_update_the_matches(self, admin_page: Page, branch: str) -> None:
        # update an attribute match
        # The current test id cannot be used for relationsip actions cell
        await admin_page.get_by_test_id("actions-cell-18462734-cb04-6ee7-3350-c5155d7058b7").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await admin_page.get_by_role("combobox", name="Attribute Name *").click()
        await admin_page.get_by_role("option", name="Description", exact=True).click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Node attribute match updated!")).to_be_visible()

        # update a relationship match
        # The current test id cannot be used for relationsip actions cell
        await admin_page.get_by_test_id("actions-cell-18462759-93ce-7eb1-3357-c51adb1d668e").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await admin_page.get_by_role("combobox", name="Relationship Name *").click()
        await admin_page.get_by_role("option", name="Asn").click()
        await admin_page.get_by_role("combobox", name="Peer").click()
        await admin_page.get_by_role("option", name="AS174").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Node relationship match")).to_be_visible()
