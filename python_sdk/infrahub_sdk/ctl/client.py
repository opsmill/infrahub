from typing import Any, Optional

from infrahub_sdk import InfrahubClient, InfrahubClientSync
from infrahub_sdk.config import Config
from infrahub_sdk.ctl import config


async def initialize_client(
    branch: Optional[str] = None,
    identifier: Optional[str] = None,
    timeout: Optional[int] = None,
    max_concurrent_execution: Optional[int] = None,
    retry_on_failure: Optional[bool] = None,
) -> InfrahubClient:
    return InfrahubClient(
        config=_define_config(
            branch=branch,
            identifier=identifier,
            timeout=timeout,
            max_concurrent_execution=max_concurrent_execution,
            retry_on_failure=retry_on_failure,
        )
    )


def initialize_client_sync(
    branch: Optional[str] = None,
    identifier: Optional[str] = None,
    timeout: Optional[int] = None,
    max_concurrent_execution: Optional[int] = None,
    retry_on_failure: Optional[bool] = None,
) -> InfrahubClientSync:
    return InfrahubClientSync(
        config=_define_config(
            branch=branch,
            identifier=identifier,
            timeout=timeout,
            max_concurrent_execution=max_concurrent_execution,
            retry_on_failure=retry_on_failure,
        )
    )


def _define_config(
    branch: Optional[str] = None,
    identifier: Optional[str] = None,
    timeout: Optional[int] = None,
    max_concurrent_execution: Optional[int] = None,
    retry_on_failure: Optional[bool] = None,
) -> Config:
    client_config: dict[str, Any] = {
        "address": config.SETTINGS.active.server_address,
        "insert_tracker": True,
        "identifier": identifier,
    }

    if config.SETTINGS.active.api_token:
        client_config["api_token"] = config.SETTINGS.active.api_token

    if timeout:
        client_config["timeout"] = timeout

    if max_concurrent_execution is not None:
        client_config["max_concurrent_execution"] = max_concurrent_execution

    if retry_on_failure is not None:
        client_config["retry_on_failure"] = retry_on_failure

    if branch:
        client_config["default_branch"] = branch

    return Config(**client_config)
