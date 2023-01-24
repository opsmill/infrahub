from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

import pendulum
from pendulum.datetime import DateTime

if TYPE_CHECKING:
    from neo4j import AsyncSession

REGEX_MAPPING = {
    "seconds": r"(\d+)(s|sec|second|seconds)",
    "minutes": r"(\d+)(m|min|minute|minutes)",
    "hours": r"(\d+)(h|hour|hours)",
}


class Timestamp:
    def __init__(self, value=None):

        if value and isinstance(value, DateTime):
            self.obj = value
        elif value and isinstance(value, self.__class__):
            self.obj = value.obj
        elif isinstance(value, str):
            self.obj = self._parse_string(value)
        else:
            self.obj = DateTime.now(tz="UTC")

    @classmethod
    def _parse_string(cls, value):

        try:
            return pendulum.parse(value)
        except pendulum.parsing.exceptions.ParserError:
            pass

        params = {}
        for key, regex in REGEX_MAPPING.items():
            match = re.search(regex, value)
            if match:
                params[key] = int(match.group(1))

        if not params:
            raise ValueError(f"Invalid time format for {value}")

        return DateTime.now(tz="UTC").subtract(**params)

    def __repr__(self) -> str:
        return f"Timestamp: {self.to_string()}"

    def to_string(self):
        return self.obj.to_iso8601_string()

    async def to_graphql(self, session: Optional[AsyncSession] = None):  # pylint: disable=unused-argument
        return self.obj

    def __eq__(self, other):
        return self.obj == other.obj

    def __lt__(self, other):
        return self.obj < other.obj

    def __gt__(self, other):
        return self.obj > other.obj

    def __le__(self, other):
        return self.obj <= other.obj

    def __ge__(self, other):
        return self.obj >= other.obj
