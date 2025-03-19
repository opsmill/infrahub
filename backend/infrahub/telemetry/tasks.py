import hashlib
import json
import platform
import time
from typing import Any

from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub import __version__, config
from infrahub.core import registry, utils
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.services import InfrahubServices

from .constants import TELEMETRY_KIND, TELEMETRY_VERSION
from .database import gather_database_information
from .models import (
    TelemetryBranchData,
    TelemetryData,
    TelemetrySchemaData,
    TelemetryWorkerData,
)
from .task_manager import gather_prefect_information
from .utils import determine_infrahub_type


@task(name="telemetry-schema-information", task_run_name="Gather Schema Information", cache_policy=NONE)
async def gather_schema_information(branch: Branch) -> TelemetrySchemaData:
    main_schema = registry.schema.get_schema_branch(name=branch.name)
    return TelemetrySchemaData(
        node_count=len(main_schema.node_names),
        generic_count=len(main_schema.generic_names),
        last_update=branch.schema_changed_at or "",
    )


@task(name="telemetry-feature-information", task_run_name="Gather Feature Information", cache_policy=NONE)
async def gather_feature_information(service: InfrahubServices) -> dict[str, int]:
    async with service.database.start_session() as db:
        data = {}
        features_to_count = [
            InfrahubKind.ARTIFACT,
            InfrahubKind.RESOURCEPOOL,
            InfrahubKind.REPOSITORY,
            InfrahubKind.GENERICGROUP,
            InfrahubKind.PROFILE,
            InfrahubKind.PROPOSEDCHANGE,
            InfrahubKind.OBJECTTEMPLATE,
            InfrahubKind.TRANSFORM,
            InfrahubKind.WEBHOOK,
        ]
        for kind in features_to_count:
            data[kind] = await utils.count_nodes(db=db, label=kind)

        return data


@task(name="telemetry-gather-data", task_run_name="Gather Anonynous Data", cache_policy=NONE)
async def gather_anonymous_telemetry_data(service: InfrahubServices) -> TelemetryData:
    start_time = time.time()

    default_branch = registry.get_branch_from_registry()
    workers = await service.component.list_workers(branch=default_branch.name, schema_hash=False)

    data = TelemetryData(
        deployment_id=registry.id,
        execution_time=None,
        infrahub_version=__version__,
        infrahub_type=determine_infrahub_type(),
        python_version=platform.python_version(),
        platform=platform.machine(),
        workers=TelemetryWorkerData(
            total=len(workers),
            active=len([w for w in workers if w.active]),
        ),
        branches=TelemetryBranchData(
            total=len(registry.branch),
        ),
        features=await gather_feature_information(service=service),
        schema_info=await gather_schema_information(branch=default_branch),
        database=await gather_database_information(db=service.database),
        prefect=await gather_prefect_information(),
    )

    data.execution_time = time.time() - start_time

    return data


@task(name="telemetry-post-data", task_run_name="Upload data", retries=5, cache_policy=NONE)
async def post_telemetry_data(service: InfrahubServices, url: str, payload: dict[str, Any]) -> None:
    """Send the telemetry data to the specified URL, using HTTP POST."""
    response = await service.http.post(url=url, json=payload)
    response.raise_for_status()


@flow(name="anonymous_telemetry_send", flow_run_name="Send anonymous telemetry")
async def send_telemetry_push(service: InfrahubServices) -> None:
    log = get_run_logger()
    if config.SETTINGS.main.telemetry_optout:
        log.info("Skipping, User opted out of this service.")
        return

    log.info(f"Pushing anonymous telemetry data to {config.SETTINGS.main.telemetry_endpoint}...")

    data = await gather_anonymous_telemetry_data(service=service)
    data_dict = data.model_dump(mode="json")
    log.info(f"Anonymous usage telemetry gathered in {data.execution_time} seconds. | {data_dict}")

    payload = {
        "kind": TELEMETRY_KIND,
        "payload_format": TELEMETRY_VERSION,
        "data": data_dict,
        "checksum": hashlib.sha256(json.dumps(data_dict).encode()).hexdigest(),
    }

    await post_telemetry_data(service=service, url=config.SETTINGS.main.telemetry_endpoint, payload=payload)
