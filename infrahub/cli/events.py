import asyncio
from asyncio import run as aiorun

import typer
from aio_pika import IncomingMessage
from rich import print as rprint

import infrahub.config as config
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.database import get_db
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import (
    InfrahubDataMessage,
    InfrahubMessage,
    MessageType,
    get_event_exchange,
)

app = typer.Typer()


async def print_event(event: IncomingMessage) -> None:
    event = InfrahubMessage.init(event)
    rprint(event)


async def _listen(topic: str, config_file: str):
    config.load_and_exit(config_file)

    connection = await get_broker()

    async with connection:
        # Creating a channel
        channel = await connection.channel()

        exchange = await get_event_exchange(channel)

        # Declaring & Binding queue
        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange, routing_key=topic)

        await queue.consume(print_event, no_ack=True)

        print(f" Waiting for events matching the topic `{topic}`. To exit press CTRL+C")
        await asyncio.Future()


async def _generate(msg_type: MessageType, config_file: str):
    config.load_and_exit(config_file)

    db = await get_db()

    async with db.session(database=config.SETTINGS.database.database) as session:
        await initialization(session=session)
        nodes = await NodeManager.query(session=session, schema="Criticality")

    event = InfrahubDataMessage(action="create", node=nodes[0])
    await event.send()


@app.command()
def listen(topic: str = "#", config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):
    """Listen to event in the Events bus and print them."""
    aiorun(_listen(topic=topic, config_file=config_file))


@app.command()
def generate(msg_type: MessageType, config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):
    aiorun(_generate(msg_type=msg_type, config_file=config_file))
