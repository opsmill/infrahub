from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect.client.orchestration import get_client as get_prefect_client

from infrahub.computed_attribute.tasks import process_transform_lifecycle
from infrahub.core.constants import InfrahubKind, MutationAction, RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import ScopedRecomputeTestBase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


# Two independent Python transforms, each feeding a different computed attribute, plus a third
# transform that feeds nothing. ``computed_a``/``computed_b`` wire their transform by name.
# ``computed_by_id`` wires its transform by the transform's UUID (set once the node exists), so
# the resolver's id fallback is exercised end to end.
CAR_PERSON_LIFECYCLE_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Car",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="nbr_seats", kind="Number", optional=True),
                AttributeSchema(
                    name="computed_a",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform_a",
                    ),
                ),
                AttributeSchema(
                    name="computed_b",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform_b",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(
                    name="owner",
                    peer="TestPerson",
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                ),
            ],
        ),
        NodeSchema(
            name="Person",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(name="cars", peer="TestCar", cardinality=RelationshipCardinality.MANY),
            ],
        ),
    ]
)


async def _make_transform(
    db: InfrahubDatabase,
    default_branch: Branch,
    name: str,
    repository: Node,
) -> Node:
    """Create a query and a Python transform reading TestCar.name.

    The edges/node structure is what the analyzer needs to record the field as a read.
    """
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query.new(
        db=db,
        name=f"query_{name}",
        query="query { TestCar { edges { node { name { value } } } } }",
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

        transform_a = await _make_transform(
            db=db, default_branch=default_branch, name="transform_a", repository=repository
        )
        transform_b = await _make_transform(
            db=db, default_branch=default_branch, name="transform_b", repository=repository
        )
        # Feeds no computed attribute: it is the scoping-floor transform.
        transform_orphan = await _make_transform(
            db=db, default_branch=default_branch, name="transform_orphan", repository=repository
        )
        # Wired into ``computed_by_id`` by its UUID once the node exists.
        transform_by_id = await _make_transform(
            db=db, default_branch=default_branch, name="transform_by_id", repository=repository
        )

        schema = CAR_PERSON_LIFECYCLE_SCHEMA.duplicate()
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
            "transform_a": transform_a.id,
            "transform_b": transform_b.id,
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
            transform_id=transform_dataset["transform_a"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {"computed_a"}

    async def test_update_of_transform_feeding_nothing_submits_no_recompute(
        self,
        transform_dataset: dict[str, str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        # The other half of "an unrelated change produces no recompute" is the update trigger's
        # match filter (fingerprint-only); that is covered by the trigger-match unit test in
        # test_triggers.py. Here the resolver returns empty, so nothing is submitted.
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
            transform_id=transform_dataset["transform_b"],
            action=MutationAction.CREATED.value,
            context=self._context(admin_account, default_branch),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {"computed_b"}

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
        # Automation names are ``computed_attr_python::<branch>::<kind>_<attribute>``, one per
        # (transform -> attribute) wiring the gather resolves from the schema and the transform nodes.
        def automation(attribute: str) -> str:
            return f"{TriggerType.COMPUTED_ATTR_PYTHON.value}{NAME_SEPARATOR}{default_branch.name}{NAME_SEPARATOR}TestCar_{attribute}"

        automation_a = automation("computed_a")
        automation_b = automation("computed_b")
        # ``computed_a`` and ``computed_b`` wire their transform by name, so the gather (which looks
        # transforms up by name) resolves both. ``computed_by_id`` wires its transform by UUID, which
        # the name lookup never finds, and ``transform_orphan`` feeds nothing; neither yields an
        # automation. So the full node-input set is exactly A and B.
        automations_full = {automation_a, automation_b}

        # Reconcile once with the full wiring so every automation exists to begin with; without this
        # baseline the assertion that A is dropped could pass on a set that never had A.
        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform_b"],
            action=MutationAction.UPDATED.value,
            context=self._context(admin_account, default_branch),
        )
        automations_before = await self._python_automation_names()
        assert automations_before == automations_full

        # Remove transform A's wiring the way a real transform delete does: drop the node and the
        # computed-attribute definition that referenced it, so the gathered set no longer yields A.
        schema = CAR_PERSON_LIFECYCLE_SCHEMA.duplicate()
        car = next(node for node in schema.nodes if node.name == "Car")
        car.attributes = [attribute for attribute in car.attributes if attribute.name != "computed_a"]
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

        transform_a = await NodeManager.get_one(id=transform_dataset["transform_a"], db=db, branch=default_branch)
        assert transform_a is not None
        await transform_a.delete(db=db)

        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

        await process_transform_lifecycle(
            branch_name=default_branch.name,
            transform_id=transform_dataset["transform_a"],
            action=MutationAction.DELETED.value,
            context=self._context(admin_account, default_branch),
        )

        # The delete leg never recomputes; the whole point is that reconciliation prunes A.
        assert self._submitted_attribute_names(workflow_recorder) == set()

        # Only A's automation is gone; the exact remaining set is B alone.
        automations_after = await self._python_automation_names()
        assert automations_after == {automation_b}
