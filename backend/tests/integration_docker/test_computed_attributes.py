from __future__ import annotations

import time
from asyncio import sleep
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from dulwich.objects import Commit
from infrahub_sdk import InfrahubClient
from infrahub_sdk.task.models import TaskFilter, TaskState
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo

from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


async def wait_for_all_tasks_to_be_completed(client: InfrahubClient) -> None:
    while (  # noqa: ASYNC110
        await client.task.count(filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED]))
        > 0
    ):
        await sleep(1)


async def load_schema_and_wait(client: InfrahubClient, schema: dict, *, branch: str | None = None) -> None:
    """Load a schema, wait for it to converge, and assert it was applied.

    When ``branch`` is omitted, also asserts that the global schema is in sync.
    Per-branch loads skip that check since ``in_sync`` reflects global state.
    """
    if branch is None:
        loaded = await client.schema.load(schemas=[schema], wait_until_converged=True)
    else:
        loaded = await client.schema.load(schemas=[schema], branch=branch, wait_until_converged=True)
    assert loaded.schema_updated
    if branch is None:
        assert await client.schema.in_sync()


def bump_order_weight(field: dict) -> None:
    """Increment ``order_weight`` so the schema diff records a real change.

    Assigning a fixed value would no-op if the field already happened to carry
    that value (for example after an earlier test in the same class run).
    """
    field["order_weight"] = (field.get("order_weight") or 0) + 100


