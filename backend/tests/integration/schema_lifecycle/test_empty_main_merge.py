from typing import Any

from infrahub.proposed_change.constants import ProposedChangeState
import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA, LOCATION_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

PROPOSED_CHANGE_CREATE = """
mutation ProposedChange(
  $name: String!,
  $source_branch: String!,
  $destination_branch: String!,
	) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source_branch},
      destination_branch: {value: $destination_branch}
    }
  ) {
    object {
      id
    }
  }
}
"""

PROPOSED_CHANGE_UPDATE = """
mutation UpdateProposedChange(
    $proposed_change_id: String!,
    $state: String
  ) {
  CoreProposedChangeUpdate(data:
    {
      id: $proposed_change_id,
      state: {value: $state}
    }
  ) {
    ok
  }
}
"""

DIFF_TREE_QUERY = """
query GetDiffTree($branch: String){
    DiffTree (branch: $branch, filters: {status: {excludes: UNCHANGED}}) {
        base_branch
        diff_branch
        from_time
        to_time
        num_added
        num_removed
        num_updated
        num_conflicts
        num_untracked_base_changes
        num_untracked_diff_changes
        nodes {
            uuid
            kind
            label
            last_changed_at
            status
            parent {
              uuid
              kind
              relationship_name
            }
            contains_conflict
            num_added
            num_removed
            num_updated
            num_conflicts
            attributes {
                name
                last_changed_at
                status
                num_added
                num_removed
                num_updated
                num_conflicts
                contains_conflict
                conflict {
                    uuid
                    base_branch_action
                    base_branch_value
                    base_branch_changed_at
                    base_branch_label
                    diff_branch_action
                    diff_branch_value
                    diff_branch_changed_at
                    diff_branch_label
                    selected_branch
                }
                properties {
                    property_type
                    last_changed_at
                    previous_value
                    new_value
                    previous_label
                    new_label
                    status
                    conflict {
                        uuid
                        base_branch_action
                        base_branch_value
                        base_branch_changed_at
                        base_branch_label
                        diff_branch_action
                        diff_branch_value
                        diff_branch_changed_at
                        diff_branch_label
                        selected_branch
                    }
                }
            }
            relationships {
                name
                last_changed_at
                status
                cardinality
                contains_conflict
                elements {
                    status
                    peer_id
                    last_changed_at
                    contains_conflict
                    conflict {
                        uuid
                        base_branch_action
                        base_branch_changed_at
                        base_branch_value
                        base_branch_label
                        diff_branch_action
                        diff_branch_value
                        diff_branch_changed_at
                        diff_branch_label
                        selected_branch
                    }
                    properties {
                        property_type
                        last_changed_at
                        previous_value
                        new_value
                        previous_label
                        new_label
                        status
                        conflict {
                            uuid
                            base_branch_action
                            base_branch_value
                            base_branch_changed_at
                            base_branch_label
                            diff_branch_action
                            diff_branch_value
                            diff_branch_changed_at
                            diff_branch_label
                            selected_branch
                        }
                    }
                }
            }
        }
    }
}
"""


