from __future__ import annotations

import random
import socket
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

from infrahub_sdk.utils import base16encode

BASE = 16
DIVISOR = BASE - 1
CHARACTERS = list("0123456789abcdefghijklmnopqrstuvwxyz")[:BASE]
HOSTNAME = socket.gethostname()
DEFAULT_NAMESPACE = str(Path(__file__).parent.resolve())

# Code inspired from https://github.com/isaacharrisholt/uuidt


def generate_uuid() -> str:
    return str(UUIDT())


def encode_number(number: int, min_length: int) -> str:
    """Encode a number into a base16 string and ensure the result has a minimum size.
    If the initial response produced doesn't match the min requirement,
    random number will be used to fill the gap
    """
    response = base16encode(number=number).lower()
    if len(response) >= min_length:
        return response
    return response + "".join(random.choices(CHARACTERS, k=min_length - len(response)))


class UUIDT:
    def __init__(
        self,
        namespace: Optional[str] = None,
        timestamp: Optional[int] = None,
        hostname: Optional[str] = None,
        random_chars: Optional[str] = None,
    ) -> None:
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.timestamp = timestamp or time.time_ns()
        self.hostname = hostname or HOSTNAME
        self.random_chars = random_chars or "".join(random.choices(CHARACTERS, k=8))

    def __str__(self) -> str:
        hostname_enc = sum(self.hostname.encode("utf-8"))
        namespace_enc = sum(self.namespace.encode("utf-8"))

        timestamp_str = encode_number(number=self.timestamp, min_length=16)
        hostname_str = encode_number(number=hostname_enc, min_length=4)
        namespace_str = encode_number(number=namespace_enc, min_length=4)

        return f"{timestamp_str[:8]}-{timestamp_str[8:12]}-{timestamp_str[-4:]}-{hostname_str[:4]}-{namespace_str[:4]}{self.random_chars[:8]}"

    def short(self) -> str:
        """Return the last 8 digit of the UUID (the most random part)"""
        return str(self)[-8:]

    @classmethod
    def new(cls, namespace: Optional[str] = None) -> UUID:
        return UUID(str(cls(namespace=namespace)))
