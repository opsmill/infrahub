import pendulum
import pytest
from fastapi.testclient import TestClient

from infrahub.main import app
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

QUERY_SPINE1_INTF_AT = """
    query($intf_name: String!) {
        device(name__value: "spine1") {
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
        interface_update(data: { id: $interface_id, description: { value: $description}}){
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
        interface_create(data: {
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

DIFF = """
    query($branch_name: String!) {
        diff(branch: $branch_name) {
            nodes {
                branch
                labels
                action
                changed_at
                attributes {
                    name
                    action
                    properties {
                        branch
                        type
                        action
                    }
                }
            }
            relationships {
                branch
                name
                properties {
                    branch
                    type
                    action
                }
                changed_at
                action
            }
        }
    }
"""


class TestUserWorkflow01:
    @pytest.fixture(scope="class")
    async def client(self):
        return TestClient(app)

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

        with client:
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Loopback0"}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        assert result["device"][0]["interfaces"][0]["name"]["value"] == "Loopback0"

        pytest.state["spine1_lo0_id"] = result["device"][0]["interfaces"][0]["id"]
        pytest.state["spine1_lo0_description_start"] = result["device"][0]["interfaces"][0]["description"]["value"]

    def test_query_spine1_ethernet1(self, client, init_db_infra, dataset01):
        """
        Query Ethernet1 to gather its ID
        """

        with client:
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        assert result["device"][0]["interfaces"][0]["name"]["value"] == "Ethernet1"

        pytest.state["spine1_eth1_id"] = result["device"][0]["interfaces"][0]["id"]
        pytest.state["spine1_eth1_description_start"] = result["device"][0]["interfaces"][0]["description"]["value"]

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
            assert result["interface_update"]["ok"]

            # Query the new description in BRANCH1 to check its value
            response = client.post(
                f"/graphql/{branch1}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Loopback0"}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["device"][0]["interfaces"][0]["description"]["value"] == new_description

    def test_update_intf_description_main(self, client, init_db_infra, dataset01):
        """
        Update the description of the interface Ethernet1 in the main branch and validate that its being properly updated
        """

        new_description = f"New description in {main_branch}"

        assert pytest.state["spine1_eth1_id"]

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
            assert result["interface_update"]["ok"]

            # Query the new description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["device"][0]["interfaces"][0]["description"]["value"] == new_description

    def test_validate_diff(self, client, dataset01):

        with client:
            variables = {"branch_name": branch1}
            response = client.post(f"/graphql", json={"query": DIFF, "variables": variables}, headers=headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        assert result == {
            "diff": {
                "nodes": [
                    {
                        "action": "updated",
                        "attributes": [
                            {
                                "action": "updated",
                                "name": "description",
                                "properties": [
                                    {
                                        "action": "updated",
                                        "branch": "branch1",
                                        # "changed_at": "2023-01-31T10:02:31.087842Z",
                                        "type": "HAS_VALUE",
                                    },
                                ],
                            },
                        ],
                        "branch": None,
                        "changed_at": None,
                        "labels": ["Interface", "Node"],
                    },
                    {
                        "action": "updated",
                        "attributes": [
                            {
                                "action": "updated",
                                "name": "description",
                                "properties": [
                                    {
                                        "action": "updated",
                                        "branch": "main",
                                        # "changed_at": "2023-01-31T10:02:33.661068Z",
                                        "type": "HAS_VALUE",
                                    },
                                ],
                            },
                        ],
                        "branch": None,
                        "changed_at": None,
                        "labels": ["Interface", "Node"],
                    },
                ],
                "relationships": [],
            },
        }

    def test_update_intf_description_branch1_again(self, client, dataset01):
        """
        Update the description of the interface in the new branch again and validate that its being properly updated
        """

        new_description = f"New New description in {branch1}"

        assert pytest.state["spine1_lo0_id"]

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
            assert result["interface_update"]["ok"]

            # Query the new new description in BRANCH1 to check its value
            response = client.post(
                f"/graphql/{branch1}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Loopback0"}},
                headers=headers,
            )

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]
        assert result["device"][0]["interfaces"][0]["description"]["value"] == new_description

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

        with client:
            # Query the description in main_branch to get its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            old_description = result["device"][0]["interfaces"][0]["description"]["value"]

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
            assert result["interface_update"]["ok"]

            # Query the new description in MAIN to check its value
            response = client.post(
                "/graphql",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["device"][0]["interfaces"][0]["description"]["value"] == new_description

            # Query the new description in BRANCH2 to check its value
            response = client.post(
                f"/graphql/{branch2}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["device"][0]["interfaces"][0]["description"]["value"] == old_description

    def test_rebase_branch2(self, client, dataset01):
        """
        Rebase Branch 2
        """

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
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )

            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            main_description = result["device"][0]["interfaces"][0]["description"]["value"]

            # Query the new description in BRANCH2 to check its value
            response = client.post(
                f"/graphql/{branch2}",
                json={"query": QUERY_SPINE1_INTF, "variables": {"intf_name": "Ethernet1"}},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["device"][0]["interfaces"][0]["description"]["value"] == main_description

    def test_query_spine1_lo0_at_start_time(self, client, dataset01):

        with client:
            response = client.post(
                "/graphql",
                json={
                    "query": QUERY_SPINE1_INTF_AT,
                    "variables": {
                        "intf_name": "Loopback0",
                    },
                },
                params={"at": pytest.state["time_start"].to_iso8601_string()},
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]
            assert result["device"][0]["interfaces"][0]["name"]["value"] == "Loopback0"

            pytest.state["spine1_lo0_description_start"] = result["device"][0]["interfaces"][0]["description"]["value"]

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
            assert result["interface_create"]["ok"]
            assert result["interface_create"]["object"]["name"]["value"] == "Ethernet8"

    def test_merge_first_branch_into_main(self, client, dataset01):

        # Expected description for Loopback0 after the merge
        expected_description = f"New New description in {branch1}"

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
                        "intf_name": "Loopback0",
                    },
                },
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]

            assert result["device"][0]["interfaces"][0]["description"]["value"] == expected_description

            # Query the new Interface in Main which should match the previous version in branch1
            response = client.post(
                "/graphql",
                json={
                    "query": QUERY_SPINE1_INTF,
                    "variables": {
                        "intf_name": "Ethernet8",
                    },
                },
                headers=headers,
            )
            assert response.status_code == 200
            assert "errors" not in response.json()
            assert response.json()["data"] is not None
            result = response.json()["data"]

            assert result["device"][0]["interfaces"][0]["name"]["value"] == "Ethernet8"
