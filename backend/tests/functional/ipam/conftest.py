from typing import Any

import pytest

from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.schema import SchemaRoot


@pytest.fixture(scope="class")
async def ipam_schema() -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "IPPrefix",
                "namespace": "Ipam",
                "default_filter": "prefix__value",
                "order_by": ["prefix__value"],
                "display_labels": ["prefix__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPPREFIX],
            },
            {
                "name": "IPAddress",
                "namespace": "Ipam",
                "default_filter": "address__value",
                "order_by": ["address__value"],
                "display_labels": ["address__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPADDRESS],
            },
        ],
    }

    return SchemaRoot(**SCHEMA)


@pytest.fixture(scope="class")
async def prefix_with_rel_in_hfid_schema() -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Prefix",
                "namespace": "Infra",
                "description": "IPv4 or IPv6 network (with mask)",
                "icon": "mdi:ip-network",
                "include_in_menu": False,
                "label": "Prefix",
                "uniqueness_constraints": [["ip_namespace", "prefix__value"]],
                "human_friendly_id": ["prefix__value", "ip_namespace__name__value"],
                "inherit_from": ["BuiltinIPPrefix"],
            }
        ]
    }

    return SchemaRoot(**SCHEMA)
