from __future__ import annotations

from typing import TYPE_CHECKING

import infrahub.config as config

from . import get_broker

if TYPE_CHECKING:
    from aio_pika.abc import AbstractExchange


async def get_event_exchange(channel=None) -> AbstractExchange:
    """Return the event exchange initialized as TOPIC."""
    if not channel:
        broker = await get_broker()
        channel = await broker.channel()

    exchange_name = f"{config.SETTINGS.broker.namespace}.events"
    return await channel.get_exchange(name=exchange_name)
