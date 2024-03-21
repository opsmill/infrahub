from infrahub.core.initialization import first_time_initialization
from infrahub.database import InfrahubDatabase


def test_first_time_initialization(aio_benchmark, db: InfrahubDatabase, default_branch):
    aio_benchmark(first_time_initialization, db=db)
