from pathlib import Path

import pyarrow.json as pa_json
import ujson

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.node import InfrahubNode

from .interface import ImporterInterface


class LineDelimitedJSONImporter(ImporterInterface):
    def __init__(self, client: InfrahubClient):
        self.client = client

    async def import_data(
        self,
        import_directory: Path,
        branch: str,
    ) -> None:
        node_file = import_directory / Path("nodes.json")
        if not node_file.exists():
            raise FileNotFoundError(f"{node_file.absolute()} does not exist")
        table = pa_json.read_json(node_file.absolute())

        for graphql_data in table.column("graphql_json"):
            node = await InfrahubNode.from_graphql(self.client, branch, ujson.loads(str(graphql_data)))
            await node.save()
