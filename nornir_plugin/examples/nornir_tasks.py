from nornir import InitNornir
from nornir.core.plugins.inventory import InventoryPluginRegister
from nornir_infrahub.plugins.inventory.infrahub import InfrahubInventory
from nornir_infrahub.plugins.tasks import (
    generate_artifacts,
    get_artifact,
    regenerate_host_artifact,
)

# from nornir_napalm.plugin.tasks import napalm_configure
from nornir_utils.plugins.functions import print_result


def main():
    InventoryPluginRegister.register("InfrahubInventory", InfrahubInventory)
    nr = InitNornir(
        inventory={
            "plugin": "InfrahubInventory",
            "options": {
                "address": "http://localhost:8000",
                "token": "06438eb2-8019-4776-878c-0941b1f1d1ec",
                # defines the Infrahub Node kind that will mapped to Nornir Hosts
                "host_node": {"kind": "InfraDevice"},
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
                "group_mappings": ["site.name"],
                "group_file": "dummy.yml",
            },
        }
    )

    # generate_artifacts, generates the artifact for all the targets in the Artifact definition
    # we only need to run this task once, per artifact definition
    run_once = nr.filter(name="jfk1-edge1")
    result = run_once.run(task=generate_artifacts, artifact="startup-config", timeout=20)

    for _, v in result.items():
        if v[0].failed:
            return 1

    # retrieves the artifact for all the hosts in the inventory
    result = nr.run(task=get_artifact, artifact="startup-config")
    print_result(result)

    # push the retrieved artifact to a device
    # print_result(run_once.run(task=napalm_configure, configuration=result["jfk1-edge1"][0].result, replace=True))

    # artifacts with content-type application/json get deserialized
    result = nr.run(task=get_artifact, artifact="openconfig-interfaces")
    print_result(result)
    assert isinstance(result["den1-edge1"][0].result, dict)

    # regenerate an artifact for a host
    print_result(nr.run(task=regenerate_host_artifact, artifact="startup-config"))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
