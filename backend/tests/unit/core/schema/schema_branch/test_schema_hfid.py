import pytest

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import ValidationError

_SCHEMA = {
    "nodes": [
        {
            "name": "Car",
            "namespace": "Test",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "nbr_seats", "kind": "Number"},
            ],
            "relationships": [
                {
                    "name": "owner",
                    "label": "Commander of Car",
                    "peer": "TestPerson",
                    "optional": False,
                    "cardinality": "one",
                    "direction": "outbound",
                },
                {
                    "name": "driver",
                    "label": "Driver of Car",
                    "peer": "TestPerson",
                    "optional": False,
                    "cardinality": "one",
                    "direction": "outbound",
                    "identifier": "drive_rel",
                },
            ],
        },
        {
            "name": "Person",
            "namespace": "Test",
            "attributes": [
                {"name": "name", "kind": "Text", "optional": False},
                {"name": "age", "kind": "Number"},
                {"name": "salary", "kind": "Number"},
            ],
            "relationships": [
                {"name": "cars_owned", "peer": "TestCar", "cardinality": "many", "direction": "inbound"},
                {
                    "name": "cars_driven",
                    "peer": "TestCar",
                    "cardinality": "many",
                    "direction": "inbound",
                    "identifier": "drive_rel",
                },
            ],
        },
    ],
}


@pytest.mark.parametrize(
    "human_friendly_id, uniqueness_constraints, should_raise",
    [
        # Valid hfid
        (["name__value", "owner__name__value"], [["name__value"]], False),
        (["owner__name__value", "owner__age__value"], [["name__value", "age__value"]], False),
        (["owner__name__value", "owner__age__value"], [["name__value"]], False),
        (["owner__name__value", "owner__age__value"], [["name__value"], ["age__value"]], False),
        (
            ["owner__name__value", "owner__age__value", "driver__name__value", "driver__age__value"],
            [["name__value"], ["age__value"]],
            False,
        ),
        (["owner__name__value", "owner__age__value", "owner__salary__value"], [["name__value", "age__value"]], False),
        # Non-valid hfid
        (["name__value", "owner__name__value"], None, True),
        (["name__value", "owner__name__value"], [["age__value"]], True),
        (
            ["owner__name__value", "owner__age__value"],
            [["age__value", "salary__value"], ["name__value", "salary__value"]],
            True,
        ),
        (["owner__name__value", "owner__age__value", "driver__name__value"], [["name__value", "age__value"]], True),
    ],
)
async def test_schema_constraints(human_friendly_id, uniqueness_constraints, should_raise) -> None:
    schema_root = SchemaRoot(**_SCHEMA)

    person_schema = schema_root.get(name="TestPerson")
    car_schema = schema_root.get(name="TestCar")

    car_schema.human_friendly_id = human_friendly_id
    person_schema.uniqueness_constraints = uniqueness_constraints

    schema_branch = SchemaBranch(cache={}, name="test")

    if should_raise:
        with pytest.raises(
            ValidationError,
            match=r"HFID of TestCar refers to peer TestPerson with a non-unique combination of attributes",
        ):
            schema_branch.load_schema(schema=schema_root)
            schema_branch.process()
    else:
        schema_branch.load_schema(schema=schema_root)
        schema_branch.process()
