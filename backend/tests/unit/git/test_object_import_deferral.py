import pytest
from infrahub_sdk.schema import NodeSchemaAPI

from infrahub.actions.schema import (
    core_generator_action,
    core_group_action,
    core_group_trigger_rule,
    core_node_trigger_rule,
)
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.definitions.core.group import core_standard_group
from infrahub.git.integrator import InfrahubRepositoryIntegrator


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        pytest.param(core_generator_action, True, id="generator-action-deferred"),
        pytest.param(core_node_trigger_rule, True, id="node-trigger-rule-deferred"),
        pytest.param(core_group_trigger_rule, True, id="group-trigger-rule-deferred"),
        pytest.param(core_group_action, False, id="group-action-not-deferred"),
        pytest.param(core_standard_group, False, id="standard-group-not-deferred"),
    ],
)
def test_object_depends_on_definitions(schema: NodeSchema, expected: bool) -> None:
    """Only the objects pointing at a definition created later in the import are deferred."""
    api_schema = NodeSchemaAPI(**schema.model_dump())

    assert InfrahubRepositoryIntegrator._object_depends_on_definitions(schema=api_schema) is expected
