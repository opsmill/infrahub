from typing import Any

import infrahub_ctl.config as config
from infrahub_client import InfrahubClient, InfrahubClientSync


async def initialize_client(**kwargs: Any) -> InfrahubClient:
    client_config = {}

    if config.SETTINGS.api_token:
        client_config["api_token"] = config.SETTINGS.api_token

    client = await InfrahubClient.init(
        address=config.SETTINGS.server_address, config=client_config or None, insert_tracker=True, **kwargs
    )

    return client


def initialize_client_sync(**kwargs: Any) -> InfrahubClientSync:
    client_config = {}

    if config.SETTINGS.api_token:
        client_config["api_token"] = config.SETTINGS.api_token

    client = InfrahubClientSync.init(
        address=config.SETTINGS.server_address, config=client_config or None, insert_tracker=True, **kwargs
    )

    return client
