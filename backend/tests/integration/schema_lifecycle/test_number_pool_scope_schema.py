from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_HOLDER, SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

DEVICE_POOL_BY_SITE = "vlan-per-site"
DEVICE_POOL_BY_ROLE = "vlan-per-role"
HOLDER_POOL_BY_SITE = "holder-vlan-per-site"


def _device() -> dict[str, Any]:
    return SCOPED_DEVICE.model_dump(mode="json", exclude_unset=True)


def _holder() -> dict[str, Any]:
    return SCOPED_HOLDER.model_dump(mode="json", exclude_unset=True)


def _field(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return next(field for field in [*schema["attributes"], *schema["relationships"]] if field["name"] == name)


def _with_field_change(name: str, **changes: Any) -> dict[str, Any]:
    device = _device()
    _field(device, name).update(changes)
    return {"version": "1.0", "nodes": [device]}


def _site_optional() -> dict[str, Any]:
    return _with_field_change("site", optional=True)


def _site_many() -> dict[str, Any]:
    return _with_field_change("site", cardinality="many")


def _site_removed() -> dict[str, Any]:
    return _with_field_change("site", state="absent")


def _role_optional() -> dict[str, Any]:
    return _with_field_change("role", optional=True)


def _role_removed() -> dict[str, Any]:
    return _with_field_change("role", state="absent")


def _vlan_id_unique() -> dict[str, Any]:
    return _with_field_change("vlan_id", unique=True)


def _holder_site_optional() -> dict[str, Any]:
    holder = _holder()
    _field(holder, "site")["optional"] = True
    return {"version": "1.0", "generics": [holder]}


def _refusal(pool: str, field: str, detail: str) -> str:
    return (
        f"'number_pool.scope' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'. Node ({pool}) is not"
        f" compliant. The error relates to field {field}='pool {pool} {detail}'."
    )


@dataclass(frozen=True)
class RefusalCase:
    name: str
    schema: Callable[[], dict[str, Any]]
    kind: str
    refusals: tuple[str, ...]


UNIQUE_DETAIL = "allocates ScopeDevice.vlan_id per division; a globally unique number cannot be allocated per division"

REFUSAL_CASES = [
    RefusalCase(
        name="relationship-made-optional",
        schema=_site_optional,
        kind=SCOPED_DEVICE.kind,
        refusals=(
            _refusal(
                pool=DEVICE_POOL_BY_SITE,
                field="site",
                detail="divides its numbers by ScopeDevice.site; a scope element must stay required",
            ),
        ),
    ),
    RefusalCase(
        name="relationship-made-many",
        schema=_site_many,
        kind=SCOPED_DEVICE.kind,
        refusals=(
            _refusal(
                pool=DEVICE_POOL_BY_SITE,
                field="site",
                detail="divides its numbers by ScopeDevice.site;"
                " a scope element must stay a relationship of cardinality one",
            ),
        ),
    ),
    RefusalCase(
        name="relationship-removed",
        schema=_site_removed,
        kind=SCOPED_DEVICE.kind,
        refusals=(
            _refusal(
                pool=DEVICE_POOL_BY_SITE,
                field="site",
                detail="divides its numbers by ScopeDevice.site;"
                " a scope element cannot be removed while the pool exists",
            ),
        ),
    ),
    RefusalCase(
        name="attribute-made-optional",
        schema=_role_optional,
        kind=SCOPED_DEVICE.kind,
        refusals=(
            _refusal(
                pool=DEVICE_POOL_BY_ROLE,
                field="role",
                detail="divides its numbers by ScopeDevice.role; a scope element must stay required",
            ),
        ),
    ),
    RefusalCase(
        name="attribute-removed",
        schema=_role_removed,
        kind=SCOPED_DEVICE.kind,
        refusals=(
            _refusal(
                pool=DEVICE_POOL_BY_ROLE,
                field="role",
                detail="divides its numbers by ScopeDevice.role;"
                " a scope element cannot be removed while the pool exists",
            ),
        ),
    ),
    RefusalCase(
        name="tracked-attribute-made-unique",
        schema=_vlan_id_unique,
        kind=SCOPED_DEVICE.kind,
        refusals=(
            _refusal(pool=DEVICE_POOL_BY_SITE, field="vlan_id", detail=UNIQUE_DETAIL),
            _refusal(pool=DEVICE_POOL_BY_ROLE, field="vlan_id", detail=UNIQUE_DETAIL),
        ),
    ),
    RefusalCase(
        name="generic-relationship-made-optional",
        schema=_holder_site_optional,
        kind=SCOPED_HOLDER.kind,
        refusals=(
            _refusal(
                pool=HOLDER_POOL_BY_SITE,
                field="site",
                detail="divides its numbers by ScopeHolder.site; a scope element must stay required",
            ),
        ),
    ),
]
REFUSAL_IDS = [case.name for case in REFUSAL_CASES]


def _error_messages(errors: dict[str, Any]) -> list[str]:
    # The API joins the violations of one constraint into one message, in the order the pools were read.
    return sorted(message for error in errors["errors"] for message in error["message"].split(",\n"))


class TestNumberPoolScopeCheckerSchemaLifecycle(TestInfrahubApp):
    """Schema loads and checks that would break, or rename, an element dividing a user-created pool."""

    @pytest.fixture(scope="class")
    async def scoped_pools(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient
    ) -> dict[str, InfrahubNode]:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, branch_name=default_branch.name, update_db=True)
        pools: dict[str, InfrahubNode] = {}
        for name, kind, scope in (
            (DEVICE_POOL_BY_SITE, SCOPED_DEVICE.kind, ["site"]),
            (DEVICE_POOL_BY_ROLE, SCOPED_DEVICE.kind, ["role"]),
            (HOLDER_POOL_BY_SITE, SCOPED_HOLDER.kind, ["site"]),
        ):
            pool = await client.create(
                kind=InfrahubKind.NUMBERPOOL,
                name=name,
                node=kind,
                node_attribute="vlan_id",
                start_range=1,
                end_range=10,
                allocation_scope=scope,
            )
            await pool.save()
            pools[name] = pool
        return pools

    @pytest.fixture(scope="class")
    async def other_branch(self, db: InfrahubDatabase, scoped_pools: dict[str, InfrahubNode]) -> Branch:
        return await create_branch(db=db, branch_name="scope-checker")

    @staticmethod
    async def _stored_kind_hash(db: InfrahubDatabase, branch: Branch, kind: str) -> str:
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        return schema_branch.get(name=kind, duplicate=False).get_hash()

    async def _assert_load_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, branch: Branch, case: RefusalCase
    ) -> None:
        before = await self._stored_kind_hash(db=db, branch=branch, kind=case.kind)

        response = await client.schema.load(schemas=[case.schema()], branch=branch.name)

        assert response.errors
        assert _error_messages(response.errors) == sorted(case.refusals)
        assert await self._stored_kind_hash(db=db, branch=branch, kind=case.kind) == before

    @pytest.mark.parametrize("case", REFUSAL_CASES, ids=REFUSAL_IDS)
    async def test_step01_load_on_default_branch_is_refused(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        scoped_pools: dict[str, InfrahubNode],
        case: RefusalCase,
    ) -> None:
        await self._assert_load_refused(db=db, client=client, branch=default_branch, case=case)

    @pytest.mark.parametrize("case", REFUSAL_CASES, ids=REFUSAL_IDS)
    async def test_step02_load_on_a_branch_is_refused(
        self, db: InfrahubDatabase, client: InfrahubClient, other_branch: Branch, case: RefusalCase
    ) -> None:
        await self._assert_load_refused(db=db, client=client, branch=other_branch, case=case)

    @pytest.mark.parametrize("case", REFUSAL_CASES, ids=REFUSAL_IDS)
    async def test_step03_check_reports_the_refusal_without_loading(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        scoped_pools: dict[str, InfrahubNode],
        case: RefusalCase,
    ) -> None:
        before = await self._stored_kind_hash(db=db, branch=default_branch, kind=case.kind)

        success, response = await client.schema.check(schemas=[case.schema()], branch=default_branch.name)

        assert not success
        assert response is not None
        assert _error_messages(response) == sorted(case.refusals)
        assert await self._stored_kind_hash(db=db, branch=default_branch, kind=case.kind) == before
