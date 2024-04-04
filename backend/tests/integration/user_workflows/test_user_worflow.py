import pendulum
import pytest
from deepdiff import DeepDiff
from fastapi.testclient import TestClient

from infrahub.core.constants import NULL_VALUE
from infrahub.database import InfrahubDatabase
from infrahub.server import app
from infrahub.test_data import dataset01 as ds01

headers = {"Authorization": "Token nelly"}

main_branch = "main"
branch1 = "branch1"
branch2 = "branch2"


QUERY_GET_ALL_DEVICES = """
    query {
        InfraDevice {
            edges {
                node {
                    id
                    name {
                        value
                    }
                }
            }
        }
    }
    """

QUERY_SPINE1_INTF = """
    query($intf_name: String!) {
        InfraDevice(name__value: "spine1") {
            edges {
                node {
                    id
                    name {
                        value
                    }
                    interfaces(name__value: $intf_name) {
                        edges {
                            node {
                                id
                                name {
                                    value
                                }
                                description {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

BRANCH_CREATE = """
    mutation($branch: String!, $isolated: Boolean!) {
        BranchCreate(data: { name: $branch, is_isolated: $isolated }) {
            ok
            object {
                id
                name
            }
        }
    }
    """

BRANCH_MERGE = """
    mutation($branch: String!) {
        BranchMerge(data: { name: $branch }) {
            ok
            object {
                id
                name
            }
        }
    }
    """

BRANCH_REBASE = """
    mutation($branch: String!) {
        BranchRebase(data: { name: $branch }) {
            ok
            object {
                id
                name
            }
        }
    }
    """

INTERFACE_UPDATE = """
    mutation($interface_id: String!, $description: String!) {
        InfraInterfaceL3Update(data: { id: $interface_id, description: { value: $description}}){
            ok
            object {
                name {
                    value
                }
                description {
                    value
                }
            }
        }
    }
"""

INTERFACE_CREATE = """
    mutation($device: String!, $intf_name: String!, $description: String!, $speed: Int!, $role: String!, $status: String!) {
        InfraInterfaceL3Create(data: {
            device: { id: $device },
            name: { value: $intf_name },
            description: { value: $description },
            role: { value: $role },
            speed: { value: $speed },
            status: { value: $status }
        })
        {
            ok
            object {
                name {
                    value
                }
            }
        }
    }
