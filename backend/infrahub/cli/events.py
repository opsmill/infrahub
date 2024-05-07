import asyncio

import typer
import ujson
from aio_pika.abc import AbstractIncomingMessage
from infrahub_sdk.async_typer import AsyncTyper
from rich import print as rprint

from infrahub import config
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus

app = AsyncTyper()


async def print_event(event: AbstractIncomingMessage) -> None:
    message = {"routing_key": event.routing_key, "message": ujson.loads(event.body)}
    rprint(message)


@app.command()
async def listen(
    topic: str = "#", config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")
) -> None:
    """Listen to event in the Events bus and print them."""
    config.load_and_exit(config_file)
    broker = RabbitMQMessageBus()
    service = InfrahubServices()
    await broker.initialize(service=service)

    queue = await broker.channel.declare_queue(exclusive=True)
    exchange_name = f"{config.SETTINGS.broker.namespace}.events"
    exchange = await broker.channel.get_exchange(name=exchange_name)
    await queue.consume(print_event, no_ack=True)

    await queue.bind(exchange, routing_key=topic)
    print(f" Waiting for events matching the topic `{topic}`. To exit press CTRL+C")
    await asyncio.Future()
