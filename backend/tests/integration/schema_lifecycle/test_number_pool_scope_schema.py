from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.registry import registry
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

DEVICE_POOL_BY_SITE = "vlan-per-site"


def _device() -> dict[str, Any]:
    return SCOPED_DEVICE.model_dump(mode="json", exclude_unset=True)


def _field(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return next(field for field in [*schema["attributes"], *schema["relationships"]] if field["name"] == name)


def _site_optional() -> dict[str, Any]:
    device = _device()
    _field(device, "site")["optional"] = True
    return {"version": "1.0", "nodes": [device]}


SITE_OPTIONAL_REFUSAL = (
    f"'number_pool.scope' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'. Node ({DEVICE_POOL_BY_SITE}) is"
    f" not compliant. The error relates to field site='pool {DEVICE_POOL_BY_SITE} divides its numbers by"
    " ScopeDevice.site; a scope element must stay required'."
)


def _error_messages(errors: dict[str, Any]) -> list[str]:
    return [error["message"] for error in errors["errors"]]


class TestNumberPoolScopeCheckerSchemaLifecycle(TestInfrahubApp):
    """A schema load and a schema check that break an element dividing a user-created pool, and a rename of it."""

    @pytest.fixture(scope="class")
    async def scoped_pool(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> InfrahubNode:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, branch_name=default_branch.name, update_db=True)
        pool = await client.create(
            kind=InfrahubKind.NUMBERPOOL,
            name=DEVICE_POOL_BY_SITE,
            node=SCOPED_DEVICE.kind,
            node_attribute="vlan_id",
            start_range=1,
            end_range=10,
            allocation_scope=["site"],
        )
        await pool.save()
        return pool

    @pytest.fixture(scope="class")
    async def other_branch(self, db: InfrahubDatabase, scoped_pool: InfrahubNode) -> Branch:
        return await create_branch(db=db, branch_name="scope-checker")

    @staticmethod
    async def _stored_device_hash(db: InfrahubDatabase, branch: Branch) -> str:
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        return schema_branch.get(name=SCOPED_DEVICE.kind, duplicate=False).get_hash()

    async def _assert_load_refused(self, db: InfrahubDatabase, client: InfrahubClient, branch: Branch) -> None:
        before = await self._stored_device_hash(db=db, branch=branch)

        response = await client.schema.load(schemas=[_site_optional()], branch=branch.name)

        assert response.errors
        assert _error_messages(response.errors) == [SITE_OPTIONAL_REFUSAL]
        assert await self._stored_device_hash(db=db, branch=branch) == before

    async def test_step01_load_on_default_branch_is_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, scoped_pool: InfrahubNode
    ) -> None:
        await self._assert_load_refused(db=db, client=client, branch=default_branch)

    async def test_step02_load_on_a_branch_is_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, other_branch: Branch
    ) -> None:
        await self._assert_load_refused(db=db, client=client, branch=other_branch)

    async def test_step03_check_reports_the_refusal_without_loading(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, scoped_pool: InfrahubNode
    ) -> None:
        before = await self._stored_device_hash(db=db, branch=default_branch)

        success, response = await client.schema.check(schemas=[_site_optional()], branch=default_branch.name)

        assert not success
        assert response is not None
        assert _error_messages(response) == [SITE_OPTIONAL_REFUSAL]
        assert await self._stored_device_hash(db=db, branch=default_branch) == before
