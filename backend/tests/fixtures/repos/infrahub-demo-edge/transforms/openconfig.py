from infrahub_sdk.transforms import InfrahubTransform


class OCInterfaces(InfrahubTransform):
    query = "oc_interfaces"
    url = "openconfig/interfaces"

    async def transform(self, data):
        response_payload = {}
        response_payload["openconfig-interfaces:interface"] = []

        for intf in data["InfraDevice"]["edges"][0]["node"]["interfaces"]["edges"]:
            intf_name = intf["node"]["name"]["value"]

            intf_config = {
                "name": intf_name,
                "config": {"enabled": intf["node"]["enabled"]["value"]},
            }

            if intf["node"].get("description", None) and intf["node"]["description"]["value"]:
                intf_config["config"]["description"] = intf["node"]["description"]["value"]

            if intf["node"].get("ip_addresses", None):
                intf_config["subinterfaces"] = {"subinterface": []}

                for idx, ip in enumerate(intf["node"]["ip_addresses"]["edges"]):
                    address, mask = ip["node"]["address"]["value"].split("/")
                    intf_config["subinterfaces"]["subinterface"].append(
                        {
                            "index": idx,
                            "openconfig-if-ip:ipv4": {
                                "addresses": {
                                    "address": [
                                        {
                                            "ip": address,
                                            "config": {
                                                "ip": address,
                                                "prefix-length": mask,
                                            },
                                        }
                                    ]
                                },
                                "config": {"enabled": True},
                            },
                        }
                    )

            response_payload["openconfig-interfaces:interface"].append(intf_config)

        return response_payload


class OCBGPNeighbors(InfrahubTransform):
    query = "oc_bgp_neighbors"
    url = "openconfig/network-instances/network-instance/protocols/protocol/bgp/neighbors"

    async def transform(self, data):
        response_payload = {}

        response_payload["openconfig-bgp:neighbors"] = {"neighbor": []}

        for session in data["InfraBGPSession"]["edges"]:
            neighbor_address = session["node"]["remote_ip"]["node"]["address"]["value"].split("/")[0]
            session_data = {
                "neighbor-address": neighbor_address,
                "config": {"neighbor-address": neighbor_address},
            }

            if session["node"]["peer_group"]:
                session_data["config"]["peer-group"] = session["node"]["peer_group"]["node"]["name"]["value"]

            if session["node"]["remote_as"]:
                session_data["config"]["peer-as"] = session["node"]["remote_as"]["node"]["asn"]["value"]

            if session["node"]["local_as"]:
                session_data["config"]["local-as"] = session["node"]["local_as"]["node"]["asn"]["value"]

            response_payload["openconfig-bgp:neighbors"]["neighbor"].append(session_data)

        return response_payload
