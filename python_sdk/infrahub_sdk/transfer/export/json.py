from pathlib import Path
from typing import List

import ujson

from infrahub_sdk.node import InfrahubNode

from ..exceptions import FileAlreadyExistsError
from .interface import ExporterInterface


class LineDelimitedJSONExporter(ExporterInterface):
    def __init__(self, destination_directory: Path):
        self.destination_directory = destination_directory

    async def export(self, nodes: List[InfrahubNode]) -> None:
        node_file = self.destination_directory / Path("nodes.json")
        if node_file.exists():
            raise FileAlreadyExistsError(f"{node_file.absolute()} already exists")
        json_lines = [ujson.dumps({"kind": n.get_kind(), "graphql": n.get_raw_graphql_data()}) for n in nodes]
        file_content = "\n".join(json_lines)

        if not self.destination_directory.exists():
            self.destination_directory.mkdir()
        node_file.touch()
        node_file.write_text(file_content)
