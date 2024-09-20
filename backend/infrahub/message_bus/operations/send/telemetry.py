import hashlib
import json
import platform
import time
from typing import Any

import httpx
from prefect import flow, task
from prefect.logging import get_run_logger

from infrahub import __version__, config
from infrahub.core import registry, utils
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices, services

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20240524"


@task
async def gather_database_information(service: InfrahubServices, branch: Branch) -> dict:  # pylint: disable=unused-argument
    data: dict[str, Any] = {
        "database_type": service.database.db_type.value,
        "relationship_count": {"total": await utils.count_relationships(db=service.database)},
        "node_count": {"total": await utils.count_nodes(db=service.database)},
    }

    for name in GRAPH_SCHEMA["relationships"]:
        data["relationship_count"][name] = await utils.count_relationships(db=service.database, label=name)

    for name in GRAPH_SCHEMA["nodes"]:
        data["node_count"][name] = await utils.count_nodes(db=service.database, label=name)

    return data


@task
async def gather_schema_information(service: InfrahubServices, branch: Branch) -> dict:  # pylint: disable=unused-argument
    data: dict[str, Any] = {}
    main_schema = registry.schema.get_schema_branch(name=branch.name)
    data["node_count"] = len(main_schema.node_names)
    data["generic_count"] = len(main_schema.generic_names)
    data["last_update"] = branch.schema_changed_at

    return data


@task
async def gather_feature_information(service: InfrahubServices, branch: Branch) -> dict:  # pylint: disable=unused-argument
    data = {}
    features_to_count = [
        InfrahubKind.ARTIFACT,
        InfrahubKind.RESOURCEPOOL,
        InfrahubKind.REPOSITORY,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.PROFILE,
        InfrahubKind.PROPOSEDCHANGE,
        InfrahubKind.TRANSFORM,
    ]
    for kind in features_to_count:
        data[kind] = await utils.count_nodes(db=service.database, label=kind)

    return data


@task
async def gather_anonymous_telemetry_data(service: InfrahubServices) -> dict:
    start_time = time.time()

    default_branch = registry.get_branch_from_registry()
    workers = await service.component.list_workers(branch=default_branch.name, schema_hash=False)

    data: dict[str, Any] = {
        "deployment_id": registry.id,
        "execution_time": None,
        "infrahub_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.machine(),
        "workers": {
            "total": len(workers),
            "active": len([w for w in workers if w.active]),
        },
        "branches": {
            "total": len(registry.branch),
        },
        "features": await gather_feature_information(service=service, branch=default_branch),
        "schema": await gather_schema_information(service=service, branch=default_branch),
        "database": await gather_database_information(service=service, branch=default_branch),
    }

    data["execution_time"] = time.time() - start_time

    return data


async def push(
    message: messages.SendTelemetryPush,  # pylint: disable=unused-argument
    service: InfrahubServices,
) -> None:
    service.log.debug("Received telemetry push message...")

    data = await gather_anonymous_telemetry_data(service=service)
    service.log.debug(f"Anonymous usage telemetry gathered in {data['execution_time']} seconds.")

    payload = {
        "kind": TELEMETRY_KIND,
        "payload_format": TELEMETRY_VERSION,
        "data": data,
        "checksum": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(config.SETTINGS.main.telemetry_endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            service.log.debug(f"HTTP exception while pushing anonymous telemetry: {exc}")


@task(retries=5)
async def post_telemetry_data(service: InfrahubServices, url: str, payload: dict[str, Any]) -> None:  # pylint: disable=unused-argument
    """Send the telemetry data to the specified URL, using HTTP POST."""
    async with httpx.AsyncClient() as client:
        response = await client.post(url=url, json=payload)
        response.raise_for_status()


@flow
async def send_telemetry_push() -> None:
    service = services.service

    log = get_run_logger()
    log.info(f"Pushing anonymous telemetry data to {config.SETTINGS.main.telemetry_endpoint}...")

    data = await gather_anonymous_telemetry_data(service=service)
    log.info(f"Anonymous usage telemetry gathered in {data['execution_time']} seconds. | {data}")

    payload = {
        "kind": TELEMETRY_KIND,
        "payload_format": TELEMETRY_VERSION,
        "data": data,
        "checksum": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
    }

    await post_telemetry_data(service=service, url=config.SETTINGS.main.telemetry_endpoint, payload=payload)
