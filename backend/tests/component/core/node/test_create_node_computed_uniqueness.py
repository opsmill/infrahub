from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.node.create import create_node
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import HFIDViolatedError, ValidationError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def car_schema_computed_hfid(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema where the human-friendly id is a required computed attribute derived from a local attribute."""
    SCHEMA = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "display_label": "name__value",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {
                        "name": "name",
                        "kind": "Text",
                        "computed_attribute": {
                            "kind": "Jinja2",
                            "jinja2_template": "{{ model__value | upper }}-CAR",
                        },
                        "read_only": True,
                        "unique": True,
                        "optional": False,
                    },
                    {"name": "model", "kind": "Text"},
                ],
            },
        ],
    }
    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def car_schema_computed_from_relationship(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema where the unique computed attribute is derived from an attribute on a peer relationship."""
    SCHEMA = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "display_label": "name__value",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {
                        "name": "name",
                        "kind": "Text",
                        "computed_attribute": {
                            "kind": "Jinja2",
                            "jinja2_template": "{{ owner__name__value | upper }}-CAR",
                        },
                        "read_only": True,
                        "unique": True,
                        "optional": False,
                    },
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "identifier": "person__car",
                        "optional": False,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "cars", "peer": "TestCar", "identifier": "person__car", "cardinality": "many"},
                ],
            },
        ],
    }
    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def car_schema_computed_secondary_unique(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema where a unique computed attribute exists alongside a separate, non-computed human-friendly id."""
    SCHEMA = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "display_label": "name__value",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {
                        "name": "vin",
                        "kind": "Text",
                        "computed_attribute": {
                            "kind": "Jinja2",
                            "jinja2_template": "VIN-{{ model__value | upper }}",
                        },
                        "read_only": True,
                        "unique": True,
                        "optional": False,
                    },
                    {"name": "model", "kind": "Text"},
                ],
            },
        ],
    }
    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


async def test_create_node_rejects_duplicate_computed_hfid(
    db: InfrahubDatabase, default_branch: Branch, car_schema_computed_hfid: SchemaRoot
) -> None:
    car_schema = registry.schema.get_node_schema(name="TestCar", branch=default_branch)

    first = await create_node(data={"model": "mustang"}, db=db, branch=default_branch, schema=car_schema)
    assert first.name.value == "MUSTANG-CAR"

    with pytest.raises(HFIDViolatedError, match=r"Violates uniqueness constraint 'name' \(computed from: model\)"):
        await create_node(data={"model": "mustang"}, db=db, branch=default_branch, schema=car_schema)


async def test_violation_message_lists_relationship_peer_attribute(
    db: InfrahubDatabase, default_branch: Branch, car_schema_computed_from_relationship: SchemaRoot
) -> None:
    car_schema = registry.schema.get_node_schema(name="TestCar", branch=default_branch)
    person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)

    alice = await create_node(data={"name": "alice"}, db=db, branch=default_branch, schema=person_schema)
    first = await create_node(data={"owner": {"id": alice.id}}, db=db, branch=default_branch, schema=car_schema)
    assert first.name.value == "ALICE-CAR"

    with pytest.raises(
        HFIDViolatedError, match=r"Violates uniqueness constraint 'name' \(computed from: owner\.name\)"
    ):
        await create_node(data={"owner": {"id": alice.id}}, db=db, branch=default_branch, schema=car_schema)


async def test_create_node_rejects_duplicate_computed_secondary_unique(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_schema_computed_secondary_unique: SchemaRoot,
) -> None:
    car_schema = registry.schema.get_node_schema(name="TestCar", branch=default_branch)

    first = await create_node(
        data={"name": "alpha", "model": "mustang"}, db=db, branch=default_branch, schema=car_schema
    )
    assert first.vin.value == "VIN-MUSTANG"

    with pytest.raises(
        ValidationError, match=r"Violates uniqueness constraint 'vin' \(computed from: model\)"
    ) as exc_info:
        await create_node(data={"name": "beta", "model": "mustang"}, db=db, branch=default_branch, schema=car_schema)
    assert not isinstance(exc_info.value, HFIDViolatedError)
