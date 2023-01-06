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
mutation ($branch_name: String!) {
    branch_create(data: { name: $branch_name, is_data_only: false }) {
        ok
        object {
            id
            name
        }
    }
}
"""


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

    def __init__(self, address="http://localhost:8000"):

        self.address = address
        self.client = None

    @classmethod
    async def init(cls, *args, **kwargs):

        return cls(*args, **kwargs)

    async def create_branch(self, branch_name: str) -> bool:

        variables = {"branch_name": branch_name}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.address}/graphql",
                json={"query": MUTATION_BRANCH_CREATE, "variables": variables},
            )
            resp.raise_for_status()

        return True

    async def get_list_branches(self) -> Dict[str, BranchData]:

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.address}/graphql", json={"query": QUERY_ALL_BRANCHES})

        branches = {
            branch["name"]: BranchData(id=branch["id"], name=branch["name"], is_data_only=branch["is_data_only"])
            for branch in resp.json()["data"]["branch"]
        }

        return branches

    async def get_list_repositories(self, branches: Dict[str, RepositoryData] = None) -> Dict[str, RepositoryData]:

        if not branches:
            branches = await self.get_list_branches()

        branch_names = sorted(branches.keys())

        async with httpx.AsyncClient() as client:

            tasks = []
            for branch_name in branch_names:
                tasks.append(
                    client.post(
                        f"{self.address}/graphql/{branch_name}",
                        json={"query": QUERY_ALL_REPOSITORIES},
                    )
                )

            # TODO need to rate limit how many requests we are sending at once to avoid doing a DOS on the API
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        repositories = {}

        for branch_name, response in zip(branch_names, responses):
            data = response.json()
            repos = data["data"]["repository"]
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.address}/graphql/{branch_name}",
                json={"query": MUTATION_COMMIT_UPDATE, "variables": variables},
            )
            resp.raise_for_status()

        return True
