from typing import Any, Optional

from infrahub_sdk import InfrahubClient, InfrahubClientSync
from infrahub_sdk.config import Config
from infrahub_sdk.ctl import config


async def initialize_client(
    branch: Optional[str] = None, identifier: Optional[str] = None, timeout: Optional[int] = None, **kwargs: Any
) -> InfrahubClient:
    client_config = {}

    if config.SETTINGS.active.api_token:
        client_config["api_token"] = config.SETTINGS.active.api_token

    if timeout:
        client_config["timeout"] = timeout

    if branch:
        client_config["default_branch"] = branch

    client = await InfrahubClient.init(
        address=config.SETTINGS.active.server_address,
        config=Config(**client_config),
        insert_tracker=True,
        identifier=identifier,
        **kwargs,
    )

    return client


def initialize_client_sync(
    branch: Optional[str] = None, identifier: Optional[str] = None, timeout: Optional[int] = None, **kwargs: Any
) -> InfrahubClientSync:
    client_config = {}

    if config.SETTINGS.active.api_token:
        client_config["api_token"] = config.SETTINGS.active.api_token

    if timeout:
        client_config["timeout"] = timeout

    if branch:
        client_config["default_branch"] = branch

    client = InfrahubClientSync.init(
        address=config.SETTINGS.active.server_address,
        config=Config(**client_config),
        insert_tracker=True,
        identifier=identifier,
        **kwargs,
    )

    return client
