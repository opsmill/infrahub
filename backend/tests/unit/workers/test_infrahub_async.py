from typing import Any

import pytest
from prefect import flow

from infrahub.services import InfrahubServices
from infrahub.workers.infrahub_async import inject_service_parameter


@flow
async def flow_with_service(service: InfrahubServices, name: str) -> None: ...


@flow
async def flow_without_service(name: str) -> None: ...


async def test_inject_service_parameter_fills_the_declared_slot() -> None:
    service = await InfrahubServices.new()
    parameters: dict[str, Any] = {"name": "repo-a"}

    inject_service_parameter(func=flow_with_service, parameters=parameters, service=service)

    assert parameters == {"name": "repo-a", "service": service}


@pytest.mark.parametrize("key", ["service", "name"])
async def test_inject_service_parameter_rejects_a_service_already_in_the_payload(key: str) -> None:
    """A service smuggled in under any parameter name is refused, not only under the declared slot."""
    service = await InfrahubServices.new()
    parameters: dict[str, Any] = {"name": "repo-a"} | {key: service}

    with pytest.raises(ValueError, match="should be injected"):
        inject_service_parameter(func=flow_with_service, parameters=parameters, service=service)


async def test_inject_service_parameter_leaves_a_flow_without_the_slot_alone() -> None:
    parameters: dict[str, Any] = {"name": "repo-a"}

    inject_service_parameter(func=flow_without_service, parameters=parameters, service=await InfrahubServices.new())

    assert parameters == {"name": "repo-a"}
