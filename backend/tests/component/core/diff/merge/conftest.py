"""Shared fixtures and helpers for the diff-and-merge matrix tests."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipDirection
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.dependencies.registry import get_component_registry
from tests.conftest import do_car_person_schema_unregistered

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def diff_repository(db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
    component_registry = get_component_registry()
    return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)


async def get_diff_coordinator(db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    return coordinator


async def get_diff_merger(db: InfrahubDatabase, branch: Branch) -> DiffMerger:
    component_registry = get_component_registry()
    return await component_registry.get_component(DiffMerger, db=db, branch=branch)


@pytest.fixture(autouse=True)
async def _setup_core_schema(register_core_models_schema: SchemaBranch) -> None:
    """Ensure the core schema is registered for every matrix test."""
    return


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
) -> SchemaBranch:
    """Overrides the shared fixture to add an AGNOSTIC ``TestManufacturer`` peer.

    Extends the standard car_person schema with:
    - ``TestManufacturer`` node (``branch: AGNOSTIC``) with ``name``, ``country``.
    - Optional one-card rel ``TestCar.manufacturer`` -> ``TestManufacturer``.
    - Reverse many-card rel ``TestManufacturer.cars`` -> ``TestCar``.

    This lets the matrix exercise aware-to-agnostic relationship add/clear
    without modifying the shared schema used by other test suites.
    """
    schema_root = copy.deepcopy(do_car_person_schema_unregistered())

    test_car = next(n for n in schema_root.nodes if n.name == "Car" and n.namespace == "Test")
    test_car.attributes.append(AttributeSchema(name="tags", kind="List", optional=True))
    test_car.relationships.append(
        RelationshipSchema(
            name="manufacturer",
            peer="TestManufacturer",
            identifier="testcar__manufacturer",
            optional=True,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        )
    )

    schema_root.nodes.append(
        NodeSchema(
            name="Manufacturer",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            branch=BranchSupportType.AGNOSTIC,
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="country", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="cars",
                    peer="TestCar",
                    identifier="testcar__manufacturer",
                    cardinality=RelationshipCardinality.MANY,
                    direction=RelationshipDirection.INBOUND,
                ),
            ],
        )
    )

    return registry.schema.register_schema(schema=schema_root, branch=default_branch.name)


@pytest.fixture
async def manufacturer_toyota_main(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> Node:
    """A pre-existing AGNOSTIC manufacturer on main.

    Used as the branch-side peer for aware-to-agnostic relationship add/clear
    scenarios: the matrix test either points a TestCar's ``manufacturer`` at
    this node or clears a pre-existing link to it.
    """
    m = await Node.init(db=db, schema="TestManufacturer", branch=default_branch)
    await m.new(db=db, name="Toyota", country="Japan")
    await m.save(db=db, user_id="main-setup-user")
    return m


@pytest.fixture
async def manufacturer_honda_main(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> Node:
    """A second AGNOSTIC manufacturer, used as the base-side conflict peer for manufacturer rels."""
    m = await Node.init(db=db, schema="TestManufacturer", branch=default_branch)
    await m.new(db=db, name="Honda", country="Japan")
    await m.save(db=db, user_id="main-setup-user")
    return m


@pytest.fixture
async def car_no_manufacturer_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
) -> Node:
    """A TestCar on main with no ``manufacturer`` set; matrix stages a branch-side add."""
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="no-manuf", nbr_seats=4, is_electric=False, owner=person_john_main.id)
    await car.save(db=db, user_id="main-setup-user")
    return await NodeManager.get_one(db=db, branch=default_branch, id=car.id)


@pytest.fixture
async def car_tagged_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
) -> Node:
    """A TestCar on main with a pre-existing list-typed ``tags`` value.

    Matrix tests use this to exercise an ``updated_attribute_value`` change
    against a list attribute — complements the scalar case on ``car_accord``.
    """
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        name="tagged",
        nbr_seats=4,
        is_electric=False,
        owner=person_john_main.id,
        tags=["alpha", "beta"],
    )
    await car.save(db=db, user_id="main-setup-user")
    return car


@pytest.fixture
async def car_with_manufacturer_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    manufacturer_toyota_main: Node,
    car_person_schema: SchemaBranch,
) -> Node:
    """A TestCar on main with ``manufacturer=Toyota`` set; matrix stages a branch-side clear."""
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        name="with-manuf",
        nbr_seats=4,
        is_electric=False,
        owner=person_john_main.id,
        manufacturer=manufacturer_toyota_main.id,
    )
    await car.save(db=db, user_id="main-setup-user")
    return await NodeManager.get_one(db=db, branch=default_branch, id=car.id)


@pytest.fixture
async def car_prop_cleared_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    car_person_schema: SchemaBranch,
) -> Node:
    """A TestCar on main with pre-existing property values that a branch can clear.

    Matrix tests use this to exercise ``cleared_attribute_property`` and
    ``cleared_relationship_property`` — both require the property to be present
    on main before the branch forks.
    """
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        name="prop-cleared",
        nbr_seats=5,
        is_electric=False,
        owner={"id": person_john_main.id, "_relation__source": person_alfred_main.id},
        driver={"id": person_jane_main.id, "_relation__source": person_alfred_main.id},
    )
    car.color.source = person_alfred_main
    car.color.value = "#CCCCCC"
    car.name.source = person_alfred_main
    await car.save(db=db, user_id="main-setup-user")
    # re-fetch so callers have the final state
    return await NodeManager.get_one(db=db, branch=default_branch, id=car.id)


@pytest.fixture
async def car_driver_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    car_person_schema: SchemaBranch,
) -> Node:
    """A TestCar on main with an optional one-relationship (``driver``) set to jane.

    Matrix tests use this to exercise ``cleared_one_relationship`` — clearing
    requires an existing peer.
    """
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        name="with-driver",
        nbr_seats=2,
        is_electric=False,
        owner=person_john_main.id,
        driver=person_jane_main.id,
    )
    await car.save(db=db, user_id="main-setup-user")
    return await NodeManager.get_one(db=db, branch=default_branch, id=car.id)
