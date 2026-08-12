from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.schema.generated.contract import READ_ONLY_FIELDS
from infrahub_sdk.schema.validate import validate_schema
from jsonschema import Draft202012Validator

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.schema.write_json_schema import ROOT_CLASS_NAME, build_write_json_schema

if TYPE_CHECKING:
    from collections.abc import Iterator

    from jsonschema.exceptions import ValidationError
    from jsonschema.protocols import Validator


@dataclass(frozen=True)
class WriteJsonSchemaCase:
    name: str
    """Descriptive name for the test scenario, used as the pytest ID."""

    payload: dict[str, Any]
    """Schema-root payload to validate against the published document."""

    expected_error: str | None = None
    """Message the document must report, or None when the payload must be accepted.

    An attribute is a discriminated union, and a union reports its own failure as "is not valid
    under any of the given schemas". The message naming the cause therefore sits in a nested error
    rather than the top-level one, which is why the whole error tree is searched.
    """


def _node(**fields: Any) -> dict[str, Any]:
    return {"version": "1.0", "nodes": [{"name": "Device", "namespace": "Infra", **fields}]}


def _attribute(**fields: Any) -> dict[str, Any]:
    return _node(attributes=[{"name": "title", "kind": "Text", **fields}])


WRITE_JSON_SCHEMA_CASES: list[WriteJsonSchemaCase] = [
    WriteJsonSchemaCase(name="minimal-attribute-accepted", payload=_attribute()),
    WriteJsonSchemaCase(name="text-parameter-on-text-accepted", payload=_attribute(parameters={"max_length": 10})),
    WriteJsonSchemaCase(
        name="number-parameter-on-number-accepted",
        payload=_node(attributes=[{"name": "speed", "kind": "Number", "parameters": {"min_value": 5}}]),
    ),
    WriteJsonSchemaCase(
        name="pool-parameter-on-pool-accepted",
        payload=_node(
            attributes=[{"name": "index", "kind": "NumberPool", "parameters": {"start_range": 1, "end_range": 9}}]
        ),
    ),
    WriteJsonSchemaCase(
        name="computed-jinja2-accepted",
        payload=_attribute(computed_attribute={"kind": "Jinja2", "jinja2_template": "{{ x }}"}),
    ),
    WriteJsonSchemaCase(
        name="computed-transform-accepted",
        payload=_attribute(computed_attribute={"kind": "TransformPython", "transform": "device_compliance"}),
    ),
    WriteJsonSchemaCase(
        name="computed-jinja2-carrying-sibling-transform-accepted",
        payload=_attribute(computed_attribute={"kind": "Jinja2", "jinja2_template": "{{ x }}", "transform": "t"}),
    ),
    WriteJsonSchemaCase(
        name="payload-read-back-from-infrahub-accepted",
        payload=_node(
            hash="abc", kind="InfraDevice", attributes=[{"name": "title", "kind": "Text", "inherited": False}]
        ),
    ),
    WriteJsonSchemaCase(
        name="unknown-field-on-node-rejected",
        payload=_node(labl="Device"),
        expected_error="Additional properties are not allowed ('labl' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="unknown-field-on-attribute-rejected",
        payload=_attribute(uniqe=True),
        expected_error="Additional properties are not allowed ('uniqe' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="unknown-field-on-relationship-rejected",
        payload=_node(relationships=[{"name": "site", "peer": "InfraSite", "cardinlity": "one"}]),
        expected_error="Additional properties are not allowed ('cardinlity' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="unknown-parameter-rejected",
        payload=_attribute(parameters={"regexx": "^a"}),
        expected_error="Additional properties are not allowed ('regexx' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="number-parameter-on-text-rejected",
        payload=_attribute(parameters={"min_value": 5}),
        expected_error="Additional properties are not allowed ('min_value' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="pool-parameter-on-text-rejected",
        payload=_attribute(parameters={"number_pool_id": "x"}),
        expected_error="Additional properties are not allowed ('number_pool_id' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="text-parameter-on-number-rejected",
        payload=_node(attributes=[{"name": "speed", "kind": "Number", "parameters": {"regex": "^a"}}]),
        expected_error="Additional properties are not allowed ('regex' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="parameter-on-kind-taking-none-rejected",
        payload=_node(attributes=[{"name": "active", "kind": "Boolean", "parameters": {"regex": "^a"}}]),
        expected_error="Additional properties are not allowed ('regex' was unexpected)",
    ),
    WriteJsonSchemaCase(
        name="wrong-parameter-value-type-rejected",
        payload=_attribute(parameters={"max_length": "sixty-four"}),
        expected_error="'sixty-four' is not of type 'integer'",
    ),
    WriteJsonSchemaCase(
        name="invalid-attribute-kind-rejected",
        payload=_node(attributes=[{"name": "title", "kind": "Str"}]),
        expected_error="'Str' is not one of ['Text', 'TextArea']",
    ),
    WriteJsonSchemaCase(
        name="computed-jinja2-without-template-rejected",
        payload=_attribute(computed_attribute={"kind": "Jinja2"}),
        expected_error="'jinja2_template' is a required property",
    ),
    WriteJsonSchemaCase(
        name="computed-transform-without-name-rejected",
        payload=_attribute(computed_attribute={"kind": "TransformPython"}),
        expected_error="'transform' is a required property",
    ),
    WriteJsonSchemaCase(
        name="invalid-computed-kind-rejected",
        payload=_attribute(computed_attribute={"kind": "Handwritten"}),
        expected_error="'User' was expected",
    ),
]


