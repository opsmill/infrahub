from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testcontainers.core.container import DockerContainer


@dataclass
class GogsServer:
    base_url: str
    port: str
    token: str
    admin: str
    password: str
    container: DockerContainer
