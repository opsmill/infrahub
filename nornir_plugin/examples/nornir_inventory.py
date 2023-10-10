from nornir import InitNornir
from nornir.core.plugins.inventory import InventoryPluginRegister
from nornir_infrahub.plugins.inventory.infrahub import InfrahubInventory


def main():
    InventoryPluginRegister.register("InfrahubInventory", InfrahubInventory)
    nr = InitNornir(
        inventory={
            "plugin": "InfrahubInventory",
            "options": {
                "address": "http://localhost:8000",
                "token": "06438eb2-8019-4776-878c-0941b1f1d1ec",
                # defines the Infrahub Node kind that will mapped to Nornir Hosts
                "host_node": {
                    "kind": "InfraDevice"
                },
                # maps a Nornir Host property to an InfraNode attributes or relation
                # name is the name of the Nornir Host property we want to map
                # mapping is the attribute or relation of the Node from which we have to extract the value
                "schema_mappings": [
                    {
                        "name": "hostname",
                        "mapping": "primary_address.address",
                    },
                    {
                        "name": "platform",
                        "mapping": "platform.nornir_platform",
                    },
                ],
                # create Nornir groups from InfraNode attributesor relations
                # groups is created as attribute__value `site__jfk1`
                "group_mappings": [
                    "site.name"
                ],
                "group_file": "dummy.yml"
            },
        }
    )
    print(nr.inventory.hosts.keys())
    print(nr.inventory.groups.keys())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
