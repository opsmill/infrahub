from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.schema.generated.contract import READ_ONLY_FIELDS
from infrahub_sdk.schema.validate import validate_schema
from jsonschema import Draft202012Validator

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.schema.write_json_schema import ROOT_CLASS_NAME, build_write_json_schema

if TYPE_CHECKING:
    from jsonschema.protocols import Validator


@dataclass
class WriteJsonSchemaCase:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    accepted: bool = True


def _node(**fields: Any) -> dict[str, Any]:
    return {"version": "1.0", "nodes": [{"name": "Device", "namespace": "Infra", **fields}]}


def _attribute(**fields: Any) -> dict[str, Any]:
    return _node(attributes=[{"name": "title", "kind": "Text", **fields}])


WRITE_JSON_SCHEMA_CASES = [
    WriteJsonSchemaCase(name="minimal-attribute", payload=_attribute()),
    WriteJsonSchemaCase(name="text-parameter-on-text", payload=_attribute(parameters={"max_length": 10})),
    WriteJsonSchemaCase(
        name="number-parameter-on-number",
        payload=_node(attributes=[{"name": "speed", "kind": "Number", "parameters": {"min_value": 5}}]),
    ),
    WriteJsonSchemaCase(
        name="pool-parameter-on-pool",
        payload=_node(
            attributes=[{"name": "index", "kind": "NumberPool", "parameters": {"start_range": 1, "end_range": 9}}]
        ),
    ),
    WriteJsonSchemaCase(
        name="computed-jinja2",
        payload=_attribute(computed_attribute={"kind": "Jinja2", "jinja2_template": "{{ x }}"}),
    ),
    WriteJsonSchemaCase(
        name="computed-jinja2-carrying-sibling-transform",
        payload=_attribute(computed_attribute={"kind": "Jinja2", "jinja2_template": "{{ x }}", "transform": "t"}),
    ),
    WriteJsonSchemaCase(
        name="payload-read-back-from-infrahub",
        payload=_node(
            hash="abc", kind="InfraDevice", attributes=[{"name": "title", "kind": "Text", "inherited": False}]
        ),
    ),
    WriteJsonSchemaCase(name="unknown-field-on-node", payload=_node(labl="Device"), accepted=False),
    WriteJsonSchemaCase(name="unknown-field-on-attribute", payload=_attribute(uniqe=True), accepted=False),
    WriteJsonSchemaCase(
        name="unknown-field-on-relationship",
        payload=_node(relationships=[{"name": "site", "peer": "InfraSite", "cardinlity": "one"}]),
        accepted=False,
    ),
    WriteJsonSchemaCase(name="unknown-parameter", payload=_attribute(parameters={"regexx": "^a"}), accepted=False),
    WriteJsonSchemaCase(
        name="number-parameter-on-text", payload=_attribute(parameters={"min_value": 5}), accepted=False
    ),
    WriteJsonSchemaCase(
        name="pool-parameter-on-text", payload=_attribute(parameters={"number_pool_id": "x"}), accepted=False
    ),
    WriteJsonSchemaCase(
        name="text-parameter-on-number",
        payload=_node(attributes=[{"name": "speed", "kind": "Number", "parameters": {"regex": "^a"}}]),
        accepted=False,
    ),
    WriteJsonSchemaCase(
        name="parameter-on-kind-taking-none",
        payload=_node(attributes=[{"name": "active", "kind": "Boolean", "parameters": {"regex": "^a"}}]),
        accepted=False,
    ),
    WriteJsonSchemaCase(
        name="computed-jinja2-without-template",
        payload=_attribute(computed_attribute={"kind": "Jinja2"}),
        accepted=False,
    ),
]


@pytest.fixture(scope="module")
def write_json_schema() -> dict[str, Any]:
    return build_write_json_schema(schema=SchemaLoadAPI.model_json_schema())


@pytest.fixture(scope="module")
def validator(write_json_schema: dict[str, Any]) -> Validator:
    Draft202012Validator.check_schema(write_json_schema)
    return Draft202012Validator(write_json_schema)


def test_every_object_forbids_additional_properties(write_json_schema: dict[str, Any]) -> None:
    open_definitions = {
        name
        for name, definition in write_json_schema["$defs"].items()
        if definition.get("type") == "object" and definition.get("additionalProperties") is not False
    }

    assert open_definitions == set()
    assert write_json_schema["additionalProperties"] is False


def test_read_only_fields_are_declared_as_deprecated(write_json_schema: dict[str, Any]) -> None:
    """A closed document that omitted these would reject a schema read back from Infrahub."""
    missing: set[str] = set()
    not_deprecated: set[str] = set()

    for class_name, field_names in READ_ONLY_FIELDS.items():
        definition = write_json_schema if class_name == ROOT_CLASS_NAME else write_json_schema["$defs"].get(class_name)
        if definition is None:
            # A base class pydantic inlines because no field refers to it by name.
            continue
        for field_name in field_names:
            declared = definition["properties"].get(field_name)
            if declared is None:
                missing.add(f"{class_name}.{field_name}")
            elif "deprecated" not in declared and field_name not in definition.get("required", []):
                not_deprecated.add(f"{class_name}.{field_name}")

    assert missing == set()
    assert not_deprecated == set()


def test_display_labels_is_deprecated(write_json_schema: dict[str, Any]) -> None:
    display_labels = write_json_schema["$defs"]["NodeSchemaWrite"]["properties"]["display_labels"]

    assert display_labels["deprecated"] is True
    assert display_labels["deprecationMessage"] == "display_labels are deprecated use display_label instead"


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in WRITE_JSON_SCHEMA_CASES])
def test_published_schema_verdict(validator: Validator, case: WriteJsonSchemaCase) -> None:
    errors = [error.message for error in validator.iter_errors(case.payload)]

    assert (not errors) is case.accepted, errors


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in WRITE_JSON_SCHEMA_CASES])
def test_published_schema_matches_load_contract_verdict(case: WriteJsonSchemaCase) -> None:
    # An editor validating against the published document must reach the same accept/reject verdict
    # as the load endpoint, or it reports an error on a file the server takes, or stays silent on one
    # the server refuses.
    result = validate_schema(schema=case.payload)

    assert result.valid is case.accepted, result.messages
