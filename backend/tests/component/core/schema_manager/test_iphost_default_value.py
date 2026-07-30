"""How an `IPHost` attribute's `default_value` is treated when the attribute refuses a prefix."""

import copy
import re
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import load_schema
from tests.helpers.schema.dns_record import DNS_RECORD_DICT

from .conftest import _get_schema_by_kind


@dataclass
class IPHostDefaultValueTestCase:
    name: str
    default_value: str
    parameters: dict[str, Any] | None = None
    recorded_default: str | None = None
    expected_error: str | None = None


IPHOST_DEFAULT_VALUE_CASES = [
    IPHostDefaultValueTestCase(
        name="declared_host_mask_is_rejected",
        default_value="10.0.0.1/32",
        parameters={"allow_prefix": False},
        expected_error="10.0.0.1/32 is not a valid default value for something because a prefix is not permitted",
    ),
    IPHostDefaultValueTestCase(
        name="declared_bare_is_recorded_bare",
        default_value="10.0.0.1",
        parameters={"allow_prefix": False},
        recorded_default="10.0.0.1",
    ),
    IPHostDefaultValueTestCase(
        name="declared_ipv6_host_mask_is_rejected",
        default_value="2001:db8::1/128",
        parameters={"allow_prefix": False},
        expected_error="2001:db8::1/128 is not a valid default value for something because a prefix is not permitted",
    ),
    IPHostDefaultValueTestCase(
        name="declared_subnet_prefix_is_rejected",
        default_value="10.0.0.1/24",
        parameters={"allow_prefix": False},
        expected_error="10.0.0.1/24 is not a valid default value for something because a prefix is not permitted",
    ),
    IPHostDefaultValueTestCase(
        name="declared_ipv6_subnet_prefix_is_rejected",
        default_value="2001:db8::1/64",
        parameters={"allow_prefix": False},
        expected_error="2001:db8::1/64 is not a valid default value for something because a prefix is not permitted",
    ),
    IPHostDefaultValueTestCase(
        name="undeclared_subnet_prefix_is_accepted",
        default_value="10.0.0.1/24",
        recorded_default="10.0.0.1/24",
    ),
    IPHostDefaultValueTestCase(
        name="undeclared_host_mask_is_kept",
        default_value="10.0.0.1/32",
        recorded_default="10.0.0.1/32",
    ),
]


@pytest.mark.parametrize("case", IPHOST_DEFAULT_VALUE_CASES, ids=lambda case: case.name)
async def test_validate_default_value_iphost_prefix_policy(
    schema_all_in_one: dict[str, Any], case: IPHostDefaultValueTestCase
) -> None:
    """A declared attribute refuses a prefixed default; an undeclared one records whatever it was given.

    A rejected case never reaches the default-value validation below: the refusal happens while the
    attribute's own model is validated, which is what keeps a subnet prefix from being reported twice.
    """
    attribute: dict[str, Any] = {
        "name": "something",
        "kind": "IPHost",
        "optional": True,
        "default_value": case.default_value,
    }
    if case.parameters is not None:
        attribute["parameters"] = case.parameters
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraTinySchema")
    schema_dict["attributes"].append(attribute)

    if case.expected_error is not None:
        with pytest.raises(PydanticValidationError, match=re.escape(case.expected_error)):
            SchemaRoot(**schema_all_in_one)
        return

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_default_values()

    assert schema.get(name="InfraTinySchema").get_attribute(name="something").default_value == case.recorded_default


async def test_bare_iphost_default_value_reaches_a_node_bare(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    init_nodes_registry: None,
) -> None:
    definition = copy.deepcopy(DNS_RECORD_DICT)
    # v6_target is allow_prefix=False
    defaults = {"v6_target": "2001:db8::1", "mgmt_ip": "10.0.0.1"}
    for attribute in definition["attributes"]:
        if attribute["name"] in defaults:
            attribute["default_value"] = defaults[attribute["name"]]
    await load_schema(db=db, schema=SchemaRoot(nodes=[definition]))

    node = await Node.init(db=db, schema="TestingDnsRecord", branch=default_branch)
    await node.new(db=db, dns_target="10.10.10.10")
    await node.save(db=db)

    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch, raise_on_error=True)

    assert reloaded.get_attribute("v6_target").value == "2001:db8::1"
    assert reloaded.get_attribute("v6_target").is_default is True
    assert reloaded.get_attribute("mgmt_ip").value == "10.0.0.1/32"
    assert reloaded.get_attribute("mgmt_ip").is_default is True
