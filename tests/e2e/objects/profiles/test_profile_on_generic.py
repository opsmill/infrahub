"""Port of frontend/app/tests/e2e/objects/profiles/profile-on-generic.spec.ts.

/objects/CoreProfile - Profile for Interface L2 and fields verification (a
serial flow): verify the optional/mandatory fields exposed by an Interface L2
profile form, create an Interface L2 profile and a generic Interface profile,
verify the saved profile values, and confirm both profiles are offered in an
object form.

Serial handling: the whole flow shares one branch (a class-scoped fixture) and
the two profiles it creates across tests. Every test depends on the SAME
fixtures (admin_page + branch) and the chain relies on pytest's default
definition-order collection (see the README's serial-specs gotcha). The
branch is cut from main, which carries the demo dataset (the `backbone_profile`,
the `Ethernet1` interface), hence the infrastructure_data dependency.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClientSync
    from playwright.sync_api import Page

PROFILE_NAME = "Interface L2 profile test"
GENERIC_PROFILE_NAME = "Generic Interface profile test"


class TestProfileOnGeneric:
    @pytest.fixture(scope="class")
    def branch(
        self,
        infrahub_client: InfrahubClientSync,
        infrastructure_data: None,
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name()
        infrahub_client.branch.create(branch_name=name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            infrahub_client.branch.delete(branch_name=name)

    def test_verify_form_fields_for_new_interface_l2_profile(self, admin_page: Page, branch: str) -> None:
        # access Interface L2 form
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        expect(admin_page.get_by_role("link", name="backbone_profile")).to_be_visible()

        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()

        # verify Interface L2 optional attributes are all visible
        expect(admin_page.get_by_label("Profile Name *")).to_be_visible()
        expect(admin_page.get_by_label("Description")).to_be_visible()
        expect(admin_page.get_by_label("MTU")).to_be_visible()
        expect(admin_page.get_by_label("Enabled")).to_be_visible()
        expect(admin_page.get_by_label("Status")).to_be_visible()
        expect(admin_page.get_by_label("Role")).to_be_visible()

        # verify Interface L2 mandatory attributes and relationships are not visible
        expect(admin_page.get_by_label("Layer2 Mode *")).not_to_be_visible()
        expect(admin_page.get_by_label("Speed *")).not_to_be_visible()
        expect(admin_page.get_by_label("Untagged VLAN")).not_to_be_visible()
        expect(admin_page.get_by_test_id("side-panel-container").get_by_text("Tagged VLANs")).to_be_visible()
        expect(admin_page.get_by_label("Device *")).not_to_be_visible()

    def test_create_interface_l2_profile(self, admin_page: Page, branch: str) -> None:
        # access Interface L2 form
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        expect(admin_page.get_by_role("link", name="backbone_profile")).to_be_visible()
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()

        # fill and submit form
        admin_page.get_by_label("Profile Name *").fill(PROFILE_NAME)
        admin_page.get_by_label("Profile Priority").fill("2000")
        admin_page.get_by_label("MTU").fill("256")
        admin_page.get_by_label("Enabled").check()
        admin_page.get_by_label("Status").click()
        admin_page.get_by_text("Provisioning").click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("InfraInterfaceL2 created")).to_be_visible()

    def test_create_generic_interface_profile(self, admin_page: Page, branch: str) -> None:
        # access Interface form
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        expect(admin_page.get_by_role("link", name="backbone_profile")).to_be_visible()
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Interface Infra", exact=True).click()

        # fill and submit form
        admin_page.get_by_label("Profile Name *").fill(GENERIC_PROFILE_NAME)
        admin_page.get_by_label("Profile Priority").fill("2000")
        admin_page.get_by_label("Status").click()
        admin_page.get_by_text("Maintenance", exact=True).click()
        admin_page.get_by_role("button", name="Save").click()
        expect(admin_page.get_by_text("InfraInterface created")).to_be_visible()

    def test_verify_profile_values_after_creation(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/CoreProfile?branch={branch}")
        admin_page.get_by_role("link", name=PROFILE_NAME).click()
        expect(admin_page.get_by_text("Profile NameInterface L2")).to_be_visible()
        expect(admin_page.get_by_text("Profile Priority2000")).to_be_visible()
        expect(admin_page.get_by_text("MTU256")).to_be_visible()
        expect(admin_page.locator("div").filter(has_text=re.compile(r"^Enabled$")).locator("svg").first).to_be_visible()
        expect(admin_page.get_by_text("Provisioning", exact=True)).to_be_visible()

    def test_verify_available_profiles_in_object_form(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/objects/InfraInterface?branch={branch}")
        expect(admin_page.get_by_role("link", name="Ethernet1", exact=True).first).to_be_visible()
        admin_page.get_by_test_id("create-object-button").click()
        admin_page.get_by_label("Select an object type").click()
        admin_page.get_by_role("option", name="Interface L2 Infra", exact=True).click()
        admin_page.get_by_label("Select profiles optional").click()
        expect(admin_page.get_by_text(PROFILE_NAME, exact=True)).to_be_visible()
        expect(admin_page.get_by_text(GENERIC_PROFILE_NAME)).to_be_visible()
