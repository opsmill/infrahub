from collections.abc import Callable
from typing import Any

import pytest

from infrahub.api.menu import get_menu
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_menu
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def init_menu(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch) -> None:
    await create_default_menu(db=db)


def test_get_menu(
    aio_benchmark: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    init_menu: None,
) -> None:
    aio_benchmark(get_menu, db=db, branch=default_branch, permission_manager=None)
