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

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestActivitiesBreadcrumb:
    def test_should_display_breadcrumb_on_activities_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/activities")

        breadcrumb = page.get_by_test_id("breadcrumb-activities")
        expect(breadcrumb.get_by_role("link", name="Activities")).to_be_visible()


class TestBranchesBreadcrumb:
    def test_should_display_breadcrumb_on_branches_list_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/branches")

        breadcrumb = page.get_by_test_id("breadcrumb-branches")
        expect(breadcrumb).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Branches")).to_be_visible()

    def test_should_display_branch_name_in_breadcrumb_on_branch_details_page(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        page.goto("/branches/main")

        breadcrumb = page.get_by_test_id("breadcrumb-branches")
        expect(breadcrumb).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Branches")).to_be_visible()
        breadcrumb.get_by_role("button", name="main").click()
        page.get_by_role("option", name="atl1-delete-upstream").click()
        expect(page).to_have_url(re.compile(r"\/branches\/atl1-delete-upstream$"))

    def test_should_navigate_back_to_branches_list_when_clicking_branches_breadcrumb(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        page.goto("/branches/main")

        page.get_by_test_id("breadcrumb-branches").get_by_role("link", name="Branches").click()
        expect(page).to_have_url(re.compile(r"\/branches$"))


class TestGraphqlBreadcrumb:
    def test_should_display_breadcrumb_on_graphql_sandbox_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/graphql")

        breadcrumb = page.get_by_test_id("breadcrumb-graphql")
        expect(breadcrumb.get_by_role("link", name="GraphQL Sandbox")).to_be_visible()


class TestIpamBreadcrumb:
    def test_should_display_breadcrumb_on_ipam_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/ipam")

        breadcrumb = page.get_by_test_id("breadcrumb-ipam")
        expect(breadcrumb.get_by_role("link", name="IP Address Manager")).to_be_visible()

        page.get_by_role("link", name="10.1.0.0/31").click()
        expect(page.get_by_role("heading", name="10.1.0.0/31")).to_be_visible()

        expect(breadcrumb.get_by_role("link", name="IP Address Manager")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="10.0.0.0/8")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="10.1.0.0/16")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="10.1.0.0/31")).to_be_visible()


class TestObjectsBreadcrumb:
    def test_should_display_object_kind_in_breadcrumb_on_objects_list_page(
        self, page: Page, demo_edge_repo: None
    ) -> None:
        page.goto("/objects/InfraDevice")
        breadcrumb = page.get_by_test_id("breadcrumb-navigation")
        expect(breadcrumb.get_by_role("link", name="Device")).to_be_visible()

        page.get_by_role("link", name="atl1-core1").click()

        expect(breadcrumb.get_by_role("link", name="Device")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="atl1-core1")).to_be_visible()

        breadcrumb.get_by_role("button", name="Select a different Device").click()
        page.get_by_role("option", name="atl1-core2").click()

        expect(breadcrumb.get_by_role("link", name="atl1-core2")).to_be_visible()
        expect(page.get_by_test_id("object-header").get_by_text("atl1-core2")).to_be_visible()

    def test_should_display_object_kind_in_breadcrumb_on_artifact_pages(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/objects/CoreArtifact")
        breadcrumb = page.get_by_test_id("breadcrumb-navigation")
        expect(breadcrumb.get_by_role("link", name="Artifact")).to_be_visible()

        page.get_by_role("link", name="openconfig-interfaces").first.click()

        expect(breadcrumb.get_by_role("link", name="Artifact")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="openconfig-interfaces")).to_be_visible()


class TestProfileBreadcrumb:
    # Source describe pins storageState ADMIN -> admin_page.
    def test_should_display_breadcrumb_on_profile_page(self, admin_page: Page, demo_edge_repo: None) -> None:
        admin_page.goto("/profile")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-profile")
        expect(breadcrumb.get_by_text("Account settings")).to_be_visible()


class TestProposedChangesBreadcrumb:
    def test_should_display_breadcrumb_on_proposed_changes_list_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/proposed-changes")

        breadcrumb = page.get_by_test_id("breadcrumb-proposed-changes")
        expect(breadcrumb.get_by_role("link", name="Proposed changes")).to_be_visible()

    # Source nested describe "when logged in as Admin" pins storageState ADMIN -> admin_page.
    def test_should_display_new_in_breadcrumb_on_proposed_change_creation_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/proposed-changes/new")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-proposed-changes")
        expect(breadcrumb.get_by_role("link", name="Proposed changes")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="new")).to_be_visible()


class TestTasksBreadcrumb:
    def test_should_display_breadcrumb_on_tasks_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/tasks")

        breadcrumb = page.get_by_test_id("breadcrumb-tasks")
        expect(breadcrumb.get_by_text("Tasks")).to_be_visible()


class TestResourceManagerBreadcrumb:
    def test_should_display_breadcrumb_on_resource_manager_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/resource-manager")

        breadcrumb = page.get_by_test_id("breadcrumb-navigation")
        expect(breadcrumb.get_by_role("link", name="Resource manager")).to_be_visible()

        page.get_by_role("link", name="External prefixes pool").click()
        expect(page.get_by_role("link", name="IP Prefix Pool")).to_be_visible()
        expect(page.get_by_role("link", name="External prefixes pool")).to_be_visible()

        page.get_by_role("link", name="View", exact=True).click()
        expect(
            page.get_by_test_id("breadcrumb-resource-manager").get_by_role("link", name="203.111.0.0/16")
        ).to_be_visible()


class TestRoleManagementBreadcrumb:
    # Source describe pins storageState ADMIN -> admin_page.
    def test_should_display_breadcrumb_on_role_management_accounts_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/role-management")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Accounts")).to_be_visible()

    def test_should_display_breadcrumb_on_role_management_groups_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/role-management/groups")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Groups")).to_be_visible()

    def test_should_display_breadcrumb_on_role_management_roles_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/role-management/roles")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Roles")).to_be_visible()

    def test_should_display_breadcrumb_on_role_management_global_permissions_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/role-management/global-permissions")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Global Permissions")).to_be_visible()

    def test_should_display_breadcrumb_on_role_management_object_permissions_page(
        self, admin_page: Page, demo_edge_repo: None
    ) -> None:
        admin_page.goto("/role-management/object-permissions")

        breadcrumb = admin_page.get_by_test_id("breadcrumb-role-management")
        expect(breadcrumb.get_by_role("link", name="Users & Permissions")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Object Permissions")).to_be_visible()


class TestSchemaViewerBreadcrumb:
    def test_should_display_breadcrumb_on_schema_page(self, page: Page, demo_edge_repo: None) -> None:
        page.goto("/schema")

        breadcrumb = page.get_by_test_id("breadcrumb-schema")
        expect(breadcrumb.get_by_text("Schema")).to_be_visible()
