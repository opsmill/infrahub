"""Port of frontend/app/tests/e2e/breadcrumb.spec.ts.

Broad breadcrumb navigation coverage across the app's top-level activities:
activities, branches (incl. the atl1-delete-upstream demo branch), GraphQL
sandbox, IPAM, objects (Device + Artifact), account profile, proposed changes,
tasks, resource manager, role management and schema viewer.

Most source tests run on the default (unauthenticated) page; the profile,
proposed-change-creation and role-management describes pin
`storageState: ACCOUNT_STATE_PATH.ADMIN` -> `admin_page` here.

Data dependencies: the demo dataset (devices atl1-core1/atl1-core2, the
10.x IPAM prefixes, the External prefixes pool, the atl1-delete-upstream branch)
plus a generated `openconfig-interfaces` artifact, so the tests depend on
`demo_edge_repo` (which registers + syncs the demo-edge repo on main and pulls
in `infrastructure_data`).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from playwright.async_api import Page


class TestActivitiesBreadcrumb:
    async def test_should_display_breadcrumb_on_activities_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/activities")

        breadcrumb = page.get_by_test_id("breadcrumb-activities")
        await expect(breadcrumb.get_by_role("link", name="Activities")).to_be_visible()


class TestBranchesBreadcrumb:
    async def test_should_display_breadcrumb_on_branches_list_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/branches")

        breadcrumb = page.get_by_test_id("breadcrumb-branches")
        await expect(breadcrumb).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Branches")).to_be_visible()

    async def test_should_display_branch_name_in_breadcrumb_on_branch_details_page(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        await page.goto("/branches/main")

        breadcrumb = page.get_by_test_id("breadcrumb-branches")
        await expect(breadcrumb).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Branches")).to_be_visible()
        await breadcrumb.get_by_role("button", name="main").click()
        await page.get_by_role("option", name="atl1-delete-upstream").click()
        await expect(page).to_have_url(re.compile(r"\/branches\/atl1-delete-upstream$"))

    async def test_should_navigate_back_to_branches_list_when_clicking_branches_breadcrumb(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        await page.goto("/branches/main")

        await page.get_by_test_id("breadcrumb-branches").get_by_role("link", name="Branches").click()
        await expect(page).to_have_url(re.compile(r"\/branches$"))


class TestGraphqlBreadcrumb:
    async def test_should_display_breadcrumb_on_graphql_sandbox_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/graphql")

        breadcrumb = page.get_by_test_id("breadcrumb-graphql")
        await expect(breadcrumb.get_by_role("link", name="GraphQL Sandbox")).to_be_visible()


class TestIpamBreadcrumb:
    async def test_should_display_breadcrumb_on_ipam_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/ipam")

        breadcrumb = page.get_by_test_id("breadcrumb-ipam")
        await expect(breadcrumb.get_by_role("link", name="IP Address Manager")).to_be_visible()

        await page.get_by_role("link", name="10.1.0.0/31").click()
        await expect(page.get_by_role("heading", name="10.1.0.0/31")).to_be_visible()

        await expect(breadcrumb.get_by_role("link", name="IP Address Manager")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="10.0.0.0/8")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="10.1.0.0/16")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="10.1.0.0/31")).to_be_visible()


class TestObjectsBreadcrumb:
    async def test_should_display_object_kind_in_breadcrumb_on_objects_list_page(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        await page.goto("/objects/InfraDevice")
        breadcrumb = page.get_by_test_id("breadcrumb-navigation")
        await expect(breadcrumb.get_by_role("link", name="Device")).to_be_visible()

        await page.get_by_role("link", name="atl1-core1").click()

        await expect(breadcrumb.get_by_role("link", name="Device")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="atl1-core1")).to_be_visible()

        await breadcrumb.get_by_role("button", name="Select a different Device").click()
        await page.get_by_role("option", name="atl1-core2").click()

        await expect(breadcrumb.get_by_role("link", name="atl1-core2")).to_be_visible()
        await expect(page.get_by_test_id("object-header").get_by_text("atl1-core2")).to_be_visible()

    async def test_should_display_object_kind_in_breadcrumb_on_artifact_pages(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        await page.goto("/objects/CoreArtifact")
        breadcrumb = page.get_by_test_id("breadcrumb-navigation")
        await expect(breadcrumb.get_by_role("link", name="Artifact")).to_be_visible()

        await page.get_by_role("link", name="openconfig-interfaces").first.click()

        await expect(breadcrumb.get_by_role("link", name="Artifact")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="openconfig-interfaces")).to_be_visible()


class TestProfileBreadcrumb:
    # Source describe pins storageState ADMIN -> admin_page.
    async def test_should_display_breadcrumb_on_profile_page(self, admin_page: Page, demo_edge_repo: None) -> None:
        await admin_page.goto("/profile")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-profile")
        await expect(breadcrumb.get_by_text("Account settings")).to_be_visible()


class TestProposedChangesBreadcrumb:
    async def test_should_display_breadcrumb_on_proposed_changes_list_page(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        await page.goto("/proposed-changes")

        breadcrumb = page.get_by_test_id("breadcrumb-proposed-changes")
        await expect(breadcrumb.get_by_role("link", name="Proposed changes")).to_be_visible()

    # Source nested describe "when logged in as Admin" pins storageState ADMIN -> admin_page.
    async def test_should_display_new_in_breadcrumb_on_proposed_change_creation_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        await admin_page.goto("/proposed-changes/new")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-proposed-changes")
        await expect(breadcrumb.get_by_role("link", name="Proposed changes")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="new")).to_be_visible()


class TestTasksBreadcrumb:
    async def test_should_display_breadcrumb_on_tasks_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/tasks")

        breadcrumb = page.get_by_test_id("breadcrumb-tasks")
        await expect(breadcrumb.get_by_text("Tasks")).to_be_visible()


class TestResourceManagerBreadcrumb:
    async def test_should_display_breadcrumb_on_resource_manager_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/resource-manager")

        breadcrumb = page.get_by_test_id("breadcrumb-navigation")
        await expect(breadcrumb.get_by_role("link", name="Resource manager")).to_be_visible()

        await page.get_by_role("link", name="External prefixes pool").click()
        await expect(page.get_by_role("link", name="IP Prefix Pool")).to_be_visible()
        await expect(page.get_by_role("link", name="External prefixes pool")).to_be_visible()

        await page.get_by_role("link", name="View", exact=True).click()
        await expect(
            page.get_by_test_id("breadcrumb-resource-manager").get_by_role("link", name="203.111.0.0/16")
        ).to_be_visible()


class TestRoleManagementBreadcrumb:
    # Source describe pins storageState ADMIN -> admin_page.
    async def test_should_display_breadcrumb_on_role_management_accounts_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        await admin_page.goto("/role-management")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        await expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Accounts")).to_be_visible()

    async def test_should_display_breadcrumb_on_role_management_groups_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        await admin_page.goto("/role-management/groups")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        await expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Groups")).to_be_visible()

    async def test_should_display_breadcrumb_on_role_management_roles_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        await admin_page.goto("/role-management/roles")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        await expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Roles")).to_be_visible()

    async def test_should_display_breadcrumb_on_role_management_global_permissions_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        await admin_page.goto("/role-management/global-permissions")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        await expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Global Permissions")).to_be_visible()

    async def test_should_display_breadcrumb_on_role_management_object_permissions_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        await admin_page.goto("/role-management/object-permissions")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        await expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        await expect(breadcrumb.get_by_role("link", name="Object Permissions")).to_be_visible()


class TestSchemaViewerBreadcrumb:
    async def test_should_display_breadcrumb_on_schema_page(self, page: Page, demo_edge_repo: None) -> None:
        await page.goto("/schema")

        breadcrumb = page.get_by_test_id("breadcrumb-schema")
        await expect(breadcrumb.get_by_text("Schema")).to_be_visible()
