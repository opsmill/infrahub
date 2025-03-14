import os
from collections import defaultdict

from infrahub_sdk import Config, InfrahubClientSync


def dedup_ip_addresses() -> None:
    internal_address = os.getenv("INFRAHUB_INTERNAL_ADDRESS")
    client = InfrahubClientSync(config=Config(address=internal_address, retry_on_failure=True))

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
    dedup_ip_addresses()
