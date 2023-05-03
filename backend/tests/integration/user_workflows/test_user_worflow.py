import pendulum
import pytest
from deepdiff import DeepDiff
from fastapi.testclient import TestClient

from infrahub.api.main import app
from infrahub.test_data import dataset01 as ds01

headers = {"Authorization": "Token nelly"}

main_branch = "main"
branch1 = "branch1"
branch2 = "branch2"


QUERY_GET_ALL_DEVICES = """
    query {
        device {
            id
            name {
                value
            }
        }
    }
    """

QUERY_SPINE1_INTF = """
    query($intf_name: String!) {
        device(name__value: "spine1") {
            id
            name {
                value
            }
            interfaces(name__value: $intf_name) {
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
    """

BRANCH_CREATE = """
    mutation($branch: String!) {
        branch_create(data: { name: $branch }) {
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
        branch_merge(data: { name: $branch }) {
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
        branch_rebase(data: { name: $branch }) {
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
        interface_l3_update(data: { id: $interface_id, description: { value: $description}}){
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
        interface_l3_create(data: {
            device: { id: $device },
            name: { value: $intf_name },
            description: { value: $description },
            role: { id: $role },
            speed: { value: $speed },
            status: { id: $status }
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
    async def dataset01(self, session, init_db_infra):
        await ds01.load_data(session=session, nbr_devices=2)

    def test_initialize_state(self):
        pytest.state = {
            "spine1_lo0_id": None,
            "time_start": None,
        }

    def test_query_all_devices(self, client, init_db_infra, dataset01):
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

        assert "device" in result.keys()
        assert len(result["device"]) == 2

        # Initialize the start time
        pytest.state["time_start"] = pendulum.now(tz="UTC")

    def test_query_spine1_loobpack0(self, client, init_db_infra, dataset01):
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
        result = response.json()["data"]

        intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
        assert len(intfs) == 1

        pytest.state["spine1_lo0_id"] = intfs[0]["id"]
        pytest.state["spine1_lo0_description_start"] = intfs[0]["description"]["value"]

    def test_query_spine1_ethernet1(self, client, init_db_infra, dataset01):
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

        intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
        assert len(intfs) == 1

        pytest.state["spine1_eth1_id"] = intfs[0]["id"]
        pytest.state["spine1_eth1_description_start"] = intfs[0]["description"]["value"]

    def test_create_first_branch(self, client, init_db_infra, dataset01):
        """
        Create a first Branch from Main
        """
        with client:
            response = client.post(
                "/graphql", json={"query": BRANCH_CREATE, "variables": {"branch": branch1}}, headers=headers
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["branch_create"]["ok"]

    def test_update_intf_description_branch1(self, client, init_db_infra, dataset01):
        """
        Update the description of the interface in the new branch and validate that its being properly updated
        """

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
            assert result["interface_l3_update"]["ok"]

            # Query the new description in BRANCH1 to check its value
            response = client.post(
                f"/graphql/{branch1}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
        assert len(intfs) == 1

        assert intfs[0]["description"]["value"] == new_description

        pytest.state["time_after_intf_update_branch1"] = pendulum.now("UTC").to_iso8601_string()

    def test_update_intf_description_main(self, client, init_db_infra, dataset01):
        """
        Update the description of the interface Ethernet1 in the main branch and validate that its being properly updated
        """

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
            assert result["interface_l3_update"]["ok"]

            # Query the new description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
        assert len(intfs) == 1

        assert intfs[0]["description"]["value"] == new_description

    def test_validate_diff_after_description_update(self, client, dataset01):
        with client:
            response = client.get(f"/diff/data?branch={branch1}&branch_only=false", headers=headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json() is not None
        result = response.json()

        expected_result_branch1 = {
            "branch": "branch1",
            "kind": "InterfaceL3",
            "id": "9e93b812-f726-444d-ab93-9640fceac04f",
            "display_label": "Loopback0",
            "changed_at": None,
            "action": "updated",
            "attributes": [
                {
                    "name": "description",
                    "id": "79e39661-ca9d-4248-8178-80e0529a1182",
                    "changed_at": None,
                    "action": "updated",
                    "properties": [
                        {
                            "branch": "branch1",
                            "type": "HAS_VALUE",
                            "changed_at": "2023-04-29T15:45:38.076309Z",
                            "action": "updated",
                            "value": {"new": "New description in branch1", "previous": "NULL"},
                        }
                    ],
                }
            ],
            "relationships": [],
        }

        expected_result_main = {
            "branch": "main",
            "kind": "InterfaceL3",
            "id": "77f7998a-0d8f-48c2-a086-aa9c50c39964",
            "display_label": "Ethernet1",
            "changed_at": None,
            "action": "updated",
            "attributes": [
                {
                    "name": "description",
                    "id": "daadd9fb-5e58-4d9f-b8a1-bcc87ff3a167",
                    "changed_at": None,
                    "action": "updated",
                    "properties": [
                        {
                            "branch": "main",
                            "type": "HAS_VALUE",
                            "changed_at": "2023-04-29T15:45:38.343810Z",
                            "action": "updated",
                            "value": {"new": "New description in main", "previous": "NULL"},
                        }
                    ],
                }
            ],
            "relationships": [],
        }

        paths_to_exclude = [
            "root['id']",
            "root['attributes'][0]['id']",
            "root['attributes'][0]['properties'][0]['changed_at']",
        ]
        assert (
            DeepDiff(
                expected_result_branch1, result["branch1"][0], exclude_paths=paths_to_exclude, ignore_order=True
            ).to_dict()
            == {}
        )
        assert (
            DeepDiff(
                expected_result_main, result["main"][0], exclude_paths=paths_to_exclude, ignore_order=True
            ).to_dict()
            == {}
        )

    def test_update_intf_description_branch1_again(self, client, dataset01):
        """
        Update the description of the interface in the new branch again and validate that its being properly updated
        """

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
            assert result["interface_l3_update"]["ok"]

            # Query the new new description in BRANCH1 to check its value
            response = client.post(
                f"/graphql/{branch1}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
        assert len(intfs) == 1

        assert intfs[0]["description"]["value"] == new_description

    @pytest.mark.xfail(reason="FIXME: Need to revisit once we have the new diff API")
    def test_validate_diff_again_after_description_update(self, client, dataset01):
        with client:
            time_from = pytest.state["time_after_intf_update_branch1"]
            time_to = pendulum.now("UTC").to_iso8601_string()
            response = client.get(
                f"/diff/data?branch={branch1}&branch_only=true&time_from={time_from}&time_to={time_to}", headers=headers
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json() is not None
        result = response.json()

        expected_result = {
            "branch": "branch1",
            "kind": "InterfaceL3",
            "id": "51bd080e-17a2-4063-a28f-739e4cad0162",
            "display_label": "Loopback0",
            "changed_at": None,
            "action": "updated",
            "attributes": [
                {
                    "name": "description",
                    "id": "309792b7-eea4-4d5e-918c-ac142bee2355",
                    "changed_at": None,
                    "action": "updated",
                    "properties": [
                        {
                            "branch": "branch1",
                            "type": "HAS_VALUE",
                            "changed_at": "2023-04-29T15:53:58.268370Z",
                            "action": "updated",
                            "value": {
                                "new": "New New description in branch1",
                                "previous": "New description in branch1",
                            },
                        }
                    ],
                }
            ],
            "relationships": [],
        }

        paths_to_exclude = [
            "root['id']",
            "root['attributes'][0]['id']",
            "root['attributes'][0]['properties'][0]['changed_at']",
        ]

        assert (
            DeepDiff(expected_result, result["branch1"][0], exclude_paths=paths_to_exclude, ignore_order=True).to_dict()
            == {}
        )

    def test_create_second_branch(self, client, init_db_infra, dataset01):
        with client:
            response = client.post(
                "/graphql", json={"query": BRANCH_CREATE, "variables": {"branch": branch2}}, headers=headers
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["branch_create"]["ok"]

    def test_update_intf_description_main_after_branch2(self, client, dataset01):
        assert pytest.state["spine1_eth1_id"]
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
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
            assert len(intfs) == 1

            old_description = intfs[0]["description"]["value"]

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
            assert result["interface_l3_update"]["ok"]

            # Query the new description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
            assert len(intfs) == 1

            assert intfs[0]["description"]["value"] == new_description

            # Query the new description in BRANCH2 to check its value
            response = client.post(
                f"/graphql/{branch2}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
            assert len(intfs) == 1
            assert intfs[0]["description"]["value"] == old_description

    def test_rebase_branch2(self, client, dataset01):
        """
        Rebase Branch 2
        """
        intf_name = "Ethernet1"
        with client:
            response = client.post(
                "/graphql", json={"query": BRANCH_REBASE, "variables": {"branch": branch2}}, headers=headers
            )
            assert response.status_code == 200
            result = response.json()["data"]
            assert result["branch_rebase"]["ok"]

            # Query the description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
            assert len(intfs) == 1
            main_description = intfs[0]["description"]["value"]

            # Query the new description in BRANCH2 to check its value
            response = client.post(
                f"/graphql/{branch2}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": intf_name}},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
            assert len(intfs) == 1
            assert intfs[0]["description"]["value"] == main_description

    def test_query_spine1_lo0_at_start_time(self, client, dataset01):
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
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf_name]
            assert len(intfs) == 1
            assert intfs[0]["name"]["value"] == "Loopback0"

            pytest.state["spine1_lo0_description_start"] = intfs[0]["description"]["value"]

    def test_add_new_interface_in_first_branch(self, client, dataset01):
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
            assert result["interface_l3_create"]["ok"]
            assert result["interface_l3_create"]["object"]["name"]["value"] == "Ethernet8"

    @pytest.mark.xfail(reason="FIXME: Need to refactor once we have the new diff API")
    def test_validate_diff_after_new_interface(self, client, dataset01):
        with client:
            response = client.get(f"/diff/data?branch={branch1}&branch_only=true", headers=headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json() is not None
        # result = response.json()

        # assert DeepDiff(result["diff"]["nodes"], expected_result_nodes, ignore_order=True).to_dict() == {}
        # assert (
        #     DeepDiff(result["diff"]["relationships"], expected_result_relationships, ignore_order=True).to_dict() == {}
        # )

    def test_merge_first_branch_into_main(self, client, dataset01):
        # Expected description for Loopback0 after the merge
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
            assert response.json()["data"]["branch_merge"]["ok"] is True

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
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf1_name]
            assert len(intfs) == 1

            assert intfs[0]["description"]["value"] == expected_description

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
            result = response.json()["data"]

            intfs = [intf for intf in result["device"][0]["interfaces"] if intf["name"]["value"] == intf2_name]
            assert len(intfs) == 1
