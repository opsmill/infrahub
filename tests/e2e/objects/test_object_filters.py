"""Port of frontend/app/tests/e2e/objects/object-filters.spec.ts.

/objects/:objectKind list-view filtering: the filter picker, the column-header
filters (attribute / relationship / metadata date / metadata user, with the
contains / is any of / is empty / is not empty conditions), filtering from a
kind (Interface L2/L3), and enum-value filtering on BGP sessions. All flows are
read-only on main; the data_topology dependency is needed because the Type
filter asserts both EXTERNAL and INTERNAL (mesh) BGP sessions, and brings the
devices atl1-*/den1-*, sites and tags transitively. No branch is needed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import TopologyHandle
    from playwright.sync_api import Page


class TestObjectFiltersFilterPicker:
    def test_filter_by_attribute_relationship_and_node_metadata(
        self, admin_page: Page, data_topology: TopologyHandle
    ) -> None:
        # navigate and verify initial state
        admin_page.goto("/objects/InfraDevice")
        expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()

        # filter by attribute with 'contains' condition
        admin_page.get_by_role("button", name="Filter").click()
        expect(admin_page.get_by_role("listbox", name="Filter fields")).to_be_visible()

        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Role").click()
        expect(admin_page.get_by_test_id("attribute-filter-form")).to_be_visible()

        admin_page.get_by_role("option", name="Edge Router").click()
        admin_page.get_by_test_id("attribute-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Role contains edge")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).not_to_be_visible()

        # update attribute filter value
        admin_page.get_by_role("row", name="Role contains edge").click()
        expect(admin_page.get_by_test_id("attribute-filter-form")).to_be_visible()

        admin_page.get_by_role("option", name="Core Router").click()
        admin_page.get_by_test_id("attribute-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Role contains core")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).not_to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()
        expect(admin_page.get_by_role("row", name="Role contains core")).not_to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()

        # filter by relationship with 'is any of' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Site").click()
        expect(admin_page.get_by_test_id("relationship-filter-form")).to_be_visible()

        admin_page.get_by_role("option", name="atl1").click()
        admin_page.get_by_test_id("relationship-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name=re.compile(r"Site.*is any of.*atl1"))).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).not_to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by attribute with 'is empty' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Name").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is empty").click()
        admin_page.get_by_test_id("attribute-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Name is empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by attribute with 'is not empty' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Name").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is not empty").click()
        admin_page.get_by_test_id("attribute-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Name is not empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by relationship with 'is empty' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Tags").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is empty").click()
        admin_page.get_by_test_id("relationship-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Tags is empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by relationship with 'is not empty' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Tags").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is not empty").click()
        admin_page.get_by_test_id("relationship-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Tags is not empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by metadata date with 'after' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Created at").click()
        expect(admin_page.get_by_test_id("metadata-date-filter-form")).to_be_visible()

        # Default condition is "after"
        admin_page.get_by_role("option", name=re.compile(r"Choose.*1st")).first.click()
        admin_page.get_by_test_id("metadata-date-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name=re.compile(r"Created at.*after"))).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by metadata date with 'before' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Created at").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="before").click()

        admin_page.get_by_role("option", name=re.compile(r"Choose.*1st")).first.click()
        admin_page.get_by_test_id("metadata-date-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name=re.compile(r"Created at.*before"))).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by metadata user with 'is any of' condition
        admin_page.get_by_role("button", name="Filter").click()
        admin_page.get_by_role("listbox", name="Filter fields").get_by_role("option", name="Created by").click()
        expect(admin_page.get_by_test_id("metadata-user-filter-form")).to_be_visible()

        admin_page.get_by_role("option", name=re.compile(r"admin", re.IGNORECASE)).first.click()
        admin_page.get_by_test_id("metadata-user-filter-form").get_by_role("button", name="Apply").click()

        expect(
            admin_page.get_by_role("row", name=re.compile(r"Created by.*is any of.*admin", re.IGNORECASE))
        ).to_be_visible()

        # clear all filters and verify initial state
        admin_page.get_by_test_id("filter-reset-button").click()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()


class TestObjectFiltersColumnHeader:
    def test_filter_by_attribute_and_relationship(self, admin_page: Page, data_topology: TopologyHandle) -> None:
        # navigate and verify initial state
        admin_page.goto("/objects/InfraDevice")
        expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()

        # filter by attribute with 'contains' condition via column header
        admin_page.get_by_role("button", name="Role").click()
        expect(admin_page.get_by_text("Filter by Role")).to_be_visible()

        admin_page.get_by_role("option", name="Edge Router").click()
        admin_page.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Role contains edge")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).not_to_be_visible()

        # update attribute filter via column header
        admin_page.get_by_test_id("object-items").get_by_role("button", name="Role").click()
        expect(admin_page.get_by_test_id("attribute-filter-form")).to_contain_text("Edge Router")

        admin_page.get_by_role("option", name="Core Router").click()
        admin_page.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Role contains core")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).not_to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by attribute with 'is empty' condition via column header
        admin_page.get_by_role("button", name="Role").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is empty").click()
        admin_page.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Role is empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by attribute with 'is not empty' condition via column header
        admin_page.get_by_role("button", name="Role").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is not empty").click()
        admin_page.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Role is not empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by relationship with 'is any of' condition via column header
        # (scope to the table; "Site" also matches the sidebar menu button)
        admin_page.get_by_test_id("object-items").get_by_role("button", name="Site").click()
        expect(admin_page.get_by_text("Filter by Site")).to_be_visible()

        admin_page.get_by_role("option", name="atl1").click()
        admin_page.get_by_test_id("relationship-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name=re.compile(r"Site.*is any of.*atl1"))).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).not_to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by relationship with 'is empty' condition via column header
        admin_page.get_by_role("button", name="Tags").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is empty").click()
        admin_page.get_by_test_id("relationship-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Tags is empty")).to_be_visible()

        # clear filters
        admin_page.get_by_test_id("filter-reset-button").click()

        # filter by relationship with 'is not empty' condition via column header
        admin_page.get_by_role("button", name="Tags").click()

        admin_page.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is not empty").click()
        admin_page.get_by_test_id("relationship-filter-form").get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Tags is not empty")).to_be_visible()

        # update filter via filter tag click
        admin_page.get_by_role("row", name="Tags is not empty").click()

        edit_popover = admin_page.get_by_role("dialog").last
        edit_popover.get_by_role("button", name=re.compile(r"select a condition")).click()
        admin_page.get_by_role("option", name="is any of").click()

        admin_page.get_by_role("option", name="blue").click()
        edit_popover.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name=re.compile(r"Tags.*is any of.*blue"))).to_be_visible()

        # clear all filters and verify initial state
        admin_page.get_by_test_id("filter-reset-button").click()
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="den1-edge1")).to_be_visible()


class TestObjectFilters:
    def test_filter_from_a_kind(self, admin_page: Page, data_topology: TopologyHandle) -> None:
        admin_page.goto("/objects/InfraInterface")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Interface L2")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Interface L3")
        expect(admin_page.get_by_test_id("object-schema-schema-selector")).to_contain_text("All Interface")

        # filter target kind
        admin_page.get_by_test_id("object-schema-schema-selector").click()
        expect(admin_page.get_by_test_id("object-schema-schema-selector-popover")).to_be_visible()
        expect(admin_page.get_by_role("option", name="Interface L2 Infra", exact=True)).to_be_visible()
        expect(admin_page.get_by_role("option", name="Interface L3 Infra", exact=True)).to_be_visible()
        admin_page.get_by_placeholder("Filter...").fill("l3")
        expect(admin_page.get_by_role("option", name="Interface L2 Infra", exact=True)).to_be_hidden()
        expect(admin_page.get_by_role("option", name="Interface L3 Infra", exact=True)).to_be_visible()

        # filter using kind
        admin_page.get_by_role("option", name="Interface L3 Infra", exact=True).click()
        expect(admin_page.get_by_test_id("object-schema-schema-selector-popover")).not_to_be_visible()

        expect(admin_page.get_by_test_id("object-schema-schema-selector")).to_contain_text("Interface L3Infra")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Interface L3")
        expect(admin_page.get_by_test_id("object-items")).not_to_contain_text("Interface L2")

        # clear kind filter
        admin_page.get_by_test_id("object-schema-schema-selector").click()
        admin_page.get_by_role("option", name="All Interface", exact=True).click()

        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Interface L2")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("Interface L3")

    def test_filter_using_enum_value(self, admin_page: Page, data_topology: TopologyHandle) -> None:
        admin_page.goto("/objects/InfraBGPSession")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("EXTERNAL")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("INTERNAL")

        admin_page.get_by_role("button", name="Type").click()
        expect(admin_page.get_by_placeholder("Filter...")).to_be_focused()
        expect(admin_page.get_by_role("option", name="EXTERNAL")).to_be_visible()
        expect(admin_page.get_by_role("option", name="INTERNAL")).to_be_visible()
        admin_page.get_by_role("option", name="EXTERNAL").click()
        expect(admin_page.get_by_role("combobox").filter(has_text="EXTERNAL")).to_be_visible()
        admin_page.get_by_role("button", name="Apply").click()

        expect(admin_page.get_by_role("row", name="Type contains EXTERNAL")).to_be_visible()
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("EXTERNAL")
        expect(admin_page.get_by_test_id("object-items")).not_to_contain_text("INTERNAL")

        admin_page.get_by_test_id("object-items").get_by_role("button", name="Type").click()
        expect(admin_page.get_by_role("combobox").filter(has_text="EXTERNAL")).to_be_visible()
        admin_page.keyboard.press("Escape")

        admin_page.get_by_role("button", name="Remove Type contains EXTERNAL").click()
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("EXTERNAL")
        expect(admin_page.get_by_test_id("object-items")).to_contain_text("INTERNAL")
