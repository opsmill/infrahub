from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk import Timestamp as BaseTimestamp

if TYPE_CHECKING:
    from pendulum.datetime import DateTime


class Timestamp(BaseTimestamp):
    async def to_graphql(self) -> DateTime:
        return self.obj


def current_timestamp() -> str:
    return Timestamp().to_string()
