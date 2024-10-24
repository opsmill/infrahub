import pytest

from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


@pytest.mark.parametrize(
    "schema_root,expected_error",
    [
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        uniqueness_constraints=[["first_name__value"]],
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="description",
                                kind="Text",
                                optional=True,
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Requested unique constraint not found within node. (`first_name__value`)",
            id="missing_all",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        uniqueness_constraints=[
                            ["first_name__value", "last_name__value"],
                            ["origin__value", "family__value"],
                        ],
                        attributes=[
                            AttributeSchema(
                                name="first_name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="last_name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="origin",
                                kind="Text",
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson.uniqueness_constraints: family__value is invalid on schema TestingPerson",
            id="missing_single",
        ),
    ],
)
async def test_schema_protected_generics(schema_root: SchemaRoot, expected_error: str):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_root)

    with pytest.raises(ValueError) as exc:
        schema.process_validate()

    assert expected_error == str(exc.value)
