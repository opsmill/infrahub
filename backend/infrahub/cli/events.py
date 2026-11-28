import asyncio

import typer
import ujson
from infrahub_sdk.async_typer import AsyncTyper
from rich import print as rprint

from infrahub import config
from infrahub.components import ComponentType
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus

app = AsyncTyper()


async def print_event(routing_key: str, body: bytes) -> None:
    message = {"routing_key": routing_key, "message": ujson.loads(body)}
    rprint(message)


@app.command()
async def listen(
    topic: str = "#", config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")
) -> None:
    """Listen to event in the Events bus and print them."""
    config.load_and_exit(config_file)

    component_type = ComponentType.NONE
    broker = await InfrahubMessageBus.new_from_driver(
        component_type=component_type, driver=config.SETTINGS.broker.driver
    )
    _ = await InfrahubServices.new(message_bus=broker, component_type=component_type)

    await broker.listen(topic=topic, listener=print_event)
    print(f" Waiting for events matching the topic `{topic}`. To exit press CTRL+C")
    await asyncio.Future()
