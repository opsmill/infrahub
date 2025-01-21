from typing import Any

from infrahub_sdk import InfrahubClient

from infrahub.testing.helpers import TestInfrahubDev
from infrahub.testing.schemas.car_person import (
    NAMESPACE,
    TESTING_PERSON,
    SchemaCarPerson,
)

import pytest
from playwright.sync_api import Page, expect, BrowserContext


class TestSchemaMigrations(TestInfrahubDev, SchemaCarPerson):
    @pytest.fixture
    def admin_login(self,infrahub_port: int, context: BrowserContext):
        page = context.new_page()
        page.goto(f'http://localhost:{infrahub_port}/login')
        expect(page.get_by_text("Log in to your account")).to_be_visible()
        page.get_by_label("Username").fill("admin")
        page.get_by_label("Password").fill("infrahub")
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_text("Proposed changes")).to_be_visible()

        return page

    def test_homepage(self, infrahub_port: int, page: Page):
        page.goto(f"http://localhost:{infrahub_port}/")
        expect(page.get_by_text("Proposed changes")).to_be_visible()
        page.screenshot(path="infrahub_homepage.png")


    async def test_setup_initial_schema(
        self, default_branch: str, infrahub_client: InfrahubClient, schema_base: dict[str, Any]
    ) -> None:
        resp = await infrahub_client.schema.load(
            schemas=[schema_base], branch=default_branch, wait_until_converged=True
        )
        assert resp.errors == {}

        await infrahub_client.schema.wait_until_converged(branch=default_branch)
        await infrahub_client.schema.fetch(branch=default_branch, namespaces=[NAMESPACE])
        _ = await infrahub_client.schema.get(kind=TESTING_PERSON, branch=default_branch)

        _ = await self.create_persons(client=infrahub_client, branch=default_branch)
        _ = await self.create_manufacturers(client=infrahub_client, branch=default_branch)

        assert True


