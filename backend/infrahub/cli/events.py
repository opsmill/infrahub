import asyncio
import json
from asyncio import run as aiorun

import typer
from aio_pika.abc import AbstractIncomingMessage
from rich import print as rprint

from infrahub import config
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import get_event_exchange

app = typer.Typer()


async def print_event(event: AbstractIncomingMessage) -> None:
    message = {"routing_key": event.routing_key, "message": json.loads(event.body)}
    rprint(message)


async def _listen(topic: str, config_file: str) -> None:
    config.load_and_exit(config_file)

    connection = await get_broker()

    async with connection:
        # Creating a channel
        channel = await connection.channel()

        exchange = await get_event_exchange(channel)

        # Declaring & Binding queue
        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange, routing_key=topic)

        await queue.consume(callback=print_event, no_ack=True)

        print(f" Waiting for events matching the topic `{topic}`. To exit press CTRL+C")
        await asyncio.Future()


@app.command()
def listen(topic: str = "#", config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")) -> None:
    """Listen to event in the Events bus and print them."""
    aiorun(_listen(topic=topic, config_file=config_file))