"""


class TestUserWorkflow01:
    @pytest.fixture(scope="class")
    async def client(self):
        client = TestClient(app)
        return client

    @pytest.fixture(scope="class")
    async def dataset01(self, db: InfrahubDatabase, init_db_infra):
        await ds01.load_data(db=db, nbr_devices=2)

    async def test_initialize_state(self):
        pytest.state = {
            "spine1_lo0_id": None,
            "time_start": None,
        }

    async def test_query_all_devices(self, client, init_db_infra, dataset01):
        """
        Query all devices to ensure that we have some data in the database
        and overall that everything is working correctly
        """

        with client:
            response = client.post("/graphql", json={"query": QUERY_GET_ALL_DEVICES}, headers=headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        assert "InfraDevice" in result.keys()
        assert len(result["InfraDevice"]["edges"]) == 2

        # Initialize the start time
        pytest.state["time_start"] = pendulum.now(tz="UTC")

    async def test_query_spine1_loobpack0(self, client, init_db_infra, dataset01):
        """
        Query Loopback0 interface on spine one to ensure that the filters are working properly and to store:
            - the ID of the interface to reuse later
            - The initial value of the description on this interface
        """

        intf_name = "Loopback0"
        with client:
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]["InfraDevice"]["edges"][0]

        intfs = [intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name]
        assert len(intfs) == 1

        pytest.state["spine1_lo0_id"] = intfs[0]["node"]["id"]
        pytest.state["spine1_lo0_description_start"] = intfs[0]["node"]["description"]["value"]

    async def test_query_spine1_ethernet1(self, client, init_db_infra, dataset01):
        """
        Query Ethernet1 to gather its ID
        """
        intf_name = "Ethernet1"
        with client:
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        intfs = [
            intf
            for intf in result["InfraDevice"]["edges"][0]["node"]["interfaces"]["edges"]
            if intf["node"]["name"]["value"] == intf_name
        ]
        assert len(intfs) == 1

        pytest.state["spine1_eth1_id"] = intfs[0]["node"]["id"]
        pytest.state["spine1_eth1_description_start"] = intfs[0]["node"]["description"]["value"]

    async def test_create_first_branch(self, client, integration_helper, init_db_infra, dataset01):
        """
        Create a first Branch from Main
        """

        headers = await integration_helper.admin_headers()

        with client:
            response = client.post(
                "/graphql",
                json={"query": BRANCH_CREATE, "variables": {"branch": branch1, "isolated": False}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["BranchCreate"]["ok"]

    async def test_update_intf_description_branch1(
        self,
        client,
        init_db_infra,
        dataset01,
        integration_helper,
    ):
        """
        Update the description of the interface in the new branch and validate that its being properly updated
        """
        headers = await integration_helper.admin_headers()

        new_description = f"New description in {branch1}"

        assert pytest.state["spine1_lo0_id"]

        intf_name = "Loopback0"
        with client:
            # Update the description in BRANCH1
            variables = {"interface_id": pytest.state["spine1_lo0_id"], "description": new_description}
            response = client.post(
                f"/graphql/{branch1}", json={"query": INTERFACE_UPDATE, "variables": variables}, headers=headers
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["InfraInterfaceL3Update"]["ok"]

            # Query the new description in BRANCH1 to check its value
            response = client.post(
                f"/graphql/{branch1}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]["InfraDevice"]["edges"][0]

        intfs = [intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name]
        assert len(intfs) == 1

        assert intfs[0]["node"]["description"]["value"] == new_description

        pytest.state["time_after_intf_update_branch1"] = pendulum.now("UTC").to_iso8601_string()

    async def test_update_intf_description_main(self, client, init_db_infra, dataset01, integration_helper):
        """
        Update the description of the interface Ethernet1 in the main branch and validate that its being properly updated
        """
        headers = await integration_helper.admin_headers()
        new_description = f"New description in {main_branch}"

        assert pytest.state["spine1_eth1_id"]

        intf_name = "Ethernet1"
        with client:
            # Update the description in MAIN
            variables = {"interface_id": pytest.state["spine1_eth1_id"], "description": new_description}
            response = client.post(
                "/graphql", json={"query": INTERFACE_UPDATE, "variables": variables}, headers=headers
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["InfraInterfaceL3Update"]["ok"]

            # Query the new description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]["InfraDevice"]["edges"][0]

        intfs = [intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name]
        assert len(intfs) == 1

        assert intfs[0]["node"]["description"]["value"] == new_description

    async def test_validate_diff_after_description_update(self, client, dataset01, integration_helper):
        headers = await integration_helper.admin_headers()

        with client:
            response = client.get(f"/api/diff/data?branch={branch1}&branch_only=false", headers=headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json() is not None
        result = response.json()

        expected_result_branch1 = {
            "action": {"branch1": "updated"},
            "display_label": {"branch1": "Loopback0"},
            "elements": {
                "description": {
                    "change": {
                        "action": "updated",
                        "branches": ["branch1"],
                        "id": "17915618-03d7-7f70-4356-1851b7247682",
                        "properties": {},
                        "summary": {"added": 0, "removed": 0, "updated": 1},
                        "type": "Attribute",
                        "value": {
                            "changes": [
                                {
                                    "action": "updated",
                                    "branch": "branch1",
                                    "changed_at": "2023-10-25T11:26:48.387801Z",
                                    "type": "HAS_VALUE",
                                    "value": {"new": "New " "description " "in " "branch1", "previous": NULL_VALUE},
                                }
                            ],
                            "path": "data/17915618-03d5-2db0-4358-185140cb1203/description/value",
                        },
                    },
                    "name": "description",
                    "path": "data/17915618-03d5-2db0-4358-185140cb1203/description",
                    "type": "Attribute",
                }
            },
            "id": "17915618-03d5-2db0-4358-185140cb1203",
            "kind": "InfraInterfaceL3",
            "path": "data/17915618-03d5-2db0-4358-185140cb1203",
            "summary": {"added": 0, "removed": 0, "updated": 1},
        }

        expected_result_main = {
            "action": {"main": "updated"},
            "display_label": {"main": "Ethernet1"},
            "elements": {
                "description": {
                    "change": {
                        "action": "updated",
                        "branches": ["main"],
                        "id": "17915618-15e5-0ca0-435e-18516f4db7c8",
                        "properties": {},
                        "summary": {"added": 0, "removed": 0, "updated": 1},
                        "type": "Attribute",
                        "value": {
                            "changes": [
                                {
                                    "action": "updated",
                                    "branch": "main",
                                    "changed_at": "2023-10-25T11:26:49.190014Z",
                                    "type": "HAS_VALUE",
                                    "value": {"new": "New " "description " "in " "main", "previous": NULL_VALUE},
                                }
                            ],
                            "path": "data/17915618-15e2-e1f0-435b-18517dcffdf5/description/value",
                        },
                    },
                    "name": "description",
                    "path": "data/17915618-15e2-e1f0-435b-18517dcffdf5/description",
                    "type": "Attribute",
                }
            },
            "id": "17915618-15e2-e1f0-435b-18517dcffdf5",
            "kind": "InfraInterfaceL3",
            "path": "data/17915618-15e2-e1f0-435b-18517dcffdf5",
            "summary": {"added": 0, "removed": 0, "updated": 1},
        }

        paths_to_exclude = [
            "root['id']",
            "root['path']",
            "root['elements']['description']['change']['id']",
            "root['elements']['description']['change']['value']['changes'][0]['changed_at']",
            "root['elements']['description']['change']['value']['path']",
            "root['elements']['description']['path']",
        ]

        assert (
            DeepDiff(
                expected_result_branch1, result["diffs"][0], exclude_paths=paths_to_exclude, ignore_order=True
            ).to_dict()
            == {}
        )
        assert (
            DeepDiff(
                expected_result_main, result["diffs"][1], exclude_paths=paths_to_exclude, ignore_order=True
            ).to_dict()
            == {}
        )

    async def test_update_intf_description_branch1_again(self, client, dataset01, integration_helper):
        """
        Update the description of the interface in the new branch again and validate that its being properly updated
        """
        headers = await integration_helper.admin_headers()

        new_description = f"New New description in {branch1}"

        assert pytest.state["spine1_lo0_id"]

        intf_name = "Loopback0"
        with client:
            # Update the description in BRANCH1
            variables = {"interface_id": pytest.state["spine1_lo0_id"], "description": new_description}
            response = client.post(
                f"/graphql/{branch1}", json={"query": INTERFACE_UPDATE, "variables": variables}, headers=headers
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["InfraInterfaceL3Update"]["ok"]

            # Query the new new description in BRANCH1 to check its value
            response = client.post(
                f"/graphql/{branch1}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]["InfraDevice"]["edges"][0]

        intfs = [intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name]
        assert len(intfs) == 1

        assert intfs[0]["node"]["description"]["value"] == new_description

    @pytest.mark.xfail(reason="FIXME: Need to investigate, Previous value is not correct")
    def test_validate_diff_again_after_description_update(self, client, dataset01):
        with client:
            time_from = pytest.state["time_after_intf_update_branch1"]
            time_to = pendulum.now("UTC").to_iso8601_string()
            response = client.get(
                f"/api/diff/data?branch={branch1}&branch_only=true&time_from={time_from}&time_to={time_to}",
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json() is not None
        result = response.json()

        expected_result = {
            "branch": "branch1",
            "kind": "InterfaceL3",
            "id": "8f3ed0a5-ed35-47bd-a76e-441f2d90c79a",
            "summary": {"added": 0, "removed": 0, "updated": 1},
            "display_label": "Loopback0",
            "changed_at": None,
            "action": "updated",
            "elements": {
                "description": {
                    "type": "Attribute",
                    "name": "description",
                    "id": "fbbf4969-ef02-4428-a05f-bc3bee178f51",
                    "changed_at": None,
                    "summary": {"added": 0, "removed": 0, "updated": 0},
                    "action": "updated",
                    "value": {
                        "branch": "branch1",
                        "type": "HAS_VALUE",
                        "changed_at": "2023-05-04T18:45:28.584932Z",
                        "action": "updated",
                        "value": {"new": "New New description in branch1", "previous": NULL_VALUE},
                    },
                    "properties": [],
                }
            },
        }

        paths_to_exclude = [
            "root['id']",
            "root['elements']['description']['id']",
            "root['elements']['description']['value']['changed_at']",
        ]

        assert (
            DeepDiff(expected_result, result["branch1"][0], exclude_paths=paths_to_exclude, ignore_order=True).to_dict()
            == {}
        )

    async def test_create_second_branch(self, client, init_db_infra, dataset01, integration_helper):
        headers = await integration_helper.admin_headers()

        with client:
            response = client.post(
                "/graphql",
                json={"query": BRANCH_CREATE, "variables": {"branch": branch2, "isolated": True}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["BranchCreate"]["ok"]

    async def test_update_intf_description_main_after_branch2(self, client, dataset01, integration_helper):
        assert pytest.state["spine1_eth1_id"]
        headers = await integration_helper.admin_headers()

        new_description = f"New description in {main_branch} after creating {branch2}"

        intf_name = "Ethernet1"
        with client:
            # Query the description in main_branch to get its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name
            ]
            assert len(intfs) == 1

            old_description = intfs[0]["node"]["description"]["value"]

            # Update the description in MAIN
            variables = {
                "branch": main_branch,
                "interface_id": pytest.state["spine1_eth1_id"],
                "description": new_description,
            }
            response = client.post(
                "/graphql", json={"query": INTERFACE_UPDATE, "variables": variables}, headers=headers
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["InfraInterfaceL3Update"]["ok"]

            # Query the new description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name
            ]
            assert len(intfs) == 1

            assert intfs[0]["node"]["description"]["value"] == new_description

            # Query the new description in BRANCH2 to check its value
            response = client.post(
                f"/graphql/{branch2}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name
            ]
            assert len(intfs) == 1
            assert intfs[0]["node"]["description"]["value"] == old_description

    async def test_rebase_branch2(self, client, dataset01, integration_helper):
        """
        Rebase Branch 2
        """
        headers = await integration_helper.admin_headers()

        intf_name = "Ethernet1"
        with client:
            response = client.post(
                "/graphql", json={"query": BRANCH_REBASE, "variables": {"branch": branch2}}, headers=headers
            )
            assert response.status_code == 200
            result = response.json()["data"]
            assert result["BranchRebase"]["ok"]

            # Query the description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name
            ]
            assert len(intfs) == 1
            main_description = intfs[0]["node"]["description"]["value"]

            # Query the new description in BRANCH2 to check its value
            response = client.post(
                f"/graphql/{branch2}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]
            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name
            ]
            assert len(intfs) == 1
            assert intfs[0]["node"]["description"]["value"] == main_description

    async def test_query_spine1_lo0_at_start_time(self, client, dataset01):
        intf_name = "Loopback0"
        with client:
            response = client.post(
                "/graphql",
                json={
                    "query": QUERY_SPINE1_INTF,
                    "variables": {
                        "intf_name": intf_name,
                    },
                },
                params={"at": pytest.state["time_start"].to_iso8601_string()},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf_name
            ]
            assert len(intfs) == 1
            assert intfs[0]["node"]["name"]["value"] == "Loopback0"

            pytest.state["spine1_lo0_description_start"] = intfs[0]["node"]["description"]["value"]

    async def test_add_new_interface_in_first_branch(self, client, dataset01, integration_helper):
        headers = await integration_helper.admin_headers()

        with client:
            response = client.post(
                f"/graphql/{branch1}",
                json={
                    "query": INTERFACE_CREATE,
                    "variables": {
                        "device": "spine1",
                        "intf_name": "Ethernet8",
                        "status": "active",
                        "role": "leaf",
                        "speed": 1000,
                        "description": "New interface added in Branch1",
                    },
                },
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["InfraInterfaceL3Create"]["ok"]
            assert result["InfraInterfaceL3Create"]["object"]["name"]["value"] == "Ethernet8"

    @pytest.mark.xfail(reason="FIXME: Need to refactor once we have the new diff API")
    def test_validate_diff_after_new_interface(self, client, dataset01):
        with client:
            response = client.get(f"/api/diff/data?branch={branch1}&branch_only=true", headers=headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json() is not None
        # result = response.json()

        # assert DeepDiff(result["diff"]["nodes"], expected_result_nodes, ignore_order=True).to_dict() == {}
        # assert (
        #     DeepDiff(result["diff"]["relationships"], expected_result_relationships, ignore_order=True).to_dict() == {}
        # )

    async def test_merge_first_branch_into_main(self, client, dataset01, integration_helper):
        # Expected description for Loopback0 after the merge
        headers = await integration_helper.admin_headers()

        expected_description = f"New New description in {branch1}"

        intf1_name = "Loopback0"
        intf2_name = "Ethernet8"

        with client:
            # Merge branch1 into main
            response = client.post(
                "/graphql",
                json={
                    "query": BRANCH_MERGE,
                    "variables": {
                        "branch": branch1,
                    },
                },
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            assert response.json()["data"]["BranchMerge"]["ok"] is True

            # Query the new value in Main which should match the pervious version in branch1
            response = client.post(
                "/graphql",
                json={
                    "query": QUERY_SPINE1_INTF,
                    "variables": {
                        "intf_name": intf1_name,
                    },
                },
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf1_name
            ]
            assert len(intfs) == 1

            assert intfs[0]["node"]["description"]["value"] == expected_description

            # Query the new Interface in Main which should match the previous version in branch1
            response = client.post(
                "/graphql",
                json={
                    "query": QUERY_SPINE1_INTF,
                    "variables": {
                        "intf_name": intf2_name,
                    },
                },
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]["InfraDevice"]["edges"][0]

            intfs = [
                intf for intf in result["node"]["interfaces"]["edges"] if intf["node"]["name"]["value"] == intf2_name
            ]
            assert len(intfs) == 1
