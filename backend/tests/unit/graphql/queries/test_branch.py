import operator

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.types import BranchType, InfrahubBranch
from tests.helpers.graphql import graphql
from tests.helpers.test_app import TestInfrahubApp


def test_check_branch_type_has_corresponding_infrahub_branch_value_field():
    exempted_fields = ("id", "created_at")
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
    ):
        for i in range(10):
            create_branch_query = """
            mutation {
                BranchCreate(data: { name: "%s", description: "%s" }) {
                    ok
                    object {
                        id
                        name
                    }
                }
            }
            """ % (
                f"sample-branch-{i}",
                f"sample description {i}",
            )

            gql_params = await prepare_graphql_params(
                db=db,
                branch=default_branch,
                account_session=session_admin,
                service=service,
            )
            branch_result = await graphql(
                schema=gql_params.schema,
                source=create_branch_query,
                context_value=gql_params.context,
                root_value=None,
                variable_values={},
            )
            assert branch_result.errors is None
            assert branch_result.data

        query = """
            query {
                InfrahubBranch(offset: 2, limit: 5) {
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

    async def test_paginated_branch_query__returns_error_on_invalid_offset_or_limit(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema,
        session_admin,
        client,
        service,
    ):
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
        assert len(all_branches.errors)
        assert all_branches.errors[0].message == "limit must be >= 1"
