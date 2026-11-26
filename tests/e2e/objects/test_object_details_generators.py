"""Generators section of the node Actions menu.

A node's Actions menu lists the generator definitions whose target group holds nodes of the node's
kind, runs one for that node only, disables it for a node outside the target group, and hides the
section where no generator applies or the user may not run one. The demo-edge repository supplies
the definitions; only `update_upstream_interfaces_description` has a populated target group
(`upstream_interfaces`, the edge routers' upstream L3 interfaces, Ethernet5 and Ethernet6).
Generators run only on throwaway branches so main keeps no generator instance.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page, Response

DEVICE_NAME = "atl1-edge1"
MEMBER_INTERFACE = "Ethernet5"
NON_MEMBER_INTERFACE = "Ethernet7"
TARGET_GROUP = "upstream_interfaces"
GENERATOR_NAME = "update_upstream_interfaces_description"
RUN_ITEM = f"Run {GENERATOR_NAME}"

TASK_FINAL_STATES = {"COMPLETED", "FAILED", "CRASHED", "CANCELLED"}
# The link keeps the page's branch query parameter after the task id.
TASK_HREF = re.compile(r"/tasks/([0-9a-f-]+)(?:\?|$)")

TASK_STATE_QUERY = """
query TaskState($id: String!) {
  InfrahubTask(ids: [$id]) {
    edges {
      node {
        state
      }
    }
  }
}
"""


async def read_task_state(client: InfrahubClient, task_id: str) -> str:
    response = await client.execute_graphql(
        query=TASK_STATE_QUERY, variables={"id": task_id}, tracker="query-task-state"
    )
    return response["InfrahubTask"]["edges"][0]["node"]["state"]


async def wait_for_task_end(client: InfrahubClient, task_id: str) -> str:
    deadline = Deadline(f"task {task_id} to end")
    while (state := await read_task_state(client, task_id)) not in TASK_FINAL_STATES:
        await deadline.tick(pause=2)
    return state


async def get_interface_id(client: InfrahubClient, name: str, branch: str) -> str:
    device = await client.get(kind="InfraDevice", name__value=DEVICE_NAME, branch=branch)
    interface = await client.get(kind="InfraInterfaceL3", device__ids=[device.id], name__value=name, branch=branch)
    return interface.id


def graphql_operation(name: str) -> Callable[[Response], bool]:
    def matches(response: Response) -> bool:
        return "/graphql" in response.url and name in (response.request.post_data or "")

    return matches


async def open_actions_menu(page: Page, after_operation: str | None = None) -> None:
    """Open the Actions menu, waiting for the named GraphQL operation the menu sends when given.

    Waiting for the request that decides the Generators section keeps an absence check from passing
    before the section had a chance to render.
    """
    menu_button = page.get_by_test_id("object-details-menu")
    if after_operation is None:
        await menu_button.click()
    else:
        async with page.expect_response(graphql_operation(after_operation)):
            await menu_button.click()
    await expect(page.get_by_role("menuitem", name="Copy ID")).to_be_visible()


async def expect_no_generators_section(page: Page) -> None:
    await expect(page.get_by_role("menuitem", name=RUN_ITEM)).to_have_count(0)
    await expect(page.get_by_role("menu").get_by_text("Generators", exact=True)).to_have_count(0)


@pytest.mark.usefixtures("demo_edge_repo")
class TestObjectDetailsGenerators:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("node-generators")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_run_generator_from_member_page(
        self, admin_page: Page, infrahub_client: InfrahubClient, branch: str
    ) -> None:
        interface_id = await get_interface_id(infrahub_client, MEMBER_INTERFACE, branch)
        await admin_page.goto(f"/objects/InfraInterfaceL3/{interface_id}?branch={branch}")

        await admin_page.get_by_test_id("object-details-menu").click()
        await admin_page.get_by_role("menuitem", name=RUN_ITEM).click()

        await expect(
            admin_page.get_by_text(f"Generator {GENERATOR_NAME} started for {MEMBER_INTERFACE}.")
        ).to_be_visible()
        task_link = admin_page.get_by_role("link", name="View task")
        await expect(task_link).to_have_attribute("href", TASK_HREF)
        href = await task_link.get_attribute("href")
        match = TASK_HREF.search(href or "")
        assert match is not None
        task_id = match.group(1)

        assert await wait_for_task_end(infrahub_client, task_id) == "COMPLETED"
        definition = await infrahub_client.get(
            kind="CoreGeneratorDefinition", name__value=GENERATOR_NAME, branch=branch
        )
        instances = await infrahub_client.filters(
            kind="CoreGeneratorInstance", definition__ids=[definition.id], branch=branch
        )
        assert [instance.object.id for instance in instances] == [interface_id]

    async def test_section_hidden_for_untargeted_kind(
        self, admin_page: Page, infrahub_client: InfrahubClient, branch: str
    ) -> None:
        site = await infrahub_client.get(kind="LocationSite", name__value="atl1", branch=branch)
        await admin_page.goto(f"/objects/LocationSite/{site.id}?branch={branch}")
        await open_actions_menu(admin_page, after_operation="GetTargetGroupKindCounts")
        await expect_no_generators_section(admin_page)

    async def test_section_hidden_for_kind_of_an_empty_target_group(
        self, admin_page: Page, infrahub_client: InfrahubClient, branch: str
    ) -> None:
        circuits = await infrahub_client.filters(kind="InfraCircuit", branch=branch, limit=1)
        await admin_page.goto(f"/objects/InfraCircuit/{circuits[0].id}?branch={branch}")
        await open_actions_menu(admin_page, after_operation="GetTargetGroupKindCounts")
        await expect_no_generators_section(admin_page)

    async def test_section_hidden_without_edit_default_branch(
        self, read_only_page: Page, infrahub_client: InfrahubClient
    ) -> None:
        interface_id = await get_interface_id(infrahub_client, MEMBER_INTERFACE, "main")
        await read_only_page.goto(f"/objects/InfraInterfaceL3/{interface_id}")
        await open_actions_menu(read_only_page, after_operation="InfrahubGlobalPermissions")
        await expect_no_generators_section(read_only_page)

    async def test_section_shown_on_branch_without_edit_default_branch(
        self, read_only_page: Page, infrahub_client: InfrahubClient, branch: str
    ) -> None:
        interface_id = await get_interface_id(infrahub_client, MEMBER_INTERFACE, branch)
        await read_only_page.goto(f"/objects/InfraInterfaceL3/{interface_id}?branch={branch}")
        await open_actions_menu(read_only_page)
        run_item = read_only_page.get_by_role("menuitem", name=RUN_ITEM)
        await expect(run_item).to_be_visible()
        await expect(run_item).not_to_have_attribute("aria-disabled", "true")

    async def test_section_hidden_when_signed_out(self, page: Page, infrahub_client: InfrahubClient) -> None:
        interface_id = await get_interface_id(infrahub_client, MEMBER_INTERFACE, "main")
        await page.goto(f"/objects/InfraInterfaceL3/{interface_id}")
        await open_actions_menu(page)
        await expect_no_generators_section(page)

    async def test_item_disabled_until_node_joins_target_group(
        self, admin_page: Page, infrahub_client: InfrahubClient, branch: str
    ) -> None:
        interface_id = await get_interface_id(infrahub_client, NON_MEMBER_INTERFACE, branch)
        await admin_page.goto(f"/objects/InfraInterfaceL3/{interface_id}?branch={branch}")
        await open_actions_menu(admin_page)

        run_item = admin_page.get_by_role("menuitem", name=RUN_ITEM)
        await expect(run_item).to_have_attribute("aria-disabled", "true")
        await run_item.hover()
        await expect(admin_page.get_by_role("tooltip")).to_have_text(
            f"{NON_MEMBER_INTERFACE} is not a member of the target group {TARGET_GROUP}"
        )
        await admin_page.keyboard.press("Escape")

        group = await infrahub_client.get(kind="CoreStandardGroup", name__value=TARGET_GROUP, branch=branch)
        await group.members.fetch()
        group.members.add(interface_id)
        await group.save()

        await admin_page.reload()
        await open_actions_menu(admin_page)
        await expect(run_item).to_be_visible()
        await expect(run_item).not_to_have_attribute("aria-disabled", "true")
