from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from infrahub_sdk.schema import validate_schema
from infrahub_sdk.schema.generated.contract import READ_ONLY_FIELDS
from infrahub_sdk.schema.generated.write import InfrahubSchemaWrite

from infrahub.api.schema import SchemaLoadAPI, SchemaReadAPI
from infrahub.core.constants import ComputedAttributeKind, HashableModelState
from infrahub.core.schema import SchemaRoot, SchemaWarningType
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


def _full_internal_dump() -> dict[str, Any]:
    """A full internal SchemaRoot dump, carrying read-only/internal fields (ids, state, ...)."""
    return SchemaRoot(version="1.0", generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST]).model_dump()


@dataclass
class LoadContractCase:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    accepted: bool = True
    use_full_dump: bool = False


LOAD_CONTRACT_CASES = [
    LoadContractCase(name="full-internal-dump-accepted", use_full_dump=True, accepted=True),
    LoadContractCase(
        name="minimal-write-payload",
        payload={
            "version": "1.0",
            "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "field_one", "kind": "Text"}]}],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="unknown-field-on-extension-rejected",
        payload={"version": "1.0", "extensions": {"nodes": [{"kind": "BuiltinTag", "namespace": "Dropped"}]}},
        accepted=False,
    ),
    LoadContractCase(
        name="unknown-field-on-node-rejected",
        payload={"version": "1.0", "nodes": [{"namespace": "Test", "name": "Widget", "not_a_field": 1}]},
        accepted=False,
    ),
    LoadContractCase(
        name="read-only-field-on-attribute-accepted",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "attributes": [{"name": "field_one", "kind": "Text", "inherited": True, "state": "present"}],
                }
            ],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="unknown-field-on-attribute-rejected",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "attributes": [{"name": "field_one", "kind": "Text", "not_a_field": 1}],
                }
            ],
        },
        accepted=False,
    ),
    LoadContractCase(
        name="read-only-field-on-relationship-accepted",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "relationships": [
                        {"name": "gadgets", "peer": "TestGadget", "cardinality": "many", "inherited": True}
                    ],
                }
            ],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="unknown-field-on-relationship-rejected",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "relationships": [
                        {"name": "gadgets", "peer": "TestGadget", "cardinality": "many", "not_a_field": 1}
                    ],
                }
            ],
        },
        accepted=False,
    ),
    LoadContractCase(
        name="computed-attribute-accepted",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "attributes": [
                        {
                            "name": "field_one",
                            "kind": "Text",
                            "optional": True,
                            "read_only": True,
                            "computed_attribute": {
                                "kind": "Jinja2",
                                "jinja2_template": "{{ name__value }}",
                            },
                        }
                    ],
                }
            ],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="unknown-field-on-computed-attribute-rejected",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "attributes": [
                        {
                            "name": "field_one",
                            "kind": "Text",
                            "computed_attribute": {
                                "kind": "Jinja2",
                                "jinja2_template": "{{ name__value }}",
                                "not_a_field": 1,
                            },
                        }
                    ],
                }
            ],
        },
        accepted=False,
    ),
    LoadContractCase(
        name="computed-attribute-unknown-kind-rejected",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "attributes": [{"name": "field_one", "kind": "Text", "computed_attribute": {"kind": "Nope"}}],
                }
            ],
        },
        accepted=False,
    ),
    LoadContractCase(name="null-extensions-tolerated", payload={"version": "1.0", "extensions": None}, accepted=True),
    LoadContractCase(
        name="out-of-range-attribute-name-rejected",
        payload={
            "version": "1.0",
            "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "ab", "kind": "Text"}]}],
        },
        accepted=False,
    ),
    LoadContractCase(
        name="missing-version-rejected",
        payload={
            "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "field_one", "kind": "Text"}]}],
        },
        accepted=False,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in LOAD_CONTRACT_CASES])
def test_schema_load_contract(case: LoadContractCase) -> None:
    payload = _full_internal_dump() if case.use_full_dump else case.payload
    if case.accepted:
        loaded = SchemaLoadAPI.model_validate(payload)
        assert loaded.internal_schema is not None
    else:
        with pytest.raises(ValueError, match="validation error for SchemaLoadAPI"):
            SchemaLoadAPI.model_validate(payload)


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in LOAD_CONTRACT_CASES])
def test_offline_validation_matches_load_contract_verdict(case: LoadContractCase) -> None:
    # The published write contract is only useful if a payload can be checked before submission:
    # the SDK's offline validator must reach the same accept/reject verdict as the load endpoint.
    payload = _full_internal_dump() if case.use_full_dump else case.payload

    result = validate_schema(schema=payload)

    assert result.valid is case.accepted, result.messages


def _read_only_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "namespace": "Test",
                "name": "Widget",
                "hierarchy": "TestThing",
                "attributes": [{"name": "field_one", "kind": "Text", "inherited": True, "state": "absent"}],
                "relationships": [{"name": "gadgets", "peer": "TestGadget", "cardinality": "many", "inherited": True}],
            }
        ],
    }