class TestProposedChangeOnEmptyMain(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def branch(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch")

    @pytest.fixture(scope="class")
    async def branch_schema(self, db: InfrahubDatabase, branch: Branch) -> None:
        combined_schema = DEVICE_SCHEMA.model_copy(deep=True)
        combined_schema.nodes.extend(LOCATION_SCHEMA.nodes)
        combined_schema.generics.extend(LOCATION_SCHEMA.generics)
        await load_schema(db=db, schema=combined_schema, branch_name=branch.name, update_db=True)

    @pytest.fixture(scope="class")
    async def branch_data(self, db: InfrahubDatabase, branch: Branch, branch_schema: None) -> dict[str, Node]:
        node_map: dict[str, Node] = {}

        # load data using template
        device_template: Node = await Node.init(schema=f"Template{TestKind.DEVICE}", db=db, branch=branch)
        await device_template.new(
            db=db, template_name="MX204 Router", manufacturer="Juniper", height=1, weight=6, airflow="Front to rear"
        )
        await device_template.save(db=db)
        node_map["device_template"] = device_template

        device: Node = await Node.init(db=db, schema=TestKind.DEVICE, branch=branch)
        await device.new(db=db, name="device-01", object_template={"id": device_template.id})
        await device.save(db=db)
        node_map["device"] = device

        # load data using profile
        interface = await Node.init(db=db, branch=branch, schema=TestKind.PHYSICAL_INTERFACE)
        await interface.new(db=db, name="interface1", device=device, phys_type="SFP (1GE)")
        await interface.save(db=db)
        node_map["interface"] = interface
        sfp_profile = await Node.init(db=db, branch=branch, schema=f"Profile{TestKind.SFP}")
        await sfp_profile.new(db=db, profile_name="sfp_part_number", part_number="12345")
        await sfp_profile.save(db=db)
        node_map["sfp_profile"] = sfp_profile
        sfp = await Node.init(db=db, branch=branch, schema=TestKind.SFP)
        await sfp.new(
            db=db,
            name="sfp1",
            interface=interface,
            phys_type="SFP (1GE)",
            serial_number="54321",
            profiles=[sfp_profile],
        )
        await sfp.save(db=db)
        node_map["sfp"] = sfp

        # load hierarchical data
        continent_map = {"antartica": ["mcmurdough", "south_pole"], "pacific": ["midway", "bikini"]}
        for continent, countries in continent_map.items():
            continent_node = await Node.init(db=db, branch=branch, schema="TestingContinent")
            await continent_node.new(db=db, name=continent, shortname=continent[:3].upper())
            await continent_node.save(db=db)
            node_map[continent] = continent_node

            for country in countries:
                country_node = await Node.init(db=db, branch=branch, schema="TestingCountry")
                await country_node.new(db=db, name=country, shortname=country[:3].upper(), parent=continent)
                await country_node.save(db=db)
                node_map[f"{continent}-{country}"] = country_node

                site_name = f"{continent}-{country}-r1"
                site_node = await Node.init(db=db, branch=branch, schema="TestingSite")
                await site_node.new(
                    db=db, name=site_name, shortname=f"{continent[:2]}-{country[:2]}-r1", parent=country
                )
                await site_node.save(db=db)
                node_map[site_name] = site_node

        return node_map

    @pytest.fixture(scope="class")
    async def proposed_change_id(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        branch: Branch,
        branch_data: dict[str, Node],
    ) -> str:
        result = await client.execute_graphql(
            query=PROPOSED_CHANGE_CREATE,
            variables={
                "name": "pc1",
                "source_branch": branch.name,
                "destination_branch": default_branch.name,
            },
        )
        proposed_change_id = result["CoreProposedChangeCreate"]["object"]["id"]
        return proposed_change_id

    def _get_diff_node_attribute_values(self, diff_node: dict[str, Any]) -> dict[str, Any]:
        diff_attribute_values_by_name = {}
        for diff_attribute in diff_node["attributes"]:
            name = diff_attribute["name"]
            for diff_property in diff_attribute["properties"]:
                if diff_property["property_type"] == "HAS_VALUE":
                    diff_attribute_values_by_name[name] = diff_property["new_value"]
        return diff_attribute_values_by_name

    async def test_retrieve_diff(
        self, client: InfrahubClient, default_branch: Branch, branch: Branch, branch_data: dict[str, Node], proposed_change_id: str
    ):
        result = await client.execute_graphql(
            query=DIFF_TREE_QUERY,
            variables={"branch": branch.name},
        )

        assert result["DiffTree"]
        diff_nodes_by_uuid = {n["uuid"]: n for n in result["DiffTree"]["nodes"]}
        branch_data_uuids = {n.id: n for n in branch_data.values()}
        assert set(branch_data_uuids.keys()) <= set(diff_nodes_by_uuid.keys())

        # verify device created with template
        device_uuid = branch_data["device"].id
        device_attr_values = self._get_diff_node_attribute_values(diff_nodes_by_uuid[device_uuid])
        assert device_attr_values == {
            "name": "device-01",
            "manufacturer": "Juniper",
            "height": "1",
            "weight": "6",
            "part_number": "NULL",
            "airflow": "Front to rear",
        }

        # verify sfp created with profile
        sfp_uuid = branch_data["sfp"].id
        sfp_attr_values = self._get_diff_node_attribute_values(diff_nodes_by_uuid[sfp_uuid])
        assert sfp_attr_values == {
            "phys_type": "SFP (1GE)",
            "serial_number": "54321",
            # no part number here because it only exists in the profile at the database level
            "part_number": "NULL",
        }

        # verify hierarchy data
        continent_map = {
            "antartica": ["antartica-mcmurdough", "antartica-south_pole"],
            "pacific": ["pacific-midway", "pacific-bikini"],
        }
        for continent_name, country_names in continent_map.items():
            continent_uuid = branch_data[continent_name].id
            continent_node = diff_nodes_by_uuid[continent_uuid]
            assert continent_node["parent"] is None

            for country_name in country_names:
                country_uuid = branch_data[country_name].id
                country_node = diff_nodes_by_uuid[country_uuid]
                assert country_node["parent"] == {
                    "uuid": continent_uuid,
                    "kind": TestKind.CONTINENT,
                    "relationship_name": "children",
                }

                site_name = f"{country_name}-r1"
                site_uuid = branch_data[site_name].id
                site_node = diff_nodes_by_uuid[site_uuid]
                assert site_node["parent"] == {
                    "uuid": country_uuid,
                    "kind": TestKind.COUNTRY,
                    "relationship_name": "children",
                }

    async def test_merge_proposed_change(self, client: InfrahubClient, default_branch: Branch, branch: Branch, branch_data: dict[str, Node], proposed_change_id: str):
        result = await client.execute_graphql(
            query=PROPOSED_CHANGE_UPDATE,
            variables={
                "proposed_change_id": proposed_change_id,
                "state": ProposedChangeState.MERGED.value,
            },
        )
        assert result["CoreProposedChangeUpdate"]["ok"]


# TODO: verify schema/data on main
