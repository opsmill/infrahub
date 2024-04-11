from typing import Optional

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
    client_config = {"insert_tracker": True, "identifier": identifier}

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

    client = await InfrahubClient.init(
        address=config.SETTINGS.active.server_address,
        config=Config(**client_config),
    )

    return client


def initialize_client_sync(
    branch: Optional[str] = None, identifier: Optional[str] = None, timeout: Optional[int] = None
) -> InfrahubClientSync:
    client_config = {"insert_tracker": True, "identifier": identifier}

    if config.SETTINGS.active.api_token:
        client_config["api_token"] = config.SETTINGS.active.api_token

    if timeout:
        client_config["timeout"] = timeout

    if branch:
        client_config["default_branch"] = branch

    client = InfrahubClientSync.init(
        address=config.SETTINGS.active.server_address,
        config=Config(**client_config),
    )

    return client
