"""Port of frontend/app/tests/e2e/triggers/triggers.spec.ts.

Node Trigger flow (serial): create a Node Trigger Rule (with a nested Group
Action + Standard Group created inline), then add an attribute match and a
relationship match to it.

Serial handling: the flow shares one branch (a class-scoped fixture) and the
trigger rule it creates in the first test. Every test depends on the SAME
fixtures (admin_page + branch), so pytest preserves their definition order. The
suite runs single-process.

Data dependency: the relationship-match step references the `atl1` site and the
skipped update step references the `AS174` ASN, both seeded by the demo data, so
the branch fixture depends on `infrastructure_data`.

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
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page


class TestNodeTrigger:
    @pytest.fixture(scope="class")
    def branch(
        self,
        infrahub_client: InfrahubClientSync,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("triggers-")
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_should_create_a_node_trigger(self, admin_page: Page, branch: str) -> None:
        # access form
        admin_page.goto(f"/objects/CoreTriggerRule?branch={branch}")
        admin_page.get_by_test_id("create-object-button").click()

        # fill and validate form
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_role("option", name="Node Trigger Rule Core").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test node trigger rule")
        admin_page.get_by_role("combobox", name="Node Kind *").click()
        admin_page.get_by_role("option", name="Device Infra").click()
        admin_page.get_by_role("combobox", name="Mutation Action *").click()
        admin_page.get_by_role("option", name="created").click()
        admin_page.get_by_role("combobox", name="Kind", exact=True).click()
        admin_page.get_by_role("option", name="Group Action Core").click()
        admin_page.get_by_role("combobox", name="Group Action *").click()
        admin_page.get_by_role("button", name="+ Add new Group Action").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test group action")
        admin_page.get_by_role("combobox", name="Kind").click()
        admin_page.get_by_role("option", name="Standard Group Core").click()
        admin_page.get_by_role("combobox", name="Standard Group *").click()
        admin_page.get_by_role("button", name="+ Add new Standard Group").click()
        admin_page.get_by_role("textbox", name="Name *").fill("test standard group")
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("StandardGroup created")).to_be_visible()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("GroupAction created")).to_be_visible()
        admin_page.get_by_role("button", name="Save").click()

        # ensure the creation is correct
        expect(admin_page.get_by_text("NodeTriggerRule created")).to_be_visible()
        expect(admin_page.get_by_role("link", name="test node trigger rule")).to_be_visible()

    def test_should_create_new_matches(self, admin_page: Page, branch: str) -> None:
        # access list view
        admin_page.goto(f"/objects/CoreTriggerRule?branch={branch}")

        # access the matches
        expect(admin_page.get_by_role("link", name="test node trigger rule")).to_be_visible()
        admin_page.get_by_role("link", name="test node trigger rule").click()
        expect(admin_page.get_by_text("Nametest node trigger rule")).to_be_visible()
        admin_page.get_by_role("link", name="Matches").click()
        expect(admin_page.get_by_text("No Node Trigger Match found")).to_be_visible()

        # create an attribute match
        admin_page.get_by_test_id("open-relationship-form-button").click()
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_role("option", name="Node Trigger Attribute Match").click()
        admin_page.get_by_role("combobox", name="Attribute Name *").click()
        admin_page.get_by_role("option", name="Name").locator("div").nth(1).click()
        expect(admin_page.get_by_role("combobox").filter(has_text="test node trigger rule")).to_be_visible()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Node attribute match created!")).to_be_visible()

        # create a relationship match
        admin_page.get_by_test_id("open-relationship-form-button").click()
        admin_page.get_by_role("combobox", name="Select an object type").click()
        admin_page.get_by_text("Node Trigger Relationship Match Core").click()
        admin_page.get_by_role("combobox", name="Relationship Name *").click()
        admin_page.get_by_role("option", name="Site").click()
        admin_page.get_by_role("combobox", name="Peer").click()
        admin_page.get_by_role("option", name="atl1").click()
        expect(admin_page.get_by_role("combobox").filter(has_text="test node trigger rule")).to_be_visible()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Node relationship match created!")).to_be_visible()

    @pytest.mark.skip(reason="`should update the matches` is test.fixme in the source; preserved as skipped.")
    def test_should_update_the_matches(self, admin_page: Page, branch: str) -> None:
        # update an attribute match
        # The current test id cannot be used for relationsip actions cell
        admin_page.get_by_test_id("actions-cell-18462734-cb04-6ee7-3350-c5155d7058b7").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        admin_page.get_by_role("combobox", name="Attribute Name *").click()
        admin_page.get_by_role("option", name="Description", exact=True).click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Node attribute match updated!")).to_be_visible()

        # update a relationship match
        # The current test id cannot be used for relationsip actions cell
        admin_page.get_by_test_id("actions-cell-18462759-93ce-7eb1-3357-c51adb1d668e").click()
        admin_page.get_by_role("menuitem", name="Edit").click()
        admin_page.get_by_role("combobox", name="Relationship Name *").click()
        admin_page.get_by_role("option", name="Asn").click()
        admin_page.get_by_role("combobox", name="Peer").click()
        admin_page.get_by_role("option", name="AS174").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("Node relationship match")).to_be_visible()
