from __future__ import annotations

import os
from typing import TYPE_CHECKING

from prefect.server.api.server import create_app

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_infrahub_prefect() -> FastAPI:
    events_retention_days = int(os.environ.get("INFRAHUB_WORKFLOW_WORKER_EVENTS_RETENTION_PERIOD", "7"))
    os.environ["PREFECT_EVENTS_RETENTION_PERIOD"] = f"{events_retention_days}d"
    return create_app()
