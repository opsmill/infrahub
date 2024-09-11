from __future__ import annotations

import re
from typing import Optional, Union

import pendulum
from pendulum.datetime import DateTime

REGEX_MAPPING = {
    "seconds": r"(\d+)(s|sec|second|seconds)",
    "minutes": r"(\d+)(m|min|minute|minutes)",
    "hours": r"(\d+)(h|hour|hours)",
}


class TimestampFormatError(ValueError): ...


class Timestamp:
    def __init__(self, value: Optional[Union[str, DateTime, Timestamp]] = None):
        if value and isinstance(value, DateTime):
            self.obj = value
        elif value and isinstance(value, self.__class__):
            self.obj = value.obj
        elif isinstance(value, str):
            self.obj = self._parse_string(value)
        else:
            self.obj = DateTime.now(tz="UTC")

    @classmethod
    def _parse_string(cls, value: str) -> DateTime:
        try:
            parsed_date = pendulum.parse(value)
            if isinstance(parsed_date, DateTime):
                return parsed_date
        except (pendulum.parsing.exceptions.ParserError, ValueError):
            pass

        params = {}
        for key, regex in REGEX_MAPPING.items():
            match = re.search(regex, value)
            if match:
                params[key] = int(match.group(1))

        if not params:
            raise TimestampFormatError(f"Invalid time format for {value}")

        return DateTime.now(tz="UTC").subtract(**params)

    def __repr__(self) -> str:
        return f"Timestamp: {self.to_string()}"

    def to_string(self, with_z: bool = True) -> str:
        iso8601_string = self.obj.to_iso8601_string()
        if not with_z and iso8601_string[-1] == "Z":
            iso8601_string = iso8601_string[:-1] + "+00:00"
        return iso8601_string

    def to_timestamp(self) -> int:
        return self.obj.int_timestamp

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.obj == other.obj

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.obj < other.obj

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.obj > other.obj

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.obj <= other.obj

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.obj >= other.obj

    def __hash__(self) -> int:
        return hash(self.to_string())

    def add_delta(self, hours: int = 0, minutes: int = 0, seconds: int = 0, microseconds: int = 0) -> Timestamp:
        time = self.obj.add(hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)
        return Timestamp(time)
