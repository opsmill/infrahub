import pendulum
import pytest
from deepdiff import DeepDiff
from fastapi.testclient import TestClient

from infrahub.database import InfrahubDatabase
from infrahub.server import app
from tests.test_data import dataset01 as ds01

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

DIFF_UPDATE = """
    mutation($branch: String!) {
        DiffUpdate(data: {branch: $branch, wait_for_completion: true}) {
            ok
        }
    }
"""

DIFF_TREE_QUERY = """
query GetDiffTree($branch: String){
    DiffTree (branch: $branch) {
        base_branch
        diff_branch
        num_added
        num_removed
        num_updated
        num_conflicts
        nodes {
            uuid
            kind
            label
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
                status
                num_added
                num_removed
                num_updated
                num_conflicts
                contains_conflict
                conflict { uuid }
                properties {
                    property_type
                    previous_value
                    new_value
                    previous_label
                    new_label
                    status
                    conflict { uuid }
                }
            }
            relationships {
                name
                status
                cardinality
                contains_conflict
                elements {
                    status
                    peer_id
                    contains_conflict
                    conflict { uuid }
                    properties {
                        property_type
                        previous_value
                        new_value
                        previous_label
                        new_label
                        status
                        conflict { uuid }
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
    mutation($device: String!, $intf_name: String!, $description: String!, $speed: BigInt!, $role: String!, $status: String!) {
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
                id
                name {
                    value
                }
            }
        }
    }
"""


class State:
    def __init__(self) -> None:
        self.data: dict = {}


state = State()


