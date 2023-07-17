from __future__ import annotations

import os
import random
import socket
import time
from typing import TYPE_CHECKING, Optional

from infrahub_client.utils import base36encode

if TYPE_CHECKING:
    from typing_extensions import Self

BASE = 36
DIVISOR = BASE - 1
CHARACTERS = list("0123456789abcdefghijklmnopqrstuvwxyz")[:BASE]

# Code inspired from https://github.com/isaacharrisholt/uuidt


class UUIDT:
    def __init__(self, namespace: str, timestamp: int, hostname: str, random_chars: str):
        self.namespace = namespace
        self.timestamp = timestamp
        self.hostname = hostname
        self.random_chars = random_chars

    def __str__(self) -> str:
        hostname_enc = sum(self.hostname.encode("utf-8"))
        namespace_enc = sum(self.namespace.encode("utf-8"))

        timestamp_str = base36encode(number=self.timestamp).lower()
        hostname_str = base36encode(number=hostname_enc).lower()
        namespace_str = base36encode(number=namespace_enc).lower()

        return f"{timestamp_str[:8]}-{timestamp_str[8:]}-{hostname_str:0>4}-" f"{namespace_str:0>4}-{self.random_chars}"

    @classmethod
    def new(cls, namespace: Optional[str] = None) -> Self:
        namespace = namespace or os.path.abspath(os.path.dirname(__file__))
        timestamp = time.time_ns()
        hostname = socket.gethostname()
        random_chars = "".join(random.choices(CHARACTERS, k=4))

        return cls(namespace, timestamp, hostname, random_chars)
