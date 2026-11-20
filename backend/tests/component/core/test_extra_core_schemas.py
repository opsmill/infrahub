from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.cli.db import check_core_schema_diff, update_core_schema
from infrahub.core import registry
from infrahub.core.initialization import first_time_initialization
from infrahub.core.schema import SchemaRoot
from infrahub.workers.dependencies import build_extra_core_schemas
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

EXTRA_SCHEMA = SchemaRoot(
    nodes=[{"name": "ExtraNode", "namespace": "Testing", "attributes": [{"name": "name", "kind": "Text"}]}]
)


async def test_first_time_initialization_stores_the_extra_core_schemas(
    db: InfrahubDatabase, default_branch: Branch, dependency_provider: Provider
) -> None:
    with override_dependency(build_extra_core_schemas, lambda: [EXTRA_SCHEMA], dependency_provider=dependency_provider):
        await first_time_initialization(db=db)

    stored_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    assert stored_schema.has(name="TestingExtraNode")


async def test_update_core_schema_adds_the_extra_core_schemas(
    db: InfrahubDatabase, default_branch: Branch, dependency_provider: Provider
) -> None:
    await first_time_initialization(db=db)
    assert not await check_core_schema_diff(db=db)

    with override_dependency(build_extra_core_schemas, lambda: [EXTRA_SCHEMA], dependency_provider=dependency_provider):
        assert await check_core_schema_diff(db=db)
        await update_core_schema(db=db, initialize=False)

    stored_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    assert stored_schema.has(name="TestingExtraNode")
