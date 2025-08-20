import os
from collections import defaultdict
from pathlib import Path

from infrahub_sdk import Config, InfrahubClientSync
from infrahub_sdk.yaml import SchemaFile


def load_patch_schemas(client: InfrahubClientSync) -> None:
    schema_path = Path(__file__).resolve().parent / "IPAddress_unique_patch.yml"
    schemas_data = SchemaFile.load_from_disk(paths=[schema_path])
    branches = client.branch.all()
    for branch in branches:
        response = client.schema.load(schemas=[item.content for item in schemas_data], branch=branch)
        assert len(response.errors) == 0


def dedup_ip_addresses(client: InfrahubClientSync) -> None:
    # Assumes load-infra-data has been run on main branch.
    nodes_addresses = client.all(kind="IpamIPAddress")
    address_values_to_nodes = defaultdict(list)
    for node_address in nodes_addresses:
        address_values_to_nodes[node_address.address.value].append(node_address)

    nb_deleted = 0
    for nodes in address_values_to_nodes.values():
        if len(nodes) > 1:
            for node in nodes[1:]:
                node.delete()
                nb_deleted += 1
    print(f"Deleted {nb_deleted} duplicated IpamIPAddress.")


if __name__ == "__main__":
    internal_address = os.getenv("INFRAHUB_INTERNAL_ADDRESS")
    client = InfrahubClientSync(config=Config(address=internal_address, retry_on_failure=True))

    dedup_ip_addresses(client)
    load_patch_schemas(client)
