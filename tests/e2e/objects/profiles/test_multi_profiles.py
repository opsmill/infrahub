"""Port of frontend/app/tests/e2e/objects/profiles/multi-profiles.spec.ts.

/objects/CoreProfile - create three Interface profiles (one generic, two L2)
and verify how stacking/removing them in an object form resolves the effective
attribute values by profile priority. Also fails on any HTTP 500 response (a
regression guard, mirroring the source `beforeEach`).

The source operates directly on main (no branch) and only creates new profile
objects without cleaning them up; it is kept faithful here (no branch
isolation). It references only the InfraInterface / InfraInterfaceL2 schema
kinds, hence the schema_base dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import expect

if TYPE_CHECKING:
    from playwright.async_api import Page, Response


class TestMultiProfiles:
    async def test_create_3_profiles_and_use_them_in_the_form(self, admin_page: Page, schema_base: None) -> None:
        # Regression guard: fail if any response is a 500 (mirrors the TS beforeEach).
        server_errors: list[str] = []

        def _record_500(response: Response) -> None:
            if response.status == 500:
                server_errors.append(response.url)

        admin_page.on("response", _record_500)

        # creates profiles
        await admin_page.goto("/objects/CoreProfile")

        # Generic profile
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Interface Infra", exact=True).click()
        await admin_page.get_by_label("Profile Name *").fill("Generic profile")
        await admin_page.get_by_label("Description").fill("Desc from generic profile")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraInterface created")).to_be_visible()
        await admin_page.get_by_test_id("close-alert").click()
        await expect(admin_page.get_by_text("InfraInterface created")).not_to_be_visible()

        # L2 profile v1
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()
        await admin_page.get_by_label("Profile Name *").fill("L2 profile v1")
        await admin_page.get_by_label("Description").fill("Desc from L2 profile v1")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraInterfaceL2 created")).to_be_visible()
        await admin_page.get_by_test_id("close-alert").click()
        await expect(admin_page.get_by_text("InfraInterfaceL2 created")).not_to_be_visible()

        # L2 profile v2
        await admin_page.get_by_test_id("create-object-button").click()
        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()
        await admin_page.get_by_label("Profile Name *").fill("L2 profile v2")
        await admin_page.get_by_label("Description").fill("Desc from L2 profile v2")
        await admin_page.get_by_label("Profile Priority").fill("10")
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text("InfraInterfaceL2 created")).to_be_visible()

        # use profiles in interface form
        await admin_page.goto("/objects/InfraInterface")
        await admin_page.get_by_test_id("create-object-button").click()

        await admin_page.get_by_label("Select an object type").click()
        await admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()

        await admin_page.get_by_label("Select profiles optional").click()
        await admin_page.get_by_role("option", name="L2 profile v1").click()
        await expect(admin_page.get_by_label("Description")).to_have_value("Desc from L2 profile v1")
        await expect(admin_page.get_by_test_id("source-profile-badge")).to_contain_text("L2 profile v1")

        await admin_page.get_by_role("option", name="L2 profile v2").click()
        await expect(admin_page.get_by_label("Description")).to_have_value("Desc from L2 profile v2")
        await expect(admin_page.get_by_test_id("source-profile-badge")).to_contain_text("L2 profile v2")

        await admin_page.get_by_role("option", name="Generic profile").click()
        await expect(admin_page.get_by_label("Description")).to_have_value("Desc from L2 profile v2")
        await expect(admin_page.get_by_test_id("source-profile-badge")).to_contain_text("L2 profile v2")

        await admin_page.get_by_text("L2 profile v2×").get_by_test_id("remove-option").click()
        await expect(admin_page.get_by_label("Description")).to_have_value("Desc from generic profile")
        await expect(admin_page.get_by_test_id("source-profile-badge")).to_contain_text("Generic profile")

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"
