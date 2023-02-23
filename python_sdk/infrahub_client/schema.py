from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_client.models import SchemaRoot
from infrahub_client.queries import QUERY_SCHEMA

if TYPE_CHECKING:
    from infrahub_client import InfrahubClient


class InfrahubSchema:
    def __init__(self, client: InfrahubClient):
        self.client = client
        self.cache = {}

    def validate(self, data):
        SchemaRoot(**data)
        return True

    def get(self):
        return self.client.execute_graphql(query=QUERY_SCHEMA)
