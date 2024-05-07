import hashlib
import json
import time
from typing import Dict

import httpx

from infrahub import __version__, config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20240514"


async def gather_telemetry_data(service: InfrahubServices) -> Dict:
    workers = await service.component.list_workers(branch="main", schema_hash=False)

    data = {
        "deployment_id": registry.id,
        "version": __version__,
        "total_workers": len(workers),
        "active_workers": len([w for w in workers if w.active]),
        "active_branches": len(registry.branch),
    }

    for kind in dir(InfrahubKind):
        if "__" not in kind:
            data[f"count_{kind}"] = await NodeManager.count(
                schema=getattr(InfrahubKind, kind), db=service.database, branch="main"
            )

    return data


async def push(
    message: messages.SendTelemetryPush,  # pylint: disable=unused-argument
    service: InfrahubServices,
) -> None:
    service.log.debug("Received telemetry push message...")
    start_time = time.time()

    data = await gather_telemetry_data(service)

    service.log.debug(f"Usage telemetry gathered in {time.time() - start_time} seconds.")

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
            service.log.debug(f"HTTP exception while pushing telemetry: {exc}")
