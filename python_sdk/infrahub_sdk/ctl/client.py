from typing import Any

from infrahub_sdk import InfrahubClient, InfrahubClientSync
from infrahub_sdk.config import Config
from infrahub_sdk.ctl import config


async def initialize_client(**kwargs: Any) -> InfrahubClient:
    client_config = {}

    if config.SETTINGS.api_token:
        client_config["api_token"] = config.SETTINGS.api_token

    timeout = kwargs.pop("timeout", None)
    if timeout:
        client_config["timeout"] = timeout

    context_identifier = kwargs.pop("context_identifier", None)

    client = await InfrahubClient.init(
        address=config.SETTINGS.server_address,
        config=Config(**client_config),
        insert_tracker=True,
        context_identifier=context_identifier,
        **kwargs,
    )

    return client


def initialize_client_sync(**kwargs: Any) -> InfrahubClientSync:
    client_config = {}

    if config.SETTINGS.api_token:
        client_config["api_token"] = config.SETTINGS.api_token

    timeout = kwargs.pop("timeout", None)
    if timeout:
        client_config["timeout"] = timeout

    context_identifier = kwargs.pop("context_identifier", None)

    client = InfrahubClientSync.init(
        address=config.SETTINGS.server_address,
        config=Config(**client_config),
        insert_tracker=True,
        context_identifier=context_identifier,
        **kwargs,
    )

    return client