@pytest.fixture(scope="module")
def write_json_schema() -> dict[str, Any]:
    return build_write_json_schema(schema=SchemaLoadAPI.model_json_schema())


@pytest.fixture(scope="module")
def validator(write_json_schema: dict[str, Any]) -> Validator:
    Draft202012Validator.check_schema(write_json_schema)
    return Draft202012Validator(write_json_schema)


def _object_schema_paths(node: Any, path: str = "$") -> Iterator[str]:
    """Yield the path of every object subschema anywhere in a JSON Schema document."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield path
        for key, value in node.items():
            yield from _object_schema_paths(node=value, path=f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _object_schema_paths(node=value, path=f"{path}[{index}]")


def _addressable_object_paths(schema: dict[str, Any]) -> set[str]:
    return {"$"} | {f"$.$defs.{name}" for name in schema["$defs"]}


def _flatten(error: ValidationError) -> Iterator[ValidationError]:
    yield error
    for nested in error.context or []:
        yield from _flatten(error=nested)


def test_every_object_schema_is_addressable(write_json_schema: dict[str, Any]) -> None:
    """Hardening reaches the root and $defs only, which covers the document while every model is hoisted.

    Pydantic lifts each nested model into $defs and refers to it, so no object subschema is inline.
    A field typed as a mapping would break that: it renders inline, carrying an additionalProperties
    that describes its values, and closing it would leave a mapping that accepts no keys at all.
    Such a field needs a deliberate decision rather than the surrounding sweep, so it fails here.
    """
    addressable = _addressable_object_paths(schema=write_json_schema)
    inline = set(_object_schema_paths(node=write_json_schema)) - addressable

    assert inline == set()
    assert len(addressable) > 1


def test_every_object_forbids_additional_properties(write_json_schema: dict[str, Any]) -> None:
    closed = {
        name
        for name, definition in write_json_schema["$defs"].items()
        if definition.get("type") == "object" and definition.get("additionalProperties") is False
    }
    objects = {name for name, definition in write_json_schema["$defs"].items() if definition.get("type") == "object"}

    assert objects - closed == set()
    assert len(closed) > 0
    assert write_json_schema["additionalProperties"] is False


def test_read_only_fields_are_declared_as_deprecated(write_json_schema: dict[str, Any]) -> None:
    """A closed document that omitted these would reject a schema read back from Infrahub."""
    missing: set[str] = set()
    not_deprecated: set[str] = set()
    asserted = 0

    for class_name, field_names in READ_ONLY_FIELDS.items():
        definition = write_json_schema if class_name == ROOT_CLASS_NAME else write_json_schema["$defs"].get(class_name)
        if definition is None:
            # A base class pydantic inlines because no field refers to it by name.
            continue
        for field_name in field_names:
            asserted += 1
            declared = definition["properties"].get(field_name)
            if declared is None:
                missing.add(f"{class_name}.{field_name}")
            elif declared.get("deprecated") is not True:
                not_deprecated.add(f"{class_name}.{field_name}")

    assert missing == set()
    assert not_deprecated == set()
    assert asserted > 0


def test_display_labels_is_deprecated(write_json_schema: dict[str, Any]) -> None:
    display_labels = write_json_schema["$defs"]["NodeSchemaWrite"]["properties"]["display_labels"]

    assert display_labels["deprecated"] is True
    assert display_labels["deprecationMessage"] == "display_labels are deprecated use display_label instead"


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in WRITE_JSON_SCHEMA_CASES])
def test_published_schema_verdict(validator: Validator, case: WriteJsonSchemaCase) -> None:
    messages = {nested.message for error in validator.iter_errors(case.payload) for nested in _flatten(error=error)}

    if case.expected_error is None:
        assert messages == set()
    else:
        assert case.expected_error in messages, sorted(messages)


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in WRITE_JSON_SCHEMA_CASES])
def test_published_schema_matches_load_contract_verdict(case: WriteJsonSchemaCase) -> None:
    # An editor validating against the published document must reach the same accept/reject verdict
    # as the load endpoint, or it reports an error on a file the server takes, or stays silent on one
    # the server refuses.
    result = validate_schema(schema=case.payload)

    assert result.valid is (case.expected_error is None), result.messages
