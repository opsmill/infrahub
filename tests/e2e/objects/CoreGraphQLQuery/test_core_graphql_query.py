"""Port of frontend/app/tests/e2e/objects/CoreGraphQLQuery/core-graphql-query.spec.ts.

/objects/CoreGraphQLQuery/:graphqlQueryId details page (a serial flow): create
a GraphQL query, then access / edit it (description + metadata), then delete it.

Serial handling: all three tests share one branch (a class-scoped fixture) and
the `test-graphql-query` the first test creates. Every test depends on the SAME
class-scoped `branch` fixture and the chain relies on pytest's default
definition-order collection (see the README's serial-specs gotcha). The
list view shows the `check_backbone_link_redundancy` query defined in the
demo-edge Git repository, hence the `demo_edge_repo` dependency (which itself
pulls in `infrastructure_data`).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestCoreGraphQLQueryDetails:
    @pytest.fixture(scope="class")
    async def branch(
        self,
        infrahub_client: InfrahubClient,
        demo_edge_repo: None,
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("core-graphql-query")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_should_create_a_new_graphql_successfully(self, admin_page: Page, branch: str) -> None:
        # Navigate to CoreGraphQLQuery page
        await admin_page.goto(f"/objects/CoreGraphQLQuery?branch={branch}")
        await expect(admin_page.get_by_role("heading", name="GraphQL Query")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="check_backbone_link_redundancy")).to_be_visible()

        # Create a new graphql query
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Name *").fill("test-graphql-query")

        await (
            admin_page.get_by_test_id("codemirror-editor")
            .get_by_role("textbox")
            .fill(
                """query GET_TAGS {
        ProfileBuiltinTag {
          edges {
            node {
              id
              display_label
              description {
                id
                value
              }
            }
          }
        }
      }"""
            )
        )

        await admin_page.get_by_label("Description").click()
        await admin_page.get_by_label("Description").fill("A profile for E2E test")

        await admin_page.get_by_role("button", name="Save").click()

        # Verify graphql query creation success
        await expect(admin_page.get_by_text("GraphQLQuery created")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="test-graphql-query")).to_be_visible()

    async def test_access_the_created_graphql_query_view_its_data_and_edit_it(
        self, admin_page: Page, branch: str
    ) -> None:
        # Navigate to CoreGraphQLQuery page
        await admin_page.goto(f"/objects/CoreGraphQLQuery?branch={branch}")
        await admin_page.get_by_role("link", name="test-graphql-query").click()

        await expect(admin_page.get_by_text("DescriptionA profile for E2E test ", exact=True)).to_be_visible()
        await expect(admin_page.get_by_text("1query GET_TAGS {")).to_be_visible()

        await admin_page.get_by_test_id("object-header").get_by_test_id("edit-button").click()
        await admin_page.get_by_label("Description").fill("A profile for E2E test updated")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("GraphQLQuery updated")).to_be_visible()
        await expect(admin_page.get_by_text("DescriptionA profile for E2E test updated", exact=True)).to_be_visible()

        await (
            admin_page.get_by_role("definition")
            .filter(has_text="test-graphql-query")
            .get_by_test_id("view-metadata-button")
            .click()
        )
        await admin_page.get_by_test_id("edit-metadata-button").click()
        await admin_page.get_by_label("is protected *").check()
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Metadata updated")).to_be_visible()

        # return to list using breadcrumb
        await admin_page.get_by_test_id("breadcrumb-navigation").get_by_role("link", name="GraphQL Query").click()
        assert "/objects/CoreGraphQLQuery" in admin_page.url

    async def test_delete_a_graphql_query(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/objects/CoreGraphQLQuery?branch={branch}")

        # Delete the graphql query
        await admin_page.get_by_test_id("actions-cell-test-graphql-query").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await expect(admin_page.get_by_text("Are you sure you want to remove test-graphql-query?")).to_be_visible()
        await admin_page.get_by_test_id("modal-delete-confirm").click()

        await expect(admin_page.get_by_text("Object test-graphql-query deleted")).to_be_visible()
