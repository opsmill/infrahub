from __future__ import annotations

from typing import Any

from pendulum.datetime import DateTime

from infrahub_client import Timestamp as BaseTimestamp


class Timestamp(BaseTimestamp):
    async def to_graphql(self, *args: Any, **kwargs: Any) -> DateTime:  # pylint: disable=unused-argument
        return self.obj