class TestUserWorkflow01:
    @pytest.fixture(scope="class")
    async def client(self, redis, nats, prefect_test_fixture):
        client = TestClient(app)
        return client

    @pytest.fixture(scope="class")
    async def dataset01(self, db: InfrahubDatabase, init_db_infra):
        await ds01.load_data(db=db, nbr_devices=2)

    async def test_initialize_state(self):
        state.data["spine1_id"] = None
        state.data["spine1_lo0_id"] = None
        state.data["time_start"] = None

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

        for device in result["InfraDevice"]["edges"]:
            if device["node"]["name"]["value"] == "spine1":
                state.data["spine1_id"] = device["node"]["id"]
        # Initialize the start time
        state.data["time_start"] = pendulum.now(tz="UTC")

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

        state.data["spine1_lo0_id"] = intfs[0]["node"]["id"]
        state.data["spine1_lo0_description_start"] = intfs[0]["node"]["description"]["value"]

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

        state.data["spine1_eth1_id"] = intfs[0]["node"]["id"]
        state.data["spine1_eth1_description_start"] = intfs[0]["node"]["description"]["value"]

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

        assert state.data["spine1_lo0_id"]

        intf_name = "Loopback0"
        with client:
            # Update the description in BRANCH1
            variables = {"interface_id": state.data["spine1_lo0_id"], "description": new_description}
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

        state.data["time_after_intf_update_branch1"] = pendulum.now("UTC").to_iso8601_string()

    async def test_update_intf_description_main(self, client, init_db_infra, dataset01, integration_helper):
        """
        Update the description of the interface Ethernet1 in the main branch and validate that its being properly updated
        """
        headers = await integration_helper.admin_headers()
        new_description = f"New description in {main_branch}"

        assert state.data["spine1_eth1_id"]

        intf_name = "Ethernet1"
        with client:
            # Update the description in MAIN
            variables = {"interface_id": state.data["spine1_eth1_id"], "description": new_description}
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
            response = client.post(
                "/graphql",
                json={"query": DIFF_UPDATE, "variables": {"branch": branch1}},
                headers=headers,
            )
            assert response.status_code == 200
            result = response.json()
            assert result.get("errors") is None
            assert result["data"]["DiffUpdate"]["ok"] is True

            response = client.post(
                "/graphql",
                json={"query": DIFF_TREE_QUERY, "variables": {"branch": branch1}},
                headers=headers,
            )
            assert response.status_code == 200

        result = response.json()
        assert "errors" not in result
        assert result

        expected_result = {
            "base_branch": "main",
            "diff_branch": "branch1",
            "num_added": 0,
            "num_removed": 0,
            "num_updated": 1,
            "num_conflicts": 0,
            "nodes": [
                {
                    "uuid": state.data["spine1_id"],
                    "kind": "InfraDevice",
                    "label": "spine1",
                    "status": "UNCHANGED",
                    "parent": None,
                    "contains_conflict": False,
                    "num_added": 0,
                    "num_removed": 0,
                    "num_updated": 0,
                    "num_conflicts": 0,
                    "attributes": [],
                    "relationships": [],
                },
                {
                    "uuid": state.data["spine1_lo0_id"],
                    "kind": "InfraInterfaceL3",
                    "label": "Loopback0",
                    "status": "UPDATED",
                    "parent": {
                        "uuid": state.data["spine1_id"],
                        "kind": "InfraDevice",
                        "relationship_name": "interfaces",
                    },
                    "contains_conflict": False,
                    "num_added": 0,
                    "num_removed": 0,
                    "num_updated": 1,
                    "num_conflicts": 0,
                    "relationships": [],
                    "attributes": [
                        {
                            "name": "description",
                            "status": "UPDATED",
                            "num_added": 1,
                            "num_removed": 0,
                            "num_updated": 0,
                            "num_conflicts": 0,
                            "contains_conflict": False,
                            "conflict": None,
                            "properties": [
                                {
                                    "property_type": "HAS_VALUE",
                                    "previous_value": "NULL",
                                    "new_value": "New description in branch1",
                                    "previous_label": None,
                                    "new_label": None,
                                    "status": "ADDED",
                                    "conflict": None,
                                }
                            ],
                        }
                    ],
                },
            ],
        }

        assert DeepDiff(expected_result, result["data"]["DiffTree"], ignore_order=True).to_dict() == {}

    async def test_update_intf_description_branch1_again(self, client, dataset01, integration_helper):
        """
        Update the description of the interface in the new branch again and validate that its being properly updated
        """
        headers = await integration_helper.admin_headers()

        new_description = f"New New description in {branch1}"

        assert state.data["spine1_lo0_id"]

        intf_name = "Loopback0"
        with client:
            # Update the description in BRANCH1
            variables = {"interface_id": state.data["spine1_lo0_id"], "description": new_description}
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

    async def test_validate_diff_again_after_description_update(self, client, dataset01, integration_helper):
        headers = await integration_helper.admin_headers()

        with client:
            response = client.post(
                "/graphql",
                json={"query": DIFF_UPDATE, "variables": {"branch": branch1}},
                headers=headers,
            )
            assert response.status_code == 200
            result = response.json()
            assert result.get("errors") is None
            assert result["data"]["DiffUpdate"]["ok"] is True

            response = client.post(
                "/graphql",
                json={"query": DIFF_TREE_QUERY, "variables": {"branch": branch1}},
                headers=headers,
            )
            assert response.status_code == 200

        result = response.json()
        assert "errors" not in result
        assert result

        expected_result = {
            "base_branch": "main",
            "diff_branch": "branch1",
            "num_added": 0,
            "num_removed": 0,
            "num_updated": 1,
            "num_conflicts": 0,
            "nodes": [
                {
                    "uuid": state.data["spine1_id"],
                    "kind": "InfraDevice",
                    "label": "spine1",
                    "status": "UNCHANGED",
                    "parent": None,
                    "contains_conflict": False,
                    "num_added": 0,
                    "num_removed": 0,
                    "num_updated": 0,
                    "num_conflicts": 0,
                    "attributes": [],
                    "relationships": [],
                },
                {
                    "uuid": state.data["spine1_lo0_id"],
                    "kind": "InfraInterfaceL3",
                    "label": "Loopback0",
                    "status": "UPDATED",
                    "parent": {
                        "uuid": state.data["spine1_id"],
                        "kind": "InfraDevice",
                        "relationship_name": "interfaces",
                    },
                    "contains_conflict": False,
                    "num_added": 0,
                    "num_removed": 0,
                    "num_updated": 1,
                    "num_conflicts": 0,
                    "relationships": [],
                    "attributes": [
                        {
                            "name": "description",
                            "status": "UPDATED",
                            "num_added": 1,
                            "num_removed": 0,
                            "num_updated": 0,
                            "num_conflicts": 0,
                            "contains_conflict": False,
                            "conflict": None,
                            "properties": [
                                {
                                    "property_type": "HAS_VALUE",
                                    "previous_value": "NULL",
                                    "new_value": "New New description in branch1",
                                    "previous_label": None,
                                    "new_label": None,
                                    "status": "ADDED",
                                    "conflict": None,
                                }
                            ],
                        }
                    ],
                },
            ],
        }

        assert DeepDiff(expected_result, result["data"]["DiffTree"], ignore_order=True).to_dict() == {}

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
        assert state.data["spine1_eth1_id"]
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
                "interface_id": state.data["spine1_eth1_id"],
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
                params={"at": state.data["time_start"].to_iso8601_string()},
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

            state.data["spine1_lo0_description_start"] = intfs[0]["node"]["description"]["value"]

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
            state.data["spine1_ethernet8_id"] = result["InfraInterfaceL3Create"]["object"]["id"]

    async def test_validate_diff_after_new_interface(self, client, dataset01, integration_helper):
        headers = await integration_helper.admin_headers()

        with client:
            response = client.post(
                "/graphql",
                json={"query": DIFF_UPDATE, "variables": {"branch": branch1}},
                headers=headers,
            )
            assert response.status_code == 200
            result = response.json()
            assert result.get("errors") is None
            assert result["data"]["DiffUpdate"]["ok"] is True

            response = client.post(
                "/graphql",
                json={"query": DIFF_TREE_QUERY, "variables": {"branch": branch1}},
                headers=headers,
            )
            assert response.status_code == 200

        result = response.json()
        assert "errors" not in result

        assert result
        diff_tree = result["data"]["DiffTree"]
        assert diff_tree["base_branch"] == "main"
        assert diff_tree["diff_branch"] == "branch1"
        assert diff_tree["num_added"] == 1
        assert diff_tree["num_removed"] == 0
        assert diff_tree["num_updated"] == 2
        assert diff_tree["num_conflicts"] == 0
        node_diffs_by_uuid = {n["uuid"]: n for n in diff_tree["nodes"]}
        assert set(node_diffs_by_uuid.keys()) == {
            state.data["spine1_lo0_id"],
            state.data["spine1_id"],
            state.data["spine1_ethernet8_id"],
        }

        expected_loopback_0 = {
            "uuid": state.data["spine1_lo0_id"],
            "kind": "InfraInterfaceL3",
            "label": "Loopback0",
            "status": "UPDATED",
            "parent": {
                "uuid": state.data["spine1_id"],
                "kind": "InfraDevice",
                "relationship_name": "interfaces",
            },
            "contains_conflict": False,
            "num_added": 0,
            "num_removed": 0,
            "num_updated": 1,
            "num_conflicts": 0,
            "attributes": [
                {
                    "name": "description",
                    "status": "UPDATED",
                    "num_added": 1,
                    "num_removed": 0,
                    "num_updated": 0,
                    "num_conflicts": 0,
                    "contains_conflict": False,
                    "conflict": None,
                    "properties": [
                        {
                            "property_type": "HAS_VALUE",
                            "previous_value": "NULL",
                            "new_value": "New New description in branch1",
                            "previous_label": None,
                            "new_label": None,
                            "status": "ADDED",
                            "conflict": None,
                        }
                    ],
                }
            ],
            "relationships": [],
        }
        assert node_diffs_by_uuid[state.data["spine1_lo0_id"]] == expected_loopback_0

        expected_spine = {
            "uuid": state.data["spine1_id"],
            "kind": "InfraDevice",
            "label": "spine1",
            "status": "UPDATED",
            "parent": None,
            "contains_conflict": False,
            "num_added": 0,
            "num_removed": 0,
            "num_updated": 1,
            "num_conflicts": 0,
            "attributes": [],
            "relationships": [
                {
                    "name": "interfaces",
                    "status": "UPDATED",
                    "cardinality": "MANY",
                    "contains_conflict": False,
                    "elements": [
                        {
                            "status": "ADDED",
                            "peer_id": state.data["spine1_ethernet8_id"],
                            "contains_conflict": False,
                            "conflict": None,
                            "properties": [
                                {
                                    "property_type": "IS_RELATED",
                                    "previous_value": None,
                                    "new_value": state.data["spine1_ethernet8_id"],
                                    "previous_label": None,
                                    "new_label": "Ethernet8",
                                    "status": "ADDED",
                                    "conflict": None,
                                },
                                {
                                    "property_type": "IS_PROTECTED",
                                    "previous_value": None,
                                    "new_value": "False",
                                    "previous_label": None,
                                    "new_label": None,
                                    "status": "ADDED",
                                    "conflict": None,
                                },
                                {
                                    "property_type": "IS_VISIBLE",
                                    "previous_value": None,
                                    "new_value": "True",
                                    "previous_label": None,
                                    "new_label": None,
                                    "status": "ADDED",
                                    "conflict": None,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        assert DeepDiff(expected_spine, node_diffs_by_uuid[state.data["spine1_id"]], ignore_order=True).to_dict() == {}

        expected_new_attributes = {
            "mtu": "1500",
            "description": "New interface added in Branch1",
            "lacp_priority": "32768",
            "enabled": "True",
            "name": "Ethernet8",
            "role": "leaf",
            "speed": "1000",
            "status": "active",
            "lacp_rate": "Normal",
        }
        expected_new_interface = {
            "uuid": state.data["spine1_ethernet8_id"],
            "kind": "InfraInterfaceL3",
            "label": "Ethernet8",
            "status": "ADDED",
            "parent": {
                "uuid": state.data["spine1_id"],
                "kind": "InfraDevice",
                "relationship_name": "interfaces",
            },
            "contains_conflict": False,
            "num_added": 10,
            "num_removed": 0,
            "num_updated": 0,
            "num_conflicts": 0,
            "attributes": [
                {
                    "name": name,
                    "status": "ADDED",
                    "num_added": 3,
                    "num_removed": 0,
                    "num_updated": 0,
                    "num_conflicts": 0,
                    "contains_conflict": False,
                    "conflict": None,
                    "properties": [
                        {
                            "property_type": "HAS_VALUE",
                            "previous_value": None,
                            "new_value": new_value,
                            "previous_label": None,
                            "new_label": None,
                            "status": "ADDED",
                            "conflict": None,
                        },
                        {
                            "property_type": "IS_PROTECTED",
                            "previous_value": None,
                            "new_value": "False",
                            "previous_label": None,
                            "new_label": None,
                            "status": "ADDED",
                            "conflict": None,
                        },
                        {
                            "property_type": "IS_VISIBLE",
                            "previous_value": None,
                            "new_value": "True",
                            "previous_label": None,
                            "new_label": None,
                            "status": "ADDED",
                            "conflict": None,
                        },
                    ],
                }
                for name, new_value in expected_new_attributes.items()
            ],
            "relationships": [
                {
                    "name": "device",
                    "status": "ADDED",
                    "cardinality": "ONE",
                    "contains_conflict": False,
                    "elements": [
                        {
                            "status": "ADDED",
                            "peer_id": state.data["spine1_id"],
                            "contains_conflict": False,
                            "conflict": None,
                            "properties": [
                                {
                                    "property_type": property_type,
                                    "previous_value": None,
                                    "new_value": new_value,
                                    "previous_label": None,
                                    "new_label": new_label,
                                    "status": "ADDED",
                                    "conflict": None,
                                }
                                for property_type, new_value, new_label in [
                                    ("IS_RELATED", state.data["spine1_id"], "spine1"),
                                    ("IS_PROTECTED", "False", None),
                                    ("IS_VISIBLE", "True", None),
                                ]
                            ],
                        }
                    ],
                }
            ],
        }
        assert (
            DeepDiff(
                expected_new_interface, node_diffs_by_uuid[state.data["spine1_ethernet8_id"]], ignore_order=True
            ).to_dict()
            == {}
        )

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
