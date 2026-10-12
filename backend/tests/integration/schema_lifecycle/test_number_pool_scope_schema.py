from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_POOL_SCHEMA,
    SCOPED_RACK,
    SCOPED_SITE,
    run_schema_updated_workflow,
)
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

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

    async def test_step04_renaming_the_relationship_renames_the_stored_element(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        service: InfrahubServices,
        scoped_pool: InfrahubNode,
    ) -> None:
        site_id = (
            registry.schema.get_node_schema(name=SCOPED_DEVICE.kind, branch=default_branch)
            .get_relationship(name="site")
            .id
        )
        assert site_id
        device = _device()
        _field(device, "site").update(name="location", id=site_id)

        response = await client.schema.load(schemas=[{"version": "1.0", "nodes": [device]}], branch=default_branch.name)
        assert not response.errors
        await run_schema_updated_workflow(service=service, branch=default_branch)

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        renamed = schema_branch.get_node(name=SCOPED_DEVICE.kind, duplicate=False).get_relationship(name="location")
        assert renamed.id == site_id
        pool = await client.get(kind=InfrahubKind.NUMBERPOOL, id=scoped_pool.id)
        assert pool.allocation_scope.value == [{"id": site_id, "name": "location"}]

    @pytest.mark.xfail(
        reason="per-division allocation lands with the allocation ticket", raises=AssertionError, strict=True
    )
    async def test_step05_new_device_allocates_per_site_after_the_rename(
        self, client: InfrahubClient, default_branch: Branch, scoped_pool: InfrahubNode
    ) -> None:
        pool_id = scoped_pool.id
        await client.schema.all(branch=default_branch.name, refresh=True)
        numbers: dict[str, int] = {}
        for site_name in ("site-a", "site-b"):
            site = await client.create(kind="ScopeSite", name=site_name)
            await site.save()
            device = await client.create(
                kind=SCOPED_DEVICE.kind,
                name=f"device-{site_name}",
                role="leaf",
                tags=[],
                location=site,
                vlan_id={"from_pool": {"id": pool_id}},
            )
            await device.save()
            numbers[site_name] = device.vlan_id.value

        assert numbers == {"site-a": 1, "site-b": 1}


def _pooled_attribute(name: str, scope: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "NumberPool",
        "optional": False,
        "read_only": True,
        "parameters": {"start_range": 1, "end_range": 100, "allocation_scope": scope},
    }


def _declared_device(scope: list[str]) -> dict[str, Any]:
    device = _device()
    device["attributes"] = [
        *(attribute for attribute in device["attributes"] if attribute["name"] != "vlan_id"),
        _pooled_attribute(name="vlan_id", scope=scope),
    ]
    return device


def _declared_schema_root(scope: list[str]) -> SchemaRoot:
    return SchemaRoot(
        generics=[SCOPED_HOLDER],
        nodes=[SCOPED_SITE, SCOPED_RACK, SCOPED_LINK, NodeSchema(**_declared_device(scope)), SCOPED_POD_HOLDER],
    )


def _declared_refusal(pool: InfrahubNode, field: str, detail: str) -> str:
    return (
        f"'number_pool.scope' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'. Node ({pool.name.value}) is"
        f" not compliant. The error relates to field {field}={f'ScopeDevice.vlan_id: {detail}'!r}."
    )


CANNOT_CHANGE = "allocation_scope can't be changed after the pool is created"


