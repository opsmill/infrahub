from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect.client.orchestration import get_client as get_prefect_client

from infrahub.computed_attribute.tasks import process_transform_lifecycle
from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import CAR_PERSON_PYTHON_SCHEMA, ScopedRecomputeTestBase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


async def _make_transform(db: InfrahubDatabase, name: str, repository: Node) -> Node:
    """Create a query and a Python transform for the given name."""
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query.new(
        db=db,
        name=f"query_{name}",
        query="query TestCarQuery($id: ID!) { TestCar(ids: [$id]) { edges { node { name { value } } } } }",
        models=["TestCar", "TestPerson"],
    )
    await query.save(db=db)

    transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
    await transform.new(
        db=db, name=name, file_path="transform.py", class_name="Transform", query=query, repository=repository
    )
    await transform.save(db=db)
    return transform


class TestTransformLifecycleRecompute(ScopedRecomputeTestBase):
    WORKFLOW = TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES

    @pytest.fixture(scope="class")
    async def transform_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> dict[str, str]:
        repository = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await repository.new(db=db, name="repo01", ref=default_branch.name, commit="commit01", location="location01")
        await repository.save(db=db)

        # transform01 and transform_opaque are wired by name in the shared schema; query content
        # does not matter here since the lifecycle flow recomputes every attribute they feed.
        transform01 = await _make_transform(db=db, name="transform01", repository=repository)
        transform_opaque = await _make_transform(db=db, name="transform_opaque", repository=repository)
        # Feeds no computed attribute.
        transform_orphan = await _make_transform(db=db, name="transform_orphan", repository=repository)
        # Wired into computed_by_id by its UUID, exercising the resolver's id path.
        transform_by_id = await _make_transform(db=db, name="transform_by_id", repository=repository)

        schema = CAR_PERSON_PYTHON_SCHEMA.duplicate()
        car = next(node for node in schema.nodes if node.name == "Car")
        car.attributes.append(
            AttributeSchema(
                name="computed_by_id",
                kind="Text",
                read_only=True,
                optional=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                    transform=transform_by_id.id,
                ),
            )
        )
        await load_schema(db=db, schema=schema, update_db=True)

        return {
            "transform01": transform01.id,
            "transform_opaque": transform_opaque.id,
            "transform_orphan": transform_orphan.id,
            "transform_by_id": transform_by_id.id,
        }

    async def test_update_recomputes_only_changed_transform_attribute(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform01"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {"computed_desc_python"}

    async def test_update_of_transform_feeding_nothing_submits_no_recompute(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        # The transform feeds nothing, so the resolver returns empty and nothing is submitted.
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform_orphan"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == set()

    async def test_update_resolves_transform_wired_by_id(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform_by_id"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {"computed_by_id"}

    async def test_created_recomputes_only_created_transform_attribute(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform_opaque"],
            action=MutationAction.CREATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {"computed_desc_python_opaque"}

    async def _python_automation_names(self) -> set[str]:
        async with get_prefect_client(sync_client=False) as prefect_client:
            automations = await gather_all_automations(client=prefect_client)
        return {
            automation.name
            for automation in automations
            if automation.name.startswith(f"{TriggerType.COMPUTED_ATTR_PYTHON.value}{NAME_SEPARATOR}")
        }

    async def test_updated_with_missing_transform_does_not_raise_and_still_reconciles(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id="00000000-0000-0000-0000-000000000000",
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == set()
        assert await self._python_automation_names(), "a missing transform must still reconcile the automations"

    async def test_delete_drops_removed_transform_automation_but_keeps_others(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        db: InfrahubDatabase,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        # Automation names are ``computed_attr_python::<branch>::TestCar_<attribute>``.
        def automation(attribute: str) -> str:
            return f"{TriggerType.COMPUTED_ATTR_PYTHON.value}{NAME_SEPARATOR}{default_branch.name}{NAME_SEPARATOR}TestCar_{attribute}"

        automation_desc = automation("computed_desc_python")
        automation_opaque = automation("computed_desc_python_opaque")
        # Both attributes wire their transform by name, so the gather resolves an automation for
        # each; computed_by_id (by UUID) and the orphan yield none, so the full set is just these two.
        automations_full = {automation_desc, automation_opaque}

        # Reconcile once so both automations exist before asserting one gets dropped.
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform_opaque"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )
        automations_before = await self._python_automation_names()
        assert automations_before == automations_full

        # Remove the wiring the way a real delete does: drop the attribute definition and the node,
        # so the gathered set no longer yields it.
        schema = CAR_PERSON_PYTHON_SCHEMA.duplicate()
        car = next(node for node in schema.nodes if node.name == "Car")
        car.attributes = [attribute for attribute in car.attributes if attribute.name != "computed_desc_python"]
        car.attributes.append(
            AttributeSchema(
                name="computed_by_id",
                kind="Text",
                read_only=True,
                optional=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                    transform=transform_dataset["transform_by_id"],
                ),
            )
        )
        await load_schema(db=db, schema=schema, update_db=True)

        transform_to_delete = await NodeManager.get_one(
            id=transform_dataset["transform01"], db=db, branch=default_branch
        )
        assert transform_to_delete is not None
        await transform_to_delete.delete(db=db)

        workflow_recorder.reset()

        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform01"],
            action=MutationAction.DELETED.value,
            context=self._context(admin_account, default_branch),
        )

        # The delete leg never recomputes; reconciliation prunes the wiring instead.
        assert self._submitted_attribute_names(workflow_recorder) == set()

        # Only the deleted transform's automation is gone.
        automations_after = await self._python_automation_names()
        assert automations_after == {automation_opaque}
