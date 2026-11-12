from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.helpers.number_pool import SCOPED_ATTRIBUTE_NAME, SCOPED_SITE, run_schema_updated_workflow
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

# Ordered by name so that the migration reads the switches of a site, and so numbers them, in a known order.
SWITCH = NodeSchema(
    name="Switch",
    namespace="Scope",
    label="Switch",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="site",
            peer=SCOPED_SITE.kind,
            identifier="scope_switch__site",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

# A second kind, so the failing load leaves the switches of the steps before it untouched.
ROUTER = NodeSchema(
    name="Router",
    namespace="Scope",
    label="Router",
    human_friendly_id=["name__value"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="site",
            peer=SCOPED_SITE.kind,
            identifier="scope_router__site",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

SITE_COUNT = 2
SWITCHES_PER_SITE = 2
VLAN_ID_END = 3


def _with_site_scoped_vlan_id(schema: NodeSchema) -> dict[str, Any]:
    switch = schema.model_dump(mode="json", exclude_unset=True)
    switch["attributes"].append(
        {
            "name": SCOPED_ATTRIBUTE_NAME,
            "kind": "NumberPool",
            "optional": False,
            "read_only": True,
            "parameters": {"start_range": 1, "end_range": VLAN_ID_END, "allocation_scope": ["site"]},
        }
    )
    return {"version": "1.0", "nodes": [switch]}


class TestNumberPoolScopeMigrationSchemaLifecycle(TestInfrahubApp):
    """A schema load that adds a NumberPool attribute of 3 numbers scoped by site to 4 switches over 2 sites."""

    @pytest.fixture(scope="class")
    async def site_ids(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, str]:
        await load_schema(
            db=db,
            schema=SchemaRoot(nodes=[SCOPED_SITE, SWITCH, ROUTER]),
            branch_name=default_branch.name,
            update_db=True,
        )
        site_ids: dict[str, str] = {}
        for site_index in range(1, SITE_COUNT + 1):
            site = await client.create(kind=SCOPED_SITE.kind, name=f"site-{site_index:02d}")
            await site.save()
            site_ids[site.name.value] = site.id
            for switch_index in range(1, SWITCHES_PER_SITE + 1):
                switch = await client.create(
                    kind=SWITCH.kind, name=f"switch-{site_index:02d}-{switch_index}", site=site
                )
                await switch.save()
        return site_ids

    async def test_step01_load_numbers_each_site_from_one(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        service: InfrahubServices,
        site_ids: dict[str, str],
    ) -> None:
        response = await client.schema.load(
            schemas=[_with_site_scoped_vlan_id(schema=SWITCH)], branch=default_branch.name
        )

        assert not response.errors
        await run_schema_updated_workflow(service=service, branch=default_branch)
        switches = await NodeManager.query(db=db, schema=SWITCH.kind, branch=default_branch)
        numbers = {
            str(switch.get_attribute("name").value): switch.get_attribute(SCOPED_ATTRIBUTE_NAME).value
            for switch in switches
        }
        assert numbers == {"switch-01-1": 1, "switch-01-2": 2, "switch-02-1": 1, "switch-02-2": 2}

    async def test_step02_new_switch_continues_after_its_site(
        self, client: InfrahubClient, default_branch: Branch, site_ids: dict[str, str]
    ) -> None:
        await client.schema.all(branch=default_branch.name, refresh=True)

        switch = await client.create(kind=SWITCH.kind, name="switch-01-3", site=site_ids["site-01"])
        await switch.save()

        stored = await client.get(kind=SWITCH.kind, id=switch.id)
        assert stored.vlan_id.value == 3

    async def test_step03_load_onto_a_full_site_fails_and_numbers_no_router(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, site_ids: dict[str, str]
    ) -> None:
        for index in range(1, 5):
            router = await client.create(kind=ROUTER.kind, name=f"router-{index:02d}", site=site_ids["site-01"])
            await router.save()

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.schema.load(schemas=[_with_site_scoped_vlan_id(schema=ROUTER)], branch=default_branch.name)

        assert exc_info.value.response.status_code == 409
        errors = exc_info.value.response.json()["errors"]
        assert [error["extensions"] for error in errors] == [{"code": 409}]
        # The pool the failed load created is rolled back, so its id in the message is not known here.
        pool_id = "[0-9a-f-]+"
        assert re.fullmatch(
            f"{re.escape(f'Pool {ROUTER.kind}.{SCOPED_ATTRIBUTE_NAME} [')}{pool_id}{re.escape('] (')}{pool_id}"
            + re.escape(
                f") has no free number left in its ranges for site '{site_ids['site-01']}': 4 node(s) of"
                f" {ROUTER.kind} being filled are in this division and the ranges hold 3 number(s)."
            ),
            errors[0]["message"],
        )
        assert [attribute.name for attribute in registry.schema.get_node_schema(name=ROUTER.kind).attributes] == [
            "name"
        ]
        results = await db.execute_query(
            query="""
            MATCH (:ScopeRouter)-[:HAS_ATTRIBUTE]->(attribute:Attribute {name: $attribute_name})
            RETURN count(attribute) AS attributes
            """,
            params={"attribute_name": SCOPED_ATTRIBUTE_NAME},
            name="count_router_vlan_id_attributes",
        )
        assert results[0]["attributes"] == 0
