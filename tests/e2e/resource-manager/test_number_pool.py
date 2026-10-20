"""Port of frontend/app/tests/e2e/resource-manager/number-pool.spec.ts.

Serial: create number pools for a generic schema, for a node schema and with a
scope and weighted ranges, check the browser and backend refusals, verify the
details, edit a pool's ranges while its node, attribute and scope stay read-only,
open the number-pool attribute-kind page, then create an InterfaceL3 that
allocates from a pool and verify the pool assignment.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the number pools it creates on that branch. Every test depends on the SAME
fixtures (admin_page + number_pool_branch) and the chain relies on pytest's
default definition-order collection (see the README's serial-specs gotcha).
Depends on data_sites (the atl1-core1 device); the InterfaceL3 schema and the
InfraService number pool come from the schema, not the data.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


CREATE_SCOPED_POOL = """
mutation CreateScopedNumberPool($name: String!) {
  CoreNumberPoolCreate(
    data: {
      name: { value: $name }
      node: { value: "InfraInterfaceL3" }
      node_attribute: { value: "speed" }
      allocation_scope: { value: ["device"] }
      ranges: [{ start: 100, end: 199 }]
    }
  ) {
    object {
      id
    }
  }
}
"""

NODE_SELECT = re.compile(r"Node$")
ATTRIBUTE_SELECT = re.compile(r"Attribute$")


def node_option(label: str, kind: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(label)} {re.escape(kind)}$")


async def open_number_pool_create_form(page: Page, branch: str) -> None:
    await page.goto(f"/resource-manager?branch={branch}")
    await page.get_by_test_id("create-object-button").click()
    await page.get_by_label("Select an object type").click()
    await page.get_by_role("option", name="Number Pool Core").click()
    await expect(page.get_by_text("Name *")).to_be_visible()


async def open_number_pool_edit_form(page: Page, branch: str, pool_name: str) -> None:
    await page.goto(f"/resource-manager?branch={branch}")
    await page.get_by_test_id("object-items").get_by_role("link", name=pool_name).click()
    header = page.locator("header").filter(has=page.get_by_role("heading", level=1))
    await header.get_by_role("button", name="Actions").click()
    await page.get_by_role("menuitem", name="Edit").click()
    await expect(page.get_by_text("What it allocates")).to_be_visible()


async def expect_range_rows(page: Page, rows: list[tuple[str, str, str]]) -> None:
    for index, (start, end, weight) in enumerate(rows, start=1):
        await expect(page.get_by_label(f"Start of range {index}")).to_have_value(start)
        await expect(page.get_by_label(f"End of range {index}")).to_have_value(end)
        await expect(page.get_by_label(f"Weight of range {index}")).to_have_value(weight)
    await expect(page.get_by_label(f"Start of range {len(rows) + 1}")).to_have_count(0)


class TestNumberPool:
    @pytest.fixture(scope="class")
    async def number_pool_branch(
        self, infrahub_client: InfrahubClient, data_sites: SitesHandle
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("number-pool")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_create_number_pool_for_generic_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await expect(admin_page.get_by_text("Name *")).to_be_visible()
        await admin_page.get_by_label("Name *").fill("number pool test for generic")
        await admin_page.get_by_role("button", name=NODE_SELECT).click()
        await expect(admin_page.get_by_role("option", name=node_option("Interface", "InfraInterface"))).to_be_visible()
        await expect(
            admin_page.get_by_role("option", name=node_option("Artifact Check", "CoreArtifactCheck"))
        ).to_be_visible()
        await admin_page.get_by_role("option", name=node_option("Interface", "InfraInterface")).click()
        await admin_page.get_by_role("button", name=ATTRIBUTE_SELECT).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_label("Start of range 1").fill("1")
        await admin_page.get_by_label("End of range 1").fill("10")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_create_number_pool_for_node_schema(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Number Pool Core").click()
        await admin_page.get_by_label("Name *").fill("number pool test for node")
        await admin_page.get_by_role("button", name=NODE_SELECT).click()
        await admin_page.get_by_role("option", name=node_option("Interface L3", "InfraInterfaceL3")).click()
        await admin_page.get_by_role("button", name=ATTRIBUTE_SELECT).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_label("Start of range 1").fill("11")
        await admin_page.get_by_label("End of range 1").fill("20")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

    async def test_create_scoped_number_pool_with_weighted_ranges(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        await open_number_pool_create_form(admin_page, number_pool_branch)
        await admin_page.get_by_label("Name *").fill("number pool test scoped")
        await admin_page.get_by_role("button", name=NODE_SELECT).click()
        await admin_page.get_by_role("option", name=node_option("Interface L3", "InfraInterfaceL3")).click()
        await admin_page.get_by_role("button", name=ATTRIBUTE_SELECT).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_role("button", name="Add a relationship or attribute").click()
        await admin_page.get_by_role("option", name="Device").click()
        await admin_page.keyboard.press("Escape")
        await admin_page.get_by_label("Start of range 1").fill("100")
        await admin_page.get_by_label("End of range 1").fill("199")
        await admin_page.get_by_label("Weight of range 1").fill("10")
        await admin_page.get_by_role("button", name="Add range").click()
        await admin_page.get_by_label("Start of range 2").fill("300")
        await admin_page.get_by_label("End of range 2").fill("399")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool created")).to_be_visible()

        await open_number_pool_edit_form(admin_page, number_pool_branch, "number pool test scoped")
        await expect_range_rows(admin_page, [("100", "199", "10"), ("300", "399", "")])

    async def test_create_number_pool_flags_overlapping_ranges(self, admin_page: Page, number_pool_branch: str) -> None:
        await open_number_pool_create_form(admin_page, number_pool_branch)
        await admin_page.get_by_label("Name *").fill("number pool test overlap")
        await admin_page.get_by_role("button", name=NODE_SELECT).click()
        await admin_page.get_by_role("option", name=node_option("Interface L3", "InfraInterfaceL3")).click()
        await admin_page.get_by_role("button", name=ATTRIBUTE_SELECT).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_label("Start of range 1").fill("100")
        await admin_page.get_by_label("End of range 1").fill("199")
        await admin_page.get_by_role("button", name="Add range").click()
        await admin_page.get_by_label("Start of range 2").fill("150")
        await admin_page.get_by_label("End of range 2").fill("250")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("Overlaps 150 – 250")).to_be_visible()
        await expect(admin_page.get_by_text("Overlaps 100 – 199")).to_be_visible()
        await expect(admin_page.get_by_text("Number pool created")).to_have_count(0)

    async def test_create_number_pool_shows_backend_refusal(self, admin_page: Page, number_pool_branch: str) -> None:
        await open_number_pool_create_form(admin_page, number_pool_branch)
        await admin_page.get_by_label("Name *").fill("number pool test for node")
        await admin_page.get_by_role("button", name=NODE_SELECT).click()
        await admin_page.get_by_role("option", name=node_option("Interface L3", "InfraInterfaceL3")).click()
        await admin_page.get_by_role("button", name=ATTRIBUTE_SELECT).click()
        await admin_page.get_by_role("option", name="Speed").click()
        await admin_page.get_by_label("Start of range 1").fill("1")
        await admin_page.get_by_label("End of range 1").fill("5")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_role("alert").filter(has_text="uniqueness")).to_be_visible()
        await expect(admin_page.get_by_label("End of range 1")).to_have_value("5")

    async def test_header_for_user_created_pool(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_test_id("object-items").get_by_role("link", name="number pool test for generic").click()

        header = admin_page.locator("header").filter(has=admin_page.get_by_role("heading", level=1))
        await expect(header.get_by_role("heading", level=1, name="number pool test for generic")).to_be_visible()
        await expect(header.get_by_text("Managed by")).to_have_count(0)
        await expect(header.get_by_text("Allocates to")).to_be_visible()
        await expect(header.get_by_role("button", name="InfraInterface", exact=True)).to_be_visible()

        await header.get_by_role("button", name="Actions").click()
        await expect(admin_page.get_by_role("menuitem", name="Edit")).not_to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Delete")).not_to_have_attribute("aria-disabled", "true")

    async def test_update_form_should_not_include_node_and_attribute_selects(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        await open_number_pool_edit_form(admin_page, number_pool_branch, "number pool test for generic")
        await expect(admin_page.get_by_role("button", name=NODE_SELECT)).to_have_count(0)
        await expect(admin_page.get_by_role("button", name=ATTRIBUTE_SELECT)).to_have_count(0)
        allocates = admin_page.get_by_role("definition")
        await expect(allocates.filter(has_text="Interface")).to_have_count(1)
        await expect(allocates.filter(has_text="Speed")).to_have_count(1)
        await expect(allocates.filter(has_text="No scope")).to_have_count(1)

    async def test_edit_number_pool_ranges(self, admin_page: Page, number_pool_branch: str) -> None:
        await open_number_pool_edit_form(admin_page, number_pool_branch, "number pool test scoped")
        await expect(admin_page.get_by_label("Start of range 1")).to_have_value("100")
        await admin_page.get_by_label("End of range 1").fill("299")
        await admin_page.get_by_role("button", name="Add range").click()
        await admin_page.get_by_label("Start of range 3").fill("500")
        await admin_page.get_by_label("End of range 3").fill("599")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Number pool updated")).to_be_visible()

        await open_number_pool_edit_form(admin_page, number_pool_branch, "number pool test scoped")
        await expect_range_rows(admin_page, [("100", "299", "10"), ("300", "399", ""), ("500", "599", "")])

    async def test_edit_form_shows_scope_read_only(self, admin_page: Page, number_pool_branch: str) -> None:
        await open_number_pool_edit_form(admin_page, number_pool_branch, "number pool test scoped")
        await expect(admin_page.get_by_role("definition").filter(has_text="Device")).to_have_count(1)
        await expect(admin_page.get_by_role("button", name="Add a relationship or attribute")).to_have_count(0)

    async def test_header_for_schema_created_pool(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await admin_page.get_by_role("link", name="InfraService.").click()

        header = admin_page.locator("header").filter(has=admin_page.get_by_role("heading", level=1))
        await expect(header.get_by_role("button", name="Managed by schema")).to_be_visible()
        await expect(header.get_by_text("Allocates to")).to_be_visible()
        await expect(header.get_by_role("button", name="InfraService", exact=True)).to_be_visible()
        await expect(header.get_by_role("button", name="service_identifier", exact=True)).to_be_visible()

        await header.get_by_role("button", name="InfraService", exact=True).click()
        await expect(admin_page.get_by_role("dialog", name="Schema viewer")).to_be_visible()
        await admin_page.keyboard.press("Escape")
        await expect(admin_page.get_by_role("dialog", name="Schema viewer")).to_have_count(0)

        await header.get_by_role("button", name="Actions").click()
        await expect(admin_page.get_by_role("menuitem", name="Edit")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="Delete")).to_have_attribute("aria-disabled", "true")
        await expect(admin_page.get_by_role("menuitem", name="View schema")).to_have_attribute(
            "href", re.compile(r"kind=CoreNumberPool")
        )

    async def test_number_pool_attribute_kind_resource_manager(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/resource-manager?branch={number_pool_branch}")
        await expect(admin_page.get_by_role("link", name="InfraService.")).to_be_visible()
        await admin_page.get_by_role("link", name="InfraService.").click()
        await expect(admin_page.get_by_role("heading", level=1)).to_be_visible()
        await save_screenshot_for_docs(admin_page, "numberpool_attribute_kind_resource_manager")

    async def test_create_node_using_number_pool_and_verify_pool_assignment(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        # Navigate to interface creation page
        await admin_page.goto(f"/objects/InfraInterfaceL3?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        # Fill in interface details
        await admin_page.get_by_role("combobox", name="Device *").click()
        await admin_page.get_by_role("option", name="atl1-core1").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test interface with pool")

        # Select number pool
        await admin_page.get_by_role("tab", name="From pool").click()
        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await expect(admin_page.get_by_role("option", name="number pool test for generic")).to_be_visible()
        await expect(admin_page.get_by_role("option", name="number pool test for node")).to_be_visible()
        await admin_page.get_by_role("option", name="number pool test for generic").click()
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()

        # Save interface
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InterfaceL3 created")).to_be_visible()

        # Verify pool assignment
        await admin_page.get_by_role("searchbox", name="Search").fill("interface with pool")
        await admin_page.get_by_role("link", name="test interface with pool").click()
        await admin_page.get_by_text("Speed1").get_by_test_id("view-metadata-button").click()
        await expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="number pool test for generic")
        ).to_be_visible()

    async def test_scoped_pool_lists_and_opens_its_allocation_scopes(
        self,
        admin_page: Page,
        number_pool_branch: str,
        infrahub_client: InfrahubClient,
        data_sites: SitesHandle,
    ) -> None:
        busy_device, quiet_device = sorted(data_sites.devices)[:2]
        result = await infrahub_client.execute_graphql(
            query=CREATE_SCOPED_POOL,
            variables={"name": "number pool test per device"},
            branch_name=number_pool_branch,
        )
        pool_id = result["CoreNumberPoolCreate"]["object"]["id"]
        for device, count in ((busy_device, 3), (quiet_device, 1)):
            for index in range(count):
                interface = await infrahub_client.create(
                    kind="InfraInterfaceL3",
                    branch=number_pool_branch,
                    name=f"allocation-scope-{index}",
                    device=data_sites.devices[device],
                    speed={"from_pool": {"id": pool_id}},
                )
                await interface.save()

        await admin_page.goto(f"/resource-manager/{pool_id}?branch={number_pool_branch}")
        await expect(admin_page.get_by_text("scoped by")).to_be_visible()
        scope_links = admin_page.get_by_role("table").get_by_role("link")
        await expect(scope_links).to_have_count(2)
        await expect(scope_links.first).to_contain_text(busy_device)

        search = admin_page.get_by_role("searchbox")
        await search.fill(quiet_device)
        await expect(scope_links).to_have_count(1)
        await expect(scope_links.first).to_contain_text(quiet_device)

        await search.fill("")
        await scope_links.filter(has_text=busy_device).click()
        await expect(admin_page).to_have_url(re.compile(r"allocation_scope="))
        await expect(admin_page.get_by_role("link", name="All allocation scopes")).to_be_visible()
        allocation_rows = admin_page.get_by_role("row").filter(has_text="allocation-scope-")
        await expect(allocation_rows).to_have_count(3)

        await admin_page.reload()
        await expect(allocation_rows).to_have_count(3)

    async def test_create_node_with_typed_number_recorded_in_pool(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraInterfaceL3?branch={number_pool_branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        await admin_page.get_by_role("combobox", name="Device *").click()
        await admin_page.get_by_role("option", name="atl1-core1").click()
        await admin_page.get_by_role("textbox", name="Name *").fill("test interface with typed pool number")

        await admin_page.get_by_role("tab", name="From pool").click()
        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await admin_page.get_by_role("option", name="number pool test for generic").click()
        await admin_page.get_by_role("spinbutton", name="Number").fill("5")

        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InterfaceL3 created")).to_be_visible()

        await admin_page.get_by_role("searchbox", name="Search").fill("typed pool number")
        await admin_page.get_by_role("link", name="test interface with typed pool number").click()
        await expect(admin_page.get_by_text("Speed5")).to_be_visible()
        await admin_page.get_by_text("Speed5").get_by_test_id("view-metadata-button").click()
        await expect(
            admin_page.get_by_test_id("metadata-tooltip").get_by_role("link", name="number pool test for generic")
        ).to_be_visible()

    async def test_edit_node_opens_pool_tab_with_pool_and_number(
        self, admin_page: Page, number_pool_branch: str
    ) -> None:
        await admin_page.goto(f"/objects/InfraInterfaceL3?branch={number_pool_branch}")
        await admin_page.get_by_role("searchbox", name="Search").fill("typed pool number")
        await admin_page.get_by_role("link", name="test interface with typed pool number").click()
        await expect(admin_page.get_by_text("Speed5")).to_be_visible()

        await admin_page.get_by_test_id("edit-button").click()
        await expect(admin_page.get_by_role("tab", name="From pool")).to_have_attribute("data-state", "active")
        await expect(admin_page.get_by_test_id("select-open-pool-option-button")).to_contain_text(
            "number pool test for generic"
        )
        await expect(admin_page.get_by_role("spinbutton", name="Number")).to_have_value("5")
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_visible()

    async def test_typed_value_takes_number_out_of_pool(self, admin_page: Page, number_pool_branch: str) -> None:
        await admin_page.goto(f"/objects/InfraInterfaceL3?branch={number_pool_branch}")
        await admin_page.get_by_role("searchbox", name="Search").fill("typed pool number")
        await admin_page.get_by_role("link", name="test interface with typed pool number").click()
        await expect(admin_page.get_by_text("Speed5")).to_be_visible()

        await admin_page.get_by_test_id("edit-button").click()
        await admin_page.get_by_role("tab", name="Value").click()
        await admin_page.get_by_role("spinbutton", name="Speed").fill("7")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InterfaceL3 updated")).to_be_visible()
        await expect(admin_page.get_by_text("Speed7")).to_be_visible()

        await admin_page.get_by_test_id("edit-button").click()
        await expect(admin_page.get_by_role("tab", name="Value")).to_have_attribute("data-state", "active")
        await expect(admin_page.get_by_role("spinbutton", name="Speed")).to_have_value("7")
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_be_hidden()
