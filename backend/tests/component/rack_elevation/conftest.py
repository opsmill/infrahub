from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .helpers import RunGraphQL
from .option_2 import Option2

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from .dataset import RackOptionFixture


@pytest.fixture(scope="session")
def rack_option() -> RackOptionFixture:
    return Option2()


@pytest.fixture
async def rack_ids(
    register_core_models_schema: None, rack_option: RackOptionFixture, db: InfrahubDatabase, default_branch: Branch
) -> dict[str, str]:
    await rack_option.load_schema(db=db, branch=default_branch)
    return await rack_option.create_dataset(db=db, branch=default_branch)


@pytest.fixture
def run_graphql(db: InfrahubDatabase) -> RunGraphQL:
    return RunGraphQL(db=db)