def test_read_only_fields_do_not_reach_the_internal_schema() -> None:
    # A read-only field is accepted so a schema read back from Infrahub still loads, but the
    # submitted value must never win over the server-owned one: ``inherited`` stays False.
    loaded = SchemaLoadAPI.model_validate(_read_only_payload())

    node = loaded.internal_schema.nodes[0]
    assert node.attributes[0].inherited is False
    assert node.relationships[0].inherited is False
    # ``state`` is settable, so the submitted value must survive where ``inherited`` did not
    assert node.attributes[0].state is HashableModelState.ABSENT
    assert loaded.internal_schema.nodes[0].hierarchy is None


def test_read_only_fields_are_reported_as_warnings_grouped_by_field() -> None:
    # The load response carries these back to the user, so each distinct read-only field is one
    # warning naming every kind and element that set it, not one warning per occurrence.
    loaded = SchemaLoadAPI.model_validate(_read_only_payload())

    assert [warning.type for warning in loaded.contract_warnings] == [
        SchemaWarningType.DEPRECATION,
        SchemaWarningType.DEPRECATION,
    ]
    reported = {
        warning.message: sorted((kind.kind, kind.field) for kind in warning.kinds)
        for warning in loaded.contract_warnings
    }
    assert reported == {
        "'hierarchy' is a read-only field, the submitted value is ignored": [("TestWidget", None)],
        "'inherited' is a read-only field, the submitted value is ignored": [
            ("TestWidget", "field_one"),
            ("TestWidget", "gadgets"),
        ],
    }


def test_a_payload_without_read_only_fields_reports_no_warning() -> None:
    payload = {
        "version": "1.0",
        "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "field_one", "kind": "Text"}]}],
    }

    assert SchemaLoadAPI.model_validate(payload).contract_warnings == []


def test_root_read_only_fields_cover_the_read_api_response() -> None:
    # A raw GET /api/schema body resubmitted to the load endpoint must warn rather than fail, so
    # every top-level key the read response adds over the write root is classified as read-only.
    read_only = READ_ONLY_FIELDS[InfrahubSchemaWrite.__name__]

    assert set(SchemaReadAPI.model_fields) - set(InfrahubSchemaWrite.model_fields) == read_only


def test_unknown_field_is_rejected_naming_the_field() -> None:
    payload = {
        "version": "1.0",
        "nodes": [
            {
                "namespace": "Test",
                "name": "Widget",
                "attributes": [{"name": "field_one", "kind": "Text", "inheritd": True}],
            }
        ],
    }

    with pytest.raises(
        ValueError,
        match=r"nodes\[0\]\.attributes\[0\]\.inheritd: Unknown field, it is not part of the schema "
        r"\(received: True\)",
    ):
        SchemaLoadAPI.model_validate(payload)


def test_computed_attribute_survives_its_discriminated_union() -> None:
    # Each attribute kind and computed-attribute kind is a separate variant of a discriminated
    # union; dropping the fields of a sibling variant must not collapse a variant onto the wrong
    # one. ``transform`` belongs to the TransformPython variant, so setting it on a Jinja2 one is
    # tolerated with a warning rather than switching the variant.
    payload = {
        "version": "1.0",
        "nodes": [
            {
                "namespace": "Test",
                "name": "Widget",
                "attributes": [
                    {
                        "name": "field_one",
                        "kind": "Text",
                        "optional": True,
                        "read_only": True,
                        "computed_attribute": {
                            "kind": "Jinja2",
                            "jinja2_template": "{{ name__value }}",
                            "transform": "my_transform",
                        },
                    }
                ],
            }
        ],
    }

    loaded = SchemaLoadAPI.model_validate(payload)

    computed = loaded.internal_schema.nodes[0].attributes[0].computed_attribute
    assert computed is not None
    assert computed.kind is ComputedAttributeKind.JINJA2
    assert computed.jinja2_template == "{{ name__value }}"
    assert computed.transform is None
    assert "transform" not in loaded.model_dump()["nodes"][0]["attributes"][0]["computed_attribute"]
    # Named relative to its owner: `transform` is settable on a TransformPython computed
    # attribute, so the warning has to say which block the ignored value sat in.
    assert [warning.message for warning in loaded.contract_warnings] == [
        "'computed_attribute.transform' is a read-only field, the submitted value is ignored"
    ]


def test_out_of_enum_attribute_kind_is_rejected_naming_the_value() -> None:
    payload = {
        "version": "1.0",
        "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "field_one", "kind": "NotAKind"}]}],
    }

    with pytest.raises(
        ValueError,
        match=r"nodes\[0\]\.attributes\[0\]: Input tag 'NotAKind' found using 'kind' does not match any of "
        r"the expected tags:",
    ):
        SchemaLoadAPI.model_validate(payload)
