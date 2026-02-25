from infrahub.core.branch import Branch
from infrahub.core.initialization import first_time_initialization
from infrahub.database import InfrahubDatabase


async def test_first_time_initialization(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)
    assert True
