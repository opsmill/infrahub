import typer
import uvicorn

import json

import asyncio
from asyncio import run as aiorun

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message, connect
from aio_pika.abc import AbstractIncomingMessage

import infrahub.config as config
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import get_event_exchange, EventType, Event

app = typer.Typer()

from rich import print as rprint

async def print_event(event: AbstractIncomingMessage) -> None:
    rprint(event)
    rprint(event.body)

async def _listen(config_file):

    config.load_and_exit(config_file)

    connection = await get_broker()

    async with connection:

        # Creating a channel
        channel = await connection.channel()

        exchange = await get_event_exchange(channel)

        # Declaring & Binding queue
        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange)

        await queue.consume(print_event, no_ack=True)

        print(" [*] Waiting for events. To exit press CTRL+C")
        await asyncio.Future()


async def _generate(type: EventType, message: str, config_file: str):

    config.load_and_exit(config_file)

    exchange = await get_event_exchange()

    message = Event(
        type=type,
        body=json.dumps({"message": message}).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
    )

    await exchange.publish(message, routing_key=config.SETTINGS.broker.namespace)

@app.command()
def listen(config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):
    """Listen to event in the Events bus and print them."""
    aiorun(_listen(config_file=config_file))

@app.command()
def generate(type: EventType, message: str = "Test Event", config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG")):
    aiorun(_generate(type, message, config_file=config_file))
