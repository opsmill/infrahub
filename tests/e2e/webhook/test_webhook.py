"""Port of frontend/app/tests/e2e/webhook/webhook.spec.ts.

Serial: create a Standard Webhook ("Ansible EDA"), view its detail/activities,
then delete it. The flow runs on main and shares the created webhook across the
three tests, so they use one class-scoped fixture; the chain relies on
pytest's default definition-order collection (see the README's serial-specs
gotcha). The webhook form's "Node Kind" / "Account Core" option and
"Standard Webhook Core" use only core (bootstrap) kinds, so no demo data is
required.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


class TestCoreWebhook:
    # when logged in as admin account (serial)
    @pytest.fixture(scope="class")
    async def webhook(self, infrahub_client: InfrahubClient) -> AsyncGenerator[str, None]:
        name = "Ansible EDA"
        yield name
        # Safety-net teardown: the Delete test removes the webhook, but clean up
        # any leftover if the flow aborted early.
        with contextlib.suppress(Exception):
            existing = await infrahub_client.filters(kind="CoreStandardWebhook", name__value=name)
            for obj in existing:
                await obj.delete()

    async def test_create_a_webhook(self, admin_page: Page, webhook: str) -> None:
        # load webhooks
        await admin_page.goto("/objects/CoreWebhook")
        await expect(admin_page.get_by_test_id("object-header")).to_contain_text("Webhook")
        await save_screenshot_for_docs(admin_page, "webhook_list")

        # create a new webhook
        await admin_page.get_by_test_id("create-object-button").click()

        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Standard Webhook Core").click()

        await expect(admin_page.get_by_role("button", name="Save")).to_be_visible()
        await admin_page.get_by_label("Name *").fill(webhook)

        await admin_page.get_by_label("Branch Scope").click()
        await admin_page.get_by_role("option", name="All Branches All branches").click()

        await admin_page.get_by_role("combobox", name="Node Kind").click()
        await admin_page.get_by_role("option", name="Account Core").click()

        await admin_page.get_by_label("Description").fill("Ansible EDA Webhook Reciever")

        await admin_page.get_by_label("Url *").fill("http://ansible-eda:8080")

        await admin_page.get_by_label("Shared Key *").fill("secret")

        await admin_page.get_by_label("Validate Certificates").uncheck()

        await save_screenshot_for_docs(admin_page, "webhook_create")

        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("Webhook created")).to_be_visible()

    async def test_access_webhook(self, admin_page: Page, webhook: str) -> None:
        # load webhooks
        await admin_page.goto("/objects/CoreWebhook")
        await expect(admin_page.get_by_test_id("object-header")).to_contain_text("Webhook")

        # webhook detail view
        # Give time for activity log to be propagated.
        await admin_page.get_by_test_id("identifier-cell").get_by_role("link", name=webhook, exact=True).click()

        await expect(admin_page.get_by_text("Activities", exact=True)).to_be_visible()
        await expect(admin_page.get_by_test_id("activities-panel").get_by_text("Loading...")).to_be_hidden()

        deadline = Deadline("the webhook activity log to be populated")
        while await admin_page.get_by_text("No activity found for this").is_visible():
            await deadline.tick()
            await admin_page.reload()
            await expect(admin_page.get_by_text("Activities", exact=True)).to_be_visible()
            await expect(admin_page.get_by_test_id("activities-panel").get_by_text("Loading...")).to_be_hidden()
        await expect(admin_page.get_by_text("NameAnsible EDA")).to_be_visible()
        await expect(admin_page.get_by_text("View all activities")).to_be_visible()
        await save_screenshot_for_docs(admin_page, "webhook_detail")

    async def test_delete_webhook(self, admin_page: Page, webhook: str) -> None:
        # load webhooks
        await admin_page.goto("/objects/CoreWebhook")
        await expect(admin_page.get_by_test_id("object-header")).to_contain_text("Webhook")

        # access and delete webhook
        await admin_page.get_by_role("link", name=webhook).click()
        await expect(admin_page.get_by_test_id("object-header").get_by_text(webhook, exact=True)).to_be_visible()
        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name="Delete").click()
        await admin_page.get_by_test_id("modal-delete-confirm").click()
        await expect(admin_page.get_by_text("Object Ansible EDA deleted")).to_be_visible()
        await admin_page.get_by_text("No Standard Webhook found").click()