class TestNumberPoolScopeDeclarationSchemaLifecycle(TestInfrahubApp):
    """Schema loads that change, or follow a rename of, the scope a NumberPool attribute declares for its pool."""

    @pytest.fixture(scope="class")
    async def schema_pool(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient, service: InfrahubServices
    ) -> InfrahubNode:
        await load_schema(
            db=db, schema=_declared_schema_root(scope=["site"]), branch_name=default_branch.name, update_db=True
        )
        await run_schema_updated_workflow(service=service, branch=default_branch)
        pools = await client.filters(kind=InfrahubKind.NUMBERPOOL, node__value=SCOPED_DEVICE.kind)
        assert len(pools) == 1
        return pools[0]

    @pytest.fixture(scope="class")
    async def declaration_branch(self, db: InfrahubDatabase, schema_pool: InfrahubNode) -> Branch:
        return await create_branch(db=db, branch_name="scope-declaration")

    @staticmethod
    async def _stored_device(db: InfrahubDatabase, branch: Branch) -> tuple[str, list[str] | None]:
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        device = schema_branch.get_node(name=SCOPED_DEVICE.kind, duplicate=False)
        parameters = device.get_attribute(name="vlan_id").parameters
        assert isinstance(parameters, NumberPoolParameters)
        return device.get_hash(), parameters.allocation_scope

    async def _assert_load_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, branch: Branch, device: dict[str, Any], refusal: str
    ) -> None:
        before = await self._stored_device(db=db, branch=branch)

        response = await client.schema.load(schemas=[{"version": "1.0", "nodes": [device]}], branch=branch.name)

        assert response.errors
        assert _error_messages(response.errors) == [refusal]
        assert await self._stored_device(db=db, branch=branch) == before

    async def test_step01_declaring_another_element_is_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, schema_pool: InfrahubNode
    ) -> None:
        assert schema_pool.allocation_scope.value == [{"id": self._site_id(branch=default_branch), "name": "site"}]

        await self._assert_load_refused(
            db=db,
            client=client,
            branch=default_branch,
            device=_declared_device(scope=["role"]),
            refusal=_declared_refusal(pool=schema_pool, field="vlan_id", detail=CANNOT_CHANGE),
        )

    async def test_step02_clearing_the_declaration_is_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, schema_pool: InfrahubNode
    ) -> None:
        await self._assert_load_refused(
            db=db,
            client=client,
            branch=default_branch,
            device=_declared_device(scope=[]),
            refusal=_declared_refusal(pool=schema_pool, field="vlan_id", detail=CANNOT_CHANGE),
        )

    async def test_step03_leaving_the_declaration_out_keeps_it(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, schema_pool: InfrahubNode
    ) -> None:
        """A load merges a parameter it leaves out as unchanged, so the stored declaration and the pool's scope stay."""
        before = await self._stored_device(db=db, branch=default_branch)
        device = _declared_device(scope=["site"])
        del _field(device, "vlan_id")["parameters"]["allocation_scope"]

        response = await client.schema.load(schemas=[{"version": "1.0", "nodes": [device]}], branch=default_branch.name)

        assert not response.errors
        assert await self._stored_device(db=db, branch=default_branch) == before
        assert before[1] == ["site"]
        pool = await client.get(kind=InfrahubKind.NUMBERPOOL, id=schema_pool.id)
        assert pool.allocation_scope.value == [{"id": self._site_id(branch=default_branch), "name": "site"}]

    async def test_step04_declaring_another_element_is_refused_on_a_branch(
        self, db: InfrahubDatabase, client: InfrahubClient, declaration_branch: Branch, schema_pool: InfrahubNode
    ) -> None:
        await self._assert_load_refused(
            db=db,
            client=client,
            branch=declaration_branch,
            device=_declared_device(scope=["role"]),
            refusal=_declared_refusal(pool=schema_pool, field="vlan_id", detail=CANNOT_CHANGE),
        )

    async def test_step05_declaring_an_element_absent_from_the_default_branch_is_refused_on_a_branch(
        self, db: InfrahubDatabase, client: InfrahubClient, declaration_branch: Branch
    ) -> None:
        device = _declared_device(scope=["site"])
        device["attributes"].extend(
            [{"name": "zone", "kind": "Text", "optional": False}, _pooled_attribute(name="port_id", scope=["zone"])]
        )

        await self._assert_load_refused(
            db=db,
            client=client,
            branch=declaration_branch,
            device=device,
            refusal='ScopeDevice.port_id: allocation_scope: "zone" is not an attribute or a relationship of'
            " ScopeDevice on branch main",
        )

    async def test_step06_renaming_the_element_without_updating_the_declaration_is_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, schema_pool: InfrahubNode
    ) -> None:
        device = _declared_device(scope=["site"])
        _field(device, "site").update(name="location", id=self._site_id(branch=default_branch))

        await self._assert_load_refused(
            db=db,
            client=client,
            branch=default_branch,
            device=device,
            refusal=_declared_refusal(
                pool=schema_pool,
                field="location",
                detail='allocation_scope: "site" was renamed to "location"; update allocation_scope to the new name',
            ),
        )

    async def test_step07_renaming_the_element_with_the_declaration_updated_is_accepted(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        service: InfrahubServices,
        schema_pool: InfrahubNode,
    ) -> None:
        site_id = self._site_id(branch=default_branch)
        device = _declared_device(scope=["location"])
        _field(device, "site").update(name="location", id=site_id)

        response = await client.schema.load(schemas=[{"version": "1.0", "nodes": [device]}], branch=default_branch.name)
        assert not response.errors
        await run_schema_updated_workflow(service=service, branch=default_branch)

        _, declaration = await self._stored_device(db=db, branch=default_branch)
        assert declaration == ["location"]
        pool = await client.get(kind=InfrahubKind.NUMBERPOOL, id=schema_pool.id)
        assert pool.allocation_scope.value == [{"id": site_id, "name": "location"}]

    @staticmethod
    def _site_id(branch: Branch) -> str:
        site_id = (
            registry.schema.get_node_schema(name=SCOPED_DEVICE.kind, branch=branch).get_relationship(name="site").id
        )
        assert site_id
        return site_id
