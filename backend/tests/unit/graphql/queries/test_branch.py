import operator

import pytest

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.types import BranchType, InfrahubBranch
from infrahub.services import InfrahubServices
from tests.helpers.graphql import graphql
from tests.helpers.test_app import TestInfrahubApp


def test_check_branch_type_has_corresponding_infrahub_branch_value_field():
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
        register_core_models_schema,
        session_admin,
        client,
        service,
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
        register_core_models_schema,
        session_admin,
        client,
        service,
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
        assert id_branches.data["InfrahubBranch"]["edges"][0]["node"]["name"]["value"] == "sample-branch-3"
        assert id_branches.data["InfrahubBranch"]["edges"][1]["node"]["name"]["value"] == "sample-branch-7"
        assert id_branches.data["InfrahubBranch"]["default_branch"]["name"]["value"] == "main"

    async def test_paginated_branch_query__returns_error_on_invalid_offset_or_limit(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema,
        session_admin,
        client,
        service,
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
        register_core_models_schema,
        session_admin,
        client,
        service,
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

    @pytest.mark.parametrize(
        "search_term,partial_match,expected_count",
        [
            ("match", True, 10),
            ("branch-zzz", True, 0),
            ("auth", False, 0),
            ("main", False, 1),
            ("MAIN", False, 0),
            ("MaTcH", True, 10),
        ],
    )
    async def test_partial_match_filter(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch_partial_match_query: str,
        service: InfrahubServices,
        search_term: str,
        session_admin: AccountSession,
        partial_match: bool,
        expected_count: int,
    ) -> None:
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
            assert branch_result.data["BranchCreate"]["ok"] is True
            assert branch_result.data["BranchCreate"]["object"]["name"] == branch_name

        gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)

        result = await graphql(
            schema=gql_params.schema,
            source=branch_partial_match_query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": search_term, "partial_match": partial_match},
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubBranch"]["count"] == expected_count
