from __future__ import annotations

import json

from jinja2 import ChainableUndefined, Environment

from infrahub.computed_attribute.triggers import (
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_CREATED,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_DELETED,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_UPDATED,
)
from infrahub.core.constants import InfrahubKind
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeUpdatedEvent
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import ExecuteWorkflow
from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM_LIFECYCLE


def _changed_elements_templates() -> list[str]:
    templates: list[str] = []
    for action in TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA.actions:
        assert isinstance(action, ExecuteWorkflow)
        assert "changed_elements" in action.parameters, "setup action is missing the changed_elements parameter"
        templates.append(action.parameters["changed_elements"]["value"]["template"])
    return templates


def _render(template: str, payload: dict) -> str:
    # Mirrors how the task manager renders action parameters: an undefined value chains
    # rather than raising, and the result is serialized to JSON with the tojson filter.
    # Autoescape stays off because the output is JSON, not HTML.
    environment = Environment(undefined=ChainableUndefined, autoescape=False)  # noqa: S701
    return environment.from_string(template).render(event={"payload": payload})


def test_both_setup_actions_carry_a_changed_elements_param() -> None:
    templates = _changed_elements_templates()
    assert len(templates) == 2


def test_changed_elements_reads_from_the_data_envelope() -> None:
    # Events are emitted as {"data": <fields>, "context": <context>}; a field has to be read
    # through event.payload['data'][...]. Reading it at the top level resolves to undefined.
    for template in _changed_elements_templates():
        assert "event.payload['data']['changed_elements']" in template


def test_template_renders_the_change_set_when_present() -> None:
    change_set = {"added_kinds": [], "removed_kinds": [], "changed_fields": {"InfraDevice": ["type"]}}
    payload = {"data": {"changed_elements": change_set}}

    for template in _changed_elements_templates():
        assert json.loads(_render(template, payload)) == change_set


def test_template_renders_null_when_change_set_absent() -> None:
    # A branch-deletion event carries no change set; rendering must yield JSON null rather
    # than raising on an undefined value.
    payload = {"data": {"branch_name": "main"}}

    for template in _changed_elements_templates():
        assert json.loads(_render(template, payload)) is None


def _lifecycle_match() -> dict:
    return {
        "infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON,
        NODE_ORIGIN_LABEL: NodeMutationOrigin.LIVE.value,
    }


def test_created_trigger_shape() -> None:
    trigger = TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_CREATED.trigger
    assert trigger.events == {NodeCreatedEvent.event_name}
    assert trigger.match == _lifecycle_match()
    assert trigger.match_related == {}


def test_updated_trigger_shape() -> None:
    trigger = TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_UPDATED.trigger
    assert trigger.events == {NodeUpdatedEvent.event_name}
    assert trigger.match == _lifecycle_match()
    assert trigger.match_related == {
        "prefect.resource.role": ["infrahub.node.attribute_update"],
        "infrahub.field.name": ["fingerprint"],
    }


def test_deleted_trigger_shape() -> None:
    trigger = TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_DELETED.trigger
    assert trigger.events == {NodeDeletedEvent.event_name}
    assert trigger.match == _lifecycle_match()
    assert trigger.match_related == {}


def test_lifecycle_triggers_run_the_lifecycle_flow() -> None:
    for definition in (
        TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_CREATED,
        TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_UPDATED,
        TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_DELETED,
    ):
        assert len(definition.actions) == 1
        action = definition.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.workflow == COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM_LIFECYCLE


def test_lifecycle_triggers_registered_and_commit_trigger_gone() -> None:
    names = {definition.name for definition in builtin_triggers}
    assert "computed-attribute-python-transform-created" in names
    assert "computed-attribute-python-transform-updated" in names
    assert "computed-attribute-python-transform-deleted" in names
    assert "computed-attribute-python-setup-on-commit" not in names
