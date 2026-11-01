from __future__ import annotations

import pytest

from infrahub.core.schema import AttributePathParsingError, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.uniqueness.checker import get_attribute_path_from_string


@pytest.fixture
def schema_branch(car_person_schema_root: SchemaRoot) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    branch.load_schema(schema=car_person_schema_root)
    branch.get_node(name="TestCar", duplicate=False).parent = "TestPerson"
    return branch


@pytest.mark.parametrize("path", ["name__value__extra", "owner__name__value__extra", "parent__name__value__extra"])
def test_rejects_extra_path_segments(schema_branch: SchemaBranch, path: str) -> None:
    node = schema_branch.get(name="TestCar")

    with pytest.raises(AttributePathParsingError, match=rf"^{path} has too many segments on schema TestCar$"):
        node.parse_schema_path(path=path, schema=schema_branch)


@pytest.mark.parametrize("path", ["name__value", "owner__name__value", "parent__name__value"])
def test_accepts_complete_path(schema_branch: SchemaBranch, path: str) -> None:
    parsed = schema_branch.get(name="TestCar").parse_schema_path(path=path, schema=schema_branch)

    assert parsed.attribute_schema is not None
    assert parsed.attribute_schema.name == "name"
    assert parsed.attribute_property_name == "value"
    if path != "name__value":
        assert parsed.related_schema is not None
        assert parsed.related_schema.kind == "TestPerson"


def test_rejects_malformed_existing_constraint_with_corrected_hfid(schema_branch: SchemaBranch) -> None:
    node = schema_branch.get(name="TestCar", duplicate=False)
    node.human_friendly_id = ["name__value", "color__value"]
    node.uniqueness_constraints = [["name__value__color__value"]]
    schema_branch.process_human_friendly_id(raise_parsing_errors=False)

    with pytest.raises(
        ValueError,
        match=r"^TestCar\.uniqueness_constraints: name__value__color__value has too many segments on schema TestCar$",
    ):
        schema_branch.validate_uniqueness_constraints()


def test_malformed_hfid_is_not_propagated_to_constraints(schema_branch: SchemaBranch) -> None:
    node = schema_branch.get(name="TestCar", duplicate=False)
    node.human_friendly_id = ["name__value__color__value"]
    node.uniqueness_constraints = []

    schema_branch.process_human_friendly_id(raise_parsing_errors=False)

    assert schema_branch.get(name="TestCar").uniqueness_constraints == []
    with pytest.raises(
        ValueError,
        match=r"^TestCar\.human_friendly_id: name__value__color__value has too many segments on schema TestCar$",
    ):
        schema_branch.validate_human_friendly_id()


@pytest.mark.parametrize("path", ["name__value__extra", "name__value__color__value", "owner__name__value"])
def test_uniqueness_checker_rejects_extra_segments(schema_branch: SchemaBranch, path: str) -> None:
    with pytest.raises(ValueError, match=rf"^{path} is not valid on TestCar$"):
        get_attribute_path_from_string(path=path, schema=schema_branch.get(name="TestCar"))
