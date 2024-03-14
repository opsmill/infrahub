from collections import defaultdict

from infrahub_sdk.checks import InfrahubCheck


class InfrahubCheckBackboneLinkRedundancy(InfrahubCheck):
    query = "check_backbone_link_redundancy"

    def validate(self, data: dict) -> None:
        site_id_by_name = {}

        backbone_links_per_site: defaultdict = defaultdict(lambda: defaultdict(int))

        for circuit in data["InfraCircuit"]["edges"]:
            status = circuit["node"]["status"]["value"]

            for endpoint in circuit["node"]["endpoints"]["edges"]:
                site_name = endpoint["node"]["site"]["node"]["name"]["value"]
                site_id_by_name[site_name] = endpoint["node"]["site"]["node"]["id"]
                backbone_links_per_site[site_name]["total"] += 1
                if endpoint["node"]["connected_endpoint"]["node"]["enabled"]["value"] and status == "active":
                    backbone_links_per_site[site_name]["operational"] += 1

        for site_name, site in backbone_links_per_site.items():
            if site.get("operational", 0) / site["total"] < 0.6:
                self.log_error(
                    message=f"{site_name} has less than 60% of backbone circuit operational ({site.get('operational', 0)}/{site['total']})",
                    object_id=site_id_by_name[site_name],
                    object_type="site",
                )
