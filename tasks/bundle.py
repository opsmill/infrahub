from __future__ import annotations

import os
from typing import TYPE_CHECKING

from invoke.tasks import task

from .container_ops import (
    collect_support_data,
)
from .shared import (
    INFRAHUB_DATABASE,
    Namespace,
)

if TYPE_CHECKING:
    from invoke.context import Context

NAMESPACE = Namespace.DEFAULT


@task(optional=["database"])
def collect(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    include_queries: bool = False,
    project: str | None = None,
    log_lines: int | None = None,
    benchmark: bool = True,
    metrics_interval: int = 30,
) -> None:
    """Collect all logs and create a support archive."""
    if project:
        os.environ["INFRAHUB_BUILD_NAME"] = project

    print("Discovering InfraHub projects...")
    collect_support_data(
        context=context,
        database=database,
        namespace=NAMESPACE,
        include_queries=include_queries,
        log_lines=log_lines,
        benchmark=benchmark,
        metrics_interval=metrics_interval,
    )
