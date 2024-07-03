import asyncio
import os

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_default_branch,
    create_global_branch,
    create_root_node,
)
from infrahub.core.schema import (
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema_manager import SchemaBranch, SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase

USE_DEMO_DATA = bool(os.getenv("INFRAHUB_BENCHMARK_USE_DEMO", False))


@pytest.fixture
async def exec_async(event_loop):
    def _wrapper(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):

            def _():
                return event_loop.run_until_complete(func(*args, **kwargs))
        else:
            return func(*args, **kwargs)

    return _wrapper


@pytest.fixture
async def aio_benchmark(benchmark, event_loop):
    def _wrapper(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):

            @benchmark
            def _():
                return event_loop.run_until_complete(func(*args, **kwargs))
        else:
            return benchmark(func, *args, **kwargs)

    return _wrapper


@pytest.fixture
async def register_core_models_schema(default_branch: Branch, register_internal_models_schema) -> SchemaBranch:
    if not USE_DEMO_DATA:
        schema = SchemaRoot(**core_models)
        schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        return schema_branch


@pytest.fixture
async def reset_environment(db: InfrahubDatabase) -> None:
    if not USE_DEMO_DATA:
        registry.delete_all()
        await delete_all_nodes(db=db)
        await create_root_node(db=db)


@pytest.fixture
async def default_branch(reset_environment, db: InfrahubDatabase) -> Branch:
    branch: Branch

    if not USE_DEMO_DATA:
        branch = await create_default_branch(db=db)
        await create_global_branch(db=db)
        registry.schema = SchemaManager()
    else:
        branch = registry.default_branch
    return branch


@pytest.fixture
async def register_default_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    if not USE_DEMO_DATA:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
        schema_branch.load_schema(schema=SchemaRoot(**core_models))
        schema_branch.process()
        default_branch.update_schema_hash()
        await default_branch.save(db=db)
        return schema_branch
