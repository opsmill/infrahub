"""The proposed-change schema-integrity check must validate relationship changes.

`_get_proposed_change_schema_integrity_constraints` consumes the output of
``client.get_diff_summary()``. This drives that real SDK output through the function and asserts a
relationship change produces relationship constraints, the same way an attribute change does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.dependencies.registry import get_component_registry
from infrahub.proposed_change.tasks import _get_proposed_change_schema_integrity_constraints  # noqa: PLC2701
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestSchemaIntegrityRelationshipConstraints(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> dict[str, str]:
        await load_schema(db, schema=CAR_SCHEMA)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)
        cyberdyne = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await cyberdyne.new(db=db, name="Cyberdyne")
        await cyberdyne.save(db=db)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)
        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(db=db, name="Jesko", color="Red", owner=john, manufacturer=koenigsegg)
        await jesko.save(db=db)
        return {"car_id": jesko.id, "cyberdyne_id": cyberdyne.id}

    async def test_relationship_change_produces_schema_integrity_constraints(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        client: InfrahubClient,
    ) -> None:
        branch = await client.branch.create(branch_name="change_car")
        car = await NodeManager.get_one(db=db, id=initial_dataset["car_id"], branch=branch.name)
        assert car
        # One attribute change and one cardinality-one relationship change on the same node.
        car.color.value = "Blue"  # type: ignore[attr-defined]
        await car.get_relationship("manufacturer").update(db=db, data={"id": initial_dataset["cyberdyne_id"]})
        await car.save(db=db)

        component_registry = get_component_registry()
        source = await Branch.get_by_name(db=db, name=branch.name)
        base = await Branch.get_by_name(db=db, name=registry.default_branch)
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=source)
        await diff_coordinator.update_branch_diff(base_branch=base, diff_branch=source)

        # The real SDK output the proposed-change pipeline consumes.
        diff_summary = await client.get_diff_summary(branch=branch.name)

        # Sanity: the SDK summary really does surface both changes on the car, so a missing
        # relationship constraint below is the function dropping it, not the SDK omitting it.
        car_elements = {
            element["name"]: element["element_type"]
            for node_diff in diff_summary
            if node_diff["kind"] == TestKind.CAR
            for element in node_diff["elements"]
        }
        assert "color" in car_elements
        assert "manufacturer" in car_elements
        assert "RELATIONSHIP" in car_elements["manufacturer"].upper()

        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        constraints = await _get_proposed_change_schema_integrity_constraints(
            db=db, schema=schema_branch, diff_summary=diff_summary, branch=source
        )
        constrained_fields = {(c.path.schema_kind, c.path.field_name) for c in constraints}

        # The attribute change is turned into constraints today.
        assert (TestKind.CAR, "color") in constrained_fields
        # The relationship change must be too (cardinality/count/peer validation).
        assert (TestKind.CAR, "manufacturer") in constrained_fields
