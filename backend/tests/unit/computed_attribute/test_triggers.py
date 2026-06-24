from __future__ import annotations

import json

from jinja2 import ChainableUndefined, Environment

from infrahub.computed_attribute.triggers import TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA
from infrahub.trigger.models import ExecuteWorkflow


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