class TestComputedAttributes(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_computed_tshirt(self) -> dict:
        return yaml.safe_load(Path(CURRENT_DIRECTORY / "test_files/computed_tshirt.yml").read_text(encoding="utf-8"))

    async def test_load_schema(self, client: InfrahubClient, schema_computed_tshirt: dict) -> None:
        """Prepare the schema."""
        await load_schema_and_wait(client, schema_computed_tshirt)

    async def test_computed_attribute_update(self, client: InfrahubClient) -> None:
        """Validate that the computed attribute is registered and created and also updated correctly."""
        first_desc = "A Sunset Explorer t-shirt. A bold, vibrant orange that captures the warmth of the setting sun."
        final_desc = "A Sunrise Explorer t-shirt. A striking, lively shade of orange that radiates the golden warmth of a sunrise."
        first_display_label = "Explorer - Sunset"
        final_display_label = "Explorer - Sunrise"
        first_hfid = ["Explorer", "Sunset"]
        final_hfid = ["Explorer", "Sunrise"]
        data = {
            "name": "Sunset",
            "description": "A bold, vibrant orange that captures the warmth of the setting sun.",
        }
        color1 = await client.create(kind="TestingColor", data=data)
        await color1.save()
        data = {
            "name": "Ember Glow",
            "description": "A deep, fiery red-orange reminiscent of smoldering embers at dusk.",
        }
        color2 = await client.create(kind="TestingColor", data=data)
        await color2.save()

        data = {
            "name": "Explorer",
            "color": color1,
        }
        tshirt1 = await client.create(kind="TestingTShirt", data=data)
        await tshirt1.save()

        tshirt1_initial = await client.get(kind="TestingTShirt", id=tshirt1.id)
        color1_initial = await client.get(kind="TestingColor", id=color1.id)

        assert tshirt1_initial.description.value == first_desc
        assert tshirt1_initial.display_label == first_display_label
        assert tshirt1_initial.hfid == first_hfid

        # Validate computed attribute defined on generic
        assert tshirt1_initial.name_code.value == "WEARABLE-EXPLORER"

        color1_initial.name.value = "Sunrise"
        color1_initial.description.value = (
            "A striking, lively shade of orange that radiates the golden warmth of a sunrise."
        )
        await color1_initial.save()

        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            # Give the computed attribute triggers a little while to run
            tshirt1_updated = await client.get(kind="TestingTShirt", id=tshirt1.id)
            if (
                tshirt1_updated.description.value != first_desc
                and tshirt1_updated.display_label != first_display_label
                and tshirt1_updated.hfid != first_hfid
            ):
                break
            await sleep(1)

        assert tshirt1_updated.description.value == final_desc
        assert tshirt1_updated.display_label == final_display_label
        assert tshirt1_updated.hfid == final_hfid

        tshirt1_second_update = await client.get(kind="TestingTShirt", id=tshirt1.id)
        tshirt1_second_update.color = color2
        await tshirt1_second_update.save()

        expected_description = (
            "A Ember Glow Explorer t-shirt. A deep, fiery red-orange reminiscent of smoldering embers at dusk."
        )

        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            # Give the computed attribute triggers a little while to run
            tshirt1_second_update_result = await client.get(kind="TestingTShirt", id=tshirt1.id)
            if tshirt1_second_update_result.description.value == expected_description:
                break
            await sleep(1)

        assert tshirt1_second_update_result.description.value == expected_description
        tshirt1_second_update_result.name.value = "Gardener"
        await tshirt1_second_update_result.save()

        expected_name_code = "WEARABLE-GARDENER"
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            # Give the computed attribute triggers a little while to run
            tshirt1_last_update_result = await client.get(kind="TestingTShirt", id=tshirt1.id)
            if tshirt1_last_update_result.name_code.value == expected_name_code:
                break
            await sleep(1)

        assert tshirt1_last_update_result.name_code.value == expected_name_code

    async def test_transform_based_computed_attribute(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        src_directory = CURRENT_DIRECTORY / "test_files/repos/computed_attribute"
        repo = GitRepo(name="computed_attribute", src_directory=src_directory, dst_directory=remote_repos_dir)
        commit = repo._repo.git[repo._repo.git.head()]
        assert len(list(repo._repo.git.get_walker())) == 1
        assert isinstance(commit, Commit)
        assert commit.message.decode("utf-8") == "First commit"

        response = await repo.add_to_infrahub(client=client)
        assert response.get(f"{repo.type.value}Create", {}).get("ok")

        repos = await client.all(kind=repo.type)
        assert repos

        europe = await client.create(
            kind="LocationContinent",
            data={
                "name": "eu",
            },
        )
        await europe.save()
        sweden = await client.create(
            kind="LocationCountry",
            data={
                "name": "se",
                "parent": europe,
            },
        )
        await sweden.save()
        sth = await client.create(
            kind="LocationSite",
            data={
                "name": "sth",
                "parent": sweden,
            },
        )

        await sth.save()
        france = await client.create(
            kind="LocationCountry",
            data={
                "name": "france",
                "parent": europe,
            },
        )
        await france.save()
        par = await client.create(
            kind="LocationSite",
            data={
                "name": "par",
                "parent": france,
            },
        )
        await par.save()

        sth_router_1 = await client.create(
            kind="InfraDevice",
            data={
                "device_type": "router",
                "instance": 1,
                "site": sth,
            },
        )
        await sth_router_1.save()

        initial_name_router_1 = "se-sth-router-1"
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            # Provide some delay for the triggers to be setup and the computed attribute to render
            sth_router_1_collected = await client.get(kind="InfraDevice", id=sth_router_1.id, include=["name"])
            if sth_router_1_collected.name.value:
                # I (@ogenstad) will investigate why this sleep is required for this test
                await sleep(1)
                break
            await sleep(1)

        assert sth_router_1_collected.name.value == initial_name_router_1
        sweden_name_update = await client.get(kind="LocationCountry", id=sweden.id)
        sweden_name_update.name.value = "swe"
        await sweden_name_update.save()

        swe_name_router_1 = "swe-sth-router-1"
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            # Give the computed attribute triggers a little while to run
            sth_router_1_swe = await client.get(kind="InfraDevice", id=sth_router_1.id, include=["name"])
            if sth_router_1_swe.name.value == swe_name_router_1:
                break
            await sleep(1)

        assert sth_router_1_swe.name.value == swe_name_router_1

    async def test_update_schema_not_related_to_computed_attribute(
        self, client: InfrahubClient, schema_computed_tshirt: dict
    ) -> None:
        nbr_task_before = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name])
        )

        # Update schema LocationSite with a change that IS NOT related to the computed attribute
        # The computed attribute of type Jinja2 should not be updated neither on the sites nor on the continents
        schema_computed_tshirt["nodes"][4]["description"] = "New Description that will trigger a new schema"
        await load_schema_and_wait(client, schema_computed_tshirt)

        await sleep(1)
        await wait_for_all_tasks_to_be_completed(client)

        nbr_task_after_not_related = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name])
        )
        assert nbr_task_after_not_related == nbr_task_before

        # Update schema LocationSite with a change that IS related to the computed attribute
        # The computed attribute of type Jinja2 should be updated
        schema_computed_tshirt["nodes"][4]["attributes"][3]["computed_attribute"]["jinja2_template"] = (
            "WELCOME TO {{ name__value }}!"
        )
        await load_schema_and_wait(client, schema_computed_tshirt)

        # Wait for the computed attribute tasks to be created and completed
        # Tasks may not be created immediately after schema load, so poll for them
        nbr_task_after_related = nbr_task_after_not_related
        deadline = time.monotonic() + PREFECT_EVENT_WAIT_SECONDS
        while time.monotonic() < deadline:
            await sleep(1)
            await wait_for_all_tasks_to_be_completed(client)
            nbr_task_after_related = await client.task.count(
                filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name])
            )
            if nbr_task_after_related >= nbr_task_after_not_related + 2:
                break

        # The computed attribute of type Jinja2 should be updated on the sites but NOT on the continents
        assert nbr_task_after_related == nbr_task_after_not_related + 2

    async def test_jinja2_scoped_recompute_on_read_field_change(
        self, client: InfrahubClient, schema_computed_tshirt: dict
    ) -> None:
        """A Jinja2 attribute recomputes when a field it reads across a relationship changes.

        TestingTShirt.description reads color__name__value, so a schema change to TestingColor.name
        recomputes it, while a change to a field no template reads recomputes nothing — the template
        itself is untouched in both cases (this is the read-field path, not a definition edit).
        """
        jinja2_before = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name])
        )

        # Unrelated: re-order a LocationSite field that no template reads -> no recompute.
        bump_order_weight(schema_computed_tshirt["nodes"][4]["attributes"][1])  # LocationSite.address
        await load_schema_and_wait(client, schema_computed_tshirt)

        await sleep(1)
        await wait_for_all_tasks_to_be_completed(client)
        jinja2_after_unrelated = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name])
        )
        assert jinja2_after_unrelated == jinja2_before

        # Related: re-order TestingColor.name, which TestingTShirt.description reads via the color relationship.
        bump_order_weight(schema_computed_tshirt["nodes"][0]["attributes"][0])  # TestingColor.name
        await load_schema_and_wait(client, schema_computed_tshirt)

        jinja2_after_related = jinja2_after_unrelated
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            await sleep(1)
            await wait_for_all_tasks_to_be_completed(client)
            jinja2_after_related = await client.task.count(
                filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name])
            )
            if jinja2_after_related > jinja2_after_unrelated:
                break

        assert jinja2_after_related > jinja2_after_unrelated

    async def test_python_scoped_recompute_on_read_field_change(
        self, client: InfrahubClient, schema_computed_tshirt: dict
    ) -> None:
        """A Python-transform attribute recomputes only when a field its query reads changes.

        The DeviceNameAttribute query reads InfraDevice.device_type, so a schema change to that field
        recomputes InfraDevice.name, while a change to a field the query does not read recomputes nothing.
        """
        python_before = await client.task.count(
            filters=TaskFilter(workflow=[TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name])
        )

        # Unrelated: re-order a LocationSite field the transform query does not read -> no recompute.
        bump_order_weight(schema_computed_tshirt["nodes"][4]["attributes"][2])  # LocationSite.contact
        await load_schema_and_wait(client, schema_computed_tshirt)

        await sleep(1)
        await wait_for_all_tasks_to_be_completed(client)
        python_after_unrelated = await client.task.count(
            filters=TaskFilter(workflow=[TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name])
        )
        assert python_after_unrelated == python_before

        # Related: re-order InfraDevice.device_type, which the DeviceNameAttribute query reads.
        bump_order_weight(schema_computed_tshirt["nodes"][5]["attributes"][0])  # InfraDevice.device_type
        await load_schema_and_wait(client, schema_computed_tshirt)

        python_after_related = python_after_unrelated
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            await sleep(1)
            await wait_for_all_tasks_to_be_completed(client)
            python_after_related = await client.task.count(
                filters=TaskFilter(workflow=[TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name])
            )
            if python_after_related > python_after_unrelated:
                break

        assert python_after_related > python_after_unrelated

    async def test_branch_isolation_scopes_recompute_to_changed_branch(
        self, client: InfrahubClient, schema_computed_tshirt: dict
    ) -> None:
        """A schema change on one branch recomputes only that branch's attributes.

        Changing a Jinja2 template on an isolated branch recomputes that branch's objects but
        must not recompute anything on the default branch — branch scoping is applied before and
        independently of changed-element scoping, so a change on one branch never broadens
        recompute onto another.
        """
        branch = await client.branch.create(branch_name="scope-isolation")

        main_before = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name], branch="main")
        )
        branch_before = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name], branch=branch.name)
        )

        # Change the LocationSite.slug template only on the isolated branch.
        branch_schema = deepcopy(schema_computed_tshirt)
        branch_schema["nodes"][4]["attributes"][3]["computed_attribute"]["jinja2_template"] = (
            "Isolated branch: {{ name__value }}"
        )
        await load_schema_and_wait(client, branch_schema, branch=branch.name)

        branch_after = branch_before
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            await sleep(1)
            await wait_for_all_tasks_to_be_completed(client)
            branch_after = await client.task.count(
                filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name], branch=branch.name)
            )
            if branch_after > branch_before:
                break

        main_after = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name], branch="main")
        )

        # The changed branch recomputed; the default branch was left untouched.
        assert branch_after > branch_before
        assert main_after == main_before

    async def test_merge_does_not_trigger_schema_scoped_recompute(
        self, client: InfrahubClient, schema_computed_tshirt: dict
    ) -> None:
        """Merging a branch's schema change does not run this feature's schema-scoped recompute.

        Merge and rebase emit branch and node events, not a schema-update event, so the
        computed-attribute setup flow is not triggered on merge. A schema-only change applied by a
        merge (no object-data change) therefore does not recompute on the target branch; merged
        data changes are recomputed by the separate data-change path. This characterizes the
        boundary and confirms a merge never broadens recompute onto the default branch.
        """
        branch = await client.branch.create(branch_name="merge-scope")

        # Schema-only change on the branch (a Jinja2 template edit); no object data is touched.
        branch_schema = deepcopy(schema_computed_tshirt)
        branch_schema["nodes"][1]["attributes"][1]["computed_attribute"]["jinja2_template"] = (
            "Merged template: {{ name__value }}"  # TestingTShirt.description
        )
        await load_schema_and_wait(client, branch_schema, branch=branch.name)

        await sleep(1)
        await wait_for_all_tasks_to_be_completed(client)
        main_before = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name], branch="main")
        )

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged

        # Give any merge-driven work time to surface, then confirm no schema-scoped recompute ran.
        await sleep(2)
        await wait_for_all_tasks_to_be_completed(client)
        main_after = await client.task.count(
            filters=TaskFilter(workflow=[COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE.name], branch="main")
        )

        assert main_after == main_before
