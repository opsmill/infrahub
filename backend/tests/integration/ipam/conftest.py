from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema_manager import SchemaBranch


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
async def register_ipam_schema(default_branch: Branch, ipam_schema: SchemaRoot) -> SchemaBranch:
    schema_branch = registry.schema.register_schema(schema=ipam_schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch
