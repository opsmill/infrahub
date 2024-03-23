import re

import pytest

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema_manager import SchemaBranch

from .conftest import _get_schema_by_kind


async def test_one_parent_relationship_allowed(schema_parent_component):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_parent_component))

    schema.validate_parent_component()


async def test_many_parent_relationships_not_allowed(schema_parent_component):
    schema_dict = _get_schema_by_kind(schema_parent_component, "TestComponentNodeOne")
    schema_dict["relationships"].append(
        {
            "name": "parent_two",
            "peer": "TestParentNodeOne",
            "kind": "Parent",
            "optional": False,
            "cardinality": "one",
        }
    )

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_parent_component))

    with pytest.raises(ValueError, match=r"Only one relationship of type parent is allowed") as exc:
        schema.validate_parent_component()

    err_msg = str(exc.value)
    assert "parent_one" in err_msg
    assert "parent_two" in err_msg


async def test_parent_relationship_must_be_cardinality_one(schema_parent_component):
    schema_dict = _get_schema_by_kind(schema_parent_component, "TestComponentNodeOne")
    schema_dict["relationships"][0]["cardinality"] = "many"

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_parent_component))

    with pytest.raises(
        ValueError, match=r"TestComponentNodeOne.parent_one: Relationship of type parent must be cardinality=one"
    ):
        schema.validate_parent_component()


async def test_parent_relationship_must_be_mandatory(schema_parent_component):
    schema_dict = _get_schema_by_kind(schema_parent_component, "TestComponentNodeOne")
    schema_dict["relationships"][0]["optional"] = True

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_parent_component))

    with pytest.raises(
        ValueError, match=r"TestComponentNodeOne.parent_one: Relationship of type parent must not be optional"
    ):
        schema.validate_parent_component()


async def test_only_one_parent_relationship_when_inheriting_from_generic(schema_parent_component):
    schema_dict = _get_schema_by_kind(schema_parent_component, "TestComponentGenericOne")
    schema_dict["relationships"].append(
        {
            "name": "parent_two",
            "peer": "TestParentNodeOne",
            "kind": "Parent",
            "optional": False,
            "cardinality": "one",
        }
    )

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_parent_component))

    with pytest.raises(ValueError, match=r"Only one relationship of type parent is allowed") as exc:
        schema.validate_parent_component()

    err_msg = str(exc.value)
    assert "parent_one" in err_msg
    assert "parent_two" in err_msg


async def test_hierarchy_cannot_contain_loop(schema_parent_component):
    schema_dict = _get_schema_by_kind(schema_parent_component, "TestComponentGenericOne")
    schema_dict["relationships"].append(
        {
            "name": "bad_component",
            "peer": "TestParentNodeOne",
            "kind": "Component",
            "optional": True,
            "cardinality": "many",
        }
    )

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_parent_component))

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cycles exist among parents and components in schema: ['TestParentNodeOne --> TestComponentNodeOne --> TestParentNodeOne']"
        ),
    ):
        schema.validate_parent_component()
