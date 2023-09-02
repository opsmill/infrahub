from nornir import InitNornir

def main():
    nr = InitNornir(
        inventory={
            "plugin": "InfrahubInventory",
            "options": {
                "address": "http://localhost:8000",
                "token": "06438eb2-8019-4776-878c-0941b1f1d1ec",
                "host_node": {
                    "kind": "InfraDevice"
                },
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
                "group_mappings": [
                    "site.name"
                ]
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
