from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from infrahub_sdk.schema import validate_schema

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.constants import ComputedAttributeKind, HashableModelState
from infrahub.core.schema import SchemaRoot
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
    LoadContractCase(name="full-internal-dump-tolerated", use_full_dump=True, accepted=True),
    LoadContractCase(
        name="minimal-write-payload",
        payload={
            "version": "1.0",
            "nodes": [{"namespace": "Test", "name": "Widget", "attributes": [{"name": "field_one", "kind": "Text"}]}],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="non-write-field-on-extension-tolerated",
        payload={"version": "1.0", "extensions": {"nodes": [{"kind": "BuiltinTag", "namespace": "Dropped"}]}},
        accepted=True,
    ),
    LoadContractCase(
        name="unknown-field-on-node-tolerated",
        payload={"version": "1.0", "nodes": [{"namespace": "Test", "name": "Widget", "not_a_field": 1}]},
        accepted=True,
    ),
    LoadContractCase(
        name="non-write-and-unknown-fields-on-attribute-tolerated",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "attributes": [
                        {"name": "field_one", "kind": "Text", "not_a_field": 1, "inherited": True, "state": "present"}
                    ],
                }
            ],
        },
        accepted=True,
    ),
    LoadContractCase(
        name="non-write-and-unknown-fields-on-relationship-tolerated",
        payload={
            "version": "1.0",
            "nodes": [
                {
                    "namespace": "Test",
                    "name": "Widget",
                    "relationships": [
                        {
                            "name": "gadgets",
                            "peer": "TestGadget",
                            "cardinality": "many",
                            "not_a_field": 1,
                            "inherited": True,
                        }
                    ],
                }
            ],
        },
        accepted=True,
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
                                "not_a_field": 1,
                            },
                        }
                    ],
                }
            ],
        },
        accepted=True,
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


def test_non_write_fields_do_not_reach_the_internal_schema() -> None:
    # Non-write and unknown keys are tolerated at every nesting level, but a submitted value must
    # never win over the server-owned one: ``inherited`` stays False even though the payload set it.
    payload = {
        "version": "1.0",
        "nodes": [
            {
                "namespace": "Test",
                "name": "Widget",
                "not_a_field": 1,
                "attributes": [
                    {"name": "field_one", "kind": "Text", "inherited": True, "state": "absent", "not_a_field": 1}
                ],
                "relationships": [
                    {
                        "name": "gadgets",
                        "peer": "TestGadget",
                        "cardinality": "many",
                        "inherited": True,
                        "not_a_field": 1,
                    }
                ],
            }
        ],
        "extensions": {"nodes": [{"kind": "BuiltinTag", "namespace": "Dropped"}]},
    }

    loaded = SchemaLoadAPI.model_validate(payload)

    node = loaded.internal_schema.nodes[0]
    assert node.attributes[0].inherited is False
    assert node.relationships[0].inherited is False
    # ``state`` is settable, so the submitted value must survive where ``inherited`` did not
    assert node.attributes[0].state is HashableModelState.ABSENT
    assert "not_a_field" not in loaded.model_dump()["nodes"][0]
    assert "not_a_field" not in loaded.model_dump()["nodes"][0]["attributes"][0]
    assert "not_a_field" not in loaded.model_dump()["nodes"][0]["relationships"][0]
    assert "namespace" not in loaded.model_dump()["extensions"]["nodes"][0]


def test_computed_attribute_survives_its_discriminated_union() -> None:
    # Each attribute kind and computed-attribute kind is a separate variant of a discriminated
    # union; dropping non-write keys must not collapse a variant onto the wrong one.
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
                            "not_a_field": 1,
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
    assert "not_a_field" not in loaded.model_dump()["nodes"][0]["attributes"][0]["computed_attribute"]


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
