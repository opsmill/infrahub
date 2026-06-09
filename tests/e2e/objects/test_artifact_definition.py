"""Port of frontend/app/tests/e2e/objects/artifact-definition.spec.ts.

/objects/CoreArtifactDefinition page (as Admin): navigate to the demo-edge
repo's "Startup Config for Edge devices" artifact definition via the breadcrumb
and trigger artifact generation. The artifact definitions come from the
demo-edge Git repository, so this depends on the `demo_edge_repo` fixture (which
pulls in infrastructure_data). The TS spec ran with storageState ADMIN ->
admin_page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.mark.usefixtures("demo_edge_repo")
class TestArtifactDefinitionPage:
    def test_should_generate_artifacts_successfully(self, admin_page: Page) -> None:
        admin_page.goto("/objects/CoreArtifactDefinition")
        breadcrumb = admin_page.get_by_test_id("breadcrumb-navigation")
        expect(breadcrumb.get_by_role("link", name="Artifact Definition")).to_be_visible()

        admin_page.get_by_role("link", name="Startup Config for Edge devices").click()
        expect(breadcrumb.get_by_role("link", name="Artifact Definition")).to_be_visible()
        expect(breadcrumb.get_by_role("link", name="Startup Config for Edge devices")).to_be_visible()

        expect(admin_page.get_by_role("button", name="Generate")).not_to_be_disabled()
        admin_page.get_by_role("button", name="Generate").click()
        expect(admin_page.get_by_text("Artifacts generated")).to_be_visible()
