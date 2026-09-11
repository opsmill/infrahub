from dataclasses import dataclass

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


@dataclass
class ObjectDeferralTestCase:
    name: str
    """Descriptive name for the test scenario."""

    schema: NodeSchema
    """The schema of the object the import is about to load."""

    expected: bool
    """Whether an object of that kind is expected to be deferred."""


OBJECT_DEFERRAL_TEST_CASES: list[ObjectDeferralTestCase] = [
    ObjectDeferralTestCase(
        name="generator_action_is_deferred",
        schema=core_generator_action,
        expected=True,
    ),
    ObjectDeferralTestCase(
        name="node_trigger_rule_is_deferred",
        schema=core_node_trigger_rule,
        expected=True,
    ),
    ObjectDeferralTestCase(
        name="group_trigger_rule_is_deferred",
        schema=core_group_trigger_rule,
        expected=True,
    ),
    ObjectDeferralTestCase(
        name="group_action_is_not_deferred",
        schema=core_group_action,
        expected=False,
    ),
    ObjectDeferralTestCase(
        name="standard_group_is_not_deferred",
        schema=core_standard_group,
        expected=False,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in OBJECT_DEFERRAL_TEST_CASES],
)
def test_object_depends_on_definitions(test_case: ObjectDeferralTestCase) -> None:
    """Only the objects pointing at a definition created later in the import are deferred.

    The intent is to defer ``CoreGeneratorAction`` objects and the ``CoreTriggerRule`` objects
    tied to one. That is not what happens today: every ``CoreTriggerRule`` is deferred, whatever
    action it points at, because the deferral decision is taken from the schema of the object
    while the action it binds to lives in the object data. Narrowing it needs a refactor, so
    both trigger rule cases assert the current over-approximation on purpose rather than the
    behaviour we want. Once a refactor leaves the rules tied to another action kind in the
    regular pass, change the expectations here rather than adding a second test beside them.
    """
    api_schema = NodeSchemaAPI(**test_case.schema.model_dump())

    result = InfrahubRepositoryIntegrator._object_depends_on_definitions(schema=api_schema)

    assert result is test_case.expected
