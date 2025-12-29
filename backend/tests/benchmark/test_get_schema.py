from collections.abc import Callable
from typing import Any

from infrahub.api.schema import get_schema
from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


def test_get_schema(
    aio_benchmark: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    aio_benchmark(get_schema, branch=default_branch, namespaces=None)
