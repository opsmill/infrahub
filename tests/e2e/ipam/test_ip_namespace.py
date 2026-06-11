"""Port of frontend/app/tests/e2e/ipam/ip-namespace.spec.ts.

IP namespace lifecycle (a serial flow): create `test-namespace`, switch to it,
search, namespace-aware redirects, prefix CRUD inside it, and finally delete it.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the `test-namespace` it creates in the second test. Every test depends on the
SAME fixtures (admin_page + namespace_branch) and the chain relies on pytest's
default definition-order collection (see the README's serial-specs gotcha). The
suite runs single-process.
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


class TestIpNamespace:
    @pytest.fixture(scope="class")
    async def namespace_branch(
        self,
        infrahub_client: InfrahubClient,
        data_sites: SitesHandle,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-namespace-")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_navigate_to_namespace_list_from_tree(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam?branch={namespace_branch}")
        await admin_page.get_by_test_id("namespace-select").click()
        await admin_page.get_by_role("link", name="View all IP namespaces").click()
        await expect(admin_page.get_by_role("link", name="default")).to_be_visible()
        assert f"/ipam/namespaces?branch={namespace_branch}" in admin_page.url

    async def test_create_ip_namespace(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam/namespaces?branch={namespace_branch}")

        await expect(admin_page.get_by_role("link", name="default")).to_be_visible()

        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Name *").fill("test-namespace")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("Namespace created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test-namespace")).to_be_visible()

    async def test_switch_from_default_namespace(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam?branch={namespace_branch}")

        await expect(admin_page.get_by_test_id("namespace-select")).to_contain_text("default")

        await admin_page.get_by_test_id("namespace-select").click()
        await admin_page.get_by_role("option", name="test-namespace").click()

        await expect(admin_page.get_by_test_id("namespace-select")).to_contain_text("test-namespace")
        assert "namespace=" in admin_page.url

    async def test_search_namespace_in_list_page(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam/namespaces?branch={namespace_branch}")

        await expect(admin_page.get_by_role("link", name="default")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test-namespace")).to_be_visible()

        await admin_page.get_by_placeholder("Search IP Namespace").fill("test")
        await expect(admin_page.get_by_role("link", name="default")).not_to_be_visible()
        await expect(admin_page.get_by_role("link", name="test-namespace")).to_be_visible()

        await admin_page.get_by_placeholder("Search IP Namespace").fill("def")
        await expect(admin_page.get_by_role("link", name="default")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test-namespace")).not_to_be_visible()

        await admin_page.get_by_placeholder("Search IP Namespace").fill("xyz")
        await expect(admin_page.get_by_role("link", name="default")).not_to_be_visible()
        await expect(admin_page.get_by_role("link", name="test-namespace")).not_to_be_visible()
        await expect(admin_page.get_by_text("No IP Namespace found")).to_be_visible()

    async def test_redirect_to_prefixes_view_on_switch(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam?branch={namespace_branch}")
        await admin_page.get_by_role("link", name="10.0.0.0/16").click()
        await expect(admin_page.get_by_role("heading", name="10.0.0.0/16")).to_be_visible()

        await admin_page.get_by_test_id("namespace-select").click()
        await admin_page.get_by_role("option", name="test-namespace").click()

        await expect(admin_page.get_by_text("No IP Prefix found")).to_be_visible()
        assert "namespace=" in admin_page.url

    async def test_redirect_to_addresses_view_on_switch(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam/ip_addresses?branch={namespace_branch}")
        await admin_page.get_by_role("link", name="10.0.0.1/32").click()

        await admin_page.get_by_test_id("namespace-select").click()
        await admin_page.get_by_role("option", name="test-namespace").click()

        await expect(admin_page.get_by_text("No IP Address found")).to_be_visible()
        assert "namespace=" in admin_page.url
        assert "/ipam/ip_addresses" in admin_page.url

    async def test_error_when_namespace_does_not_exist(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam?namespace=non-existent&branch={namespace_branch}")
        await expect(admin_page.get_by_text("Cannot find IP Namespace with id non-existent")).to_be_visible()

        await admin_page.get_by_role("link", name="Go to default IP namespace").click()
        await expect(admin_page.get_by_test_id("namespace-select")).to_contain_text("default")

    async def test_create_validate_and_delete_prefix_on_other_namespace(
        self, admin_page: Page, namespace_branch: str
    ) -> None:
        await admin_page.goto(f"/ipam?branch={namespace_branch}")
        await admin_page.get_by_test_id("namespace-select").click()
        await admin_page.get_by_role("option", name="test-namespace").click()
        ipam_tree = admin_page.get_by_role("treegrid", name="IPAM tree")

        # create a prefix at top level
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Prefix *").fill("11.0.0.0/8")
        await admin_page.get_by_text("IP Namespace Kind").get_by_label("IPAM Namespace").click()
        await admin_page.get_by_role("option", name="test-namespace").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Prefix 11.0.0.0/8 created")).to_be_visible()

        # validate new top level tree
        await expect(ipam_tree.get_by_text("11.0.0.0/8")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 1

        # create a children prefix
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Prefix *").fill("11.0.0.0/16")
        await admin_page.get_by_text("IP Namespace Kind").get_by_label("IPAM Namespace").click()
        await admin_page.get_by_role("option", name="test-namespace").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Prefix 11.0.0.0/16 created")).to_be_visible()

        # validate the tree shows the new child once expanded
        await expect(ipam_tree.get_by_text("11.0.0.0/8")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 1
        await ipam_tree.get_by_role("button", name="Expand 11.0.0.0/8").click()
        await expect(ipam_tree.get_by_text("11.0.0.0/16")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 2

        # create an intermediate prefix between parent and child
        await ipam_tree.get_by_text("11.0.0.0/8").click()
        breadcrumb = admin_page.get_by_test_id("breadcrumb-navigation")
        await expect(breadcrumb.get_by_role("link", name="11.0.0.0/8")).to_be_visible()
        await breadcrumb.get_by_role("button", name="Select a different IP Prefix").click()
        await expect(admin_page.get_by_role("option")).to_have_count(2)
        await admin_page.get_by_placeholder("Search...").press("Escape")

        await admin_page.get_by_role("link", name="Children").click()
        await expect(admin_page.get_by_role("link", name="11.0.0.0/16")).to_be_visible()
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Prefix *").fill("11.0.0.0/10")
        await admin_page.get_by_text("IP Namespace Kind").get_by_label("IPAM Namespace").click()
        await admin_page.get_by_role("option", name="test-namespace").click()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IP Prefix 11.0.0.0/10 created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="11.0.0.0/10")).to_be_visible()

        # validate tree position
        await expect(admin_page.get_by_role("button", name="Collapse 11.0.0.0/8")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 2
        await ipam_tree.get_by_role("button", name="Expand 11.0.0.0/10").click()
        await expect(ipam_tree.get_by_text("11.0.0.0/16")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 3

        # validate breadcrumb navigation for the intermediate prefix
        await ipam_tree.get_by_text("11.0.0.0/10").click()
        await expect(admin_page.get_by_role("heading", name="11.0.0.0/10")).to_be_visible()
        breadcrumb = admin_page.get_by_test_id("breadcrumb-navigation")
        await expect(breadcrumb.get_by_role("link", name="11.0.0.0/10")).to_be_visible()
        await breadcrumb.get_by_role("button", name="Select a different IP Prefix").last.click()
        await expect(admin_page.get_by_role("option")).to_have_count(1)
        await admin_page.get_by_placeholder("Search...").press("Escape")

        # edit intermediate prefix
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await admin_page.get_by_label("Prefix *").fill("11.0.0.0/11")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("IPPrefix updated")).to_be_visible()
        await expect(ipam_tree.get_by_text("11.0.0.0/11")).to_be_visible()
        await expect(admin_page.get_by_role("heading", name="11.0.0.0/11", exact=True)).to_be_visible()

        # delete intermediate prefix
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_test_id("modal-delete")).to_contain_text(
            'Are you sure you want to remove the IP Prefix"11.0.0.0/11"?'
        )
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object 11.0.0.0/11 deleted")).to_be_visible()

        # verify intermediate prefix removed from tree
        await expect(ipam_tree.get_by_text("11.0.0.0/8")).to_be_visible()
        await expect(ipam_tree.get_by_text("11.0.0.0/16")).to_be_visible()
        await expect(ipam_tree.get_by_text("11.0.0.0/11")).to_be_hidden()
        assert await ipam_tree.get_by_role("row").count() == 2

        # delete child prefix
        await admin_page.get_by_role("link", name="Children").click()
        await admin_page.get_by_test_id("actions-cell-11.0.0.0/16").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_test_id("modal-delete")).to_contain_text(
            "Are you sure you want to remove 11.0.0.0/16?"
        )
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object 11.0.0.0/16 deleted")).to_be_visible()

        # verify child prefix removed from tree
        await expect(ipam_tree.get_by_text("11.0.0.0/16")).to_be_hidden()
        assert await ipam_tree.get_by_role("row").count() == 1
        await expect(ipam_tree.get_by_role("link", name="11.0.0.0/16")).to_be_hidden()

        # delete top-level prefix
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_test_id("modal-delete")).to_contain_text(
            'Are you sure you want to remove the IP Prefix"11.0.0.0/8"?'
        )
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object 11.0.0.0/8 deleted")).to_be_visible()

        # verify tree is empty after all prefixes deleted
        await expect(ipam_tree.get_by_text("11.0.0.0/8")).to_be_hidden()
        await expect(ipam_tree.get_by_text("No ip prefix", exact=True)).to_be_visible()

    async def test_delete_ip_namespace(self, admin_page: Page, namespace_branch: str) -> None:
        await admin_page.goto(f"/ipam/namespaces?branch={namespace_branch}")

        await admin_page.get_by_role("link", name="test-namespace").click()
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_test_id("modal-delete")).to_contain_text(
            'Are you sure you want to remove the IPAM Namespace"test-namespace"?'
        )
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object test-namespace deleted")).to_be_visible()

        await expect(admin_page.get_by_role("link", name="test-namespace")).to_be_hidden()
