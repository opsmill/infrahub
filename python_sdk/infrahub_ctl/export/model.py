from typing import Dict

from infrahub_sdk.node.model import InfrahubNode


class NodeToExport(InfrahubNode):
    graphql_response: Dict
