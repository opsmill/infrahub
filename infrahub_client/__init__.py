import asyncio
from typing import List, Dict

import typer
from pydantic import BaseModel
from rich.logging import RichHandler

import httpx

QUERY_ALL_REPOSITORIES = """
query {
    repository {
        id
        name {
            value
        }
        location {
            value
        }
        commit {
            value
        }
    }
}
"""

QUERY_ALL_BRANCHES = """
query {
    branch {
        id
        name
        is_data_only
    }
}
"""

MUTATION_COMMIT_UPDATE = """
mutation ($repository_id: String!, $commit: String!) {
    repository_update(data: { id: $repository_id, commit: { value: $commit } }) {
        ok
        object {
            commit {
                value
            }
        }
    }
}
"""

MUTATION_BRANCH_CREATE = """
mutation ($branch_name: String!, $background_execution: Boolean!) {
    branch_create(background_execution: $background_execution, data: { name: $branch_name, is_data_only: false }) {
        ok
        object {
            id
            name
        }
    }
}
"""


class GraphQLError(Exception):
    def __init__(self, errors: List[str], query: str = None, variables: dict = None):
        self.query = query
        self.variables = variables
        self.errors = errors
        self.message = f"An error occured while executing the GraphQL Query {self.query}, {self.errors}"
        super().__init__(self.message)


class BranchData(BaseModel):
    id: str
    name: str
    is_data_only: bool


class RepositoryData(BaseModel):
    id: str
    name: str
    location: str
    branches: Dict[str, str]


class InfrahubClient:
    """GraphQL Client to interact with Infrahub."""

    def __init__(self, address="http://localhost:8000", default_timeout=5):

        self.address = address
        self.client = None
        self.default_timeout = default_timeout

    @classmethod
    async def init(cls, *args, **kwargs):

        return cls(*args, **kwargs)

    async def execute_graphql(
        self, query, variables: dict = None, branch_name: str = None, timeout: int = None, raise_for_error: bool = True
    ):

        url = f"{self.address}/graphql"
        if branch_name:
            url += f"/{branch_name}"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url=url,
                json=payload,
                timeout=timeout or self.default_timeout,
            )
            if raise_for_error:
                resp.raise_for_status()

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    async def create_branch(self, branch_name: str, background_execution: bool = False) -> bool:

        variables = {"branch_name": branch_name, "background_execution": background_execution}

        response = await self.execute_graphql(query=MUTATION_BRANCH_CREATE, variables=variables)

        return True

    async def get_list_branches(self) -> Dict[str, BranchData]:

        data = await self.execute_graphql(query=QUERY_ALL_BRANCHES)

        branches = {
            branch["name"]: BranchData(id=branch["id"], name=branch["name"], is_data_only=branch["is_data_only"])
            for branch in data["branch"]
        }

        return branches

    async def get_list_repositories(self, branches: Dict[str, RepositoryData] = None) -> Dict[str, RepositoryData]:

        if not branches:
            branches = await self.get_list_branches()

        branch_names = sorted(branches.keys())

        tasks = []
        for branch_name in branch_names:
            tasks.append(self.execute_graphql(query=QUERY_ALL_REPOSITORIES, branch_name=branch_name))
            # TODO need to rate limit how many requests we are sending at once to avoid doing a DOS on the API

        responses = await asyncio.gather(*tasks)

        repositories = {}

        for branch_name, response in zip(branch_names, responses):
            repos = response["repository"]
            for repository in repos:
                repo_name = repository["name"]["value"]
                if repo_name not in repositories:
                    repositories[repo_name] = RepositoryData(
                        id=repository["id"], name=repo_name, location=repository["location"]["value"], branches={}
                    )

                repositories[repo_name].branches[branch_name] = repository["commit"]["value"]

        return repositories

    async def repository_update_commit(self, branch_name, repository_id: str, commit: str) -> bool:

        variables = {"repository_id": str(repository_id), "commit": str(commit)}
        await self.execute_graphql(query=MUTATION_COMMIT_UPDATE, variables=variables, branch_name=branch_name)

        return True
