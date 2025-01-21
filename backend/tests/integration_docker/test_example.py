import re
from playwright.sync_api import Page, expect

from infrahub.testing.helpers import TestInfrahub


class TestPaul(TestInfrahub):
    def test_infrahub(self, infrahub_port, infrahub_client_sync, page: Page):
        infrahub_client_sync.branch.create(branch_name='test', description='test')
        infrahub_client_sync.create(branch="test", kind="BuiltinTag", data={ "name": "purple" }).save()

        page.goto(f'http://localhost:{infrahub_port}/objects/BuiltinTag?branch=test')

        expect(page).to_have_title(re.compile("Infrahub"))
        expect(page.get_by_test_id("branch-selector-trigger")).to_contain_text("test")
        expect(page.get_by_role("link", name="purple")).to_be_visible()

