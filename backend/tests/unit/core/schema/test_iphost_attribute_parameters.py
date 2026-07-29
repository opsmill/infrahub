from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.attribute_parameters import (
    AttributeParameters,
    IPHostAttributeParameters,
    TextAttributeParameters,
)
from infrahub.core.schema.attribute_schema import AttributeSchema, IPHostAttributeSchema
from tests.helpers.schema.dns_record import DNS_RECORD_DEFINITION


def _dns_record_definition() -> dict[str, Any]:
    return deepcopy(DNS_RECORD_DEFINITION)


def _set_default_value(definition: dict[str, Any], attribute_name: str, default_value: Any) -> None:
    attribute = next(attr for attr in definition["attributes"] if attr["name"] == attribute_name)
    attribute["default_value"] = default_value


def _iphost_attribute(node: NodeSchema, name: str) -> IPHostAttributeSchema:
    """Return an IPHost attribute as its per-kind class, which is what makes the flag reachable."""
    attribute = node.get_attribute(name=name)
    assert isinstance(attribute, IPHostAttributeSchema)
    return attribute


class TestAllowPrefixDeclaration:
    def test_declared_and_undeclared_attributes_carry_their_own_flag(self) -> None:
        node = NodeSchema(**_dns_record_definition())

        flags = {name: _iphost_attribute(node, name).parameters.allow_prefix for name in node.attribute_names}

        assert flags == {"dns_target": False, "mgmt_ip": True, "v6_target": False}

    def test_an_iphost_attribute_declaring_nothing_keeps_prefixes(self) -> None:
        attribute = IPHostAttributeSchema(name="mgmt_ip", kind="IPHost")

        assert attribute.parameters == IPHostAttributeParameters(allow_prefix=True)

    def test_allow_prefix_cannot_be_updated(self) -> None:
        field = IPHostAttributeParameters.model_fields["allow_prefix"]

        assert field.json_schema_extra == {"update": UpdateSupport.NOT_SUPPORTED.value}

    @pytest.mark.parametrize("kind", ["Boolean", "IPNetwork"])
    def test_iphost_parameters_are_refused_on_another_kind(self, kind: str) -> None:
        message = f"IPHostAttributeParameters can't be used as parameters for {kind}"

        with pytest.raises(ValidationError, match=re.escape(message)):
            AttributeSchema(name="some_attr", kind=kind, parameters=IPHostAttributeParameters(allow_prefix=False))

    @pytest.mark.parametrize("parameters_class", [AttributeParameters, TextAttributeParameters])
    def test_allow_prefix_is_refused_by_other_parameters_models(
        self, parameters_class: type[AttributeParameters]
    ) -> None:
        with pytest.raises(ValidationError, match=r"allow_prefix\n  Extra inputs are not permitted"):
            parameters_class.model_validate({"allow_prefix": False})

    def test_allow_prefix_declared_on_another_kind_is_dropped_on_load(self) -> None:
        """Pin the coercion behaviour shared by every attribute parameter.

        An attribute is coerced to the parameters model of its own kind and unknown keys are dropped
        in the process, so a loaded schema declaring the flag on another kind is accepted and the
        flag is lost rather than reported. Recorded so a change to that becomes a deliberate one.
        """
        definition = _dns_record_definition()
        definition["attributes"].append(
            {"name": "record_label", "kind": "Text", "optional": True, "parameters": {"allow_prefix": False}}
        )

        node = NodeSchema(**definition)

        assert node.get_attribute(name="record_label").parameters == TextAttributeParameters()
        assert _iphost_attribute(node, "dns_target").parameters.allow_prefix is False


class TestDefaultValueNormalisation:
    @dataclass
    class Case:
        name: str
        attribute_name: str
        declared_default: str
        expected_default: str

    @pytest.mark.parametrize(
        "case",
        [
            Case(
                name="declared_ipv4_host_mask_is_stripped",
                attribute_name="dns_target",
                declared_default="10.0.0.1/32",
                expected_default="10.0.0.1",
            ),
            Case(
                name="declared_ipv4_bare_is_left_alone",
                attribute_name="dns_target",
                declared_default="10.0.0.1",
                expected_default="10.0.0.1",
            ),
            Case(
                name="declared_ipv6_host_mask_is_stripped",
                attribute_name="v6_target",
                declared_default="2001:db8::1/128",
                expected_default="2001:db8::1",
            ),
            Case(
                name="declared_subnet_prefix_is_left_to_format_validation",
                attribute_name="dns_target",
                declared_default="10.0.0.1/24",
                expected_default="10.0.0.1/24",
            ),
            Case(
                name="undeclared_host_mask_is_untouched",
                attribute_name="mgmt_ip",
                declared_default="10.0.0.1/32",
                expected_default="10.0.0.1/32",
            ),
            Case(
                name="undeclared_bare_is_untouched",
                attribute_name="mgmt_ip",
                declared_default="10.0.0.1",
                expected_default="10.0.0.1",
            ),
        ],
        ids=lambda case: case.name,
    )
    def test_default_value(self, case: Case) -> None:
        definition = _dns_record_definition()
        _set_default_value(definition, case.attribute_name, case.declared_default)

        node = NodeSchema(**definition)

        assert node.get_attribute(name=case.attribute_name).default_value == case.expected_default
