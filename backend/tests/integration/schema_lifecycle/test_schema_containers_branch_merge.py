from __future__ import annotations

from copy import deepcopy
from operator import itemgetter
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.api.schema import evaluate_candidate_schemas
from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from tests.helpers.schema.lag_interface import LAG_SCHEMA

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.schema import MainSchemaTypesAPI

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

LAG_BRANCH = "lag-containers"
RELABEL_BRANCH = "lag-containers-relabel"
L2_KIND = "InfraLagInterfaceL2"
L3_KIND = "InfraLagInterfaceL3"

L2_CONTAINERS = [
    {"name": "lacp", "label": "LACP", "description": None, "order_weight": 100, "collapsed": False, "state": "present"},
    {
        "name": "layer2",
        "label": "Layer 2",
        "description": "Switching settings of the bundle",
        "order_weight": 200,
        "collapsed": False,
        "state": "present",
    },
    {
        "name": "layer3",
        "label": "Layer 3",
        "description": None,
        "order_weight": 300,
        "collapsed": True,
        "state": "present",
    },
]


def _containers(node: MainSchemaTypesAPI) -> list[dict[str, Any]]:
    return sorted((container.model_dump() for container in node.containers), key=itemgetter("order_weight"))


def _field_containers(node: MainSchemaTypesAPI) -> dict[str, str | None]:
    return {field.name: field.container for field in [*node.attributes, *node.relationships]}


class TestSchemaLifecycleContainersBranchMerge(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_lag(self) -> dict[str, Any]:
        return deepcopy(LAG_SCHEMA)

    @pytest.fixture(scope="class")
    async def initial_schema(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step01: dict[str, Any]
    ) -> None:
        """Persist a first schema on the default branch, as a running instance has before any branch exists."""
        await load_schema(db=db, schema=schema_step01)

    @pytest.fixture(scope="class")
    def schema_lag_relabelled(self, schema_lag: dict[str, Any]) -> dict[str, Any]:
        schema = deepcopy(schema_lag)
        lacp = next(container for container in schema["generics"][0]["containers"] if container["name"] == "lacp")
        lacp["label"] = "Link aggregation"
        return schema

    async def test_containers_loaded_on_a_branch_are_returned_on_that_branch(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        initial_schema: None,
        schema_lag: dict[str, Any],
    ) -> None:
        await client.branch.create(branch_name=LAG_BRANCH, sync_with_git=False)
        response = await client.schema.load(schemas=[schema_lag], branch=LAG_BRANCH)
        assert not response.errors

        l2 = await client.schema.get(kind=L2_KIND, branch=LAG_BRANCH, refresh=True)
        assert _containers(l2) == L2_CONTAINERS
        assert _field_containers(l2) == {
            "name": None,
            "description": None,
            "lacp_rate": "lacp",
            "lacp_mode": "lacp",
            "l2_mode": "layer2",
            "mac_address": "layer2",
            "mtu": "layer3",
            "sub_interfaces": "advanced",
            "member_of_groups": None,
            "subscriber_of_groups": None,
            "profiles": None,
        }
        assert "inherited" not in l2.containers[0].model_fields

        l3 = await client.schema.get(kind=L3_KIND, branch=LAG_BRANCH)
        assert [container["label"] for container in _containers(l3)] == ["LACP", "Layer 2", "Layer 3 (routed)"]

        default_schema = await client.schema.all(branch=default_branch.name, refresh=True)
        assert L2_KIND not in default_schema

    async def test_merging_the_branch_returns_the_containers_on_the_default_branch(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch
    ) -> None:
        await client.branch.merge(branch_name=LAG_BRANCH)

        l2 = await client.schema.get(kind=L2_KIND, branch=default_branch.name, refresh=True)
        assert _containers(l2) == L2_CONTAINERS
        assert _field_containers(l2)["mtu"] == "layer3"
        assert _field_containers(l2)["sub_interfaces"] == "advanced"

        stored_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        stored_l2 = stored_schema.get_node(name=L2_KIND, duplicate=False)
        assert [container.name for container in stored_l2.containers] == ["lacp", "layer2", "layer3"]
        assert stored_l2.get_attribute(name="mtu").container == "layer3"
        assert stored_l2.get_relationship(name="sub_interfaces").container == "advanced"

    async def test_a_label_change_on_the_branch_needs_no_migration(
        self, client: InfrahubClient, default_branch: Branch, schema_lag_relabelled: dict[str, Any]
    ) -> None:
        await client.branch.create(branch_name=RELABEL_BRANCH, sync_with_git=False)

        branch_schema = registry.schema.get_schema_branch(name=RELABEL_BRANCH)
        _, result = evaluate_candidate_schemas(
            branch_schema=branch_schema, schemas_to_evaluate=[SchemaRoot(**schema_lag_relabelled)]
        )
        assert result.migrations == []
        assert result.constraints == []
        assert "InfraLagInterface" in result.diff.changed

        response = await client.schema.load(schemas=[schema_lag_relabelled], branch=RELABEL_BRANCH)
        assert not response.errors
        assert response.schema_updated

        l2 = await client.schema.get(kind=L2_KIND, branch=RELABEL_BRANCH, refresh=True)
        assert [container["label"] for container in _containers(l2)] == ["Link aggregation", "Layer 2", "Layer 3"]

        default_l2 = await client.schema.get(kind=L2_KIND, branch=default_branch.name, refresh=True)
        assert [container["label"] for container in _containers(default_l2)] == ["LACP", "Layer 2", "Layer 3"]
