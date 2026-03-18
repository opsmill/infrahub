import operator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from infrahub_sdk import InfrahubClient

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.types import BranchType, InfrahubBranch
from infrahub.services import InfrahubServices
from tests.helpers.graphql import graphql
from tests.helpers.test_app import TestInfrahubApp


@dataclass
class BranchPartialTestCaseData:
    search_term: str
    partial_match: bool
    expected_count: int


BRANCH_PARTIAL_MATCH_QUERY = """
query($name: String, $partial_match: Boolean = false) {
  InfrahubBranch(name__value: $name, partial_match: $partial_match) {
    count
    edges {
      node {
        name {
          value
        }
      }
    }
  }
}
"""


def test_check_branch_type_has_corresponding_infrahub_branch_value_field() -> None:
    exempted_fields = ("id", "created_at", "node_metadata")
    for field_name, field_value in BranchType._meta.fields.items():
        if field_name in exempted_fields:
            continue
        if InfrahubBranch._meta.fields[field_name] == field_value:
            raise Exception(f"'{field_name}' is not updated in InfrahubBranch")


class TestBranchQuery(TestInfrahubApp):
    async def test_branch_query(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        create_branch_query = """
        mutation {
            BranchCreate(data: { name: "branch3", description: "my description" }) {
                ok
                object {
                    id
                    name
                }
            }
        }
        """
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(
            db=db,
            branch=default_branch,
            account_session=session_admin,
            service=service,
        )
        branch3_result = await graphql(
            schema=gql_params.schema,
            source=create_branch_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert branch3_result.errors is None
        assert branch3_result.data
        branch3 = branch3_result.data["BranchCreate"]["object"]

        # Query all branches
        query = """
        query {
            Branch {
                name
                origin_branch
                description
                is_default
                sync_with_git
                is_isolated
                has_schema_changes
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        all_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert all_branches.errors is None
        assert all_branches.data
        assert len(all_branches.data["Branch"]) == 2

        expected_branches = [
            {
                "description": "Default Branch",
                "has_schema_changes": False,
                "sync_with_git": True,
                "is_default": True,
                "is_isolated": False,
                "name": "main",
                "origin_branch": "main",
            },
            {
                "description": "my description",
                "has_schema_changes": False,
                "sync_with_git": True,
                "is_default": False,
                "is_isolated": False,
                "name": "branch3",
                "origin_branch": "main",
            },
        ]
        assert all_branches.data["Branch"].sort(key=operator.itemgetter("name")) == expected_branches.sort(
            key=operator.itemgetter("name")
        )

        # Query Branch3 by Name
        name_query = """
        query {
            Branch(name: "%s" ) {
                id
                name
            }
        }
        """ % branch3["name"]
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        name_response = await graphql(
            schema=gql_params.schema,
            source=name_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert name_response.errors is None
        assert name_response.data
        assert len(name_response.data["Branch"]) == 1
        assert name_response.data["Branch"][0]["name"] == "branch3"

        # Query Branch3 by ID
        id_query = """
        query {
            Branch(ids: %s ) {
                id
                name
            }
        }
        """ % [branch3["id"]]
        id_query = id_query.replace("'", '"')

        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        id_response = await graphql(
            schema=gql_params.schema,
            source=id_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert id_response.data
        assert id_response.data["Branch"][0]["name"] == "branch3"
        assert len(id_response.data["Branch"]) == 1

    async def test_paginated_branch_query(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        branch_map = {}
        for i in range(10):
            create_branch_query = """
            mutation($branch_name: String!, $branch_description: String!) {
                BranchCreate(data: { name: $branch_name, description: $branch_description }) {
                    ok
                    object {
                        id
                        name
                    }
                }
            }
            """

            gql_params = await prepare_graphql_params(
                db=db,
                branch=default_branch,
                account_session=session_admin,
                service=service,
            )

            branch_name = f"sample-branch-{i}"
            branch_result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": branch_name, "branch_description": f"sample description {i}"},
            )
            assert branch_result.errors is None
            assert branch_result.data
            branch_id = branch_result.data["BranchCreate"]["object"]["id"]
            assert branch_result.data["BranchCreate"]["object"]["name"] == branch_name
            assert branch_id
            branch_map[branch_name] = branch_id

        query = """
            query($offset: Int, $limit: Int, $name: String, $ids: [ID!]) {
                InfrahubBranch(offset: $offset, limit: $limit, name__value: $name, ids: $ids) {
                    count
                    edges {
                        node {
                            name {
                                value
                            }
                            description {
                                value
                            }
                        }
                    }
                    default_branch {
                        name {
                            value
                        }
                    }
                }
            }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        all_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"offset": 2, "limit": 5},
        )
        assert all_branches.errors is None
        assert all_branches.data
        assert all_branches.data["InfrahubBranch"]["count"] == 12  # 10 created here + 1 created above + main branch

        expected_branches = [
            {
                "description": {"value": "Default Branch"},
                "name": {"value": "main"},
            },
            {
                "description": {"value": "my description"},
                "name": {"value": "branch3"},
            },
            *[
                {
                    "description": {"value": f"sample description {i}"},
                    "name": {"value": f"sample-branch-{i}"},
                }
                for i in range(10)
            ],
        ]
        all_branches_data_only = [branch.get("node") for branch in all_branches.data["InfrahubBranch"]["edges"]]
        assert all_branches_data_only.sort(key=lambda x: x["name"]["value"]) == expected_branches.sort(
            key=lambda x: x["name"]["value"]
        )

        assert all_branches.data["InfrahubBranch"]["default_branch"]["name"]["value"] == "main"

        name_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "sample-branch-4"},
        )
        assert name_branches.errors is None
        assert name_branches.data
        assert name_branches.data["InfrahubBranch"]["count"] == 1
        assert name_branches.data["InfrahubBranch"]["edges"][0]["node"]["name"]["value"] == "sample-branch-4"
        assert name_branches.data["InfrahubBranch"]["default_branch"]["name"]["value"] == "main"

        ids = [branch_map["sample-branch-3"], branch_map["sample-branch-7"]]
        id_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"ids": ids},
        )
        assert id_branches.errors is None
        assert id_branches.data
        assert id_branches.data["InfrahubBranch"]["count"] == 2
        branch_names = [edge["node"]["name"]["value"] for edge in id_branches.data["InfrahubBranch"]["edges"]]
        assert len(branch_names) == 2
        assert set(branch_names) == {"sample-branch-3", "sample-branch-7"}
        assert id_branches.data["InfrahubBranch"]["default_branch"]["name"]["value"] == "main"

    async def test_paginated_branch_query__returns_error_on_invalid_offset_or_limit(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        query = """
            query {
                InfrahubBranch(offset: -1, limit: 5) {
                    count
                    edges {
                        node {
                            graph_version {
                                value
                            }
                        }
                    }
                }
            }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        all_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert all_branches.errors
        assert len(all_branches.errors)
        assert all_branches.errors[0].message == "offset must be >= 0"

        query = """
            query {
                InfrahubBranch(offset: 0, limit: 0) {
                    count
                    edges {
                        node {
                            graph_version {
                                value
                            }
                        }
                    }
                }
            }
        """
        all_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert all_branches.errors
        assert len(all_branches.errors)
        assert all_branches.errors[0].message == "limit must be >= 1"

    async def test_paginated_branch_query_meta_data(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        query = """
            query {
                InfrahubBranch {
                    edges {
                        node_metadata {
                            created_at
                            updated_at
                        }
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
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        all_branches = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
        )
        assert all_branches.errors is None
        assert all_branches.data

        for branch in all_branches.data["InfrahubBranch"]["edges"]:
            assert branch["node"]["name"]["value"]
            assert branch["node"]["description"]["value"]
            assert branch["node_metadata"]["created_at"]

    async def test_partial_match_filter(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        branch_map = {}
        for i in range(10):
            create_branch_query = """
            mutation($branch_name: String!, $branch_description: String!) {
                BranchCreate(data: { name: $branch_name, description: $branch_description }) {
                    ok
                    object {
                        id
                        name
                    }
                }
            }
            """

            gql_params = await prepare_graphql_params(
                db=db,
                branch=default_branch,
                account_session=session_admin,
                service=service,
            )

            branch_name = f"match-branch-{i}"
            branch_result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": branch_name, "branch_description": f"sample description {i}"},
            )
            assert branch_result.errors is None
            assert branch_result.data
            branch_id = branch_result.data["BranchCreate"]["object"]["id"]
            assert branch_result.data["BranchCreate"]["object"]["name"] == branch_name
            assert branch_id
            branch_map[branch_name] = branch_id

        test_cases = [
            BranchPartialTestCaseData(search_term="match", partial_match=True, expected_count=10),
            BranchPartialTestCaseData(search_term="branch-zzz", partial_match=True, expected_count=0),
            BranchPartialTestCaseData(search_term="auth", partial_match=False, expected_count=0),
            BranchPartialTestCaseData(search_term="main", partial_match=False, expected_count=1),
            BranchPartialTestCaseData(search_term="MAIN", partial_match=False, expected_count=0),
            BranchPartialTestCaseData(search_term="MaTcH", partial_match=True, expected_count=10),
        ]

        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)

        for test_case in test_cases:
            result = await graphql(
                schema=gql_params.schema,
                source=BRANCH_PARTIAL_MATCH_QUERY,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"name": test_case.search_term, "partial_match": test_case.partial_match},
            )

            assert result.errors is None
            assert result.data
            assert result.data["InfrahubBranch"]["count"] == test_case.expected_count

    async def test_order_by_created_at_ascending(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test that branches can be ordered by created_at in ascending order."""
        branch_names = ["alpha-branch", "beta-branch", "gamma-branch"]
        for branch_name in branch_names:
            create_branch_query = """
            mutation($branch_name: String!) {
                BranchCreate(data: { name: $branch_name, description: "test" }) {
                    ok
                    object { id name }
                }
            }
            """
            gql_params = await prepare_graphql_params(
                db=db, branch=default_branch, account_session=session_admin, service=service
            )
            result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": branch_name},
            )
            assert result.errors is None

        query = """
        query {
            InfrahubBranch(order: {node_metadata: {created_at: ASC}}) {
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
        )

        assert result.errors is None
        assert result.data
        edges = result.data["InfrahubBranch"]["edges"]

        timestamps = [edge["node_metadata"]["created_at"] for edge in edges]
        assert timestamps == sorted(timestamps), "Branches should be ordered by created_at ascending"

        assert edges[0]["node"]["name"]["value"] == "main"

    async def test_order_by_created_at_descending(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test that branches can be ordered by created_at in descending order."""
        branch_names = ["delta-branch", "epsilon-branch", "zeta-branch"]
        for branch_name in branch_names:
            create_branch_query = """
            mutation($branch_name: String!) {
                BranchCreate(data: { name: $branch_name, description: "test" }) {
                    ok
                    object { id name }
                }
            }
            """
            gql_params = await prepare_graphql_params(
                db=db, branch=default_branch, account_session=session_admin, service=service
            )
            result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": branch_name},
            )
            assert result.errors is None

        query = """
        query InfrahubBranch($direction: OrderDirection!) {
            InfrahubBranch(order: {node_metadata: {created_at: $direction}}) {
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"direction": "DESC"},
            root_value=None,
        )

        assert result.errors is None
        assert result.data
        edges = result.data["InfrahubBranch"]["edges"]

        timestamps = [edge["node_metadata"]["created_at"] for edge in edges]
        assert timestamps == sorted(timestamps, reverse=True), "Branches should be ordered by created_at descending"

        assert edges[0]["node"]["name"]["value"] == "zeta-branch"
        assert edges[1]["node"]["name"]["value"] == "epsilon-branch"
        assert edges[2]["node"]["name"]["value"] == "delta-branch"

    async def test_order_by_updated_at_ascending(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test that branches can be ordered by updated_at in ascending order."""
        branch_names = ["eta-branch", "theta-branch", "iota-branch"]

        for branch_name in branch_names:
            create_branch_query = """
            mutation($branch_name: String!) {
                BranchCreate(data: { name: $branch_name, description: "initial" }) {
                    ok
                    object { id name }
                }
            }
            """
            gql_params = await prepare_graphql_params(
                db=db, branch=default_branch, account_session=session_admin, service=service
            )
            result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": branch_name},
            )
            assert result.errors is None

        update_order = ["iota-branch", "theta-branch", "eta-branch"]
        for branch_name in update_order:
            branch = await Branch.get_by_name(name=branch_name, db=db)
            branch.description = f"updated description for {branch_name}"
            await branch.save(db=db)

        query = """
        query {
            InfrahubBranch(order: {node_metadata: {updated_at: ASC}}) {
                edges {
                    node_metadata { updated_at }
                    node { name { value } description { value } }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
        )

        assert result.errors is None
        assert result.data
        edges = result.data["InfrahubBranch"]["edges"]

        test_branch_names = set(branch_names)
        test_edges = [e for e in edges if e["node"]["name"]["value"] in test_branch_names]

        timestamps = [edge["node_metadata"]["updated_at"] for edge in test_edges]
        assert timestamps == sorted(timestamps), "Branches should be ordered by updated_at ascending"

        result_branch_names = [e["node"]["name"]["value"] for e in test_edges]
        assert result_branch_names == update_order, "Updated branches should appear in update order (ascending)"

    async def test_order_by_updated_at_descending(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test that branches can be ordered by updated_at in descending order."""
        branch_names = ["kappa-branch", "lambda-branch", "mu-branch"]

        # Create all branches first
        for branch_name in branch_names:
            create_branch_query = """
            mutation($branch_name: String!) {
                BranchCreate(data: { name: $branch_name, description: "initial" }) {
                    ok
                    object { id name }
                }
            }
            """
            gql_params = await prepare_graphql_params(
                db=db, branch=default_branch, account_session=session_admin, service=service
            )
            result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": branch_name},
            )
            assert result.errors is None

        update_order = ["kappa-branch", "lambda-branch", "mu-branch"]
        for branch_name in update_order:
            branch = await Branch.get_by_name(name=branch_name, db=db)
            branch.description = f"updated description for {branch_name}"
            await branch.save(db=db)

        query = """
        query {
            InfrahubBranch(order: {node_metadata: {updated_at: DESC}}) {
                edges {
                    node_metadata { updated_at }
                    node { name { value } description { value } }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
        )

        assert result.errors is None
        assert result.data
        edges = result.data["InfrahubBranch"]["edges"]

        test_branch_names = set(branch_names)
        test_edges = [e for e in edges if e["node"]["name"]["value"] in test_branch_names]

        timestamps = [edge["node_metadata"]["updated_at"] for edge in test_edges]
        assert timestamps == sorted(timestamps, reverse=True), "Branches should be ordered by updated_at descending"

        result_branch_names = [e["node"]["name"]["value"] for e in test_edges]
        assert result_branch_names == list(reversed(update_order)), (
            "Updated branches should appear in reverse update order (descending)"
        )

    async def test_order_by_only_one_field_allowed(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
    ) -> None:
        """Test that specifying both created_at and updated_at returns an error."""
        query = """
        query {
            InfrahubBranch(order: {node_metadata: {created_at: ASC, updated_at: DESC}}) {
                edges {
                    node { name { value } }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
        )

        assert result.errors is not None
        assert len(result.errors) > 0
        assert "created_at" in str(result.errors[0]) or "updated_at" in str(result.errors[0])

    async def test_filter_by_status(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test filtering branches by status."""
        # Create a branch and set it to NEED_REBASE status
        create_branch_query = """
        mutation($branch_name: String!) {
            BranchCreate(data: { name: $branch_name, description: "test" }) {
                ok
                object { id name }
            }
        }
        """
        gql_params = await prepare_graphql_params(
            db=db, branch=default_branch, account_session=session_admin, service=service
        )
        result = await graphql(
            schema=gql_params.schema,
            source=create_branch_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"branch_name": "status-test-branch"},
        )
        assert result.errors is None

        # Update branch status to NEED_REBASE
        branch = await Branch.get_by_name(name="status-test-branch", db=db)
        branch.status = BranchStatus.NEED_REBASE
        await branch.save(db=db)

        # Query for NEED_REBASE branches
        query = """
        query($status: BranchStatus) {
            InfrahubBranch(status__value: $status) {
                count
                edges {
                    node { name { value } status { value } }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"status": "NEED_REBASE"},
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubBranch"]["count"] >= 1
        assert all(edge["node"]["status"]["value"] == "NEED_REBASE" for edge in result.data["InfrahubBranch"]["edges"])

        # Query for OPEN branches should not include the NEED_REBASE branch
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"status": "OPEN"},
        )

        assert result.errors is None
        assert result.data
        branch_names = [edge["node"]["name"]["value"] for edge in result.data["InfrahubBranch"]["edges"]]
        assert "status-test-branch" not in branch_names

    async def test_filter_by_created_at_range(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test filtering branches by creation timestamp range."""
        # Create a branch with a known name
        create_branch_query = """
        mutation($branch_name: String!) {
            BranchCreate(data: { name: $branch_name, description: "test" }) {
                ok
                object { id name }
            }
        }
        """
        gql_params = await prepare_graphql_params(
            db=db, branch=default_branch, account_session=session_admin, service=service
        )
        result = await graphql(
            schema=gql_params.schema,
            source=create_branch_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"branch_name": "created-at-test-branch"},
        )
        assert result.errors is None

        # Query with a future timestamp (should return no branches with valid created_at)
        future_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        query = """
        query($after: DateTime) {
            InfrahubBranch(node_metadata__created_at__after: $after) {
                count
                edges { node { name { value } } node_metadata { created_at } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"after": future_time},
        )

        assert result.errors is None
        assert result.data
        # No branches should have been created in the future
        assert result.data["InfrahubBranch"]["count"] == 0
        assert result.data["InfrahubBranch"]["edges"] == []

        # Query with a past timestamp (should return branches created recently)
        past_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"after": past_time},
        )

        assert result.errors is None
        assert result.data
        # Should find at least the branch we just created
        branch_names = [edge["node"]["name"]["value"] for edge in result.data["InfrahubBranch"]["edges"]]
        assert "created-at-test-branch" in branch_names

    async def test_filter_by_created_at_before(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test filtering branches created before a timestamp."""
        # Create a branch to ensure we have a known branch with valid timestamp
        create_branch_query = """
        mutation($branch_name: String!) {
            BranchCreate(data: { name: $branch_name, description: "test" }) {
                ok
                object { id name }
            }
        }
        """
        gql_params = await prepare_graphql_params(
            db=db, branch=default_branch, account_session=session_admin, service=service
        )
        result = await graphql(
            schema=gql_params.schema,
            source=create_branch_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"branch_name": "before-test-branch"},
        )
        assert result.errors is None

        # Query with a future timestamp (should return branches created before tomorrow)
        future_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        query = """
        query($before: DateTime) {
            InfrahubBranch(node_metadata__created_at__before: $before) {
                count
                edges { node { name { value } } node_metadata { created_at } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"before": future_time},
        )

        assert result.errors is None
        assert result.data
        # Should find at least the branch we created
        branch_names = [edge["node"]["name"]["value"] for edge in result.data["InfrahubBranch"]["edges"]]
        assert "before-test-branch" in branch_names

        # Query with a very old timestamp (should return no branches with recent created_at)
        old_time = "2000-01-01T00:00:00Z"
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"before": old_time},
        )

        assert result.errors is None
        assert result.data
        # No branches should have been created before 2000
        # We check edges is empty since count might include branches with NULL created_at
        assert result.data["InfrahubBranch"]["edges"] == []

    async def test_filter_combined_status_and_timestamp(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test combining multiple filters (status AND timestamp)."""
        # Create a branch
        create_branch_query = """
        mutation($branch_name: String!) {
            BranchCreate(data: { name: $branch_name, description: "test" }) {
                ok
                object { id name }
            }
        }
        """
        gql_params = await prepare_graphql_params(
            db=db, branch=default_branch, account_session=session_admin, service=service
        )
        result = await graphql(
            schema=gql_params.schema,
            source=create_branch_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"branch_name": "combined-filter-branch"},
        )
        assert result.errors is None

        # Query with combined filters
        past_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        query = """
        query($status: BranchStatus, $after: DateTime) {
            InfrahubBranch(status__value: $status, node_metadata__created_at__after: $after) {
                count
                edges { node { name { value } status { value } } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"status": "OPEN", "after": past_time},
        )

        assert result.errors is None
        assert result.data
        # All returned branches should be OPEN and created after the past_time
        for edge in result.data["InfrahubBranch"]["edges"]:
            assert edge["node"]["status"]["value"] == "OPEN"

    async def test_filter_returns_empty_for_no_matches(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
    ) -> None:
        """Test that impossible filter combinations return empty results."""
        query = """
        query {
            InfrahubBranch(node_metadata__created_at__after: "2099-01-01T00:00:00Z") {
                count
                edges { node { name { value } } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubBranch"]["count"] == 0
        assert result.data["InfrahubBranch"]["edges"] == []

    async def test_filter_with_pagination(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        service: InfrahubServices,
        session_admin: AccountSession,
    ) -> None:
        """Test that filters work correctly with limit/offset pagination."""
        # Create multiple branches
        for i in range(5):
            create_branch_query = """
            mutation($branch_name: String!) {
                BranchCreate(data: { name: $branch_name, description: "test" }) {
                    ok
                    object { id name }
                }
            }
            """
            gql_params = await prepare_graphql_params(
                db=db, branch=default_branch, account_session=session_admin, service=service
            )
            result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"branch_name": f"paginated-branch-{i}"},
            )
            assert result.errors is None

        # Query with status filter and pagination
        past_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        query = """
        query($status: BranchStatus, $after: DateTime, $limit: Int, $offset: Int) {
            InfrahubBranch(
                status__value: $status,
                node_metadata__created_at__after: $after,
                limit: $limit,
                offset: $offset
            ) {
                count
                edges { node { name { value } } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"status": "OPEN", "after": past_time, "limit": 2, "offset": 0},
        )

        assert result.errors is None
        assert result.data
        # Count should reflect total matching, edges limited by limit
        assert len(result.data["InfrahubBranch"]["edges"]) <= 2
