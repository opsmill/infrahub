from collections import defaultdict

from infrahub_sdk.checks import InfrahubCheck


class InfrahubCheckBackboneLinkRedundancy(InfrahubCheck):
    query = "check_backbone_link_redundancy"

    def validate(self, data):
        site_id_by_name = {}

        backbone_links_per_site = defaultdict(lambda: defaultdict(int))

        if data["InfraCircuit"]["edges"]:
            circuits = data["InfraCircuit"]["edges"]

            for circuit in circuits:
                circuit_node = circuit["node"]
                circuit_status = circuit_node["status"]["value"]

                if circuit_node["endpoints"]["edges"]:
                    endpoints = circuit_node["endpoints"]["edges"]

                    for endpoint in endpoints:
                        endpoint_node = endpoint["node"]
                        site_name = endpoint_node["site"]["node"]["name"]["value"]

                        site_node = endpoint_node["site"]["node"]
                        site_id_by_name[site_name] = site_node["id"]
                        backbone_links_per_site[site_name]["total"] += 1

                        if endpoint_node["connected_endpoint"]:
                            connected_endpoint_node = endpoint_node["connected_endpoint"]["node"]
                            if connected_endpoint_node:
                                if connected_endpoint_node["enabled"]["value"] and circuit_status == "active":
                                    backbone_links_per_site[site_name]["operational"] += 1

            for site_name, site in backbone_links_per_site.items():
                if site.get("operational", 0) / site["total"] < 0.6:
                    self.log_error(
                        message=f"{site_name} has less than 60% of backbone circuit operational ({site.get('operational', 0)}/{site['total']})",
                        object_id=site_id_by_name[site_name],
                        object_type="site",
                    )
