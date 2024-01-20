from __future__ import annotations

from enum import Enum
from typing import List


class MessageTTL(int, Enum):
    """Defines the message TTL in seconds, the values themselves are in milliseconds."""

    FIVE = 5000
    TEN = 10000
    TWENTY = 20000

    @classmethod
    def variations(cls) -> List[MessageTTL]:
        """Return available variations of message time to live."""
        return [cls(cls.__members__[member].value) for member in list(cls.__members__)]


class MessagePriority(int, Enum):
    """Defines the message priority."""

    LOWEST = 1
    LOW = 2
    NORMAL = 3
    HIGH = 4
    HIGEST = 5
